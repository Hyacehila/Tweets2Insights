from typing import Literal
from pydantic import Field
from .base import Contract, Identifier

JobStatus = Literal['queued', 'running', 'waiting_for_auth', 'cancel_requested', 'cancelled', 'partial', 'completed', 'failed']


class JobRef(Contract):
    job_id: Identifier
    event_id: Identifier
    run_id: Identifier
    kind: str
    status: JobStatus = 'queued'
    revision: int = Field(default=0, ge=0)
    stage: str = ''
    error_type: str = ''
    stop_reason: str = ''
    worker: str | None = None
    lease_until: float | None = None
    lease_token: str | None = None
    retry_of: Identifier | None = None
