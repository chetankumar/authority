"""Shared API dependencies — service singletons."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import load_config
from app.core.event_hub import EventHub
from app.services.ai_job_service import AiJobService
from app.services.ai_orchestrator import AIOrchestrator
from app.services.ai_tools import ToolRegistry
from app.services.audio_service import AudioService
from app.services.book_registry import BookRegistry
from app.services.book_scanner import BookScanner
from app.services.book_service import BookService
from app.services.context_assembler import ContextAssembler
from app.services.conversation_service import ConversationService
from app.services.enrichment_service import EnrichmentService
from app.services.git_service import GitService
from app.services.proposal_service import ProposalService
from app.services.resource_service import ResourceService
from app.services.scene_service import SceneService
from app.services.settings_service import SettingsService
from app.services.structure_service import StructureService
from app.services.todo_service import TodoService
from app.worker.audio_worker import AudioWorker
from app.worker.conversation_worker import ConversationWorker
from app.worker.git_status_worker import GitStatusWorker


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    return SettingsService(load_config())


@lru_cache(maxsize=1)
def get_event_hub() -> EventHub:
    return EventHub()


@lru_cache(maxsize=1)
def get_book_scanner() -> BookScanner:
    return BookScanner(get_settings_service())


@lru_cache(maxsize=1)
def get_book_service() -> BookService:
    return BookService(get_settings_service(), get_book_scanner())


@lru_cache(maxsize=1)
def get_book_registry() -> BookRegistry:
    return BookRegistry(get_book_scanner(), get_event_hub())


@lru_cache(maxsize=1)
def get_scene_service() -> SceneService:
    return SceneService(get_book_registry(), hub=get_event_hub())


@lru_cache(maxsize=1)
def get_structure_service() -> StructureService:
    return StructureService(get_book_registry())


@lru_cache(maxsize=1)
def get_todo_service() -> TodoService:
    return TodoService(get_book_registry())


@lru_cache(maxsize=1)
def get_resource_service() -> ResourceService:
    return ResourceService(get_book_registry())


@lru_cache(maxsize=1)
def get_git_service() -> GitService:
    return GitService(get_book_registry(), get_settings_service(), get_event_hub())


@lru_cache(maxsize=1)
def get_git_status_worker() -> GitStatusWorker:
    return GitStatusWorker(get_git_service(), get_event_hub())


@lru_cache(maxsize=1)
def get_ai_orchestrator() -> AIOrchestrator:
    return AIOrchestrator()


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    # Getter, not instance — see ToolRegistry.__init__ on the construction cycle.
    return ToolRegistry(get_book_registry(), get_scene_service)


@lru_cache(maxsize=1)
def get_context_assembler() -> ContextAssembler:
    return ContextAssembler()


@lru_cache(maxsize=1)
def get_conversation_service() -> ConversationService:
    return ConversationService(
        get_book_registry(),
        get_settings_service(),
        get_event_hub(),
        get_ai_orchestrator(),
        get_tool_registry(),
        get_context_assembler(),
    )


@lru_cache(maxsize=1)
def get_audio_service() -> AudioService:
    return AudioService(get_book_registry(), get_settings_service())


@lru_cache(maxsize=1)
def get_audio_worker() -> AudioWorker:
    return AudioWorker(get_audio_service(), get_event_hub())


@lru_cache(maxsize=1)
def get_proposal_service() -> ProposalService:
    return ProposalService(
        get_book_registry(),
        get_scene_service(),
        get_event_hub(),
        get_structure_service(),
        get_todo_service(),
        get_resource_service(),
        get_audio_service(),
    )


@lru_cache(maxsize=1)
def get_enrichment_service() -> EnrichmentService:
    return EnrichmentService(
        get_book_registry(),
        get_settings_service(),
        get_event_hub(),
        get_conversation_service(),
    )


@lru_cache(maxsize=1)
def get_ai_job_service() -> AiJobService:
    return AiJobService(get_book_registry(), get_settings_service(), get_conversation_service())


@lru_cache(maxsize=1)
def get_conversation_worker() -> ConversationWorker:
    return ConversationWorker(get_conversation_service(), get_book_registry())
