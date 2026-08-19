"""Book search — ask/answer + derived index status (not manuscript truth)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchAskRequest(BaseModel):
    question: str


class SearchHit(BaseModel):
    sceneId: str
    title: str
    seq: int | None = None
    chunkIndex: int
    kind: str
    snippet: str
    score: float
    stale: bool = False


class SearchAskResponse(BaseModel):
    answer: str
    hits: list[SearchHit] = Field(default_factory=list)
    indexedSceneCount: int = 0


class IndexedScene(BaseModel):
    id: str
    contentHash: str = ""
    chunkCount: int = 0
    indexedAt: str = ""


class SearchIndexStatus(BaseModel):
    status: str = "idle"
    sceneId: str | None = None
    done: int = 0
    total: int = 0
    error: str | None = None
    indexedSceneCount: int = 0
    scenes: list[IndexedScene] = Field(default_factory=list)
