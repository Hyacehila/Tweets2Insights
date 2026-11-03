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
            job.status, job.revision = status, job.revision + 1
            job.stage, job.error_type, job.stop_reason = stage, error_type, stop_reason
            self._save(db, job)
            return job

    def claim(self, worker, lease_seconds=60):
        if lease_seconds <= 0:
            raise ValueError('lease must be positive')
        with self._db() as db:
            for row in db.execute('SELECT payload FROM jobs ORDER BY rowid').fetchall():
                job = JobRef.model_validate_json(row[0])
                expired = job.status == 'running' and job.lease_until is not None and job.lease_until < time.time()
                if job.status == 'queued' or expired:
                    job.status, job.worker = 'running', worker
                    job.lease_until, job.revision = time.time() + lease_seconds, job.revision + 1
                    self._save(db, job)
                    return job
        return None

    def heartbeat(self, job_id, worker, lease_seconds=60):
        with self._db() as db:
            job = self._owned(db, job_id, worker)
            job.lease_until = time.time() + lease_seconds
            self._save(db, job)

    def _owned(self, db, job_id, worker):
        job = self._get(db, job_id)
        if job.worker != worker or job.status != 'running' or not job.lease_until or job.lease_until <= time.time():
            raise TransitionConflict('worker lease expired or job stopped')
        return job

    def commit_batch(self, job_id, worker, batch_id, result):
        with self._db() as db:
            self._owned(db, job_id, worker)
            db.execute('INSERT OR IGNORE INTO batches VALUES (?,?,?)', (job_id, batch_id, json.dumps(result, allow_nan=False)))

    def batches(self, job_id):
        with self._db() as db:
            self._get(db, job_id)
            return {key: json.loads(value) for key, value in db.execute('SELECT batch,payload FROM batches WHERE job=?', (job_id,))}
