from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from opinion_gateway.jobs import JobStore, TransitionConflict


def test_persistent_state_and_cancellation_completion_race(tmp_path):
    store = JobStore(tmp_path / 'jobs.sqlite')
    job = store.submit('e', 'r', 'stats', {'data_version': 'v1'})
    assert store.submit('e', 'r', 'stats', {'data_version': 'v1'}).job_id == job.job_id
    running = store.transition(job.job_id, 'running', expected_revision=0)
    barrier = Barrier(2)
    def update(state):
        barrier.wait()
        try:
            return store.transition(job.job_id, state, expected_revision=running.revision).status
        except TransitionConflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(update, ['cancel_requested', 'completed']))
    assert results.count('conflict') == 1
    persisted = JobStore(tmp_path / 'jobs.sqlite').get(job.job_id)
    if persisted.status == 'cancel_requested':
        with pytest.raises(TransitionConflict):
            store.transition(job.job_id, 'completed', expected_revision=persisted.revision)
        persisted = store.transition(job.job_id, 'cancelled', expected_revision=persisted.revision)
    with pytest.raises(TransitionConflict):
        store.transition(job.job_id, 'running', expected_revision=persisted.revision)


def test_claim_lease_and_committed_batches_survive_restart(tmp_path):
    store = JobStore(tmp_path / 'jobs.sqlite')
    j = store.submit('e', 'r', 'label', {'schema': 's'})
    claimed = store.claim('worker1', lease_seconds=30)
    assert claimed.job_id == j.job_id
    assert store.claim('worker2') is None
    store.commit_batch(j.job_id, 'worker1', 'batch1', {'asset': 'a'})
    assert JobStore(tmp_path / 'jobs.sqlite').batches(j.job_id) == {'batch1': {'asset': 'a'}}
    with pytest.raises(TransitionConflict):
        store.commit_batch(j.job_id, 'worker2', 'batch2', {})


def test_waiting_partial_and_failed_transitions(tmp_path):
    store = JobStore(tmp_path / 'jobs.sqlite')
    j = store.submit('e', 'r', 'crawl', {})
    for status in ['running', 'waiting_for_auth', 'queued', 'running', 'partial']:
        j = store.transition(j.job_id, status, expected_revision=j.revision)
    assert j.status == 'partial'
