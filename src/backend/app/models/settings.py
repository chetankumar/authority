"""Settings schemas (doc 04 §2.2, §3; doc 03 app.json).

Three layers per resource: the persisted shape (stored in app.json), the
request bodies (create/patch), and the response shape (secrets masked).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import OutputType, Provider

Theme = Literal["light", "dark", "system"]

# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserSettings(BaseModel):
    name: str | None = None
    booksHome: str | None = None


class UserPatch(BaseModel):
    name: str | None = None
    booksHome: str | None = None
    createBooksHome: bool = False


# ---------------------------------------------------------------------------
# Models (LLM configs)
# ---------------------------------------------------------------------------


class ModelConfig(BaseModel):
    """Persisted form (app.json) — carries the real key/reference."""

    id: str
    label: str
    provider: Provider
    modelName: str
    apiKey: str | None = None
    baseUrl: str | None = None


class ModelConfigOut(BaseModel):
    """Response form — the real key never leaves the server."""

    id: str
    label: str
    provider: Provider
    modelName: str
    apiKeyMasked: str | None = None
    baseUrl: str | None = None


class ModelTestResult(BaseModel):
    """Result of a live `hello model` check. Failures are results, not errors."""

    ok: bool
    message: str | None = None
    error: str | None = None
    latencyMs: int | None = None


class ModelCreate(BaseModel):
    label: str = Field(min_length=1)
    provider: Provider
    modelName: str = Field(min_length=1)
    apiKey: str | None = None
    baseUrl: str | None = None


class ModelPatch(BaseModel):
    label: str | None = None
    provider: Provider | None = None
    modelName: str | None = None
    # Omitted apiKey keeps the stored secret; clients round-trip the masked form
    # by simply not sending the field.
    apiKey: str | None = None
    baseUrl: str | None = None


def mask_key(key: str | None) -> str | None:
    """Return a masked hint of a stored key/reference, never the secret itself."""
    if not key:
        return None
    tail = key[-4:] if len(key) >= 4 else key
    return f"\u2026{tail}"


def to_model_out(model: ModelConfig) -> ModelConfigOut:
    return ModelConfigOut(
        id=model.id,
        label=model.label,
        provider=model.provider,
        modelName=model.modelName,
        apiKeyMasked=mask_key(model.apiKey),
        baseUrl=model.baseUrl,
    )


# ---------------------------------------------------------------------------
# Appearance (app-wide theme)
# ---------------------------------------------------------------------------


class Appearance(BaseModel):
    """App-level color theme (doc 06 §1.2). Lenient on load — an unknown or
    missing value degrades to ``system`` rather than quarantining app.json."""

    theme: str = "system"

    @field_validator("theme", mode="before")
    @classmethod
    def _coerce(cls, value: object) -> str:
        return value if value in ("light", "dark", "system") else "system"


class AppearancePatch(BaseModel):
    """Strict on input — a bad theme is a 422, not a silent coercion."""

    theme: Theme


# ---------------------------------------------------------------------------
# AI (utility model + task-specific model slots)
# ---------------------------------------------------------------------------


class AISettings(BaseModel):
    utilityModelId: str | None = None
    commitMessageModelId: str | None = None
    characterParsingModelId: str | None = None
    sceneSummaryModelId: str | None = None
    chatDefaultModelId: str | None = None


class AISettingsPatch(BaseModel):
    utilityModelId: str | None = None
    commitMessageModelId: str | None = None
    characterParsingModelId: str | None = None
    sceneSummaryModelId: str | None = None
    chatDefaultModelId: str | None = None


# ---------------------------------------------------------------------------
# AI-Jobs
# ---------------------------------------------------------------------------


class AIJobDefinition(BaseModel):
    id: str
    name: str
    prompt: str
    defaultModelId: str
    outputType: OutputType


class AIJobCreate(BaseModel):
    name: str = Field(min_length=1)
    prompt: str = ""
    defaultModelId: str
    outputType: OutputType
    force: bool = False


class AIJobPatch(BaseModel):
    name: str | None = None
    prompt: str | None = None
    defaultModelId: str | None = None
    outputType: OutputType | None = None
    force: bool = False


# ---------------------------------------------------------------------------
# Placeholders
# ---------------------------------------------------------------------------


class Placeholder(BaseModel):
    name: str
    description: str


# ---------------------------------------------------------------------------
# app.json root
# ---------------------------------------------------------------------------


class AppData(BaseModel):
    user: UserSettings = Field(default_factory=UserSettings)
    appearance: Appearance = Field(default_factory=Appearance)
    ai: AISettings = Field(default_factory=AISettings)
    models: list[ModelConfig] = Field(default_factory=list)
    aiJobs: list[AIJobDefinition] = Field(default_factory=list)
