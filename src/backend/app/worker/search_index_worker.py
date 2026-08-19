"""SearchIndexWorker — background index / rebuild / delete for book search.

Concurrency 1 globally (one book at a time). Emits ``search-index`` SSE so the
UI can show progress. Ask/answer is in-request, not this worker.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.core.event_hub import EventHub
from app.services.search_service import SearchService

log = logging.getLogger("authority.search_worker")

JobKind = Literal["index-scene", "rebuild", "delete"]


@dataclass
class SearchIndexJob:
    kind: JobKind
    book_id: str
    scene_id: str | None = None


class SearchIndexWorker:
    def __init__(self, search: SearchService, hub: EventHub) -> None:
        self._search = search
        self._hub = hub
        self._queue: asyncio.Queue[SearchIndexJob] = asyncio.Queue()
        self._runs: dict[str, dict[str, Any]] = {}

    def run_snapshot(self, book_id: str) -> dict[str, Any] | None:
        return self._runs.get(book_id)

    def enqueue_scene(self, book_id: str, scene_id: str) -> None:
        self._queue.put_nowait(SearchIndexJob("index-scene", book_id, scene_id))

    def enqueue_rebuild(self, book_id: str) -> None:
        self._queue.put_nowait(SearchIndexJob("rebuild", book_id))

    def enqueue_delete(self, book_id: str) -> None:
        self._queue.put_nowait(SearchIndexJob("delete", book_id))

    def _set_run(self, book_id: str, **fields: Any) -> dict[str, Any]:
        current = dict(self._runs.get(book_id) or {})
        current.update(fields)
        self._runs[book_id] = current
        return current

    def _emit(self, book_id: str) -> None:
        snap = self._runs.get(book_id) or {}
        self._hub.emit(
            book_id,
            "search-index",
            {
                "status": snap.get("status") or "idle",
                "sceneId": snap.get("sceneId"),
                "done": snap.get("done") or 0,
                "total": snap.get("total") or 0,
                "error": snap.get("error"),
            },
        )

    async def run(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("search index job failed for %s", job.book_id)
                self._set_run(
                    job.book_id,
                    status="failed",
                    error=str(exc),
                    sceneId=job.scene_id,
                )
                self._emit(job.book_id)

    async def _process(self, job: SearchIndexJob) -> None:
        if job.kind == "delete":
            self._set_run(job.book_id, status="running", sceneId=None, done=0, total=1, error=None)
            self._emit(job.book_id)
            await self._search.delete_index(job.book_id)
            self._set_run(job.book_id, status="idle", sceneId=None, done=1, total=1, error=None)
            self._emit(job.book_id)
            return

        if job.kind == "index-scene":
            scene_id = job.scene_id or ""
            self._set_run(
                job.book_id,
                status="running",
                sceneId=scene_id,
                done=0,
                total=1,
                error=None,
            )
            self._emit(job.book_id)
            await self._search.index_scene(job.book_id, scene_id)
            self._set_run(
                job.book_id,
                status="idle",
                sceneId=scene_id,
                done=1,
                total=1,
                error=None,
            )
            self._emit(job.book_id)
            return

        ids = self._search.list_indexable_scene_ids(job.book_id)
        total = max(len(ids), 1)
        self._set_run(job.book_id, status="running", sceneId=None, done=0, total=len(ids), error=None)
        self._emit(job.book_id)
        done = 0
        for scene_id in ids:
            self._set_run(job.book_id, sceneId=scene_id, done=done, total=len(ids))
            self._emit(job.book_id)
            await self._search.index_scene(job.book_id, scene_id)
            done += 1
            self._set_run(job.book_id, sceneId=scene_id, done=done, total=len(ids))
            self._emit(job.book_id)
        self._set_run(
            job.book_id,
            status="idle",
            sceneId=None,
            done=done,
            total=total if ids else 0,
            error=None,
        )
        self._emit(job.book_id)
