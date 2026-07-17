"""EnrichmentService — leave-scene + on-demand bookkeeping (doc 05).

A **creator only**. It builds the prompt, opens a `queued` bookkeeping
conversation with that prompt inside, and stops. The conversation worker sends
it; the model does the work by calling the execute tools (`set_scene_summary`,
`set_scene_characters`); `ConversationService` records the outcome. There is no
Job record and no separate escalation mechanism — a run that ends without a
tool call *is* the AI asking the author something, and the conversation lands
in `waiting` for them to answer in the thread.

Summary and character parsing stay two independent runs against two
independently-configured models, so `both` creates two conversations.
Never schedules from content autosave.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import ApiError, validation
from app.core.event_hub import EventHub
from app.models.conversation import Conversation
from app.models.enums import EnrichScope
from app.models.scene import SceneCharacterRef
from app.services.book_registry import BookRegistry
from app.services.conversation_service import ConversationService
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.enrichment")

_SUMMARY_TITLE = "Scene summarization"
_CHARACTERS_TITLE = "Character enrichment"


class EnrichmentService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        hub: EventHub,
        conversations: ConversationService,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._hub = hub
        self._conversations = conversations

    # ---- entry points ---------------------------------------------------------

    async def enrich_auto(self, book_id: str, scene_id: str) -> list[Conversation]:
        """Leave-scene path: honor the standing-consent toggles."""
        mgr = self._registry.get(book_id)
        self._require_scene(mgr, scene_id)
        bk = mgr.config.bookkeeping
        return self._create(
            book_id,
            scene_id,
            want_summary=bk.summaryOnSave,
            want_characters=bk.charactersOnSave,
        )

    async def enrich_on_demand(
        self, book_id: str, scene_id: str, scope: EnrichScope
    ) -> list[Conversation]:
        """Scene Modal ↻ AI-redo: ignore the toggles, the author asked directly."""
        mgr = self._registry.get(book_id)
        self._require_scene(mgr, scene_id)
        convs = self._create(
            book_id,
            scene_id,
            want_summary=scope in (EnrichScope.summary, EnrichScope.both),
            want_characters=scope in (EnrichScope.characters, EnrichScope.both),
        )
        if not convs:
            raise ApiError(
                422,
                "No model configured for the requested enrichment.",
                {"code": "no-utility-model"},
            )
        return convs

    # ---- creation -------------------------------------------------------------

    def _create(
        self, book_id: str, scene_id: str, *, want_summary: bool, want_characters: bool
    ) -> list[Conversation]:
        """One conversation per field in scope, each on its own configured model.
        A field whose toggle is on but has no resolvable model is skipped, not
        failed — there's nothing the author did wrong to report."""
        mgr = self._registry.get(book_id)
        scene = self._require_scene(mgr, scene_id)
        prose = mgr.read_scene_content(scene.file)
        created: list[Conversation] = []

        if want_summary:
            model = self._settings.get_scene_summary_model()
            if model is None:
                log.info("scene-summary enrichment skipped for %s — no model configured", scene_id)
            else:
                created.append(
                    self._conversations.create_bookkeeping_conversation(
                        book_id,
                        scene_id=scene_id,
                        title=_SUMMARY_TITLE,
                        model_id=model.id,
                        prompt=self._summary_prompt(scene, prose),
                    )
                )

        if want_characters:
            model = self._settings.get_character_parsing_model()
            if model is None:
                log.info("character-parsing enrichment skipped for %s — no model configured", scene_id)
            else:
                chars = list(getattr(mgr, "get_characters", lambda: [])())
                existing = self._format_existing_scene_characters(
                    mgr.get_scene_bookkeeping(scene_id).characters, chars
                )
                created.append(
                    self._conversations.create_bookkeeping_conversation(
                        book_id,
                        scene_id=scene_id,
                        title=_CHARACTERS_TITLE,
                        model_id=model.id,
                        prompt=self._characters_prompt(
                            scene, prose, self._directory(chars), existing
                        ),
                    )
                )

        return created

    # ---- prompts --------------------------------------------------------------

    @staticmethod
    def _summary_prompt(scene: Any, prose: str) -> str:
        return "\n".join(
            [
                "You maintain scene bookkeeping for a novel.",
                "Read the scene below and record a concise summary of what happens in it",
                "by calling set_scene_summary.",
                "If the scene is empty or too fragmentary to summarize, don't call the tool —",
                "say so instead and the author will pick it up.",
                "",
                f"Scene title: {scene.title}",
                f"Scene prose:\n{prose[:20000]}",
            ]
        )

    @staticmethod
    def _characters_prompt(scene: Any, prose: str, directory: str, existing: str) -> str:
        return "\n".join(
            [
                "You maintain per-scene character involvement for a novel.",
                "Work out which characters from the directory appear in this scene and what each",
                "does or undergoes in it, then record the complete list by calling",
                "set_scene_characters. The list replaces what's there, so include everyone who",
                "belongs — not just newcomers.",
                "",
                "Use BOTH the existing scene_characters entries and the scene prose.",
                "Treat existing involvement as an author-reviewed draft: keep wording that still",
                "fits the prose; refine only where the prose contradicts or adds detail; fill in",
                "empty involvement from the prose. Keep tagged characters who still appear or are",
                "clearly implied; drop one only when the prose no longer supports them.",
                "Involvement must be specific to this scene — not a general character bio.",
                "",
                "Only use ids from the directory; never invent one. If a proper name in the prose",
                "isn't in the directory, or you can't tell which character someone is, DO NOT",
                "call the tool: ask the author about it in plain language and stop. They'll answer",
                "here and you can finish then. Asking is the right move when you're unsure —",
                "a wrong tag is worse than a question.",
                "",
                f"Character directory:\n{directory}",
                "",
                f"Existing scene_characters:\n{existing}",
                "",
                f"Scene title: {scene.title}",
                f"Scene prose:\n{prose[:20000]}",
            ]
        )

    # ---- helpers --------------------------------------------------------------

    @staticmethod
    def _require_scene(mgr: Any, scene_id: str) -> Any:
        scene = next((s for s in mgr.get_scenes() if s.id == scene_id), None)
        if scene is None:
            raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})
        return scene

    @staticmethod
    def _directory(chars: list[Any]) -> str:
        lines = []
        for c in chars:
            aliases = ", ".join(getattr(c, "aliases", []) or [])
            lines.append(f"- id={c.id} name={c.name}" + (f" aliases={aliases}" if aliases else ""))
        return "\n".join(lines) if lines else "(empty — no characters defined)"

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
