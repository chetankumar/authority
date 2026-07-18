"""Character & character-relationship schemas (doc 03 db/characters.json,
db/character_relationships.json; doc 04 §2.2, §7).

``CharacterRecord`` is the persisted shape in ``db/characters.json``.
``Character`` is the API response — the record plus computed ``sceneCount``
(scanned from scenes' ``characters[].characterId``, never stored).

``CharacterRelationship`` is a full row in ``db/character_relationships.json``
— there is no separate "record" type because nothing about it is computed.
Relationships are directional on both sides: ``aToB`` describes how
``characterAId`` relates to ``characterBId`` (e.g. "mother of") and ``bToA``
the reverse (e.g. "daughter of"), since most character relationships are not
symmetric.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import CharacterRelationshipCategory


class CharacterRecord(BaseModel):
    """Persisted row in ``db/characters.json``."""

    id: str
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
    voiceId: str = ""
    voiceName: str = ""
    createdAt: str
    updatedAt: str


class Character(CharacterRecord):
    """API response: record + computed sceneCount."""

    sceneCount: int = 0


class CharacterRelationship(BaseModel):
    """Row in ``db/character_relationships.json``."""

    id: str
    characterAId: str
    characterBId: str
    category: CharacterRelationshipCategory
    aToB: str
    bToA: str
    description: str = ""
    createdAt: str
    updatedAt: str


# ---- request bodies ---------------------------------------------------------


class CharacterCreate(BaseModel):
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
    voiceId: str = ""
    voiceName: str = ""


class CharacterUpdate(BaseModel):
    """Partial PATCH: omitted fields unchanged."""

    name: str | None = None
    aliases: list[str] | None = None
    age: str | None = None
    gender: str | None = None
    nationality: str | None = None
    ethnicity: str | None = None
    occupation: str | None = None
    want: str | None = None
    need: str | None = None
    flaw: str | None = None
    arc: str | None = None
    personality: str | None = None
    history: str | None = None
    notes: str | None = None
    voiceId: str | None = None
    voiceName: str | None = None


class CharacterRelationshipCreate(BaseModel):
    characterAId: str
    characterBId: str
    category: CharacterRelationshipCategory
    aToB: str
    bToA: str
    description: str = ""


class CharacterRelationshipUpdate(BaseModel):
    category: CharacterRelationshipCategory | None = None
    aToB: str | None = None
    bToA: str | None = None
    description: str | None = None
