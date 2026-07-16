"""EventHub — per-book SSE pub/sub (doc 04 §12).

Generic core infrastructure with **no dependency on the AI layer** (doc 07 §24).
The build-phase list groups the SSE hub under "AI layer" only because streaming
was its first intended consumer; nothing about per-book pub/sub needs LangChain,
jobs, or conversations. Whichever phase first needs to push builds it; later
consumers just call :meth:`EventHub.emit`.

Two subscription modes:

* :meth:`subscribe` — one queue per connected browser tab, drained by
  ``GET /api/books/{id}/events``.
* :meth:`subscribe_all` — one queue receiving every book's events, for
  server-side consumers (today: the git-status worker).

The channel is **stateless**: nothing is buffered for absent subscribers and no
history is replayed on reconnect. Clients refetch instead. That statelessness is
what makes the client's redundant 10s ``git/status`` poll safe — poll and event
carry identical server truth, so they cannot disagree (doc 07 §28).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("authority.events")

# A slow/stuck subscriber must never block a writer. Queues are bounded; on
# overflow we drop the event for that subscriber rather than stall the emitter
# (the client's poll is the backstop for anything dropped here).
_QUEUE_MAXSIZE = 256


class Event(dict):
    """One event: ``{"bookId": ..., "event": ..., "data": {...}}``."""


class EventHub:
    def __init__(self) -> None:
        self._per_book: dict[str, set[asyncio.Queue[Event]]] = {}
        self._global: set[asyncio.Queue[Event]] = set()

    # ---- subscription -------------------------------------------------------

    def subscribe(self, book_id: str) -> asyncio.Queue[Event]:
        """Subscribe to one book's events (one queue per connected tab)."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._per_book.setdefault(book_id, set()).add(queue)
        return queue

    def subscribe_all(self) -> asyncio.Queue[Event]:
        """Subscribe to every book's events (internal server-side consumers)."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._global.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event], book_id: str | None = None) -> None:
        """Drop a queue. Pass ``book_id`` for per-book queues; omit for global."""
        if book_id is None:
            self._global.discard(queue)
            return

        subscribers = self._per_book.get(book_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            del self._per_book[book_id]

    # ---- emission -----------------------------------------------------------

    def emit(self, book_id: str, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Fan an event out to this book's subscribers and all global ones.

        Synchronous and non-blocking by design: callers (including request
        handlers holding a book lock) must never await a subscriber.
        """
        event = Event(bookId=book_id, event=event_type, data=data or {})
        targets = list(self._per_book.get(book_id, ())) + list(self._global)
        for queue in targets:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Never stall a writer for a subscriber that isn't draining.
                log.warning("Dropping %s for a full subscriber queue (book %s)", event_type, book_id)
