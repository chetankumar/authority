"""Shared API dependencies — service singletons."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import load_config
from app.services.book_registry import BookRegistry
from app.services.book_scanner import BookScanner
from app.services.book_service import BookService
from app.services.scene_service import SceneService
from app.services.settings_service import SettingsService
from app.services.structure_service import StructureService


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    return SettingsService(load_config())


@lru_cache(maxsize=1)
def get_book_scanner() -> BookScanner:
    return BookScanner(get_settings_service())


@lru_cache(maxsize=1)
def get_book_service() -> BookService:
    return BookService(get_settings_service(), get_book_scanner())


@lru_cache(maxsize=1)
def get_book_registry() -> BookRegistry:
    return BookRegistry(get_book_scanner())


@lru_cache(maxsize=1)
def get_scene_service() -> SceneService:
    return SceneService(get_book_registry())


@lru_cache(maxsize=1)
def get_structure_service() -> StructureService:
    return StructureService(get_book_registry())
