"""Shared enums (doc 04 §2.1). Only the settings-phase enums are defined here;
the rest are added as their build phases land.
"""

from __future__ import annotations

from enum import Enum


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"
    openai_compatible = "openai-compatible"
    ollama = "ollama"

    @property
    def requires_api_key(self) -> bool:
        return self in (Provider.anthropic, Provider.openai)

    @property
    def requires_base_url(self) -> bool:
        return self in (Provider.openai_compatible, Provider.ollama)


class OutputType(str, Enum):
    chat = "chat"
    edit_proposals = "edit-proposals"
    metadata_proposals = "metadata-proposals"
