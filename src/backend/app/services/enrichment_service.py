"""EnrichmentService — settle-then-run bookkeeping (doc 05).

Clear cases write summary/characterIds under standing consent.
Unclear cases escalate to a chat via EscalationService.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ApiError, validation
from app.core.event_hub import EventHub
from app.models.enums import JobScope, JobStatus, ParentType
from app.models.job import Job
from app.services.ai_orchestrator import AIOrchestrator
from app.services.book_registry import BookRegistry
from app.services.context_assembler import ContextAssembler
from app.services.escalation_service import EscalationIssue, EscalationService
from app.services.output_parsers import parse_enrichment_result
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.enrichment")

_SETTLE_SECONDS = 60.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EnrichmentService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        hub: EventHub,
        orchestrator: AIOrchestrator,
        escalation: EscalationService,
        job_service: Any | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._hub = hub
        self._orch = orchestrator
        self._escalation = escalation
        self._jobs = job_service
        self._timers: dict[tuple[str, str], asyncio.Task[None]] = {}
        self._assembler = ContextAssembler()

    def set_job_service(self, job_service: Any) -> None:
        self._jobs = job_service

    def reset_settle_timer(self, book_id: str, scene_id: str) -> None:
        key = (book_id, scene_id)
        existing = self._timers.get(key)
        if existing is not None:
            existing.cancel()
        self._timers[key] = asyncio.create_task(self._settle_after(book_id, scene_id))

    def settle_now(self, book_id: str, scene_id: str) -> None:
        key = (book_id, scene_id)
        existing = self._timers.get(key)
        if existing is not None:
            existing.cancel()
            del self._timers[key]
        asyncio.create_task(self._enqueue_if_needed(book_id, scene_id))

    async def _settle_after(self, book_id: str, scene_id: str) -> None:
        try:
            await asyncio.sleep(_SETTLE_SECONDS)
            await self._enqueue_if_needed(book_id, scene_id)
        except asyncio.CancelledError:
            raise
        finally:
            key = (book_id, scene_id)
            if self._timers.get(key) is asyncio.current_task():
                del self._timers[key]

    async def _enqueue_if_needed(self, book_id: str, scene_id: str) -> None:
        if self._jobs is None:
            return
        mgr = self._registry.get(book_id)
        bk = mgr.config.bookkeeping
        scopes: list[str] = []
        if bk.summaryOnSave and self._settings.get_scene_summary_model() is not None:
            scopes.append("summary")
        if bk.charactersOnSave and self._settings.get_character_parsing_model() is not None:
            scopes.append("characters")
        if not scopes:
            log.info("enrichment skipped for %s/%s — no model configured for the enabled toggle(s)", book_id, scene_id)
            return
        if len(scopes) == 2:
            scope = JobScope.both
        elif scopes[0] == "summary":
            scope = JobScope.summary
        else:
            scope = JobScope.characters
        # No fixed model_id here — run() resolves the model per sub-task (scene
        # summary vs character parsing may be different models) at execution time.
        self._jobs.enqueue_system(book_id, scene_id=scene_id, scope=scope, model_id=None, replace_queued=True)

    async def enrich_on_demand(self, book_id: str, scene_id: str, scope: JobScope) -> Job:
        if scope not in (JobScope.summary, JobScope.characters, JobScope.both):
            raise validation({"scope": "Use summary, characters, or both."})
        want_summary = scope in (JobScope.summary, JobScope.both)
        want_chars = scope in (JobScope.characters, JobScope.both)
        have_summary = want_summary and self._settings.get_scene_summary_model() is not None
        have_chars = want_chars and self._settings.get_character_parsing_model() is not None
        if not have_summary and not have_chars:
            raise ApiError(422, "No model configured for the requested enrichment.", {"code": "no-utility-model"})
        if self._jobs is None:
            raise ApiError(500, "Job service not ready.", {})
        mgr = self._registry.get(book_id)
        if not any(s.id == scene_id for s in mgr.get_scenes()):
            raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})
        return self._jobs.enqueue_system(book_id, scene_id=scene_id, scope=scope, model_id=None, replace_queued=True)

    async def run(self, book_id: str, job: Job) -> None:
        mgr = self._registry.get(book_id)
        scene = next((s for s in mgr.get_scenes() if s.id == job.sceneId), None)
        if scene is None:
            raise RuntimeError(f"Scene {job.sceneId} missing")
        prose = mgr.read_scene_content(scene.file)
        book = mgr.get_book()

        # Character directory for matching (may be empty / unavailable).
        chars: list[Any] = []
        getter = getattr(mgr, "get_characters", None)
        if getter is not None:
            chars = list(getter())

        directory_lines = []
        for c in chars:
            aliases = ", ".join(getattr(c, "aliases", []) or [])
            directory_lines.append(f"- id={c.id} name={c.name}" + (f" aliases={aliases}" if aliases else ""))
        directory = "\n".join(directory_lines) if directory_lines else "(empty — no characters defined)"

        want_summary = job.scope in (JobScope.summary, JobScope.both)
        want_chars = job.scope in (JobScope.characters, JobScope.both)

        # Summarization and character-parsing are independent calls, each on
        # its own configured model — a scene may want its summary from one
        # model and its cast list matched by another. Doing this as two calls
        # (rather than one combined prompt) is the whole point of separating
        # the settings slots; if scope is `both` and both slots resolve to the
        # same model, that's still two calls, kept simple and uniform.
        parsed: dict[str, Any] = {}
        models_used: dict[str, str] = {}

        if want_summary:
            summary_model = self._settings.get_scene_summary_model()
            if summary_model is not None:
                messages = self._assembler.for_structured(
                    self._summary_prompt(scene, prose), book.systemPrompt
                )
                raw = await self._orch.invoke_structured(summary_model, messages, timeout=120.0)
                parsed.update(parse_enrichment_result(raw))
                models_used["sceneSummary"] = summary_model.id
            else:
                log.info("scene-summary enrichment skipped for %s — no model configured", job.sceneId)

        chars_model = self._settings.get_character_parsing_model() if want_chars else None
        if want_chars:
            if chars_model is not None:
                messages = self._assembler.for_structured(
                    self._characters_prompt(scene, prose, directory), book.systemPrompt
                )
                raw = await self._orch.invoke_structured(chars_model, messages, timeout=120.0)
                parsed.update(parse_enrichment_result(raw))
                models_used["characterParsing"] = chars_model.id
            else:
                log.info("character-parsing enrichment skipped for %s — no model configured", job.sceneId)

        changed: list[str] = []
        unrecognized: list[str] = []
        conversation_ids: list[str] = []

        async with mgr.lock:
            records = {r.id: r.model_copy(deep=True) for r in mgr.get_scenes()}
            rec = records.get(job.sceneId or "")
            if rec is None:
                raise RuntimeError("Scene vanished")

            if want_summary and isinstance(parsed.get("summary"), str) and parsed["summary"].strip():
                rec.summary = parsed["summary"].strip()
                changed.append("summary")

            if want_chars and chars_model is not None:
                matched = parsed.get("matchedCharacterIds") or []
                if isinstance(matched, list):
                    valid_ids = {c.id for c in chars}
                    # Also allow exact name/alias match without model ids.
                    exact = self._exact_match_ids(prose, chars)
                    ids = [i for i in matched if i in valid_ids]
                    for i in exact:
                        if i not in ids:
                            ids.append(i)
                    if ids:
                        rec.characterIds = ids
                        changed.append("characterIds")

                for name in parsed.get("unrecognizedNames") or []:
                    if isinstance(name, str) and name.strip():
                        unrecognized.append(name.strip())

                for amb in parsed.get("ambiguous") or []:
                    if not isinstance(amb, dict):
                        continue
                    amb_name = str(amb.get("name") or "").strip() or "this character"
                    q = amb.get("question") or f"I'm unsure about '{amb_name}'. How should I treat this character?"
                    cid = self._escalation.escalate(
                        book_id,
                        parent_type=ParentType.scene,
                        parent_id=rec.id,
                        issue=EscalationIssue(
                            kind="ambiguity",
                            title=f"who is {amb_name}?",
                            message=q,
                            context={
                                "name": amb_name,
                                "candidates": amb.get("candidates") or [],
                                "excerpt": prose[:400],
                            },
                        ),
                        model_id=chars_model.id,
                    )
                    conversation_ids.append(cid)

                for name in unrecognized:
                    cid = self._escalation.escalate(
                        book_id,
                        parent_type=ParentType.scene,
                        parent_id=rec.id,
                        issue=EscalationIssue(
                            kind="unmatched_name",
                            title=f"who is {name}?",
                            message=(
                                f"I found '{name}' in this scene, but it's not on the character sheet. "
                                "Should I propose adding them, link to an existing character, or ignore "
                                "(e.g. a minor walk-on)?"
                            ),
                            context={"name": name, "excerpt": prose[:400]},
                        ),
                        model_id=chars_model.id,
                    )
                    conversation_ids.append(cid)

            rec.updatedAt = _now()
            mgr.save_scenes(list(records.values()))

        if changed:
            self._hub.emit(book_id, "scene-updated", {"id": job.sceneId, "changed": changed})

        job.result = {
            "unrecognizedNames": unrecognized,
            "conversationIds": conversation_ids,
            "modelsUsed": models_used,
        }
        job.status = JobStatus.done
        job.finishedAt = _now()
        if self._jobs is not None:
            self._jobs.update_job(book_id, job)

    @staticmethod
    def _summary_prompt(scene: Any, prose: str) -> str:
        return "\n".join(
            [
                "You maintain scene bookkeeping for a novel.",
                "Return a single fenced JSON object: { \"summary\": string }.",
                "",
                f"Scene title: {scene.title}",
                f"Scene prose:\n{prose[:20000]}",
            ]
        )

    @staticmethod
    def _characters_prompt(scene: Any, prose: str, directory: str) -> str:
        return "\n".join(
            [
                "You maintain the character directory for a novel.",
                "Return a single fenced JSON object with keys:",
                '  "matchedCharacterIds": [ids from the directory that clearly appear],',
                '  "unrecognizedNames": [proper names in prose not in the directory],',
                '  "ambiguous": [{"name": "...", "candidates": ["id:...", ...], "question": "..."}]',
                "Only exact/clear matches go in matchedCharacterIds. When unsure, use ambiguous.",
                "Never invent character ids.",
                "",
                f"Character directory:\n{directory}",
                "",
                f"Scene title: {scene.title}",
                f"Scene prose:\n{prose[:20000]}",
            ]
        )

    @staticmethod
    def _exact_match_ids(prose: str, chars: list[Any]) -> list[str]:
        """Deterministic exact name/alias matches (case-insensitive word boundaries)."""
        text = prose
        found: list[str] = []
        for c in chars:
            names = [c.name, *list(getattr(c, "aliases", []) or [])]
            for n in names:
                if not n or not n.strip():
                    continue
                pattern = re.compile(rf"\b{re.escape(n.strip())}\b", re.IGNORECASE)
                if pattern.search(text):
                    found.append(c.id)
                    break
        return found
