import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


def test_launcher_waits_for_api_before_announcing_success(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/dev.py"
    spec = importlib.util.spec_from_file_location("local_launcher", path)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    seen = []

    @contextmanager
    def urlopen(url, **kwargs):
        seen.append(url)
        yield SimpleNamespace(status=503 if url.endswith("/api/health") else 200)

    monkeypatch.setattr(launcher, "urlopen", urlopen)
    assert launcher.wait_for_workspace(timeout=0.01) is False
    assert any(url.endswith("/api/health") for url in seen)
