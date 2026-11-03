"""
Shared pipeline running state (lock file).
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from utils.path_manager import get_report_dir


LOCK_STALE_SECONDS = 6 * 60 * 60


def lock_path() -> Path:
    """Return lock file path under report/."""
    return Path(get_report_dir()) / ".pipeline_running.lock"


def is_running() -> bool:
    """Check if pipeline lock file exists and references a live process."""
    path = lock_path()
    if not path.exists():
        return False

    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return path.exists()

    if not raw:
        if _lock_is_stale(path):
            _remove_lock(path)
            return False
        return True

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Backward compatibility with legacy plain timestamp lock content.
        if _lock_is_stale(path, raw=raw):
            _remove_lock(path)
            return False
        return True

    pid = int(payload.get("pid", 0) or 0) if isinstance(payload, dict) else 0
    if pid > 0:
        if _pid_alive(pid):
            return True
        _remove_lock(path)
        return False

    if _lock_is_stale(path, payload=payload):
        _remove_lock(path)
        return False
    return True


def set_running(flag: bool) -> None:
    """Create or remove the pipeline lock file."""
    path = lock_path()
    if flag:
        path.parent.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        payload = {
            "pid": os.getpid(),
            "started_at": started_at,
            "timestamp": started_at,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    else:
        if path.exists():
            path.unlink()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            CREATE_NO_WINDOW = 0x08000000
            output = subprocess.check_output(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                text=True,
                encoding="utf-8",
                errors="ignore",
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            import csv
            return any(len(row) > 1 and row[1] == str(pid) for row in csv.reader(output.splitlines()))
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        except Exception:
            return False
        return True


def _remove_lock(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _lock_is_stale(path: Path, payload: Optional[dict[str, Any]] = None, raw: str = "") -> bool:
    started_at = ""
    if isinstance(payload, dict):
        started_at = str(payload.get("started_at", "") or payload.get("timestamp", "")).strip()
    if not started_at:
        started_at = str(raw or "").strip()

    started_dt = _parse_utc(started_at)
    if started_dt is None:
        try:
            started_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return False

    age_seconds = (datetime.now(timezone.utc) - started_dt).total_seconds()
    return age_seconds > LOCK_STALE_SECONDS


def _parse_utc(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
