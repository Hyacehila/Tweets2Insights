from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from ..dependencies import store, runtime

router = APIRouter(prefix="/api/threads", tags=["threads"])


class CreateThread(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    title: str = Field(default="新研究会话", max_length=120)


@router.post("")
def create(body: CreateThread, db=Depends(store)):
    return db.create(body.event_id, body.title)


@router.get("")
def list_threads(db=Depends(store)):
    return db.list()


@router.get("/{thread_id}")
def get_thread(thread_id: str, db=Depends(store)):
    return {**db.get(thread_id), "latest_execution": db.latest_execution(thread_id)}


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


@router.put("/{thread_id}/memory")
def update_memory(thread_id: str, body: dict, db=Depends(store)):
    db.set_memory(thread_id, body)
    return {"saved": True}
