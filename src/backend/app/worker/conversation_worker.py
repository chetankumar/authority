"""ConversationWorker — standing asyncio task draining queued conversations.

Mirrors GitStatusWorker: one process-wide task, started in main's lifespan.
Concurrency: 1 per book, ≤2 global.

Automatic leave-scene enrichment is fire-and-forget — the author has navigated
away, no modal is open, nothing is awaiting a response. Something still has to
run it, off the request, with a ceiling on how many model calls are in flight.
That's this. It drains conversations sitting at `queued` and sends them down
exactly the same `send_message` path the UI uses; it does not care what `kind`
they are.
"""

from __future__ import annotations

import asyncio
import logging

from app.models.enums import ConversationStatus
from app.services.book_registry import BookRegistry
from app.services.conversation_service import ConversationService

log = logging.getLogger("authority.conversations")

_POLL_IDLE_SECONDS = 1.0
_GLOBAL_LIMIT = 2


class ConversationWorker:
    def __init__(self, conversations: ConversationService, registry: BookRegistry) -> None:
        self._conversations = conversations
        self._registry = registry
        self._wake = asyncio.Event()
        self._conversations.set_wake(self._wake)
        self._running_books: set[str] = set()
        self._in_flight = 0

    async def run(self) -> None:
        log.info("Conversation worker started")
        try:
            while True:
                self._wake.clear()
                await self._drain_once()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=_POLL_IDLE_SECONDS)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        finally:
            log.info("Conversation worker stopped")

    async def _drain_once(self) -> None:
        for book_id in self._loaded_book_ids():
            if book_id in self._running_books:
                continue
            if self._in_flight >= _GLOBAL_LIMIT:
                break
            conv_id = self._next_queued(book_id)
            if conv_id is None:
                continue
            self._running_books.add(book_id)
            self._in_flight += 1
            asyncio.create_task(self._run_one(book_id, conv_id))

    def _loaded_book_ids(self) -> list[str]:
        return list(self._registry._managers.keys())

    def _next_queued(self, book_id: str) -> str | None:
        """Oldest queued conversation for this book. The index already carries
        `status`, so this is an in-memory filter — no conversation files opened."""
        mgr = self._registry.get(book_id)
        queued = [
            s for s in mgr.get_conversation_index() if s.status == ConversationStatus.queued
        ]
        if not queued:
            return None
        queued.sort(key=lambda s: s.updatedAt)
        return queued[0].id

    async def _run_one(self, book_id: str, conversation_id: str) -> None:
        try:
            # body=None: the prompt is already the thread's first message, so
            # generate against what's there rather than inventing a user turn.
            # send_message is an async generator — it only does its work while
            # something consumes it, and nobody is watching a background run,
            # so drain the SSE events to nowhere. The conversation is where the
            # result lands.
            async for _event in self._conversations.send_message(book_id, conversation_id):
                pass
        except Exception as exc:
            log.warning("conversation worker error for %s/%s: %s", book_id, conversation_id, exc)
        finally:
            self._running_books.discard(book_id)
            self._in_flight = max(0, self._in_flight - 1)
            self._wake.set()
