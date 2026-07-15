"""SettingsService (doc 04 §3).

Owns ``app.json``: author identity, model configs, the utility model, and
AI-Job definitions. All writes go through the app-level asyncio lock and the
atomic-write helper. Secrets are stored verbatim (literal or ``${ENV_VAR}``)
and only ever leave the server masked.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Config
from app.core.errors import ApiError, blocked, not_found, validation
from app.models.enums import Provider
from app.models.settings import (
    AIJobCreate,
    AIJobDefinition,
    AIJobPatch,
    AISettings,
    AISettingsPatch,
    AppData,
    ModelConfig,
    ModelConfigOut,
    ModelCreate,
    ModelPatch,
    Placeholder,
    UserPatch,
    UserSettings,
    to_model_out,
)
from app.services.placeholder_registry import PlaceholderRegistry

log = logging.getLogger("authority.settings")


def _new_id(prefix: str, existing: set[str]) -> str:
    while True:
        candidate = f"{prefix}-{secrets.token_hex(3)}"
        if candidate not in existing:
            return candidate


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class SettingsService:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._path = config.app_json
        self._lock = asyncio.Lock()

    # -- persistence ---------------------------------------------------------

    def _load(self) -> AppData:
        if not self._path.exists():
            return AppData()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return AppData.model_validate(raw)
        except Exception as exc:  # corrupt-load recovery (doc 03 §Data safety)
            quarantine = self._path.with_suffix(f".corrupt-{int(time.time())}")
            self._path.replace(quarantine)
            log.error("app.json failed to load (%s); quarantined to %s", exc, quarantine)
            return AppData()

    def _save(self, data: AppData) -> None:
        from app.core.atomic import atomic_write_json

        atomic_write_json(self._path, data.model_dump())

    # -- user ----------------------------------------------------------------

    def get_user(self) -> UserSettings:
        return self._load().user

    async def patch_user(self, patch: UserPatch) -> UserSettings:
        async with self._lock:
            data = self._load()
            fields = patch.model_fields_set

            if "name" in fields:
                data.user.name = patch.name

            if "booksHome" in fields and patch.booksHome:
                resolved = self._resolve_books_home(patch.booksHome, patch.createBooksHome)
                data.user.booksHome = str(resolved)
            elif "booksHome" in fields:
                data.user.booksHome = patch.booksHome  # explicit clear

            self._save(data)
            return data.user

    def _resolve_books_home(self, raw: str, create: bool) -> Path:
        path = Path(raw).expanduser()
        if not path.exists():
            if not create:
                raise ApiError(
                    422,
                    "That folder doesn't exist yet.",
                    {"code": "path-not-found", "path": str(path)},
                )
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ApiError(403, "Couldn't create that folder.", {"path": str(path)}) from exc

        if not path.is_dir():
            raise validation({"booksHome": "That path is not a folder."})

        # Writability probe via a real tempfile.
        try:
            with tempfile.NamedTemporaryFile(dir=path, prefix=".authority-probe-", delete=True):
                pass
        except OSError as exc:
            raise ApiError(
                403,
                "That folder isn't writable — pick another location.",
                {"path": str(path)},
            ) from exc
        return path

    # -- models --------------------------------------------------------------

    def list_models(self) -> list[ModelConfigOut]:
        return [to_model_out(m) for m in self._load().models]

    def _find_model(self, data: AppData, model_id: str) -> ModelConfig:
        for m in data.models:
            if m.id == model_id:
                return m
        raise not_found("model", model_id)

    @staticmethod
    def _validate_provider(provider: Provider, api_key: str | None, base_url: str | None) -> None:
        fields: dict[str, str] = {}
        if provider.requires_api_key and not api_key:
            fields["apiKey"] = "This provider requires an API key."
        if provider.requires_base_url:
            if not base_url:
                fields["baseUrl"] = "This provider requires a base URL."
            elif not _is_http_url(base_url):
                fields["baseUrl"] = "Base URL must be a valid http(s) URL."
        if fields:
            raise validation(fields)

    async def create_model(self, body: ModelCreate) -> ModelConfigOut:
        self._validate_provider(body.provider, body.apiKey, body.baseUrl)
        async with self._lock:
            data = self._load()
            model = ModelConfig(
                id=_new_id("mdl", {m.id for m in data.models}),
                label=body.label,
                provider=body.provider,
                modelName=body.modelName,
                apiKey=body.apiKey or None,
                baseUrl=body.baseUrl or None,
            )
            data.models = [*data.models, model]
            self._save(data)
            return to_model_out(model)

    async def patch_model(self, model_id: str, patch: ModelPatch) -> ModelConfigOut:
        async with self._lock:
            data = self._load()
            existing = self._find_model(data, model_id)
            fields = patch.model_fields_set

            merged = existing.model_copy()
            if "label" in fields and patch.label is not None:
                merged.label = patch.label
            if "modelName" in fields and patch.modelName is not None:
                merged.modelName = patch.modelName
            if "provider" in fields and patch.provider is not None:
                merged.provider = patch.provider
            if "baseUrl" in fields:
                merged.baseUrl = patch.baseUrl or None
            if "apiKey" in fields:  # omitted → keep stored secret
                merged.apiKey = patch.apiKey or None

            self._validate_provider(merged.provider, merged.apiKey, merged.baseUrl)
            data.models = [merged if m.id == model_id else m for m in data.models]
            self._save(data)
            return to_model_out(merged)

    async def delete_model(self, model_id: str) -> None:
        async with self._lock:
            data = self._load()
            self._find_model(data, model_id)

            referencing_jobs = [
                {"id": j.id, "name": j.name} for j in data.aiJobs if j.defaultModelId == model_id
            ]
            utility_ref = data.ai.utilityModelId == model_id
            if referencing_jobs or utility_ref:
                raise blocked({"aiJobs": referencing_jobs, "utilityModel": utility_ref})

            data.models = [m for m in data.models if m.id != model_id]
            self._save(data)

    # -- ai (utility model) --------------------------------------------------

    def get_ai(self) -> AISettings:
        return self._load().ai

    async def patch_ai(self, patch: AISettingsPatch) -> AISettings:
        async with self._lock:
            data = self._load()
            if "utilityModelId" in patch.model_fields_set:
                model_id = patch.utilityModelId
                if model_id is not None and not any(m.id == model_id for m in data.models):
                    raise validation({"utilityModelId": "Unknown model."})
                data.ai.utilityModelId = model_id
            self._save(data)
            return data.ai

    # -- ai-jobs -------------------------------------------------------------

    def list_jobs(self) -> list[AIJobDefinition]:
        return list(self._load().aiJobs)

    def _find_job(self, data: AppData, job_id: str) -> AIJobDefinition:
        for j in data.aiJobs:
            if j.id == job_id:
                return j
        raise not_found("ai-job", job_id)

    @staticmethod
    def _validate_job(data: AppData, name: str, prompt: str, default_model_id: str, force: bool) -> None:
        fields: dict[str, str] = {}
        if not name.strip():
            fields["name"] = "Give the job a name."
        if not any(m.id == default_model_id for m in data.models):
            fields["defaultModelId"] = "Unknown model."
        if fields:
            raise validation(fields)

        if not force:
            unknown = PlaceholderRegistry.unknown_tokens(prompt)
            if unknown:
                raise ApiError(
                    422,
                    "The prompt uses placeholders that aren't in the registry.",
                    {"unknownPlaceholders": unknown},
                )

    async def create_job(self, body: AIJobCreate) -> AIJobDefinition:
        async with self._lock:
            data = self._load()
            self._validate_job(data, body.name, body.prompt, body.defaultModelId, body.force)
            job = AIJobDefinition(
                id=_new_id("aij", {j.id for j in data.aiJobs}),
                name=body.name,
                prompt=body.prompt,
                defaultModelId=body.defaultModelId,
                outputType=body.outputType,
            )
            data.aiJobs = [*data.aiJobs, job]
            self._save(data)
            return job

    async def patch_job(self, job_id: str, patch: AIJobPatch) -> AIJobDefinition:
        async with self._lock:
            data = self._load()
            existing = self._find_job(data, job_id)
            fields = patch.model_fields_set

            merged = existing.model_copy()
            if "name" in fields and patch.name is not None:
                merged.name = patch.name
            if "prompt" in fields and patch.prompt is not None:
                merged.prompt = patch.prompt
            if "defaultModelId" in fields and patch.defaultModelId is not None:
                merged.defaultModelId = patch.defaultModelId
            if "outputType" in fields and patch.outputType is not None:
                merged.outputType = patch.outputType

            self._validate_job(data, merged.name, merged.prompt, merged.defaultModelId, patch.force)
            data.aiJobs = [merged if j.id == job_id else j for j in data.aiJobs]
            self._save(data)
            return merged

    async def delete_job(self, job_id: str) -> None:
        async with self._lock:
            data = self._load()
            self._find_job(data, job_id)
            data.aiJobs = [j for j in data.aiJobs if j.id != job_id]
            self._save(data)

    # -- placeholders --------------------------------------------------------

    @staticmethod
    def placeholders() -> list[Placeholder]:
        return PlaceholderRegistry.all()
