import asyncio, json
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from ..dependencies import store

router = APIRouter(tags=["streaming"])


@router.get("/api/threads/{thread_id}/events")
async def stream(
    thread_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    db=Depends(store),
):
    db.get(thread_id)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        raise ValueError("invalid event cursor")

    async def generate():
        nonlocal cursor
        while not await request.is_disconnected():
            try:
                db.get(thread_id)
            except KeyError:
                return
            events = db.events(thread_id, cursor)
            for event in events:
                cursor = event["id"]
                yield f"id: {cursor}\nevent: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            if not events:
                yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
