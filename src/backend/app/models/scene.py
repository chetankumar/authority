"""Scene & soft-relationship schemas (doc 03 §db/scenes.json, §db/relationships.json;
doc 04 §2.2, §5, §6).

``SceneRecord`` is the persisted shape in ``db/scenes.json``. ``Scene`` is the API
response — the record plus ``seq``/``placement``, which ChainService **computes on
read** and never stores. Prose lives only in the ``.md`` file; it rides a response
only for the editor load (``SceneWithContent``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import Placement, RelationshipType, SceneStatus

# Virtual sentinels (doc 03 §ID scheme): recordless, valid chain endpoints.
START_ID = "scn-START"
END_ID = "scn-END"
SENTINELS = (START_ID, END_ID)


class SceneRecord(BaseModel):
    """Persisted row in ``db/scenes.json``."""

    id: str
    title: str
    file: str
    description: str = ""
    location: str = ""
    dateTime: str = ""
    previousSceneId: str | None = None
    nextSceneId: str | None = None
    chapterId: str | None = None
    partId: str | None = None
    mood: str = ""
    emotionalArc: str = ""
    summary: str = ""
    characterIds: list[str] = Field(default_factory=list)
    status: SceneStatus = SceneStatus.active
    contentHash: str = ""
    wordCount: int = 0
    createdAt: str
    updatedAt: str


class Scene(SceneRecord):
    """API scene (doc 04 §2.2): record + computed placement/seq."""

    seq: int | None = None
    placement: Placement = Placement.orphan


class SceneWithContent(Scene):
    """Editor load only (doc 04 §5 GET scene): metadata + full prose."""

    content: str = ""


class SoftRelationship(BaseModel):
    """Soft edge in ``db/relationships.json`` (doc 03, doc 04 §2.2)."""

    id: str
    fromSceneId: str
    toSceneId: str
    type: RelationshipType
    createdAt: str


# ---- request bodies ---------------------------------------------------------


class SoftRelationInput(BaseModel):
    type: RelationshipType
    sceneId: str


class SceneCreate(BaseModel):
    title: str
    description: str
    previousSceneId: str | None = None
    nextSceneId: str | None = None
    softRelations: list[SoftRelationInput] = Field(default_factory=list)
    chapterId: str | None = None
    partId: str | None = None
    location: str = ""
    dateTime: str = ""
    mood: str = ""
    emotionalArc: str = ""


class SceneUpdate(BaseModel):
    """Partial PATCH (doc 04 §5): omitted = unchanged; explicit ``null`` clears a
    nullable field. ``model_fields_set`` distinguishes "omitted" from "sent null".
    """

    title: str | None = None
    description: str | None = None
    location: str | None = None
    dateTime: str | None = None
    mood: str | None = None
    emotionalArc: str | None = None
    summary: str | None = None
    characterIds: list[str] | None = None
    chapterId: str | None = None
    partId: str | None = None
    previousSceneId: str | None = None
    nextSceneId: str | None = None
    status: SceneStatus | None = None


class ContentUpdate(BaseModel):
    content: str


class RelationshipCreate(BaseModel):
    fromSceneId: str
    toSceneId: str
    type: RelationshipType


# ---- response bodies --------------------------------------------------------


class ScenesResponse(BaseModel):
    scenes: list[Scene]
    relationships: list[SoftRelationship]
    sentinels: list[str] = Field(default_factory=lambda: list(SENTINELS))


class SceneMutationResult(BaseModel):
    """POST/PATCH scene (doc 04 §5): the scene plus neighbors whose links changed,
    so the client patches the graph without a refetch."""

    scene: Scene
    affectedScenes: list[Scene] = Field(default_factory=list)


class ContentSaveResult(BaseModel):
    wordCount: int
    contentHash: str
    todosCreated: list[dict] = Field(default_factory=list)
