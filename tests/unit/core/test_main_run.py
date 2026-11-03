"""
main.run contract tests.
"""
from __future__ import annotations

import asyncio

import pytest

import legacy.main as main_module


class _BrokenFlow:
    async def run_async(self, shared):
        _ = shared
        raise RuntimeError("boom")


def test_run_reraises_pipeline_exception(monkeypatch):
    monkeypatch.setattr(main_module, "print_banner", lambda: None)
    monkeypatch.setattr(main_module, "print_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_results", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "create_main_flow", lambda **kwargs: _BrokenFlow())
    monkeypatch.setattr(main_module, "start_status_run", lambda path=None: {"run_id": "run-test"})

    shared = {
        "pipeline_state": {"start_stage": 1},
        "status_file": "",
    }

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(main_module.run(shared, concurrent_num=1, max_retries=1, wait_time=0))
