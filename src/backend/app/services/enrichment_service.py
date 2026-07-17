"""EnrichmentService — leave-scene + on-demand bookkeeping (doc 05).

Clear cases write summary / characters[{characterId, involvement}] under
standing consent (auto) or explicit redo. Unclear cases escalate via
EscalationService. Never schedules from content autosave.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ApiError, validation
from app.core.event_hub import EventHub
from app.models.conversation import AiParticipant, ConversationCreate, ConversationPatch
from app.models.enums import ConversationKind, JobScope, JobStatus, ParentType
from app.models.job import Job
from app.models.scene import SceneCharacterRef
from app.services.ai_orchestrator import AIOrchestrator
from app.services.book_registry import BookRegistry
from app.services.context_assembler import ContextAssembler
from app.services.conversation_service import ConversationService
from app.services.escalation_service import EscalationIssue, EscalationService
from app.services.output_parsers import parse_enrichment_result
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.enrichment")

_SCOPE_TITLES = {
    JobScope.summary: "Scene summarization",
    JobScope.characters: "Character enrichment",
    JobScope.both: "Scene summarization & character enrichment",
}


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
        conversations: ConversationService,
        job_service: Any | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._hub = hub
        self._orch = orchestrator
        self._escalation = escalation
        self._conversations = conversations
        self._jobs = job_service
        self._assembler = ContextAssembler()

    def set_job_service(self, job_service: Any) -> None:
        self._jobs = job_service

    async def enrich_auto(self, book_id: str, scene_id: str) -> Job | None:
        """Leave-scene path: enqueue only for enabled toggles with resolvable models."""
        if self._jobs is None:
            raise ApiError(500, "Job service not ready.", {})
        mgr = self._registry.get(book_id)
        if not any(s.id == scene_id for s in mgr.get_scenes()):
            raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})
        return self._enqueue_if_needed(book_id, scene_id)

    def _enqueue_if_needed(self, book_id: str, scene_id: str) -> Job | None:
        if self._jobs is None:
            return None
        mgr = self._registry.get(book_id)
        bk = mgr.config.bookkeeping
        scopes: list[str] = []
        if bk.summaryOnSave and self._settings.get_scene_summary_model() is not None:
            scopes.append("summary")
        if bk.charactersOnSave and self._settings.get_character_parsing_model() is not None:
            scopes.append("characters")
        if not scopes:
            log.info(
                "enrichment skipped for %s/%s — no model configured for the enabled toggle(s)",
                book_id,
                scene_id,
            )
            return None
        if len(scopes) == 2:
            scope = JobScope.both
        elif scopes[0] == "summary":
            scope = JobScope.summary
        else:
            scope = JobScope.characters
        return self._jobs.enqueue_system(
            book_id, scene_id=scene_id, scope=scope, model_id=None, replace_queued=True
        )

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

        conv = self._conversations.create(
            book_id,
            ConversationCreate(
                kind=ConversationKind.ai_job,
                parentType=ParentType.scene,
                parentId=scene.id,
                title=_SCOPE_TITLES.get(job.scope, "Bookkeeping"),
                aiParticipant=AiParticipant(enabled=False, modelId=None),
            ),
        )
        job.conversationId = conv.id
        if self._jobs is not None:
            self._jobs.update_job(book_id, job)

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
                existing_refs = mgr.get_scene_bookkeeping(scene.id).characters
                existing_block = self._format_existing_scene_characters(existing_refs, chars)
                messages = self._assembler.for_structured(
                    self._characters_prompt(scene, prose, directory, existing_block),
                    book.systemPrompt,
                )
                raw = await self._orch.invoke_structured(chars_model, messages, timeout=120.0)
                parsed.update(parse_enrichment_result(raw))
                models_used["characterParsing"] = chars_model.id
            else:
                log.info("character-parsing enrichment skipped for %s — no model configured", job.sceneId)

        changed: list[str] = []
        unrecognized: list[str] = []
        matched_names: list[str] = []
        ai_enabled_for_escalation = False

        async with mgr.lock:
            if not any(s.id == scene.id for s in mgr.get_scenes()):
                raise RuntimeError("Scene vanished")
            bookkeeping = mgr.get_scene_bookkeeping(scene.id).model_copy()

            if want_summary and isinstance(parsed.get("summary"), str) and parsed["summary"].strip():
                bookkeeping.summary = parsed["summary"].strip()
                changed.append("summary")

            if want_chars and chars_model is not None:
                refs = self._build_character_refs(parsed, prose, chars)
                if refs:
                    bookkeeping.characters = refs
                    changed.append("characters")
                    by_id = {c.id: c for c in chars}
                    matched_names = [by_id[r.characterId].name for r in refs if r.characterId in by_id]

                for name in parsed.get("unrecognizedNames") or []:
                    if isinstance(name, str) and name.strip():
                        unrecognized.append(name.strip())

                escalations_pending = bool(parsed.get("ambiguous")) or bool(unrecognized)
                if escalations_pending and not ai_enabled_for_escalation:
                    # Let the author's reply in-thread get an AI response.
                    self._conversations.patch(
                        book_id,
                        conv.id,
                        ConversationPatch(aiParticipant=AiParticipant(enabled=True, modelId=chars_model.id)),
                    )
                    ai_enabled_for_escalation = True

                for amb in parsed.get("ambiguous") or []:
                    if not isinstance(amb, dict):
                        continue
                    amb_name = str(amb.get("name") or "").strip() or "this character"
                    q = amb.get("question") or f"I'm unsure about '{amb_name}'. How should I treat this character?"
                    self._escalation.escalate_in(
                        book_id,
                        conversation_id=conv.id,
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
                    )

                for name in unrecognized:
                    self._escalation.escalate_in(
                        book_id,
                        conversation_id=conv.id,
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
                    )

            if changed:
                bookkeeping.updatedAt = _now()
                mgr.save_scene_bookkeeping(scene.id, bookkeeping)

        if changed:
            self._hub.emit(book_id, "scene-updated", {"id": job.sceneId, "changed": changed})

        summary_lines: list[str] = []
        if "summary" in changed:
            summary_lines.append("Updated the scene summary.")
        if "characters" in changed:
            summary_lines.append(
                f"Matched {len(matched_names)} character(s): {', '.join(matched_names)}."
                if matched_names
                else "Updated character involvement."
            )
        if summary_lines:
            self._conversations.append_system_message(book_id, conv.id, " ".join(summary_lines))

        job.result = {
            "unrecognizedNames": unrecognized,
            "modelsUsed": models_used,
        }
        job.status = JobStatus.done
        job.finishedAt = _now()
        if self._jobs is not None:
            self._jobs.update_job(book_id, job)

    @classmethod
    def _build_character_refs(
        cls, parsed: dict[str, Any], prose: str, chars: list[Any]
    ) -> list[SceneCharacterRef]:
        valid_ids = {c.id for c in chars}
        by_id: dict[str, SceneCharacterRef] = {}

        matched = parsed.get("matched") or []
        if isinstance(matched, list):
            for item in matched:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("characterId") or "").strip()
                if cid not in valid_ids:
                    continue
                involvement = str(item.get("involvement") or "").strip()
                by_id[cid] = SceneCharacterRef(characterId=cid, involvement=involvement)

        # Legacy: bare id list → empty involvement
        legacy_ids = parsed.get("matchedCharacterIds") or []
        if isinstance(legacy_ids, list):
            for cid in legacy_ids:
                if isinstance(cid, str) and cid in valid_ids and cid not in by_id:
                    by_id[cid] = SceneCharacterRef(characterId=cid, involvement="")

        for cid in cls._exact_match_ids(prose, chars):
            if cid not in by_id:
                by_id[cid] = SceneCharacterRef(characterId=cid, involvement="")

        return list(by_id.values())

    @staticmethod
    def _summary_prompt(scene: Any, prose: str) -> str:
        return "\n".join(
            [
                "You maintain scene bookkeeping for a novel.",
                'Return a single fenced JSON object: { "summary": string }.',
                "",
                f"Scene title: {scene.title}",
                f"Scene prose:\n{prose[:20000]}",
            ]
        )

    @staticmethod
    def _format_existing_scene_characters(refs: list[SceneCharacterRef], chars: list[Any]) -> str:
        if not refs:
            return "(none tagged yet)"
        by_id = {c.id: c for c in chars}
        lines: list[str] = []
        for ref in refs:
            c = by_id.get(ref.characterId)
            name = c.name if c is not None else "(unknown)"
            involvement = ref.involvement.strip() or "(empty — author tagged but left involvement blank)"
            lines.append(f"- characterId={ref.characterId} name={name} involvement={involvement}")
        return "\n".join(lines) if lines else "(none tagged yet)"

    @staticmethod
    def _characters_prompt(scene: Any, prose: str, directory: str, existing: str) -> str:
        return "\n".join(
            [
                "You maintain per-scene character involvement for a novel.",
                "Return a single fenced JSON object with keys:",
                '  "matched": [{"characterId": "id from the directory", "involvement": "one-line what they do/undergo in THIS scene"}],',
                '  "unrecognizedNames": [proper names in prose not in the directory],',
                '  "ambiguous": [{"name": "...", "candidates": ["id:...", ...], "question": "..."}]',
                "Use BOTH the existing scene_characters entries and the scene_prose.",
                "Treat existing involvement as author-reviewed draft: keep wording that still fits the prose;",
                "refine or rewrite only when prose clearly contradicts or adds detail; fill empty involvement from prose.",
                "Keep tagged characters who still appear or are clearly implied; drop only when prose no longer supports them.",
                "Add newly clear matches from prose that are not already tagged.",
                "Only exact/clear matches go in matched. When unsure, use ambiguous.",
                "involvement must be specific to this scene's prose — not a general character bio.",
                "Never invent character ids.",
                "",
                f"Character directory:\n{directory}",
                "",
                f"Existing scene_characters:\n{existing}",
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
