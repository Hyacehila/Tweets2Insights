from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from ..dependencies import runtime, store

router = APIRouter(prefix="/api/threads/{thread_id}/runs", tags=["agent runs"])


class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=16000)
    request: dict | None = None
    execute: bool = False


@router.post("")
async def start(thread_id: str, body: RunBody, manager=Depends(runtime)):
    return await manager.start(thread_id, body.message, body.request, body.execute)


@router.get("/{execution_id}")
def status(thread_id: str, execution_id: str, db=Depends(store)):
    result = db.execution(execution_id)
    if result["thread_id"] != thread_id:
        raise ValueError("execution belongs to another thread")
    return result


@router.post("/{execution_id}/cancel")
async def cancel(thread_id: str, execution_id: str, manager=Depends(runtime)):
    return manager.cancel(thread_id, execution_id)
