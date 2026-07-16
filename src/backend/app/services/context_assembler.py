"""ContextAssembler — build LangChain message lists for the orchestrator."""

from __future__ import annotations

from typing import Any

from app.models.conversation import Conversation, Message
from app.models.enums import MessageAuthor

ASSISTANT_FRAMING = """
You are assisting a novelist in Authority, a local writing studio.
- You may read book data via tools.
- You never write prose or metadata directly. To suggest changes, use propose_* tools.
- The author must accept every proposal before anything is applied.
- Be concise and respect the author's voice.
""".strip()


class ContextAssembler:
    def system_messages(self, book_system_prompt: str) -> list[Any]:
        from langchain_core.messages import SystemMessage

        parts = [ASSISTANT_FRAMING]
        if book_system_prompt.strip():
            parts.insert(0, book_system_prompt.strip())
        return [SystemMessage(content="\n\n".join(parts))]

    def from_conversation(self, conv: Conversation, book_system_prompt: str = "") -> list[Any]:
        """Map persisted messages → LangChain roles; inject context excerpts."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages: list[Any] = self.system_messages(book_system_prompt)
        for msg in conv.messages:
            content = self._message_content(msg)
            if msg.author == MessageAuthor.system:
                messages.append(SystemMessage(content=content))
            elif msg.author == MessageAuthor.assistant:
                messages.append(AIMessage(content=content))
            else:
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
