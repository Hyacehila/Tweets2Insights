"""
PathManager:统一报告与图表输出路径。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from contextvars import ContextVar

_run_context = ContextVar('opinion_run_context', default=None)


def current_run_context():
    return _run_context.get()


@contextmanager
def run_context(root, event_id, dataset_id, run_id):
    from opinion_gateway.dataset_repository import DatasetRepository
    repo = DatasetRepository(root)
    directory = repo.run_dir(event_id, dataset_id, run_id)
    token = _run_context.set((repo, event_id, dataset_id, directory))
    try:
        yield directory
    finally:
        _run_context.reset(token)


class PathManager:
    """Centralized path helper for report outputs."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.getcwd()).resolve()

    def report_dir(self) -> Path:
        return self.base_dir / "report"

    def images_dir(self) -> Path:
        return self.report_dir() / "images"

    def ensure_dir(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    def report_file(self, filename: str) -> Path:
        return self.report_dir() / filename


def ensure_dir(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def get_report_dir(path: Optional[str] = None) -> str:
    context = current_run_context()
    if context:
        return ensure_dir(str(context[3]))
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            project_root = os.environ.get("PROJECT_ROOT")
            if project_root:
                candidate = Path(project_root) / candidate
        target = str(candidate)
    else:
        target = os.environ.get("REPORT_DIR") or str(PathManager().report_dir())
    return ensure_dir(target)


def get_images_dir(path: Optional[str] = None) -> str:
    context = current_run_context()
    if context:
        return ensure_dir(str(context[3] / 'images'))
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            project_root = os.environ.get("PROJECT_ROOT")
            if project_root:
                candidate = Path(project_root) / candidate
        target = str(candidate)
    else:
        report_dir = os.environ.get("REPORT_DIR")
        if report_dir:
            target = str(Path(report_dir) / "images")
        else:
            target = str(PathManager().images_dir())
    return ensure_dir(target)
