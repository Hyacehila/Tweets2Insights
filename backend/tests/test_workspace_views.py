from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from opinion_gateway.application import ApplicationService
from src.agents.memory import ThreadStore
from src.gateway.app import create_app


@pytest.fixture
def workspace(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    db = ThreadStore(state)
    thread = db.create("demo", "Demo")
    other = db.create("other", "Other")
    service = ApplicationService(tmp_path / "assets")
    dataset = service.repo.register(
        "demo",
        [
            {
                "post_id": "1",
                "content": "first",
                "platform": "wb",
                "published_at": "2024-11-01T23:00:00Z",
                "media_refs": ["a.jpg", "b.jpg"],
                "like_count": 3,
                "repost_count": 2,
            },
            {
                "post_id": "2",
                "content": "second",
                "platform": "wb",
                "published_at": None,
                "media_refs": [],
                "like_count": 0,
            },
        ],
    )
    app = create_app()
    app.state.store = db
    app.state.settings = SimpleNamespace(asset_root=service.repo.root)
    return SimpleNamespace(
        client=TestClient(app),
        db=db,
        thread=thread,
        other=other,
        service=service,
        dataset=dataset,
    )


def test_rename_changes_only_display_title_and_survives_reload(workspace):
    r = workspace
    url = f"/api/threads/{r.thread['thread_id']}"
    r.db.append(r.thread["thread_id"], "user", "keep conversation")
    response = r.client.put(url, json={"title": "  夜骑开封  "})
    assert response.status_code == 200
    assert r.client.get(url).json()["title"] == "夜骑开封"
    assert r.db.get(r.thread["thread_id"])["event_id"] == "demo"
    assert (
        r.db.get(r.thread["thread_id"])["messages"][0]["content"] == "keep conversation"
    )
    assert r.client.put(url, json={"title": "   "}).status_code == 422


def test_dataset_overview_counts_missing_data_and_uses_shanghai_days(workspace):
    r = workspace
    url = f"/api/threads/{r.thread['thread_id']}/datasets/{r.dataset['dataset_id']}/overview"
    response = r.client.get(url)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["metrics"]["posts"] == 2
    assert data["metrics"]["images"] == 2
    assert data["metrics"]["image_posts"] == 1
    assert data["metrics"]["interactions"] == 5
    assert data["missing"]["published_at"] == 1
    assert data["missing"]["like_count"] == 0
    assert data["missing"]["read_count"] == 2
    assert data["charts"]["daily"]["data"][0]["label"] == "2024-11-02"
    assert (
        r.client.get(
            url.replace(r.thread["thread_id"], r.other["thread_id"])
        ).status_code
        == 404
    )


def test_failed_job_exposes_saved_trace_and_completed_stages(workspace):
    r = workspace
    store = r.service.jobs
    job = store.submit(
        "demo",
        "run",
        "analysis_run",
        {
            "plan": {
                "tasks": [
                    {
                        "task_id": "input",
                        "role": "InputAgent",
                        "operation": "load_dataset",
                    },
                    {"task_id": "forum", "role": "ForumHost", "operation": "forum"},
                ]
            }
        },
    )
    owned = store.claim("test")
    store.commit_batch(
        job.job_id, owned.worker, "input", {}, lease_token=owned.lease_token
    )
    store.set_stage(owned, "forum")
    try:
        raise ValueError("Model returned invalid JSON")
    except ValueError as exc:
        from opinion_gateway.diagnostics import exception_details

        store.record_event(owned, "failed", exception_details(exc, stage="forum"))
    store.stop_owned(owned, "ValueError")
    response = r.client.get(
        f"/api/threads/{r.thread['thread_id']}/jobs/{job.job_id}/progress"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["stages"][0]["status"] == "completed"
    assert data["stages"][1]["status"] == "failed"
    assert data["error"]["message"] == "Model returned invalid JSON"
    assert "ValueError" in data["error"]["traceback"]
    assert data["events"][-1]["timestamp"]
    assert (
        r.client.get(
            f"/api/threads/{r.other['thread_id']}/jobs/{job.job_id}/progress"
        ).status_code
        == 404
    )


def test_diagnostics_redacts_credentials(monkeypatch):
    from opinion_gateway.diagnostics import exception_details

    monkeypatch.setenv("OPENAI_API_KEY", "private-test-key-012345")
    try:
        raise RuntimeError(
            "Authorization: Bearer private-test-key-012345; api_key=hidden-value; Cookie: session=private-cookie"
        )
    except RuntimeError as exc:
        details = str(exception_details(exc))
    for secret in ("private-test-key-012345", "hidden-value", "private-cookie"):
        assert secret not in details


def test_overview_uses_real_imported_demo_without_model_calls(workspace):
    response = workspace.client.get("/api/overview")
    assert response.status_code == 200, response.text
    assert response.json()["dataset"]["metrics"]["posts"] == 2
    assert response.json()["thread_id"] == workspace.thread["thread_id"]


def test_worker_persists_real_exception_without_running_a_model(workspace):
    from opinion_gateway.domain_worker import DomainWorker

    r = workspace
    job = r.service.jobs.submit(
        "demo", "outdated-source", "analysis_run", {"code_version": "outdated"}
    )
    DomainWorker(r.service.repo.root).run_once()
    assert r.service.jobs.get(job.job_id).status == "failed"
    details = r.service.jobs.events(job.job_id)[-1]
    assert "worker source changed" in details["message"]
    assert "domain_worker.py" in details["traceback"]
    assert details["error_type"] == "ValueError"
