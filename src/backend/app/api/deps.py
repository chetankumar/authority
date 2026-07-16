"""Shared API dependencies — service singletons."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import load_config
from app.core.event_hub import EventHub
from app.services.book_registry import BookRegistry
from app.services.book_scanner import BookScanner
from app.services.book_service import BookService
from app.services.git_service import GitService
from app.services.scene_service import SceneService
from app.services.settings_service import SettingsService
from app.services.structure_service import StructureService
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
    return SceneService(get_book_registry())


@lru_cache(maxsize=1)
def get_structure_service() -> StructureService:
    return StructureService(get_book_registry())


@lru_cache(maxsize=1)
def get_git_service() -> GitService:
    return GitService(get_book_registry(), get_settings_service(), get_event_hub())


@lru_cache(maxsize=1)
def get_git_status_worker() -> GitStatusWorker:
    return GitStatusWorker(get_git_service(), get_event_hub())
