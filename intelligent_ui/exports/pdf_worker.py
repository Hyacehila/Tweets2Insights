"""
Isolated Playwright worker used by dashboard PDF generation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from playwright.sync_api import sync_playwright


_BROWSER_ENV_KEY = "PLAYWRIGHT_BROWSERS_PATH"


class WorkerPdfError(RuntimeError):
    """Structured exception type for worker-side failures."""

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


def _tail(text: str, *, limit: int = 4000) -> str:
    raw = str(text or "")
    return raw[-limit:]


def _configure_windows_event_loop_policy() -> None:
    if sys.platform != "win32":
        return
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_browsers_path() -> Path:
    env_value = os.environ.get(_BROWSER_ENV_KEY, "").strip()
    if env_value:
        return Path(env_value).resolve()
    return (_project_root() / ".playwright-browsers").resolve()


def _path_to_file_url(path: Path) -> str:
    resolved = Path(path).resolve()
    return f"file:///{str(resolved).replace(os.sep, '/')}"


def _build_worker_error(stage: str, error: Exception, diagnostics: Dict[str, Any] | None = None) -> WorkerPdfError:
    message = str(error).strip() or repr(error).strip() or error.__class__.__name__
    return WorkerPdfError(
        stage=stage,
        error_type=error.__class__.__name__,
        message=message,
        traceback_text=traceback.format_exc(),
        diagnostics=diagnostics or {},
    )


@contextmanager
def _scoped_browser_env(browsers_path: Path) -> Iterator[None]:
    original = os.environ.get(_BROWSER_ENV_KEY)
    os.environ[_BROWSER_ENV_KEY] = str(browsers_path)
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(_BROWSER_ENV_KEY, None)
        else:
            os.environ[_BROWSER_ENV_KEY] = original


def _install_chromium(browsers_path: Path) -> Dict[str, str]:
    env = os.environ.copy()
    env[_BROWSER_ENV_KEY] = str(browsers_path)
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_project_root()),
    )
    diagnostics = {
        "install_returncode": int(result.returncode),
        "install_stdout_tail": _tail(result.stdout),
        "install_stderr_tail": _tail(result.stderr),
    }
    if result.returncode != 0:
        raise WorkerPdfError(
            stage="install",
            error_type="CalledProcessError",
            message=f"playwright install chromium failed with exit code {result.returncode}.",
            traceback_text="",
            diagnostics=diagnostics,
        )
    return diagnostics


def _ensure_playwright_browsers(*, browsers_path: Path) -> Dict[str, Any]:
    browsers_path = Path(browsers_path).resolve()
    browsers_path.mkdir(parents=True, exist_ok=True)

    install_attempted = False
    install_details: Dict[str, Any] = {}

    def _launch_once() -> None:
        with _scoped_browser_env(browsers_path):
            with sync_playwright() as p:
                browser = p.chromium.launch()
                browser.close()

    try:
        _launch_once()
    except Exception:
        install_attempted = True
        try:
            install_details = _install_chromium(browsers_path)
        except WorkerPdfError:
            raise
        except Exception as exc:
            raise _build_worker_error(
                "install",
                exc,
                diagnostics={"browsers_path": str(browsers_path)},
            ) from exc

        try:
            _launch_once()
        except Exception as exc:
            diagnostics = {
                "browsers_path": str(browsers_path),
                "browser_install_attempted": True,
            }
            diagnostics.update(install_details)
            raise _build_worker_error("launch_check", exc, diagnostics=diagnostics) from exc

    diagnostics = {
        "browsers_path": str(browsers_path),
        "browser_install_attempted": install_attempted,
    }
    diagnostics.update(install_details)
    return diagnostics


def _goto_with_fallback(page: Any, file_url: str) -> str:
    try:
        page.goto(file_url, wait_until="load")
        return "load"
    except Exception:
        load_traceback = traceback.format_exc()
        try:
            page.goto(file_url, wait_until="domcontentloaded")
            return "domcontentloaded"
        except Exception as exc:
            raise _build_worker_error(
                "goto",
                exc,
                diagnostics={
                    "target_file_url": file_url,
                    "load_traceback": load_traceback,
                },
            ) from exc


def _run_preflight(report_dir: Path, browsers_path: Path) -> Dict[str, Any]:
    report_dir = Path(report_dir).resolve()
    html_path = (report_dir / "report.html").resolve()

    diagnostics: Dict[str, Any] = {
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "playwright_import_ok": True,
        "event_loop_policy": type(asyncio.get_event_loop_policy()).__name__,
        "browsers_path": str(browsers_path),
        "target_html_path": str(html_path),
        "target_file_url": _path_to_file_url(html_path),
        "browser_install_attempted": False,
    }

    env_info = _ensure_playwright_browsers(browsers_path=browsers_path)
    diagnostics.update(env_info)
    return {"ok": True, "stage": "ready", "diagnostics": diagnostics}


def _run_render(html_path: Path, pdf_path: Path, browsers_path: Path) -> Dict[str, Any]:
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve()

    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    env_info = _ensure_playwright_browsers(browsers_path=browsers_path)
    file_url = _path_to_file_url(html_path)

    try:
        with _scoped_browser_env(browsers_path):
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                goto_wait_until = _goto_with_fallback(page, file_url)
                page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "2cm", "bottom": "2cm", "left": "1cm", "right": "1cm"},
                )
                context.close()
                browser.close()
    except WorkerPdfError:
        raise
    except Exception as exc:
        raise _build_worker_error(
            "pdf",
            exc,
            diagnostics={
                "target_html_path": str(html_path),
                "target_file_url": file_url,
                "output_pdf_path": str(pdf_path),
                "browsers_path": str(browsers_path),
            },
        ) from exc

    diagnostics: Dict[str, Any] = {
        "target_html_path": str(html_path),
        "target_file_url": file_url,
        "output_pdf_path": str(pdf_path),
        "goto_wait_until": goto_wait_until,
    }
    diagnostics.update(env_info)
    return {
        "ok": True,
        "stage": "pdf",
        "pdf_path": str(pdf_path),
        "diagnostics": diagnostics,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dashboard PDF worker")
    parser.add_argument("--mode", choices=("preflight", "render"), required=True)
    parser.add_argument("--report-dir", default="report")
    parser.add_argument("--html-path", default="")
    parser.add_argument("--pdf-path", default="")
    parser.add_argument("--browsers-path", default="")
    return parser.parse_args(argv)


def _error_payload(exc: WorkerPdfError) -> Dict[str, Any]:
    return {
        "ok": False,
        "stage": exc.stage,
        "error_type": exc.error_type,
        "error_message": exc.message,
        "traceback": exc.traceback_text,
        "diagnostics": exc.diagnostics,
    }


def main(argv: list[str] | None = None) -> int:
    _configure_windows_event_loop_policy()
    args = _parse_args(argv)

    browsers_path_value = str(args.browsers_path or "").strip()
    browsers_path = Path(browsers_path_value).resolve() if browsers_path_value else _resolve_browsers_path()

    try:
        if args.mode == "preflight":
            payload = _run_preflight(report_dir=Path(args.report_dir), browsers_path=browsers_path)
        else:
            html_path_raw = str(args.html_path or "").strip()
            pdf_path_raw = str(args.pdf_path or "").strip()
            if not html_path_raw or not pdf_path_raw:
                raise WorkerPdfError(
                    stage="input",
                    error_type="ValueError",
                    message="render mode requires --html-path and --pdf-path.",
                    traceback_text="",
                    diagnostics={},
                )
            payload = _run_render(
                html_path=Path(html_path_raw),
                pdf_path=Path(pdf_path_raw),
                browsers_path=browsers_path,
            )
    except WorkerPdfError as exc:
        payload = _error_payload(exc)
    except Exception as exc:
        payload = _error_payload(
            _build_worker_error(
                "worker",
                exc,
                diagnostics={
                    "python_executable": sys.executable,
                    "platform": platform.platform(),
                    "event_loop_policy": type(asyncio.get_event_loop_policy()).__name__,
                    "browsers_path": str(browsers_path),
                },
            )
        )

    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
