"""JobWorker — standing asyncio task draining per-book job queues.

Mirrors GitStatusWorker: one process-wide task, started in main lifespan.
Concurrency: 1 per book, ≤2 global.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.book_registry import BookRegistry
from app.services.job_service import JobService

log = logging.getLogger("authority.jobs")

_POLL_IDLE_SECONDS = 1.0
_GLOBAL_LIMIT = 2


class JobWorker:
    def __init__(self, jobs: JobService, registry: BookRegistry) -> None:
        self._jobs = jobs
        self._registry = registry
        self._wake = asyncio.Event()
        self._jobs.set_wake(self._wake)
        self._running_books: set[str] = set()
        self._in_flight = 0

    async def run(self) -> None:
        log.info("Job worker started")
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
            log.info("Job worker stopped")

    async def _drain_once(self) -> None:
        # Discover books with queued jobs from currently loaded managers.
        book_ids = list(getattr(self._registry, "_managers", {}).keys()) if hasattr(self._registry, "_managers") else []
        # BookRegistry stores managers — inspect public API.
        book_ids = self._loaded_book_ids()
        for book_id in book_ids:
            if book_id in self._running_books:
                continue
            if self._in_flight >= _GLOBAL_LIMIT:
                break
            job = self._jobs.next_queued(book_id)
            if job is None:
                continue
            self._running_books.add(book_id)
            self._in_flight += 1
            asyncio.create_task(self._run_job(book_id, job.id))

    def _loaded_book_ids(self) -> list[str]:
        return list(self._registry._managers.keys())

    async def _run_job(self, book_id: str, job_id: str) -> None:
        try:
            job = next((j for j in self._jobs.list_jobs(book_id) if j.id == job_id), None)
            if job is None:
                return
            await self._jobs.execute(book_id, job)
        except Exception as exc:
            log.warning("job worker error for %s/%s: %s", book_id, job_id, exc)
        finally:
            self._running_books.discard(book_id)
            self._in_flight = max(0, self._in_flight - 1)
            self._wake.set()
