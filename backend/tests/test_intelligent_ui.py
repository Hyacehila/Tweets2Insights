import json
from types import SimpleNamespace

import pytest

from test_workspace_views import workspace
from test_workflow_contracts import case


def test_ui_context_filters_real_posts_and_keeps_event_scope(workspace):
    r = workspace
    url = f"/api/threads/{r.thread['thread_id']}/intelligence/context"
    response = r.client.get(url, params={"dataset_id": r.dataset['dataset_id'], "start": "2024-11-02", "end": "2024-11-02"})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['dataset']['metrics']['posts'] == 1
    assert value['dataset']['metrics']['interactions'] == 5
    assert value['total_posts'] == 2
    assert value['dataset']['top_posts'][0]['post_id'] == '1'
    assert r.client.get(url, params={"start": "2024-11-03", "end": "2024-11-01"}).status_code == 422
    assert r.client.get(url.replace(r.thread['thread_id'], r.other['thread_id']), params={"dataset_id": r.dataset['dataset_id']}).status_code == 404
    empty = r.client.get(url, params={"platform": "nonexistent"}).json()
    assert empty['dataset']['metrics']['posts'] == 0


def test_ui_stream_persists_output_and_uses_server_context(workspace, monkeypatch):
    from src.gateway.routers import intelligence
    seen = []

    async def model(config, messages):
        seen.extend(messages)
        yield {"delta": 'root = ResearchView([Summary("Observed data"), '}
        yield {"delta": 'Metric("posts")])'}
        yield {"usage": {"prompt_tokens": 20, "completion_tokens": 10}}

    monkeypatch.setattr(intelligence, "stream_model", model)
    r = workspace
    url = f"/api/threads/{r.thread['thread_id']}/intelligence"
    response = r.client.post(url + '/chat', json={"message": "Show daily volume", "locale": "en-US"})
    assert response.status_code == 200, response.text
    assert 'event: delta' in response.text and 'event: complete' in response.text
    assert 'first' in str(seen) and 'dataset' in str(seen)
    history = r.client.get(url + '/messages').json()
    assert [item['role'] for item in history] == ['user', 'assistant']
    assert history[-1]['status'] == 'completed'
    assert history[-1]['usage']['completion_tokens'] == 10
    assert 'Metric("posts")' in history[-1]['content']
    assert r.client.get(url.replace(r.thread['thread_id'], r.other['thread_id']) + '/messages').json() == []
    assert r.db.get(r.thread['thread_id'])['messages'] == []  # Leader history stays independent.


def test_ui_stream_exposes_failure_without_leaking_credentials(workspace, monkeypatch):
    from src.gateway.routers import intelligence

    async def model(config, messages):
        yield {"delta": 'root = ResearchView(['}
        raise ValueError('Upstream HTTP 429; api_key=private-secret')

    monkeypatch.setattr(intelligence, "stream_model", model)
    r = workspace
    url = f"/api/threads/{r.thread['thread_id']}/intelligence"
    response = r.client.post(url + '/chat', json={"message": "Analyze"})
    assert 'event: error' in response.text
    assert '429' in response.text and 'private-secret' not in response.text
    last = r.client.get(url + '/messages').json()[-1]
    assert last['status'] == 'failed' and last['error']['error_type'] == 'ValueError'


def test_simulation_requires_model_and_rejects_cross_event_job(workspace):
    r = workspace
    job = r.service.jobs.submit('other', 'other-run', 'analysis_run', {})
    url = f"/api/threads/{r.thread['thread_id']}/intelligence/simulate"
    body = {"job_id": job.job_id, "horizon": 3, "shift": 0.1, "assumption": "Conditional state shift"}
    assert r.client.post(url, json=body).status_code == 404
    job = r.service.jobs.submit('demo', 'no-model', 'analysis_run', {})
    body['job_id'] = job.job_id
    assert r.client.post(url, json=body).status_code == 409
    body['horizon'] = 1000
    assert r.client.post(url, json=body).status_code == 422


def test_event_delete_removes_assistant_history_but_preserves_dataset(workspace):
    r = workspace
    r.db.event(r.thread['thread_id'], 'ui_message', {"role": "assistant", "content": "saved UI"})
    assert r.client.delete(f"/api/threads/{r.thread['thread_id']}/event").status_code == 200
    assert r.service.repo.read('demo', r.dataset['dataset_id'])
    assert r.db.events(r.thread['thread_id']) == []


def test_simulation_reuses_fitted_state_and_persists_real_paired_results(workspace, case):
    from datetime import datetime
    from opinion_core.analytics.observations import build_observations
    from opinion_core.dynamics.engine import fit_assimilate
    from opinion_core.schemas.workflow import ModelSpec

    r = workspace
    observations = build_observations(*case)
    config = ModelSpec(training_cutoff=datetime.fromisoformat(observations['windows'][3]['end']), particles=8, ensemble_size=4, horizon=1, latent_dimensions=2, calibrate=False)
    state = fit_assimilate(observations, config)
    ref = r.service.assets.put('demo', 'trained', 'state', state)
    job = r.service.jobs.submit('demo', 'trained', 'analysis_run', {})
    claimed = r.service.jobs.claim('test')
    r.service.jobs.finish(claimed, {"artifacts": {"state": ref}})
    url = f"/api/threads/{r.thread['thread_id']}/intelligence"
    assert r.client.get(url + '/context').json()['model_runs'][0]['job_id'] == job.job_id
    body = {"job_id": job.job_id, "horizon": 3, "shift": 0.0, "assumption": "Zero shift keeps paired trajectories equal"}
    response = r.client.post(url + '/simulate', json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    rows = result['charts']['stance']['data']
    assert len(rows) == 6
    assert [row['value'] for row in rows[:3]] == [row['value'] for row in rows[3:]]
    assert r.service.assets.read('demo', 'trained', ref['artifact_id'], 'state') == state
    assert r.client.get(url + '/simulations').json()[-1]['artifact'] == result['artifact']
    body['shift'] = 0.5
    shifted = r.client.post(url + '/simulate', json=body).json()['charts']['stance']['data']
    assert [row['value'] for row in shifted[:3]] != [row['value'] for row in shifted[3:]]
