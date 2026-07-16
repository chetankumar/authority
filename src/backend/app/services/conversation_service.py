"""ConversationService — thread primitive for notes/chat/AI-jobs (doc 04 §9)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from app.core.errors import ApiError, not_found, validation
from app.core.event_hub import EventHub
from app.core.ids import new_id
from app.models.conversation import (
    AiParticipant,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    ConversationSummary,
    Message,
    MessageCreate,
)
from app.models.enums import ConversationKind, ConversationStatus, MessageAuthor, ParentType
from app.services.ai_orchestrator import AIOrchestrator
from app.services.ai_tools import ToolRegistry
from app.services.book_registry import BookRegistry
from app.services.context_assembler import ContextAssembler, CurrentSceneRef
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.conversations")

_TITLE_TIMEOUT_SECONDS = 12.0
_TITLE_SYSTEM = (
    "You name short chat threads for a novelist. "
    "Reply with only a 3 to 5 word title that captures the author's request. "
    "No quotes, punctuation, numbering, or explanation."
)
_TITLE_USER_PREFIX = (
    "Title this writing-studio chat request in 3 to 5 words.\n"
    "Example: for 'Please give an editorial review of this scene' → Scene editorial review\n\n"
    "Request:\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_words(text: str, n: int = 5) -> str:
    words = text.strip().split()
    if not words:
        return "Untitled"
    return " ".join(words[:n])


class ConversationService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        hub: EventHub,
        orchestrator: AIOrchestrator,
        tools: ToolRegistry,
        assembler: ContextAssembler | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._hub = hub
        self._orch = orchestrator
        self._tools = tools
        self._assembler = assembler or ContextAssembler()
        # conversation_id → lock for generation-in-progress
        self._generating: set[str] = set()

    def create(self, book_id: str, body: ConversationCreate) -> Conversation:
        mgr = self._registry.get(book_id)
        existing = {s.id for s in mgr.get_conversation_index()}
        now = _now()
        ai = body.aiParticipant or AiParticipant()
        title = (body.title or "").strip() or "Untitled"
        conv = Conversation(
            id=new_id("cnv", existing),
            kind=body.kind,
            title=title,
            parentType=body.parentType,
            parentId=body.parentId,
            aiParticipant=ai,
            status=ConversationStatus.open,
            createdAt=now,
            updatedAt=now,
            messages=[],
        )
        mgr.save_conversation(conv)
        return conv

    def get(self, book_id: str, conversation_id: str) -> Conversation:
        mgr = self._registry.get(book_id)
        conv = mgr.get_conversation(conversation_id)
        if conv is None:
            raise not_found("conversation", conversation_id)
        return conv

    def list_for_scene(self, book_id: str, scene_id: str) -> list[ConversationSummary]:
        mgr = self._registry.get(book_id)
        return mgr.list_conversations_for_parent(ParentType.scene.value, scene_id)

    def patch(self, book_id: str, conversation_id: str, body: ConversationPatch) -> Conversation:
        mgr = self._registry.get(book_id)
        conv = self.get(book_id, conversation_id)
        fields = body.model_fields_set
        if "title" in fields and body.title is not None:
            conv.title = body.title.strip() or conv.title
        if "status" in fields and body.status is not None:
            conv.status = body.status
        if "aiParticipant" in fields and body.aiParticipant is not None:
            merged = conv.aiParticipant.model_copy()
            ap = body.aiParticipant
            ap_fields = ap.model_fields_set if hasattr(ap, "model_fields_set") else {"enabled", "modelId"}
            if "enabled" in ap_fields:
                merged.enabled = ap.enabled
            if "modelId" in ap_fields:
                merged.modelId = ap.modelId
            if merged.enabled and not merged.modelId:
                raise validation({"aiParticipant": "Pick a model to bring the AI in."}, code="model-required")
            if merged.modelId and self._settings.get_model(merged.modelId) is None:
                raise validation({"aiParticipant.modelId": "Unknown model."})
            conv.aiParticipant = merged
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        return conv

    def delete(self, book_id: str, conversation_id: str) -> None:
        mgr = self._registry.get(book_id)
        self.get(book_id, conversation_id)  # 404 if missing
        if conversation_id in self._generating:
            raise ApiError(409, "Generation already in progress.", {"code": "generation-in-progress"})
        mgr.delete_conversation(conversation_id)
        jobs = list(mgr.get_jobs())
        changed = False
        for job in jobs:
            if job.conversationId == conversation_id:
                job.conversationId = None
                changed = True
        if changed:
            mgr.save_jobs(jobs)

    async def send_message(
        self, book_id: str, conversation_id: str, body: MessageCreate
    ) -> AsyncIterator[dict]:
        """Yield SSE event dicts: {event, data}. AI-off → single message then done as JSON path
        is handled by the router; when AI-on this streams token/message/done/error.
        """
        if conversation_id in self._generating:
            raise ApiError(409, "Generation already in progress.", {"code": "generation-in-progress"})

        mgr = self._registry.get(book_id)
        conv = self.get(book_id, conversation_id)
        if not body.content.strip():
            raise validation({"content": "Message can't be empty."})

        now = _now()
        user_msg = Message(
            id=new_id("msg"),
            author=MessageAuthor.user,
            content=body.content.strip(),
            context=list(body.context or []),
            createdAt=now,
        )
        needs_title = conv.title == "Untitled"
        conv.messages.append(user_msg)
        conv.updatedAt = now
        mgr.save_conversation(conv)

        if needs_title:
            title = await self._semantic_title(user_msg.content)
            conv = self.get(book_id, conversation_id)
            conv.title = title
            conv.updatedAt = _now()
            mgr.save_conversation(conv)
            yield {"event": "title", "data": {"title": title}}

        yield {"event": "message", "data": {"message": user_msg.model_dump(mode="json"), "ai": False}}

        if not conv.aiParticipant.enabled:
            yield {"event": "done", "data": {"title": conv.title}}
            return

        model_id = conv.aiParticipant.modelId
        if not model_id:
            yield {"event": "error", "data": {"error": "Pick a model to bring the AI in."}}
            return

        cfg = self._settings.get_model(model_id)
        if cfg is None:
            yield {"event": "error", "data": {"error": "That model no longer exists."}}
            return

        self._generating.add(conversation_id)
        try:
            book = mgr.get_book()
            tools, acc = self._tools.bind(book_id)
            conv = self.get(book_id, conversation_id)
            current = self._current_scene_ref(mgr, conv)
            messages = self._assembler.from_conversation(
                conv, book.systemPrompt, current_scene=current, mgr=mgr
            )

            queue: asyncio.Queue[str | None] = asyncio.Queue()

            async def on_token(text: str) -> None:
                await queue.put(text)

            async def run() -> None:
                try:
                    turn = await self._orch.invoke_stream(
                        cfg, messages, tools=tools, accumulator=acc, on_token=on_token
                    )
                    await queue.put(None)
                    # Stash turn on the queue sentinel via attribute.
                    queue.turn = turn  # type: ignore[attr-defined]
                except Exception as exc:
                    queue.turn = None  # type: ignore[attr-defined]
                    queue.error = str(exc)  # type: ignore[attr-defined]
                    await queue.put(None)

            task = asyncio.create_task(run())
            while True:
                piece = await queue.get()
                if piece is None:
                    break
                yield {"event": "token", "data": {"text": piece}}

            await task
            turn = getattr(queue, "turn", None)
            err = getattr(queue, "error", None)
            if err and turn is None:
                yield {"event": "error", "data": {"error": err}}
                return
            if turn is None:
                yield {"event": "error", "data": {"error": "No response from model."}}
                return
            if turn.error and not turn.content:
                yield {"event": "error", "data": {"error": turn.error}}
                return

            assistant = Message(
                id=new_id("msg"),
                author=MessageAuthor.assistant,
                modelId=model_id,
                content=turn.content,
                proposals=turn.proposals,
                createdAt=_now(),
            )
            conv = self.get(book_id, conversation_id)
            conv.messages.append(assistant)
            conv.updatedAt = _now()
            mgr.save_conversation(conv)
            yield {"event": "message", "data": {"message": assistant.model_dump(mode="json")}}
            if turn.error:
                yield {"event": "error", "data": {"error": turn.error}}
            yield {"event": "done", "data": {"title": conv.title}}
        finally:
            self._generating.discard(conversation_id)

    async def _semantic_title(self, user_content: str) -> str:
        """Utility-model 3–5 word title; fallback to first words of the message."""
        from langchain_core.messages import HumanMessage, SystemMessage

        fallback = _first_words(user_content, n=5)
        cfg = self._settings.get_utility_model()
        if cfg is None:
            return fallback
        try:
            messages = [
                SystemMessage(content=_TITLE_SYSTEM),
                HumanMessage(content=_TITLE_USER_PREFIX + user_content[:4000]),
            ]
            raw = await self._orch.invoke_once(cfg, messages, timeout=_TITLE_TIMEOUT_SECONDS)
            title = raw.strip()
            if title:
                return title
        except Exception as exc:  # noqa: BLE001 — author still gets a title
            log.warning("semantic title fell back: %s", exc)
        return fallback

    @staticmethod
    def _current_scene_ref(mgr: Any, conv: Conversation) -> CurrentSceneRef | None:
        if conv.parentType != ParentType.scene:
            return None
        scene = next((s for s in mgr.get_scenes() if s.id == conv.parentId), None)
        title = scene.title if scene else "(unknown title)"
        return CurrentSceneRef(id=conv.parentId, title=title)

    def append_system_message(self, book_id: str, conversation_id: str, content: str) -> Message:
        mgr = self._registry.get(book_id)
        conv = self.get(book_id, conversation_id)
        msg = Message(
            id=new_id("msg"),
            author=MessageAuthor.system,
            content=content,
            createdAt=_now(),
        )
        conv.messages.append(msg)
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        return msg

    def create_ai_job_conversation(
        self,
        book_id: str,
        *,
        scene_id: str,
        title: str,
        model_id: str,
        ai_job_id: str,
        ai_job_name: str,
    ) -> Conversation:
        mgr = self._registry.get(book_id)
        existing = {s.id for s in mgr.get_conversation_index()}
        now = _now()
        conv = Conversation(
            id=new_id("cnv", existing),
            kind=ConversationKind.ai_job,
            title=title,
            parentType=ParentType.scene,
            parentId=scene_id,
            aiParticipant=AiParticipant(enabled=True, modelId=model_id),
            aiJobId=ai_job_id,
            aiJobName=ai_job_name,
            status=ConversationStatus.open,
            createdAt=now,
            updatedAt=now,
            messages=[],
        )
        mgr.save_conversation(conv)
        return conv


def sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
