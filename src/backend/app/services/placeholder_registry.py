"""PlaceholderRegistry (doc 05).

Server-defined placeholder vocabulary. Single source of truth for the frontend
`@` autocomplete and for AI-Job prompt save-time validation. Token grammar:
``@[a-z0-9_]+``.
"""

from __future__ import annotations

import re

from app.models.settings import Placeholder

TOKEN_RE = re.compile(r"@[a-z0-9_]+")

# Order is display order in the autocomplete.
_REGISTRY: list[Placeholder] = [
    Placeholder(name="@current_scene", description="Full prose of the target scene"),
    Placeholder(name="@selection", description="The selected text (empty if none)"),
    Placeholder(name="@selection_or_scene", description="Selection if present, else full scene"),
    Placeholder(
        name="@scene_metadata",
        description="Title, description, location, dateTime, mood, arc, summary of the target scene",
    ),
    Placeholder(name="@scene_characters", description="Character sheets of characters tagged in the scene"),
    Placeholder(name="@character_sheet", description="All character sheets in the book"),
    Placeholder(
        name="@previous_scenes_summary",
        description="Hard prev-chain back to Start, in story order as 'Title — summary' lines",
    ),
    Placeholder(name="@all_scene_summaries", description="Every active scene's title + summary in seq order"),
    Placeholder(name="@story_summary", description="The book's story summary"),
    Placeholder(name="@plotlines", description="Plotline titles + descriptions, this scene's links flagged"),
]

_NAMES = {p.name for p in _REGISTRY}


class PlaceholderRegistry:
    @staticmethod
    def all() -> list[Placeholder]:
        return list(_REGISTRY)

    @staticmethod
    def unknown_tokens(prompt: str) -> list[str]:
        """Return distinct tokens in the prompt that are not registered, in order."""
        seen: list[str] = []
        for match in TOKEN_RE.findall(prompt):
            if match not in _NAMES and match not in seen:
                seen.append(match)
        return seen
