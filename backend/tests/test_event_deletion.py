"""Event deletion uses temporary stores and never touches imported datasets."""

import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from opinion_gateway.application import ApplicationService
from opinion_gateway.dataset_repository import storage_id
from src.agents.memory import ThreadStore
from src.gateway.app import create_app


@pytest.fixture
def research(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    store = ThreadStore(state)
    service = ApplicationService(tmp_path / "assets")
    first = store.create("rain", "Rain")
    second = store.create("rain", "Rain follow-up")
    other = store.create("Rain", "Different case")
    for thread in (first, second, other):
        store.append(thread["thread_id"], "user", "Research this event")
        store.event(thread["thread_id"], "agent_update", {"status": "completed"})
    dataset = service.repo.register("rain", [{"content": "keep this input"}])
    artifact = service.assets.put("rain", "run", "report", {"text": "remove"})
    service.assets.put("Rain", "run", "report", {"text": "keep"})
    job = service.jobs.submit("rain", "run", "analysis_run", {})
    claimed = service.jobs.claim("fixture")
    service.jobs.commit_batch(
        job.job_id, "fixture", "one", {}, lease_token=claimed.lease_token
    )
    service.jobs.finish(claimed, {"report": artifact})
    service.jobs.submit("rain", "queued", "analysis_run", {})
    service.jobs.submit("Rain", "other", "analysis_run", {})
    with sqlite3.connect(service.runs_path) as db:
        db.execute(
            "INSERT INTO runs VALUES (?,?,?)",
            (storage_id("rain") + ":run", "{}", job.job_id),
        )
    app = create_app()
    app.state.store = store
    app.state.settings = SimpleNamespace(asset_root=service.repo.root)
    return SimpleNamespace(
        client=TestClient(app),
        store=store,
        service=service,
        first=first,
        second=second,
        other=other,
        dataset=dataset,
        state=state,
    )


def test_delete_event_removes_all_sessions_and_outputs_but_keeps_data(research):
    r = research
    # Exercise durable graph state, schema/annotation caches and model accounting.
    with sqlite3.connect(r.state / "checkpoints.sqlite") as db:
        db.execute("CREATE TABLE checkpoints (thread_id TEXT)")
        db.execute("CREATE TABLE writes (thread_id TEXT)")
        for table in ("checkpoints", "writes"):
            db.executemany(
                f"INSERT INTO {table} VALUES (?)",
                [(r.first["thread_id"],), (r.other["thread_id"],)],
            )
    from opinion_core.labeling.event_preparation import EventPreparation
    from opinion_core.labeling.pipeline import WeakLabeler
    from opinion_gateway.budget import CallLedger
    from opinion_gateway.label_workflow import DurableLabelBudget

    root = r.service.repo.root
    prep = EventPreparation(root, search=None, builder=None, builder_version="test")
    prep._change(
        "prep",
        lambda _: {
            "event": {"event_id": "rain"},
            "schema": {"schema_version": "schema-rain"},
        },
    )
    cache = WeakLabeler(root, None, prompt_version="test")
    with sqlite3.connect(cache.path) as db:
        db.execute(
            "INSERT INTO annotations VALUES (?,?)",
            ("annotation", json.dumps({"schema_version": "schema-rain"})),
        )
    scope = hashlib.sha256(b"rain\0run").hexdigest()
    CallLedger(root, scope, 10).reserve("label", "test")
    DurableLabelBudget(root / "label-budget.sqlite", scope, 10)
    response = r.client.delete(f"/api/threads/{r.first['thread_id']}/event")
    assert response.status_code == 200, response.text
    assert set(response.json()["deleted_thread_ids"]) == {
        r.first["thread_id"],
        r.second["thread_id"],
    }
    assert r.service.repo.read("rain", r.dataset["dataset_id"]) == [
        {"content": "keep this input"}
    ]
    assert r.service.assets.list("rain", "run") == []
    assert len(r.service.assets.list("Rain", "run")) == 1
    assert r.service.jobs.list_jobs("rain") == []
    assert len(r.service.jobs.list_jobs("Rain")) == 1
    assert [x["thread_id"] for x in r.store.list()] == [r.other["thread_id"]]
    with sqlite3.connect(r.store.path) as db:
        assert db.execute("SELECT count(*) FROM turns").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
    for file, table in (
        ("event-preparation.sqlite", "preparations"),
        ("annotation-cache.sqlite", "annotations"),
        ("call-ledger.sqlite", "calls"),
        ("label-budget.sqlite", "budgets"),
        ("runs.sqlite", "runs"),
    ):
        with sqlite3.connect(root / file) as db:
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    with sqlite3.connect(r.state / "checkpoints.sqlite") as db:
        assert db.execute("SELECT thread_id FROM checkpoints").fetchall() == [
            (r.other["thread_id"],)
        ]
        assert db.execute("SELECT thread_id FROM writes").fetchall() == [
            (r.other["thread_id"],)
        ]
    # Reusing the event ID exposes the preserved input, with no previous results.
    r.store.create("rain", "New research")
    assert r.service.list_datasets("rain")[0]["dataset_id"] == r.dataset["dataset_id"]
    assert (
        r.client.delete(f"/api/threads/{r.first['thread_id']}/event").status_code == 404
    )


@pytest.mark.parametrize("active", ["agent", "worker", "cancelling"])
def test_active_event_cannot_be_deleted(research, active):
    r = research
    if active == "agent":
        r.store.begin_execution(r.second["thread_id"])
    else:
        claimed = r.service.jobs.claim("fixture")
        if active == "cancelling":
            r.service.jobs.transition(
                claimed.job_id, "cancel_requested", expected_revision=claimed.revision
            )
    response = r.client.delete(f"/api/threads/{r.first['thread_id']}/event")
    assert response.status_code == 409
    assert len(r.store.list()) == 3
    assert r.service.assets.list("rain", "run")
    assert r.service.repo.read("rain", r.dataset["dataset_id"])


def test_deleted_thread_cannot_start_an_orphan_execution(research):
    r = research
    assert (
        r.client.delete(f"/api/threads/{r.first['thread_id']}/event").status_code == 200
    )
    with pytest.raises(KeyError):
        r.store.begin_execution(r.first["thread_id"])
    r.store.event(r.first["thread_id"], "run_finished", {"status": "completed"})
    assert r.store.events(r.first["thread_id"]) == []


def test_file_move_failure_preserves_research_and_inputs(research, monkeypatch):
    from pathlib import Path

    from src.gateway.event_deletion import delete_event_research

    r = research
    crawl = r.service.repo.path(storage_id("rain"), "crawl")
    crawl.mkdir()
    (crawl / "checkpoint.json").write_text("{}")
    original_rename = Path.rename
    moves = 0

    def fail_second_move(path, target):
        nonlocal moves
        if path.parent.name == storage_id("rain"):
            moves += 1
            if moves == 2:
                raise PermissionError("synthetic locked file")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_second_move)
    with pytest.raises(PermissionError):
        delete_event_research(r.store, r.service.repo.root, r.first["thread_id"])
    assert len(r.store.list()) == 3
    assert r.service.assets.list("rain", "run")
    assert (crawl / "checkpoint.json").exists()
    assert r.service.repo.read("rain", r.dataset["dataset_id"])
    assert not list(r.service.repo.root.glob(".event-delete-*"))
