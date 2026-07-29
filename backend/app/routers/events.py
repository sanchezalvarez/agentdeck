import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..services.broadcaster import broadcaster, format_sse

router = APIRouter(prefix="/events", tags=["events"])

KEEPALIVE_SECONDS = 15


@router.get("/stream")
async def event_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events stream with periodic keep-alives."""

    async def generator():
        queue = broadcaster.subscribe()
        try:
            yield format_sse("connected", {"ok": True})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    yield format_sse(message["event"], message["data"])
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
