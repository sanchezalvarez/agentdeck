import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Simple in-process SSE broadcaster.

    Subscribers get an asyncio.Queue; slow/disconnected clients are dropped
    rather than blocking publishers.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event_type: str, data: dict[str, Any]) -> None:
        message = {"event": event_type, "data": data}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the slow subscriber; its stream will terminate.
                self._subscribers.discard(queue)
                logger.warning("Dropped slow SSE subscriber")


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


broadcaster = EventBroadcaster()
