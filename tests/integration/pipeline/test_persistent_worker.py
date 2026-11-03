import subprocess
import sys
import pytest
from opinion_gateway.mcp_server import DomainService
from opinion_gateway.worker import InventoryWorker
from opinion_gateway.jobs import TransitionConflict


def setup_job(tmp_path):
    service = DomainService(tmp_path)
    dataset = service.register_dataset('event', [
        {'post_id': 'p', 'raw_id': '1', 'platform': 'test', 'content': 'source'}])
    job = service.submit_inventory_job('event', dataset['dataset_id'], 'run')
    return service, dataset, job


def test_submit_returns_queued_and_real_worker_publishes_after_restart(tmp_path):
    service, dataset, job = setup_job(tmp_path)
    assert job['status'] == 'queued'
    assert service.submit_inventory_job('event', dataset['dataset_id'], 'run')['job_id'] == job['job_id']
    with pytest.raises(ValueError):
        service.read_job_artifact('event', job['job_id'])
    result = subprocess.run([sys.executable, '-m', 'opinion_gateway.worker', '--root', str(tmp_path), '--once'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    reopened = DomainService(tmp_path)
    assert reopened.list_jobs('event')[0]['status'] == 'completed'
    artifact = reopened.read_job_artifact('event', job['job_id'])
    assert artifact['statistics']['count'] == 1 and '[P:p]' in artifact['markdown']
    with pytest.raises(ValueError):
        reopened.read_job_artifact('other', job['job_id'])


def test_expired_worker_is_fenced_and_completed_batches_are_reused(tmp_path, monkeypatch):
    service, _, job = setup_job(tmp_path)
    clock = [100.0]
    monkeypatch.setattr('opinion_gateway.jobs.time.time', lambda: clock[0])
    first = service.jobs.claim('same-worker-name', lease_seconds=10, kinds=['inventory_report'])
    service.jobs.commit_batch(first.job_id, first.worker, 'statistics', {'count': 99}, lease_token=first.lease_token)
    clock[0] = 111
    second = service.jobs.claim('same-worker-name', lease_seconds=10, kinds=['inventory_report'])
    assert second.lease_token != first.lease_token
    with pytest.raises(TransitionConflict):
        service.jobs.finish(first, {'bad': True})
    with pytest.raises(TransitionConflict):
        service.jobs.commit_batch(first.job_id, first.worker, 'evidence', {}, lease_token=first.lease_token)
    with pytest.raises(TransitionConflict):
        service.jobs.transition(second.job_id, 'completed', expected_revision=second.revision)
    service.jobs.finish(second, {'ok': True})
    assert service.jobs.result(job['job_id']) == {'ok': True}
    assert service.jobs.batches(job['job_id'])['statistics'] == {'count': 99}


def test_cancel_between_stages_and_retry_reuses_committed_stage(tmp_path, monkeypatch):
    service, _, job = setup_job(tmp_path)
    worker = InventoryWorker(tmp_path)
    original = worker.service.describe_dataset
    def cancel_after_statistics(*args, **kwargs):
        result = original(*args, **kwargs)
        worker.service.cancel_job('event', job['job_id'])
        return result
    monkeypatch.setattr(worker.service, 'describe_dataset', cancel_after_statistics)
    worker.run_once()
    assert service.job_status('event', job['job_id'])['status'] == 'cancelled'
    with pytest.raises(ValueError):
        service.read_job_artifact('event', job['job_id'])
    retried = service.retry_job('event', job['job_id'])
    assert retried['job_id'] != job['job_id'] and retried['retry_of'] == job['job_id']
    assert service.retry_job('event', job['job_id'])['job_id'] == retried['job_id']
    InventoryWorker(tmp_path).run_once()
    assert service.job_status('event', retried['job_id'])['status'] == 'completed'


def test_crash_resume_skips_committed_statistics(tmp_path, monkeypatch):
    service, _, job = setup_job(tmp_path)
    clock = [100.0]
    monkeypatch.setattr('opinion_gateway.jobs.time.time', lambda: clock[0])
    old = service.jobs.claim('dead', lease_seconds=1, kinds=['inventory_report'])
    parameters = service.jobs.parameters(old.job_id)
    stats = service.describe_dataset(old.event_id, parameters['dataset_id'], old.run_id)
    service.jobs.commit_batch(old.job_id, old.worker, 'statistics', stats, lease_token=old.lease_token)
    clock[0] = 102
    worker = InventoryWorker(tmp_path)
    monkeypatch.setattr(worker.service, 'describe_dataset', lambda *a: pytest.fail('committed statistics repeated'))
    worker.run_once()
    assert service.job_status('event', job['job_id'])['status'] == 'completed'


def test_expired_cancel_request_is_finalized_without_new_work(tmp_path, monkeypatch):
    service, _, job = setup_job(tmp_path)
    clock = [10.0]
    monkeypatch.setattr('opinion_gateway.jobs.time.time', lambda: clock[0])
    service.jobs.claim('dead', lease_seconds=1, kinds=['inventory_report'])
    service.cancel_job('event', job['job_id'])
    clock[0] = 12
    assert InventoryWorker(tmp_path).run_once() is None
    assert service.job_status('event', job['job_id'])['status'] == 'cancelled'


def test_artifact_read_does_not_create_a_job(tmp_path):
    service, dataset, job = setup_job(tmp_path)
    before = service.list_jobs('event')
    with pytest.raises(ValueError):
        service.read_artifact('event', dataset['dataset_id'], 'unknown', 'report')
    assert service.list_jobs('event') == before
