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


class TodoStatus(str, Enum):
    open = "open"
    done = "done"
    closed = "closed"


class TodoOrigin(str, Enum):
    user = "user"
    dependency = "dependency"
    ai = "ai"


class ConversationKind(str, Enum):
    note = "note"
    chat = "chat"
    ai_job = "ai-job"
    task_discussion = "task-discussion"


class ConversationStatus(str, Enum):
    open = "open"
    archived = "archived"


class MessageAuthor(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ProposalType(str, Enum):
    edit = "edit"
    metadata_update = "metadata-update"
    todo_create = "todo-create"
    character_create = "character-create"
    character_relationship_create = "character-relationship-create"


class ProposalStatus(str, Enum):
    pending = "pending"
    applied = "applied"
    rejected = "rejected"
    not_found = "not-found"


class JobType(str, Enum):
    user = "user"
    system = "system"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobScope(str, Enum):
    full = "full"
    selection = "selection"
    summary = "summary"
    characters = "characters"
    both = "both"


class ParentType(str, Enum):
    scene = "scene"
    chapter = "chapter"
    part = "part"
    book = "book"


class CharacterRelationshipCategory(str, Enum):
    """Broad category for a character-to-character relationship (doc 04 §2.1);
    the directional ``aToB``/``bToA`` free-text labels carry the actual nuance."""

    family = "family"
    romantic = "romantic"
    friendship = "friendship"
    rivalry = "rivalry"
    professional = "professional"
    mentorship = "mentorship"
    other = "other"
