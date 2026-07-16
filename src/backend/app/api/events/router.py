"""Events router (doc 04 §12) — the per-book SSE channel.

One connection per open book. Any service emits through the
:class:`~app.core.event_hub.EventHub`; this router just drains one subscriber
queue onto the wire. The channel is stateless — clients refetch on reconnect,
and anything that renders git state also polls as a safety net (doc 07 §28).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from app.api.deps import get_event_hub
from app.core.event_hub import Event, EventHub

log = logging.getLogger("authority.events")

router = APIRouter(prefix="/books/{book_id}", tags=["events"])

Hub = Depends(get_event_hub)

# Idle comment frames keep proxies and browsers from reaping a quiet stream.
_KEEPALIVE_SECONDS = 25.0


def _frame(event: Event) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


async def _stream(request: Request, hub: EventHub, book_id: str) -> AsyncIterator[str]:
    queue = hub.subscribe(book_id)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield _frame(event)
    finally:
        hub.unsubscribe(queue, book_id)


@router.get("/events")
async def book_events(request: Request, book_id: str, hub: EventHub = Hub) -> StreamingResponse:
    return StreamingResponse(
        _stream(request, hub, book_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Same-origin in production, but a dev proxy in front of us must not buffer.
            "X-Accel-Buffering": "no",
        },
    )
