from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from ..dependencies import runtime, store, settings
from opinion_core.labeling.media import MAX_IMAGE_BYTES
from opinion_gateway.media_assets import MediaAssets
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/threads/{thread_id}/datasets", tags=["datasets"])


class Upload(BaseModel):
    records: list[dict] = Field(max_length=100000)


@router.post("/images")
async def upload_image(
    thread_id: str, request: Request, db=Depends(store), config=Depends(settings)
):
    event = db.get(thread_id)["event_id"]
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Each image must be at most 16 MiB")
    try:
        ref = await run_in_threadpool(
            MediaAssets(config.asset_root, event).save, bytes(data)
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"media_ref": ref}


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
