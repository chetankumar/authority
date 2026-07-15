"""Shared API dependencies — service singletons."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import load_config
from app.services.settings_service import SettingsService


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    return SettingsService(load_config())
