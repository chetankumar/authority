"""Shared API dependencies — service singletons."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import load_config
from app.core.event_hub import EventHub
from app.services.ai_orchestrator import AIOrchestrator
from app.services.ai_tools import ToolRegistry
from app.services.book_registry import BookRegistry
from app.services.book_scanner import BookScanner
from app.services.book_service import BookService
from app.services.context_assembler import ContextAssembler
from app.services.conversation_service import ConversationService
from app.services.enrichment_service import EnrichmentService
from app.services.escalation_service import EscalationService
from app.services.git_service import GitService
from app.services.job_service import JobService
from app.services.proposal_service import ProposalService
from app.services.scene_service import SceneService
from app.services.settings_service import SettingsService
from app.services.structure_service import StructureService
from app.services.todo_service import TodoService
from app.worker.git_status_worker import GitStatusWorker
from app.worker.job_worker import JobWorker


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
    return SceneService(get_book_registry(), enrichment=get_enrichment_service(), hub=get_event_hub())


@lru_cache(maxsize=1)
def get_structure_service() -> StructureService:
    return StructureService(get_book_registry())


@lru_cache(maxsize=1)
def get_todo_service() -> TodoService:
    return TodoService(get_book_registry())


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
    return ToolRegistry(get_book_registry())


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
def get_proposal_service() -> ProposalService:
    return ProposalService(
        get_book_registry(), get_scene_service(), get_event_hub(), get_structure_service(), get_todo_service()
    )


@lru_cache(maxsize=1)
def get_escalation_service() -> EscalationService:
    return EscalationService(get_conversation_service(), get_settings_service(), get_event_hub())


@lru_cache(maxsize=1)
def get_enrichment_service() -> EnrichmentService:
    svc = EnrichmentService(
        get_book_registry(),
        get_settings_service(),
        get_event_hub(),
        get_ai_orchestrator(),
        get_escalation_service(),
        get_conversation_service(),
    )
    return svc


@lru_cache(maxsize=1)
def get_job_service() -> JobService:
    jobs = JobService(
        get_book_registry(),
        get_settings_service(),
        get_conversation_service(),
        get_event_hub(),
        enrichment=get_enrichment_service(),
    )
    get_enrichment_service().set_job_service(jobs)
    return jobs


@lru_cache(maxsize=1)
def get_job_worker() -> JobWorker:
    # Ensure job service + enrichment are wired.
    return JobWorker(get_job_service(), get_book_registry())
