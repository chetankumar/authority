"""AudioWorker — standing asyncio task for ElevenLabs synthesis jobs.

One global queue; jobs processed inline (concurrency 1) because ElevenLabs
limits are per-account. Within a job, a small semaphore parallelizes lines.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.core.event_hub import EventHub
from app.models.enums import AudioLineStatus, AudioSynthesisStatus
from app.services.audio_service import AudioService, read_manifest_if_exists

log = logging.getLogger("authority.audio_worker")

LINE_CONCURRENCY = 2


@dataclass
class AudioJob:
    book_id: str
    scene_id: str
    line_id: str | None = None  # None = all pending


class AudioWorker:
    def __init__(self, audio: AudioService, hub: EventHub) -> None:
        self._audio = audio
        self._hub = hub
        self._queue: asyncio.Queue[AudioJob] = asyncio.Queue()

    def enqueue(self, book_id: str, scene_id: str, line_id: str | None = None) -> None:
        self._queue.put_nowait(AudioJob(book_id, scene_id, line_id))

    async def run(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("audio synthesis failed for %s/%s", job.book_id, job.scene_id)
                await self._mark_failed(job.book_id, job.scene_id, "internal error")

    async def _process(self, job: AudioJob) -> None:
        mgr = self._audio._registry.get(job.book_id)
        manifest = read_manifest_if_exists(mgr.book_dir, job.scene_id)
        if manifest is None:
            await self._mark_failed(job.book_id, job.scene_id, "no manifest")
            return

        if job.line_id:
            pending = [it for it in manifest.sequence if it.id == job.line_id]
        else:
            pending = [
                it
                for it in manifest.sequence
                if it.generation_status in (AudioLineStatus.new, AudioLineStatus.regenerate)
            ]

        if not pending:
            manifest.synthesisStatus = AudioSynthesisStatus.done
            await self._audio.write_manifest_status(job.book_id, job.scene_id, manifest)
            self._emit(job, "done", completed=0, total=0)
            return

        total = len(pending)
        completed = 0
        failed: list[str] = []
        sem = asyncio.Semaphore(LINE_CONCURRENCY)

        async def one(item):
            nonlocal completed
            async with sem:
                try:
                    await self._audio.synthesize_line(job.book_id, job.scene_id, item)
                    completed += 1
                    self._emit(job, "line", line_id=item.id, completed=completed, total=total)
                except Exception as exc:
                    log.exception("line %s failed", item.id)
                    failed.append(f"{item.id}: {exc}")

        await asyncio.gather(*(one(it) for it in pending))

        # Reload after per-line writes
        manifest = read_manifest_if_exists(mgr.book_dir, job.scene_id)
        if manifest is None:
            return

        if failed:
            manifest.synthesisStatus = AudioSynthesisStatus.failed
            manifest.lastError = "; ".join(failed[:5])
            await self._audio.write_manifest_status(job.book_id, job.scene_id, manifest)
            self._emit(job, "error", completed=completed, total=total, message=manifest.lastError)
            return

        self._emit(job, "stitch", completed=completed, total=total)
        try:
            await self._audio.stitch(job.book_id, job.scene_id)
        except Exception as exc:
            log.exception("stitch failed")
            manifest = read_manifest_if_exists(mgr.book_dir, job.scene_id)
            if manifest:
                manifest.synthesisStatus = AudioSynthesisStatus.failed
                manifest.lastError = f"stitch failed: {exc}"
                await self._audio.write_manifest_status(job.book_id, job.scene_id, manifest)
            self._emit(job, "error", completed=completed, total=total, message=str(exc))
            return

        manifest = read_manifest_if_exists(mgr.book_dir, job.scene_id)
        if manifest:
            manifest.synthesisStatus = AudioSynthesisStatus.done
            manifest.lastError = None
            await self._audio.write_manifest_status(job.book_id, job.scene_id, manifest)
        self._emit(job, "done", completed=completed, total=total)

    async def _mark_failed(self, book_id: str, scene_id: str, message: str) -> None:
        try:
            mgr = self._audio._registry.get(book_id)
            manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
            if manifest is None:
                return
            manifest.synthesisStatus = AudioSynthesisStatus.failed
            manifest.lastError = message
            await self._audio.write_manifest_status(book_id, scene_id, manifest)
            self._hub.emit(
                book_id,
                "audio-progress",
                {"sceneId": scene_id, "phase": "error", "message": message, "completed": 0, "total": 0},
            )
        except Exception:
            log.exception("could not mark audio failed")

    def _emit(
        self,
        job: AudioJob,
        phase: str,
        *,
        completed: int = 0,
        total: int = 0,
        line_id: str | None = None,
        message: str | None = None,
    ) -> None:
        payload: dict = {
            "sceneId": job.scene_id,
            "phase": phase,
            "completed": completed,
            "total": total,
        }
        if line_id:
            payload["lineId"] = line_id
        if message:
            payload["message"] = message
        self._hub.emit(job.book_id, "audio-progress", payload)
