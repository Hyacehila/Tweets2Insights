from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from ..dependencies import runtime, store

router = APIRouter(prefix="/api/threads/{thread_id}/datasets", tags=["datasets"])


class Upload(BaseModel):
    records: list[dict] = Field(max_length=100000)


@router.get("")
async def list_datasets(thread_id: str, db=Depends(store), manager=Depends(runtime)):
    event = db.get(thread_id)["event_id"]
    return await manager.mcp.call("list_datasets", {"event_id": event})


@router.post("")
async def register(
    thread_id: str, body: Upload, db=Depends(store), manager=Depends(runtime)
):
    event = db.get(thread_id)["event_id"]
    return await manager.mcp.call(
        "register_dataset", {"event_id": event, "records": body.records}
    )
