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
from app.models.enums import ConversationKind, ConversationStatus, MessageAuthor, OutputType, ParentType
from app.services.ai_orchestrator import AIOrchestrator
from app.services.ai_tools import ToolRegistry
from app.services.book_registry import BookRegistry
from app.services.context_assembler import ContextAssembler, CurrentSceneRef
from app.services.output_parsers import parse_edit_proposals, parse_metadata_proposals
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
        self._wake: asyncio.Event | None = None  # set by ConversationWorker

    def set_wake(self, event: asyncio.Event) -> None:
        self._wake = event

    def _notify(self) -> None:
        """Nudge the worker so a queued conversation starts now rather than on
        its next idle poll."""
        if self._wake is not None:
            self._wake.set()

    def create(
        self,
        book_id: str,
        body: ConversationCreate,
        *,
        status: ConversationStatus = ConversationStatus.open,
    ) -> Conversation:
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
            status=status,
            createdAt=now,
            updatedAt=now,
            messages=[],
        )
        mgr.save_conversation(conv)
        self._emit(book_id, conv)
        return conv

    def _emit(self, book_id: str, conv: Conversation) -> None:
        """Announce a conversation's existence or lifecycle change. Replaces the
        old `job` event — the conversation is the run now, so there's one signal."""
        self._hub.emit(
            book_id,
            "conversation",
            {
                "id": conv.id,
                "kind": conv.kind.value,
                "parentType": conv.parentType.value,
                "parentId": conv.parentId,
                "status": conv.status.value,
            },
        )

    def _set_status(self, book_id: str, conv: Conversation, status: ConversationStatus) -> None:
        mgr = self._registry.get(book_id)
        conv.status = status
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        self._emit(book_id, conv)

    def get(self, book_id: str, conversation_id: str) -> Conversation:
        mgr = self._registry.get(book_id)
        conv = mgr.get_conversation(conversation_id)
        if conv is None:
            raise not_found("conversation", conversation_id)
        return conv

    def list_for_scene(self, book_id: str, scene_id: str) -> list[ConversationSummary]:
        mgr = self._registry.get(book_id)
        return mgr.list_conversations_for_parent(ParentType.scene.value, scene_id)

    def list_for_book(self, book_id: str) -> list[ConversationSummary]:
        """Threads parented to the book itself, not to any scene.

        These are the Resources page's chats: the author asking about the whole
        manuscript with no scene in context. The parent id is the book id, so
        there is exactly one such parent per book.
        """
        mgr = self._registry.get(book_id)
        return mgr.list_conversations_for_parent(ParentType.book.value, book_id)

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
        self._hub.emit(book_id, "conversation", {"id": conversation_id, "status": "deleted"})

    async def send_message(
        self, book_id: str, conversation_id: str, body: MessageCreate | None = None
    ) -> AsyncIterator[dict]:
        """Yield SSE event dicts: {event, data}. AI-off → single message then done as JSON path
        is handled by the router; when AI-on this streams token/message/done/error.

        ``body=None`` generates against the thread as it already stands, with no
        new message. That's how the worker runs a queued bookkeeping
        conversation: its prompt is already inside it, and inventing a user
        message the author never typed would put words in their mouth.
        """
        if conversation_id in self._generating:
            raise ApiError(409, "Generation already in progress.", {"code": "generation-in-progress"})

        mgr = self._registry.get(book_id)
        conv = self.get(book_id, conversation_id)
        if body is not None and not body.content.strip():
            raise validation({"content": "Message can't be empty."})

        def fail(error_text: str) -> None:
            """A run that can't proceed: record why in the thread itself, where
            the author will actually see it, and mark the conversation failed."""
            latest = self.get(book_id, conversation_id)
            latest.messages.append(
                Message(
                    id=new_id("msg"),
                    author=MessageAuthor.system,
                    content=error_text,
                    createdAt=_now(),
                )
            )
            self._set_status(book_id, latest, ConversationStatus.failed)

        if body is not None:
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

        # Only AI runs carry a lifecycle. A note or a chat just sits at `open`
        # forever — its status has nothing to say.
        is_run = conv.kind in (ConversationKind.ai_job, ConversationKind.bookkeeping)

        if not conv.aiParticipant.enabled:
            # Deliberate: the author turned the AI off. Not a failure, even on a
            # run — they've chosen to use the thread as a notepad.
            yield {"event": "done", "data": {"title": conv.title}}
            return

        model_id = conv.aiParticipant.modelId
        if not model_id:
            if is_run:
                fail("Pick a model to bring the AI in.")
            yield {"event": "error", "data": {"error": "Pick a model to bring the AI in."}}
            return

        cfg = self._settings.get_model(model_id)
        if cfg is None:
            if is_run:
                fail("That model no longer exists.")
            yield {"event": "error", "data": {"error": "That model no longer exists."}}
            return

        if is_run:
            self._set_status(book_id, conv, ConversationStatus.running)

        self._generating.add(conversation_id)
        try:
            book = mgr.get_book()
            conv = self.get(book_id, conversation_id)
            # Bookkeeping runs get the execute tools, bound to their own scene:
            # this is the one path allowed to write metadata without an author's
            # click, and only because the Bookkeeping toggles consented to it.
            bookkeeping_scene = (
                conv.parentId
                if conv.kind == ConversationKind.bookkeeping and conv.parentType == ParentType.scene
                else None
            )
            tools, acc = self._tools.bind(book_id, bookkeeping_scene_id=bookkeeping_scene)
            current = self._current_scene_ref(mgr, conv)
            messages = self._assembler.from_conversation(
                conv, book.systemPrompt, current_scene=current, mgr=mgr
            )

            queue: asyncio.Queue[str | None] = asyncio.Queue()
            tool_calls = 0

            async def on_token(text: str) -> None:
                await queue.put(text)

            async def on_tool(name: str, args: dict, result: str) -> None:
                nonlocal tool_calls
                tool_calls += 1

            async def run() -> None:
                try:
                    turn = await self._orch.invoke_stream(
                        cfg, messages, tools=tools, accumulator=acc, on_token=on_token, on_tool=on_tool
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
                if is_run:
                    fail(err)
                yield {"event": "error", "data": {"error": err}}
                return
            if turn is None:
                if is_run:
                    fail("No response from model.")
                yield {"event": "error", "data": {"error": "No response from model."}}
                return
            if turn.error and not turn.content:
                if is_run:
                    fail(turn.error)
                yield {"event": "error", "data": {"error": turn.error}}
                return

            content = turn.content
            proposals = turn.proposals
            # An AI-Job's definition decides whether its reply's trailing JSON
            # block becomes proposal cards. Keyed off the conversation now —
            # it carries aiJobId and its scene parent, so the old Job record
            # had nothing extra to offer here.
            if conv.aiJobId:
                definition = self._settings.get_ai_job(conv.aiJobId)
                scene_id = conv.parentId if conv.parentType == ParentType.scene else ""
                if definition is not None and definition.outputType == OutputType.edit_proposals:
                    display, parsed = parse_edit_proposals(content, scene_id)
                    if parsed:
                        content, proposals = display, [*parsed, *proposals]
                elif definition is not None and definition.outputType == OutputType.metadata_proposals:
                    display, parsed = parse_metadata_proposals(content, scene_id)
                    if parsed:
                        content, proposals = display, [*parsed, *proposals]

            assistant = Message(
                id=new_id("msg"),
                author=MessageAuthor.assistant,
                modelId=model_id,
                content=content,
                proposals=proposals,
                createdAt=_now(),
            )
            conv = self.get(book_id, conversation_id)
            conv.messages.append(assistant)
            conv.updatedAt = _now()
            mgr.save_conversation(conv)
            if is_run:
                # A bookkeeping run that called no tool didn't do the work — it
                # asked the author something. That absence *is* the escalation;
                # there's no separate mechanism for it any more.
                asked = conv.kind == ConversationKind.bookkeeping and tool_calls == 0
                self._set_status(
                    book_id, conv, ConversationStatus.waiting if asked else ConversationStatus.done
                )
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
        self._emit(book_id, conv)
        return conv

    def create_bookkeeping_conversation(
        self,
        book_id: str,
        *,
        scene_id: str,
        title: str,
        model_id: str,
        prompt: str,
    ) -> Conversation:
        """A queued bookkeeping run: prompt already inside, nobody watching.
        The conversation worker picks it up off `queued` and sends it."""
        mgr = self._registry.get(book_id)
        existing = {s.id for s in mgr.get_conversation_index()}
        now = _now()
        conv = Conversation(
            id=new_id("cnv", existing),
            kind=ConversationKind.bookkeeping,
            title=title,
            parentType=ParentType.scene,
            parentId=scene_id,
            aiParticipant=AiParticipant(enabled=True, modelId=model_id),
            status=ConversationStatus.queued,
            createdAt=now,
            updatedAt=now,
            messages=[
                Message(
                    id=new_id("msg"),
                    author=MessageAuthor.system,
                    content=prompt,
                    createdAt=now,
                )
            ],
        )
        mgr.save_conversation(conv)
        self._emit(book_id, conv)
        self._notify()
        return conv


def sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
