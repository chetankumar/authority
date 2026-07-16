"""Job schemas (doc 03 db/jobs.json; doc 04 §2.2 / §11)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import JobScope, JobStatus, JobType


class JobResult(BaseModel):
    unrecognizedNames: list[str] = Field(default_factory=list)
    warning: str | None = None
    conversationId: str | None = None


class Job(BaseModel):
    id: str
    type: JobType
    aiJobId: str | None = None
    conversationId: str | None = None
    sceneId: str | None = None
    scope: JobScope
    modelId: str | None = None
    status: JobStatus = JobStatus.queued
    error: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    startedAt: str | None = None
    finishedAt: str | None = None


class EnrichRequest(BaseModel):
    scope: JobScope = JobScope.both  # summary | characters | both
