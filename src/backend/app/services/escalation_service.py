"""EscalationService — unclear → ask the author, in-thread (engine rule)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.event_hub import EventHub
from app.services.conversation_service import ConversationService
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.escalation")


@dataclass
class EscalationIssue:
    """Caller-built escalation. ``title`` documents intent; ``message`` is the question asked."""

    kind: str  # unmatched_name | ambiguity | minor_character | other
    message: str
    title: str = ""
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

    def escalate_in(self, book_id: str, *, conversation_id: str, issue: EscalationIssue) -> None:
        """Post an escalation question as a system message into an already-open
        conversation (the bookkeeping run that raised it), instead of spawning
        a new, disconnected chat per question."""
        opening = issue.message
        extras: list[str] = []
        if issue.context.get("excerpt"):
            extras.append(f"> {issue.context['excerpt']}")
        if issue.context.get("candidates"):
            extras.append("Candidates: " + ", ".join(str(c) for c in issue.context["candidates"]))
        if extras:
            opening = opening + "\n\n" + "\n".join(extras)
        self._conversations.append_system_message(book_id, conversation_id, opening)
        log.info("escalated %s into %s", issue.kind, conversation_id)
