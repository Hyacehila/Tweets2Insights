"""
Helper module to generate PDF from HTML through an isolated worker process.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Mapping, Union


PDF_RUNTIME_VERSION = "2026-02-21-fix5-worker"
_BROWSER_ENV_KEY = "PLAYWRIGHT_BROWSERS_PATH"
_WORKER_MODULE = "intelligent_ui.exports.pdf_worker"
_WORKER_TIMEOUT_SECONDS = 240


class PdfGenerationError(RuntimeError):
    """Structured error used by dashboard PDF generation flow."""

    def __init__(
        self,
        *,
        stage: str,
        error_type: str,
        message: str,
        traceback_text: str,
        diagnostics: Dict[str, Any] | None = None,
    ) -> None:
        self.stage = str(stage or "").strip()
        self.error_type = str(error_type or "Exception").strip()
        self.message = str(message or "").strip() or self.error_type
        self.traceback_text = str(traceback_text or "").strip()
        self.diagnostics = dict(diagnostics or {})
        super().__init__(self.message)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_browsers_path() -> Path:
    return _project_root() / ".playwright-browsers"


def _path_to_file_url(path: Union[str, Path]) -> str:
    resolved = Path(path).resolve()
    return f"file:///{str(resolved).replace(os.sep, '/')}"


def _build_pdf_error(stage: str, error: Exception, diagnostics: Dict[str, Any] | None = None) -> PdfGenerationError:
    message = str(error).strip() or repr(error).strip() or error.__class__.__name__
    return PdfGenerationError(
        stage=stage,
        error_type=error.__class__.__name__,
        message=message,
        traceback_text=traceback.format_exc(),
        diagnostics=diagnostics or {},
    )


def _tail(text: str, *, limit: int = 4000) -> str:
    data = str(text or "")
    return data[-limit:]


def _parse_worker_payload(stdout_text: str) -> Dict[str, Any]:
    raw = str(stdout_text or "").strip()
    if not raw:
        raise ValueError("Invalid worker JSON output: empty stdout.")

    parse_candidates = [raw]
    if "\n" in raw:
        parse_candidates.extend(
            line.strip()
            for line in raw.splitlines()[::-1]
            if line.strip().startswith("{") and line.strip().endswith("}")
        )

    for candidate in parse_candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    raise ValueError(f"Invalid worker JSON output: {raw[-500:]}")


def _run_pdf_worker(
    *,
    mode: str,
    worker_args: Mapping[str, object],
    browsers_path: Path | None = None,
    timeout_seconds: int = _WORKER_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    resolved_browsers_path = Path(browsers_path or _resolve_browsers_path()).resolve()
    resolved_browsers_path.mkdir(parents=True, exist_ok=True)

    command: list[str] = [sys.executable, "-m", _WORKER_MODULE, "--mode", str(mode)]
    for key, value in worker_args.items():
        option_name = "--" + str(key).strip().replace("_", "-")
        command.extend([option_name, str(value)])

    env = os.environ.copy()
    env[_BROWSER_ENV_KEY] = str(resolved_browsers_path)

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_project_root()),
        timeout=int(timeout_seconds),
    )

    common_diagnostics: Dict[str, Any] = {
        "worker_mode": str(mode),
        "worker_returncode": int(completed.returncode),
        "worker_stdout_tail": _tail(completed.stdout),
        "worker_stderr_tail": _tail(completed.stderr),
        "browsers_path": str(resolved_browsers_path),
        "python_executable": sys.executable,
    }

    try:
        payload = _parse_worker_payload(completed.stdout)
    except Exception as exc:
        raise PdfGenerationError(
            stage="worker",
            error_type="WorkerProtocolError",
            message=str(exc).strip() or "Invalid worker JSON output.",
            traceback_text=traceback.format_exc(),
            diagnostics=common_diagnostics,
        ) from exc

    payload_diagnostics_raw = payload.get("diagnostics", {})
    payload_diagnostics = payload_diagnostics_raw if isinstance(payload_diagnostics_raw, dict) else {}
    merged_diagnostics: Dict[str, Any] = dict(common_diagnostics)
    merged_diagnostics.update(payload_diagnostics)

    if completed.returncode != 0 or not bool(payload.get("ok")):
        stage = str(payload.get("stage", "") or "").strip() or "worker"
        error_type = str(payload.get("error_type", "") or "").strip() or "WorkerProcessError"
        message = str(payload.get("error_message", "") or "").strip()
        if not message:
            if completed.returncode != 0:
                message = f"PDF worker exited with code {completed.returncode}."
            else:
                message = f"PDF worker reported failure in mode={mode}."
        traceback_text = str(payload.get("traceback", "") or "").strip()
        raise PdfGenerationError(
            stage=stage,
            error_type=error_type,
            message=message,
            traceback_text=traceback_text,
            diagnostics=merged_diagnostics,
        )

    payload.setdefault("diagnostics", merged_diagnostics)
    return payload


def generate_pdf_from_html(html_path: Union[str, Path]) -> bytes:
    """Generate a PDF byte string from a local HTML file."""
    html_path_obj = Path(html_path).resolve()
    if not html_path_obj.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path_obj}")

    browsers_path = _resolve_browsers_path().resolve()
    temp_pdf_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".preview.pdf",
            dir=html_path_obj.parent,
            delete=False,
        ) as handle:
            temp_pdf_path = Path(handle.name)

        payload = _run_pdf_worker(
            mode="render",
            worker_args={
                "html_path": str(html_path_obj),
                "pdf_path": str(temp_pdf_path),
            },
            browsers_path=browsers_path,
        )

        output_pdf_path = Path(str(payload.get("pdf_path", "") or str(temp_pdf_path))).resolve()
        if not output_pdf_path.exists():
            raise FileNotFoundError(f"Worker output PDF not found: {output_pdf_path}")

        pdf_bytes = output_pdf_path.read_bytes()
        if not pdf_bytes:
            raise ValueError(f"Worker generated an empty PDF: {output_pdf_path}")
        return pdf_bytes
    except PdfGenerationError:
        raise
    except Exception as exc:
        raise _build_pdf_error(
            "pdf",
            exc,
            diagnostics={
                "target_html_path": str(html_path_obj),
                "target_file_url": _path_to_file_url(html_path_obj),
                "browsers_path": str(browsers_path),
            },
        ) from exc
    finally:
        if temp_pdf_path and temp_pdf_path.exists():
            temp_pdf_path.unlink()


def generate_pdf_from_html_content(html_content: str, report_dir: Union[str, Path] = Path("report")) -> bytes:
    """Generate a PDF byte string from HTML content by using a temporary file under report_dir."""
    base_dir = Path(report_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    temp_html_path: Path | None = None
    try:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".preview_pdf.html",
                dir=base_dir,
                delete=False,
            ) as handle:
                handle.write(html_content)
                temp_html_path = Path(handle.name)
        except Exception as exc:
            raise _build_pdf_error(
                "write_temp_html",
                exc,
                diagnostics={"report_dir": str(base_dir)},
            ) from exc

        return generate_pdf_from_html(temp_html_path)
    finally:
        if temp_html_path and temp_html_path.exists():
            temp_html_path.unlink()


def diagnose_pdf_runtime(report_dir: Union[str, Path] = Path("report")) -> Dict[str, Any]:
    base_dir = Path(report_dir).resolve()
    html_path = base_dir / "report.html"
    browsers_path = _resolve_browsers_path().resolve()

    diagnostics: Dict[str, Any] = {
        "ok": False,
        "stage": "",
        "error_type": "",
        "error_message": "",
        "traceback": "",
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "playwright_import_ok": True,
        "pdf_runtime_version": PDF_RUNTIME_VERSION,
        "browsers_path": str(browsers_path),
        "target_html_path": str(html_path),
        "target_file_url": _path_to_file_url(html_path),
        "browser_install_attempted": False,
    }

    try:
        payload = _run_pdf_worker(
            mode="preflight",
            worker_args={"report_dir": str(base_dir)},
            browsers_path=browsers_path,
        )
        diagnostics["ok"] = bool(payload.get("ok", True))
        diagnostics["stage"] = str(payload.get("stage", "") or "ready")
        worker_diagnostics = payload.get("diagnostics", {})
        if isinstance(worker_diagnostics, dict):
            diagnostics.update(worker_diagnostics)
    except PdfGenerationError as exc:
        diagnostics["stage"] = exc.stage
        diagnostics["error_type"] = exc.error_type
        diagnostics["error_message"] = exc.message
        diagnostics["traceback"] = exc.traceback_text
        if isinstance(exc.diagnostics, dict):
            diagnostics.update(exc.diagnostics)
    except Exception as exc:
        diagnostics["stage"] = "diagnose"
        diagnostics["error_type"] = exc.__class__.__name__
        diagnostics["error_message"] = str(exc).strip() or repr(exc).strip()
        diagnostics["traceback"] = traceback.format_exc()

    return diagnostics
