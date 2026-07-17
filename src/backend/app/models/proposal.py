"""Proposal schemas (doc 03 conversations; doc 04 §2.2 / §10).

Proposals live on assistant messages. Write tools only *emit* them; the author
accepts or rejects via ProposalService — the sole mutation path for AI output
(aside from enrichment's exact-match bookkeeping writes).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CharacterRelationshipCategory, ParentType, ProposalStatus, ProposalType


class EditPayload(BaseModel):
    sceneId: str
    find: str
    replace: str
    rationale: str = ""


class MetadataUpdatePayload(BaseModel):
    targetType: str = "scene"
    targetId: str
    field: str
    oldValue: Any = None
    newValue: Any = None
    rationale: str = ""


class TodoCreatePayload(BaseModel):
    parentType: ParentType
    parentId: str
    action: str


class CharacterCreatePayload(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    age: str = ""
    gender: str = ""
    nationality: str = ""
    ethnicity: str = ""
    occupation: str = ""
    want: str = ""
    need: str = ""
    flaw: str = ""
    arc: str = ""
    personality: str = ""
    history: str = ""
    notes: str = ""
    rationale: str = ""
    # Optional: tag this scene after create.
    sceneId: str | None = None


class CharacterRelationshipCreatePayload(BaseModel):
    characterAId: str
    characterBId: str
    category: CharacterRelationshipCategory
    aToB: str
    bToA: str
    description: str = ""
    rationale: str = ""


class ResourceCreatePayload(BaseModel):
    filename: str
    content: str
    rationale: str = ""


class Proposal(BaseModel):
    id: str
    type: ProposalType
    status: ProposalStatus = ProposalStatus.pending
    resolvedAt: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ProposalAcceptResult(BaseModel):
    proposal: Proposal
    result: dict[str, Any] = Field(default_factory=dict)
