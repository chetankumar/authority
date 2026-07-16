"""EscalationService — unclear → open a chat for the author (engine rule)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.event_hub import EventHub
from app.models.conversation import AiParticipant, ConversationCreate
from app.models.enums import ConversationKind, ParentType
from app.services.conversation_service import ConversationService
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.escalation")


@dataclass
class EscalationIssue:
    kind: str  # unmatched_name | ambiguity | minor_character | other
    message: str
    context: dict[str, Any] = field(default_factory=dict)


class EscalationService:
    def __init__(
        self,
        conversations: ConversationService,
        settings: SettingsService,
        hub: EventHub,
    ) -> None:
        self._conversations = conversations
        self._settings = settings
        self._hub = hub

    def escalate(
        self,
        book_id: str,
        *,
        parent_type: ParentType = ParentType.scene,
        parent_id: str,
        issue: EscalationIssue,
        model_id: str | None = None,
    ) -> str:
        """Create a chat seeded with the question. Returns conversation id."""
        utility = self._settings.get_utility_model()
        mid = model_id or (utility.id if utility else None)
        ai = AiParticipant(enabled=bool(mid), modelId=mid)
        title_bits = issue.message.strip().split()
        short = " ".join(title_bits[:8]) if title_bits else "Needs your input"
        conv = self._conversations.create(
            book_id,
            ConversationCreate(
                kind=ConversationKind.chat,
                parentType=parent_type,
                parentId=parent_id,
                aiParticipant=ai,
                title=short,
            ),
        )

        opening = issue.message
        extras: list[str] = []
        if issue.context.get("excerpt"):
            extras.append(f"> {issue.context['excerpt']}")
        if issue.context.get("candidates"):
            extras.append("Candidates: " + ", ".join(str(c) for c in issue.context["candidates"]))
        if extras:
            opening = opening + "\n\n" + "\n".join(extras)
        self._conversations.append_system_message(book_id, conv.id, opening)

        log.info("escalated %s on %s/%s → %s", issue.kind, parent_type.value, parent_id, conv.id)
        self._hub.emit(
            book_id,
            "job",
            {
                "id": None,
                "type": "system",
                "sceneId": parent_id if parent_type == ParentType.scene else None,
                "status": "done",
                "result": {"conversationId": conv.id, "escalation": issue.kind},
            },
        )
        return conv.id
