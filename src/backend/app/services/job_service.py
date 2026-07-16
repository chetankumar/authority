"""JobService — queue + status for user and system AI jobs (doc 04 §11)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ApiError, not_found, validation
from app.core.event_hub import EventHub
from app.core.ids import new_id
from app.models.conversation import AiJobRunRequest, AiJobRunResponse
from app.models.enums import JobScope, JobStatus, JobType, OutputType
from app.models.job import Job
from app.services.book_registry import BookRegistry
from app.services.conversation_service import ConversationService
from app.services.output_parsers import (
    EDIT_FORMAT_INSTRUCTIONS,
    METADATA_FORMAT_INSTRUCTIONS,
    parse_edit_proposals,
    parse_metadata_proposals,
)
from app.services.placeholder_registry import PlaceholderRegistry
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.jobs")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JobService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        conversations: ConversationService,
        hub: EventHub,
        enrichment: Any | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._conversations = conversations
        self._hub = hub
        self._enrichment = enrichment
        self._wake: asyncio.Event | None = None  # set by worker

    def set_wake(self, event: Any) -> None:
        self._wake = event

    def _notify(self) -> None:
        if self._wake is not None:
            self._wake.set()

    def list_jobs(
        self,
        book_id: str,
        *,
        scene_id: str | None = None,
        status: JobStatus | None = None,
        type_: JobType | None = None,
    ) -> list[Job]:
        mgr = self._registry.get(book_id)
        jobs = list(mgr.get_jobs())
        if scene_id:
            jobs = [j for j in jobs if j.sceneId == scene_id]
        if status:
            jobs = [j for j in jobs if j.status == status]
        if type_:
            jobs = [j for j in jobs if j.type == type_]
        jobs.sort(key=lambda j: j.createdAt, reverse=True)
        return jobs

    def enqueue_system(
        self,
        book_id: str,
        *,
        scene_id: str,
        scope: JobScope,
        model_id: str | None,
        replace_queued: bool = True,
    ) -> Job:
        mgr = self._registry.get(book_id)
        jobs = list(mgr.get_jobs())
        if replace_queued:
            jobs = [
                j
                for j in jobs
                if not (
                    j.type == JobType.system
                    and j.sceneId == scene_id
                    and j.status == JobStatus.queued
                )
            ]
        job = Job(
            id=new_id("job", {j.id for j in jobs}),
            type=JobType.system,
            sceneId=scene_id,
            scope=scope,
            modelId=model_id,
            status=JobStatus.queued,
            createdAt=_now(),
        )
        jobs.append(job)
        mgr.save_jobs(jobs)
        self._emit(book_id, job)
        self._notify()
        return job

    async def run_ai_job(self, book_id: str, body: AiJobRunRequest) -> AiJobRunResponse:
        definition = self._settings.get_ai_job(body.aiJobId)
        if definition is None:
            raise not_found("ai-job", body.aiJobId)
        mgr = self._registry.get(book_id)
        scene = next((s for s in mgr.get_scenes() if s.id == body.sceneId), None)
        if scene is None:
            raise not_found("scene", body.sceneId)
        scope = JobScope(body.scope) if body.scope in ("full", "selection") else JobScope.full
        if scope == JobScope.selection and not (body.selectionText or "").strip():
            raise validation({"selectionText": "Selection text is required for selection scope."})

        title = definition.name
        conv = self._conversations.create_ai_job_conversation(
            book_id,
            scene_id=body.sceneId,
            title=title,
            model_id=definition.defaultModelId,
            ai_job_id=definition.id,
            ai_job_name=definition.name,
        )
        jobs = list(mgr.get_jobs())
        job = Job(
            id=new_id("job", {j.id for j in jobs}),
            type=JobType.user,
            aiJobId=definition.id,
            conversationId=conv.id,
            sceneId=body.sceneId,
            scope=scope,
            modelId=definition.defaultModelId,
            status=JobStatus.queued,
            result={"selectionText": body.selectionText} if body.selectionText else {},
            createdAt=_now(),
        )
        jobs.append(job)
        mgr.save_jobs(jobs)
        self._emit(book_id, job)
        self._notify()
        return AiJobRunResponse(jobId=job.id, conversationId=conv.id)

    def _emit(self, book_id: str, job: Job) -> None:
        self._hub.emit(
            book_id,
            "job",
            {
                "id": job.id,
                "type": job.type.value,
                "sceneId": job.sceneId,
                "status": job.status.value,
                "result": job.result or None,
            },
        )

    def update_job(self, book_id: str, job: Job) -> None:
        mgr = self._registry.get(book_id)
        jobs = [job if j.id == job.id else j for j in mgr.get_jobs()]
        if not any(j.id == job.id for j in jobs):
            jobs.append(job)
        mgr.save_jobs(jobs)
        self._emit(book_id, job)

    def next_queued(self, book_id: str) -> Job | None:
        for j in self.list_jobs(book_id):
            if j.status == JobStatus.queued:
                return j
        # list is newest first — want oldest queued
        queued = [j for j in self._registry.get(book_id).get_jobs() if j.status == JobStatus.queued]
        queued.sort(key=lambda j: j.createdAt)
        return queued[0] if queued else None

    async def execute(self, book_id: str, job: Job) -> None:
        job.status = JobStatus.running
        job.startedAt = _now()
        self.update_job(book_id, job)
        try:
            if job.type == JobType.system:
                if self._enrichment is None:
                    raise RuntimeError("EnrichmentService not wired")
                await self._enrichment.run(book_id, job)
            else:
                await self._execute_user_job(book_id, job)
            if job.status == JobStatus.running:
                job.status = JobStatus.done
                job.finishedAt = _now()
                self.update_job(book_id, job)
        except Exception as exc:
            log.exception("job %s failed", job.id)
            job.status = JobStatus.failed
            job.error = str(exc)
            job.finishedAt = _now()
            self.update_job(book_id, job)

    async def _execute_user_job(self, book_id: str, job: Job) -> None:
        from app.services.ai_orchestrator import AIOrchestrator
        from app.services.ai_tools import ToolRegistry
        from app.services.context_assembler import ContextAssembler, CurrentSceneRef
        from app.api.deps import get_ai_orchestrator, get_tool_registry

        definition = self._settings.get_ai_job(job.aiJobId or "")
        if definition is None:
            raise ApiError(422, "AI-Job definition was deleted.", {"code": "ai-job-missing"})
        cfg = self._settings.get_model(job.modelId or definition.defaultModelId)
        if cfg is None:
            raise ApiError(422, "Model missing for this job.", {"code": "model-missing"})

        mgr = self._registry.get(book_id)
        selection = (job.result or {}).get("selectionText")
        resolved = PlaceholderRegistry.resolve(
            definition.prompt,
            mgr=mgr,
            scene_id=job.sceneId or "",
            selection_text=selection,
        )
        if definition.outputType == OutputType.edit_proposals:
            resolved = resolved + "\n\n" + EDIT_FORMAT_INSTRUCTIONS
        elif definition.outputType == OutputType.metadata_proposals:
            resolved = resolved + "\n\n" + METADATA_FORMAT_INSTRUCTIONS

        assert job.conversationId
        self._conversations.append_system_message(book_id, job.conversationId, resolved)

        orch = get_ai_orchestrator()
        tools_reg = get_tool_registry()
        tools, acc = tools_reg.bind(book_id)
        book = mgr.get_book()
        conv = self._conversations.get(book_id, job.conversationId)
        assembler = ContextAssembler()
        scene_ref = None
        if job.sceneId:
            scene = next((s for s in mgr.get_scenes() if s.id == job.sceneId), None)
            scene_ref = CurrentSceneRef(
                id=job.sceneId,
                title=scene.title if scene else "(unknown title)",
            )
        messages = assembler.from_conversation(
            conv, book.systemPrompt, current_scene=scene_ref, mgr=mgr
        )

        turn = await orch.invoke_stream(cfg, messages, tools=tools, accumulator=acc)
        if turn.error and not turn.content:
            raise RuntimeError(turn.error)

        content = turn.content
        proposals = list(turn.proposals)
        warning = None
        if definition.outputType == OutputType.edit_proposals:
            display, parsed = parse_edit_proposals(content, job.sceneId or "")
            if parsed:
                content, proposals = display, parsed + proposals
            else:
                warning = "Could not parse edit proposals; treating as chat."
        elif definition.outputType == OutputType.metadata_proposals:
            display, parsed = parse_metadata_proposals(content, job.sceneId or "")
            if parsed:
                content, proposals = display, parsed + proposals
            else:
                warning = "Could not parse metadata proposals; treating as chat."

        from app.core.ids import new_id as nid
        from app.models.conversation import Message
        from app.models.enums import MessageAuthor

        assistant = Message(
            id=nid("msg"),
            author=MessageAuthor.assistant,
            modelId=cfg.id,
            content=content,
            proposals=proposals,
            createdAt=_now(),
        )
        conv = self._conversations.get(book_id, job.conversationId)
        conv.messages.append(assistant)
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        job.result = {**(job.result or {}), "warning": warning, "conversationId": conv.id}
        job.status = JobStatus.done
        job.finishedAt = _now()
        self.update_job(book_id, job)
