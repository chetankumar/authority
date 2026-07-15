"""Shared enums (doc 04 §2.1). Only the settings-phase enums are defined here;
the rest are added as their build phases land.
"""

from __future__ import annotations

from enum import Enum


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    gemini = "gemini"
    openai_compatible = "openai-compatible"
    ollama = "ollama"

    @property
    def requires_api_key(self) -> bool:
        return self in (Provider.anthropic, Provider.openai, Provider.gemini)

    @property
    def requires_base_url(self) -> bool:
        return self in (Provider.openai_compatible, Provider.ollama)


class OutputType(str, Enum):
    chat = "chat"
    edit_proposals = "edit-proposals"
    metadata_proposals = "metadata-proposals"


class SceneStatus(str, Enum):
    active = "active"
    archived = "archived"


class RelationshipType(str, Enum):
    """Soft placement: *fromScene is definitely-{type} toScene* (doc 04 §2.1)."""

    before = "before"
    after = "after"
    around = "around"


class Placement(str, Enum):
    """Computed scene classification (ChainService); never stored (doc 04 §2.1)."""

    trunk = "trunk"
    unanchored = "unanchored"
    floating = "floating"
    orphan = "orphan"
    archived = "archived"
