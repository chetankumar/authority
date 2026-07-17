"""AiJobService — turn a saved AI-Job definition into a ready conversation.

This is all that survives of the old JobService, and it's the only part that
was ever really about *jobs*: look up the `AIJobDefinition` the author picked,
resolve its `@placeholders` against the scene, and open a conversation with the
resolved prompt already inside. After that it is just a conversation — the
author reviews the prompt and sends, `ConversationService` runs the model.

Nothing here executes anything, and nothing here persists a run record: the
conversation is the run.
"""

from __future__ import annotations

import logging

from app.core.errors import not_found, validation
from app.models.conversation import AiJobRunRequest, Conversation
from app.models.enums import OutputType
from app.services.book_registry import BookRegistry
from app.services.conversation_service import ConversationService
from app.services.output_parsers import EDIT_FORMAT_INSTRUCTIONS, METADATA_FORMAT_INSTRUCTIONS
from app.services.placeholder_registry import PlaceholderRegistry
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.ai")


class AiJobService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        conversations: ConversationService,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._conversations = conversations

    def prepare(self, book_id: str, body: AiJobRunRequest) -> Conversation:
        """Resolve the prompt and open the conversation. Synchronous and cheap —
        no model call — so the author sees the prompt the instant the modal
        opens, and nothing runs until they send."""
        definition = self._settings.get_ai_job(body.aiJobId)
        if definition is None:
            raise not_found("ai-job", body.aiJobId)
        mgr = self._registry.get(book_id)
        if not any(s.id == body.sceneId for s in mgr.get_scenes()):
            raise not_found("scene", body.sceneId)
        if body.scope == "selection" and not (body.selectionText or "").strip():
            raise validation({"selectionText": "Selection text is required for selection scope."})

        resolved = PlaceholderRegistry.resolve(
            definition.prompt,
            mgr=mgr,
            scene_id=body.sceneId,
            selection_text=body.selectionText,
        )
        if definition.outputType == OutputType.edit_proposals:
            resolved = resolved + "\n\n" + EDIT_FORMAT_INSTRUCTIONS
        elif definition.outputType == OutputType.metadata_proposals:
            resolved = resolved + "\n\n" + METADATA_FORMAT_INSTRUCTIONS

        conv = self._conversations.create_ai_job_conversation(
            book_id,
            scene_id=body.sceneId,
            title=definition.name,
            model_id=definition.defaultModelId,
            ai_job_id=definition.id,
            ai_job_name=definition.name,
        )
        self._conversations.append_system_message(book_id, conv.id, resolved)
        return self._conversations.get(book_id, conv.id)
