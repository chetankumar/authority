"""ContextAssembler — build LangChain message lists for the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.conversation import Conversation, Message
from app.models.enums import MessageAuthor, ParentType

ASSISTANT_FRAMING = """
You are assisting a novelist in Authority, a local writing studio.
- You may read book data via tools.
- You never write prose or metadata directly. To suggest changes, use propose_* tools.
- The author must accept every proposal before anything is applied.
- Be concise and respect the author's voice.
""".strip()


@dataclass(frozen=True)
class CurrentSceneRef:
    """The scene the author is editing — never infer this from freshness or seq."""

    id: str
    title: str


class ContextAssembler:
    def system_messages(
        self,
        book_system_prompt: str,
        *,
        current_scene: CurrentSceneRef | None = None,
    ) -> list[Any]:
        from langchain_core.messages import SystemMessage

        parts = [ASSISTANT_FRAMING]
        if book_system_prompt.strip():
            parts.insert(0, book_system_prompt.strip())
        if current_scene is not None:
            parts.append(
                "CURRENT SCENE (author is editing this page — do not guess another):\n"
                f"- id: {current_scene.id}\n"
                f"- title: {current_scene.title}\n"
                "When the author says @current_scene, \"this scene\", or \"the current scene\", "
                f"use get_scene(\"{current_scene.id}\") or the prose already provided for that id. "
                "Do not pick a different scene based on update time, sequence, or word count."
            )
        return [SystemMessage(content="\n\n".join(parts))]

    def from_conversation(
        self,
        conv: Conversation,
        book_system_prompt: str = "",
        *,
        current_scene: CurrentSceneRef | None = None,
        mgr: Any | None = None,
    ) -> list[Any]:
        """Map persisted messages → LangChain roles; inject context excerpts.

        When ``mgr`` and ``current_scene`` are set, ``@placeholders`` in *user*
        messages are resolved for the model only — stored conversation text is unchanged.
        """
        from langchain_core.messages import AIMessage, HumanMessage

        from app.services.placeholder_registry import PlaceholderRegistry

        scene_ref = current_scene
        if scene_ref is None and conv.parentType == ParentType.scene:
            scene_ref = CurrentSceneRef(id=conv.parentId, title="(see get_scene)")

        messages: list[Any] = self.system_messages(book_system_prompt, current_scene=scene_ref)
        for msg in conv.messages:
            content = self._message_content(msg)
            if (
                msg.author == MessageAuthor.user
                and mgr is not None
                and scene_ref is not None
                and "@" in content
            ):
                selection = msg.context[0].excerpt if msg.context else None
                content = PlaceholderRegistry.resolve(
                    content,
                    mgr=mgr,
                    scene_id=scene_ref.id,
                    selection_text=selection,
                )
            if msg.author == MessageAuthor.assistant:
                messages.append(AIMessage(content=content))
            else:
                # System-authored conversation messages (job prompts, escalation
                # questions) are content the model must act on, not framing —
                # the book/framing system prompt is already injected above via
                # system_messages(). Sending them as SystemMessage instead would
                # let langchain-anthropic fold them into the top-level `system`
                # field, leaving an empty `messages` array when nothing else has
                # spoken yet (Anthropic 400: "at least one message is required").
                messages.append(HumanMessage(content=content))
        return messages

    def for_once(self, user_prompt: str, book_system_prompt: str = "") -> list[Any]:
        from langchain_core.messages import HumanMessage

        return [*self.system_messages(book_system_prompt), HumanMessage(content=user_prompt)]

    def for_structured(self, user_prompt: str, book_system_prompt: str = "") -> list[Any]:
        return self.for_once(user_prompt, book_system_prompt)

    @staticmethod
    def _message_content(msg: Message) -> str:
        parts: list[str] = []
        for ctx in msg.context:
            parts.append(f'> From scene {ctx.sceneId}:\n> {ctx.excerpt.replace(chr(10), chr(10) + "> ")}')
        if msg.content:
            parts.append(msg.content)
        return "\n\n".join(parts) if parts else ""
