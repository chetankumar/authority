"""GitStatusWorker — keeps the top-bar git badge honest, off the write path.

One standing asyncio task for the whole process (doc 07 §25): **not** one per
book, and **not** a separate OS process — a single-process local app gains
nothing from IPC. It subscribes to the EventHub's global channel, consumes the
internal ``book-changed`` signal, and re-checks git after a **pure 5s debounce**
per book (doc 07 §26): every new signal cancels the pending timer and starts a
fresh one, so the check runs only once writes go quiet.

Why not just run ``git status`` inline on each save? Because that shells out to a
subprocess on the one path that must never stutter — typing. The author's autosave
returns immediately; the badge catches up a few seconds later, and the client's
10s poll (doc 07 §28) covers anything this worker misses.

Explicit git actions never reach here: stage/commit/push/pull emit ``git-status``
themselves, in-request (doc 07 §27).
"""

from __future__ import annotations

import asyncio
import logging

from app.core.errors import ApiError
from app.core.event_hub import EventHub
from app.services.git_service import GitService

log = logging.getLogger("authority.git")

_DEBOUNCE_SECONDS = 5.0


class GitStatusWorker:
    def __init__(self, git: GitService, hub: EventHub) -> None:
        self._git = git
        self._hub = hub
        self._pending: dict[str, asyncio.Task[None]] = {}

    async def run(self) -> None:
        """Drain the global event channel until cancelled (app shutdown)."""
        queue = self._hub.subscribe_all()
        log.info("Git-status worker started")
        try:
            while True:
                event = await queue.get()
                if event.get("event") != "book-changed":
                    continue
                book_id = event.get("bookId")
                if book_id:
                    self._restart_debounce(book_id)
        except asyncio.CancelledError:
            raise
        finally:
            self._hub.unsubscribe(queue)
            for task in self._pending.values():
                task.cancel()
            self._pending.clear()
            log.info("Git-status worker stopped")

    def _restart_debounce(self, book_id: str) -> None:
        existing = self._pending.get(book_id)
        if existing is not None:
            existing.cancel()
        self._pending[book_id] = asyncio.create_task(self._check_after_debounce(book_id))

    async def _check_after_debounce(self, book_id: str) -> None:
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)
            status = await self._git.status(book_id)
            self._hub.emit(book_id, "git-status", status.model_dump())
        except asyncio.CancelledError:
            raise  # superseded by a newer write, or shutting down
        except ApiError as exc:
            # A book without a .git (or an unreadable one) isn't worth retrying
            # or shouting about — the badge simply stays quiet.
            log.debug("Git status skipped for %s: %s", book_id, exc.error)
        except Exception as exc:  # noqa: BLE001 — a bad book must not kill the worker
            log.warning("Git status check failed for %s: %s", book_id, exc)
        finally:
            # Drop our own finished entry; a newer task will have replaced it.
            if self._pending.get(book_id) is asyncio.current_task():
                del self._pending[book_id]
