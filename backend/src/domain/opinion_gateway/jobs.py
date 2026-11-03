"""Transactional jobs with revision checks, worker leases and durable batch checkpoints."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from opinion_core.schemas.job import JobRef

TRANSITIONS = {
    'queued': {'running', 'cancelled'},
    'running': {'waiting_for_auth', 'cancel_requested', 'partial', 'completed', 'failed'},
    'waiting_for_auth': {'queued', 'cancel_requested', 'failed'},
    'cancel_requested': {'cancelled', 'partial'},
    'cancelled': set(), 'partial': set(), 'completed': set(), 'failed': set(),
}


class TransitionConflict(ValueError):
    pass


class JobStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, dedup TEXT UNIQUE, payload TEXT, parameters TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS batches (job TEXT, batch TEXT, payload TEXT, PRIMARY KEY(job,batch))')
            db.execute('CREATE TABLE IF NOT EXISTS job_results (job TEXT PRIMARY KEY, payload TEXT)')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                yield db
        finally:
            db.close()

    def _get(self, db, job_id):
        row = db.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return JobRef.model_validate_json(row[0])

    def _save(self, db, job):
        db.execute('UPDATE jobs SET payload=? WHERE id=?', (job.model_dump_json(), job.job_id))

    def submit(self, event_id, run_id, kind, parameters):
        params = json.dumps(parameters, sort_keys=True, allow_nan=False)
        dedup = hashlib.sha256(json.dumps([event_id, run_id, kind, params]).encode()).hexdigest()
        with self._db() as db:
            existing = db.execute('SELECT payload FROM jobs WHERE dedup=?', (dedup,)).fetchone()
            if existing:
                return JobRef.model_validate_json(existing[0])
            job = JobRef(job_id=uuid.uuid4().hex, event_id=event_id, run_id=run_id, kind=kind)
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (job.job_id, dedup, job.model_dump_json(), params))
            return job

    def get(self, job_id):
        with self._db() as db:
            return self._get(db, job_id)

    def transition(self, job_id, status, *, expected_revision, stage='', error_type='', stop_reason=''):
        with self._db() as db:
            job = self._get(db, job_id)
            if job.revision != expected_revision or status not in TRANSITIONS[job.status]:
                raise TransitionConflict('stale revision or illegal status transition')
            if job.worker and job.status == 'running' and status != 'cancel_requested':
                raise TransitionConflict('leased work must finish through its owner token')
            job.status, job.revision = status, job.revision + 1
            job.stage, job.error_type, job.stop_reason = stage, error_type, stop_reason
            self._save(db, job)
            return job

    def claim(self, worker, lease_seconds=60, kinds=None):
        if lease_seconds <= 0:
            raise ValueError('lease must be positive')
        with self._db() as db:
            for row in db.execute('SELECT payload FROM jobs ORDER BY rowid').fetchall():
                job = JobRef.model_validate_json(row[0])
                if kinds is not None and job.kind not in kinds:
                    continue
                if job.status == 'cancel_requested' and (job.lease_until is None or job.lease_until <= time.time()):
                    job.status, job.revision = 'cancelled', job.revision + 1
                    job.stop_reason = 'cancelled_after_worker_exit'
                    self._save(db, job)
                    continue
                expired = job.status == 'running' and job.lease_until is not None and job.lease_until < time.time()
                if job.status == 'queued' or expired:
                    job.status, job.worker = 'running', worker
                    job.lease_token = uuid.uuid4().hex
                    job.lease_until, job.revision = time.time() + lease_seconds, job.revision + 1
                    self._save(db, job)
                    return job
        return None

    def heartbeat(self, job_id, worker, lease_seconds=60, *, lease_token):
        if lease_seconds <= 0:
            raise ValueError('lease must be positive')
        with self._db() as db:
            job = self._owned(db, job_id, worker, lease_token)
            job.lease_until = time.time() + lease_seconds
            self._save(db, job)

    def _owned(self, db, job_id, worker, lease_token, allow_cancel=False):
        job = self._get(db, job_id)
        states = {'running', 'cancel_requested'} if allow_cancel else {'running'}
        if job.worker != worker or not lease_token or job.lease_token != lease_token or job.status not in states or not job.lease_until or job.lease_until <= time.time():
            raise TransitionConflict('worker lease expired or job stopped')
        return job

    def commit_batch(self, job_id, worker, batch_id, result, *, lease_token):
        with self._db() as db:
            self._owned(db, job_id, worker, lease_token)
            db.execute('INSERT OR IGNORE INTO batches VALUES (?,?,?)', (job_id, batch_id, json.dumps(result, allow_nan=False)))

    def batches(self, job_id):
        with self._db() as db:
            self._get(db, job_id)
            return {key: json.loads(value) for key, value in db.execute('SELECT batch,payload FROM batches WHERE job=?', (job_id,))}

    def discard_batches(self, claimed, batch_ids):
        with self._db() as db:
            self._owned(db,claimed.job_id,claimed.worker,claimed.lease_token)
            db.executemany('DELETE FROM batches WHERE job=? AND batch=?',[(claimed.job_id,key) for key in batch_ids])

    def parameters(self, job_id):
        with self._db() as db:
            self._get(db, job_id)
            return json.loads(db.execute('SELECT parameters FROM jobs WHERE id=?', (job_id,)).fetchone()[0])

    def list_jobs(self, event_id, limit=50):
        if not 1 <= limit <= 200:
            raise ValueError('limit must be in 1..200')
        with self._db() as db:
            results = []
            for row in db.execute('SELECT payload FROM jobs ORDER BY rowid DESC'):
                job = JobRef.model_validate_json(row[0])
                if job.event_id == event_id:
                    results.append(job)
                if len(results) == limit:
                    break
            return results

    def find(self, event_id, run_id, kind, parameters):
        params = json.dumps(parameters, sort_keys=True, allow_nan=False)
        dedup = hashlib.sha256(json.dumps([event_id, run_id, kind, params]).encode()).hexdigest()
        with self._db() as db:
            row = db.execute('SELECT payload FROM jobs WHERE dedup=?', (dedup,)).fetchone()
            return JobRef.model_validate_json(row[0]) if row else None

    def set_stage(self, claimed, stage):
        with self._db() as db:
            job = self._owned(db, claimed.job_id, claimed.worker, claimed.lease_token)
            job.stage, job.revision = stage, job.revision + 1
            self._save(db, job)

    def finish(self, claimed, result, status='completed'):
        """Publish result and completed state in the same SQLite transaction."""
        if status not in {'completed', 'partial'}:
            raise ValueError('invalid publication status')
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False)
        with self._db() as db:
            job = self._owned(db, claimed.job_id, claimed.worker, claimed.lease_token)
            db.execute('INSERT INTO job_results VALUES (?,?)', (job.job_id, payload))
            job.status, job.stage, job.revision = status, status, job.revision + 1
            self._save(db, job)
            return job

    def stop_owned(self, claimed, error_type='worker_error'):
        with self._db() as db:
            job = self._owned(db, claimed.job_id, claimed.worker, claimed.lease_token, allow_cancel=True)
            if job.status == 'cancel_requested':
                job.status, job.stop_reason = 'cancelled', 'user_cancelled'
            else:
                job.status, job.error_type = 'failed', error_type
            job.revision += 1
            self._save(db, job)
            return job

    def result(self, job_id):
        with self._db() as db:
            job = self._get(db, job_id)
            if job.status not in {'completed', 'partial'}:
                raise ValueError('job result is not committed')
            row = db.execute('SELECT payload FROM job_results WHERE job=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('job has no domain result')
            return json.loads(row[0])

    def wait_for_auth(self, claimed):
        with self._db() as db:
            job = self._owned(db, claimed.job_id, claimed.worker, claimed.lease_token)
            job.status, job.error_type = 'waiting_for_auth', 'authentication_required'
            job.worker = job.lease_token = job.lease_until = None
            job.revision += 1
            self._save(db,job)
            return job

    def resume(self, job_id):
        with self._db() as db:
            job = self._get(db,job_id)
            if job.status != 'waiting_for_auth':
                raise TransitionConflict('only waiting_for_auth can resume')
            job.status,job.error_type,job.stop_reason = 'queued','',''
            job.worker = job.lease_token = job.lease_until = None
            job.revision += 1
            self._save(db,job)
            return job

    def retry(self, job_id):
        """Create one idempotent successor; preserve original terminal status and checkpoints."""
        with self._db() as db:
            old = self._get(db, job_id)
            if old.status not in {'cancelled', 'failed', 'partial'}:
                raise TransitionConflict('only stopped jobs can be retried')
            dedup = 'retry:' + job_id
            row = db.execute('SELECT payload FROM jobs WHERE dedup=?', (dedup,)).fetchone()
            if row:
                return JobRef.model_validate_json(row[0])
            parameters = db.execute('SELECT parameters FROM jobs WHERE id=?', (job_id,)).fetchone()[0]
            new = JobRef(job_id=uuid.uuid4().hex, event_id=old.event_id, run_id=old.run_id, kind=old.kind, retry_of=job_id)
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', (new.job_id, dedup, new.model_dump_json(), parameters))
            db.execute('INSERT INTO batches SELECT ?,batch,payload FROM batches WHERE job=?', (new.job_id, job_id))
            return new
