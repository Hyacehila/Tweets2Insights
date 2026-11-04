from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import runtime, settings, store
from ..event_deletion import EventBusy, delete_event_research

router = APIRouter(prefix="/api/threads", tags=["threads"])


class CreateThread(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    title: str = Field(default="新研究会话", max_length=120)


class RenameThread(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)


@router.put("/{thread_id}")
def rename(thread_id: str, body: RenameThread, db=Depends(store)):
    return db.rename(thread_id, body.title)


@router.post("")
def create(body: CreateThread, db=Depends(store)):
    return db.create(body.event_id, body.title)


@router.get("")
def list_threads(db=Depends(store)):
    return db.list()


@router.get("/{thread_id}")
def get_thread(thread_id: str, db=Depends(store)):
    return {**db.get(thread_id), "latest_execution": db.latest_execution(thread_id)}


@router.delete("/{thread_id}/event")
def delete_event(thread_id: str, db=Depends(store), config=Depends(settings)):
    try:
        return delete_event_research(db, config.asset_root, thread_id)
    except EventBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{thread_id}/state")
async def get_state(thread_id: str, db=Depends(store), manager=Depends(runtime)):
    db.get(thread_id)
    snapshot = await manager.graph.aget_state(
        {"configurable": {"thread_id": thread_id}}
    )
    return {
        k: v
        for k, v in snapshot.values.items()
        if k in {"run_request", "plan", "job", "status", "reply"}
    }


@router.get('/{thread_id}/activity')
def activity(thread_id: str, db=Depends(store)):
    fields = {'node', 'status', 'reply', 'execution_id', 'error_type', 'message', 'traceback', 'timestamp'}
    return [{key: value for key, value in item['data'].items() if key in fields} for item in db.recent_events(thread_id)]


@router.put("/{thread_id}/memory")
def update_memory(thread_id: str, body: dict, db=Depends(store)):
    db.set_memory(thread_id, body)
    return {"saved": True}
