"""Scene, soft-relationship & dependency schemas (doc 03; doc 04 2.2, 5, 6).

Persistence is split three ways per scene, by how often each part changes and
who owns it:

- ``SceneRecord`` — the master row in ``db/scenes.json``: identity, hard-chain
  (previousSceneId/nextSceneId/status), and structure (chapter/part/plotline
  links). Low-churn, author-driven, and what ChainService/the graph/the table
  need in bulk. ``status`` lives here (not with the rest of soft-metadata)
  because archive/unarchive fires chain splice/heal in the same atomic
  mutation that rewires prev/next — splitting it out would break that
  operation's one-file atomicity.
- ``SceneMeta`` — ``scenes/{id}/meta.json``: soft narrative metadata the
  author edits by hand (location/dateTime/mood/emotionalArc).
- ``SceneBookkeeping`` — ``scenes/{id}/bookkeeping.json``: AI-owned fields
  that churn on enrichment (summary + characters with per-scene involvement)
  plus content-derived stats (contentHash/wordCount).

``Scene`` (the API response) is the assembled full shape — record + meta +
bookkeeping + computed ``seq``/``placement`` — unchanged from what callers saw
before this split; only the storage layer knows the three pieces are separate.
Prose lives only in the ``.md`` file; it rides a response only for the editor
load (``SceneWithContent``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Placement, RelationshipType, SceneStatus

# Virtual sentinels (doc 03 ID scheme): recordless, valid chain endpoints.
START_ID = "scn-START"
END_ID = "scn-END"
SENTINELS = (START_ID, END_ID)


class SceneRecord(BaseModel):
    """Persisted master row in ``db/scenes.json``."""

    id: str
    title: str
    file: str
    description: str = ""
    previousSceneId: str | None = None
    nextSceneId: str | None = None
    status: SceneStatus = SceneStatus.active
    chapterId: str | None = None
    partId: str | None = None
    primaryPlotlineId: str | None = None
    secondaryPlotlineIds: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class SceneMeta(BaseModel):
    """Persisted in ``scenes/{id}/meta.json`` — soft, author-edited metadata."""

    location: str = ""
    dateTime: str = ""
    mood: str = ""
    emotionalArc: str = ""
    updatedAt: str = ""


class SceneCharacterRef(BaseModel):
    """A cast member tagged on a scene, plus what they do/undergo there."""

    characterId: str
    involvement: str = ""


class SceneBookkeeping(BaseModel):
    """Persisted in ``scenes/{id}/bookkeeping.json`` — AI-owned + content-derived."""

    summary: str = ""
    characters: list[SceneCharacterRef] = Field(default_factory=list)
    contentHash: str = ""
    wordCount: int = 0
    updatedAt: str = ""

    @model_validator(mode="before")
    @classmethod
    def _migrate_character_ids(cls, data: object) -> object:
        """Old shape stored ``characterIds: string[]``; promote to involvement rows."""
        if not isinstance(data, dict):
            return data
        if "characters" not in data and "characterIds" in data:
            ids = data.pop("characterIds") or []
            data["characters"] = [
                {"characterId": cid, "involvement": ""} for cid in ids if isinstance(cid, str)
            ]
        else:
            data.pop("characterIds", None)
        return data


class Scene(BaseModel):
    """API scene (doc 04 2.2): assembled record + meta + bookkeeping +
    computed placement/seq. Full shape preserved from before the storage
    split — this is what every caller (frontend, placeholders, proposals)
    still sees."""

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
    primaryPlotlineId: str | None = None
    secondaryPlotlineIds: list[str] = Field(default_factory=list)
    mood: str = ""
    emotionalArc: str = ""
    summary: str = ""
    characters: list[SceneCharacterRef] = Field(default_factory=list)
    status: SceneStatus = SceneStatus.active
    contentHash: str = ""
    wordCount: int = 0
    seq: int | None = None
    placement: Placement = Placement.orphan
    createdAt: str
    updatedAt: str


class SceneWithContent(Scene):
    """Editor load only (doc 04 5 GET scene): metadata + full prose."""

    content: str = ""


class SoftRelationship(BaseModel):
    """Soft edge, persisted in the *from* scene's ``scenes/{id}/relationships.json``
    (doc 03, doc 04 2.2). ``BookDataManager.get_relationships()`` still returns
    the flattened aggregate across all scenes, so this shape and every reader
    of it are unchanged."""

    id: str
    fromSceneId: str
    toSceneId: str
    type: RelationshipType
    createdAt: str


class Dependency(BaseModel):
    """Prerequisite edge, persisted in the dependent scene's
    ``scenes/{id}/dependencies.json``. Not yet exposed via CRUD API — this
    model exists so the storage layer has a real shape instead of raw dicts."""

    id: str
    sceneId: str
    dependsOnSceneId: str
    reason: str = ""
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
    primaryPlotlineId: str | None = None
    secondaryPlotlineIds: list[str] = Field(default_factory=list)
    location: str = ""
    dateTime: str = ""
    mood: str = ""
    emotionalArc: str = ""


class SceneUpdate(BaseModel):
    """Partial PATCH (doc 04 5): omitted = unchanged; explicit ``null`` clears a
    nullable field. ``model_fields_set`` distinguishes "omitted" from "sent null".
    Fields route to master/meta/bookkeeping storage per SceneService's routing
    table; this request shape stays flat regardless.
    """

    title: str | None = None
    description: str | None = None
    location: str | None = None
    dateTime: str | None = None
    mood: str | None = None
    emotionalArc: str | None = None
    summary: str | None = None
    characters: list[SceneCharacterRef] | None = None
    chapterId: str | None = None
    partId: str | None = None
    primaryPlotlineId: str | None = None
    secondaryPlotlineIds: list[str] | None = None
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
    """POST/PATCH scene (doc 04 5): the scene plus neighbors whose links changed,
    so the client patches the graph without a refetch."""

    scene: Scene
    affectedScenes: list[Scene] = Field(default_factory=list)


class ContentSaveResult(BaseModel):
    wordCount: int
    contentHash: str
    todosCreated: list[dict] = Field(default_factory=list)
