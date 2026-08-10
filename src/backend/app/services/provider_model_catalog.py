"""Provider model-name catalogs for Settings autocomplete.

Persists to ``{appDataRoot}/provider-models-cache.json`` only — never
``app.json``. GET returns the cache; POST sync hits the provider list API and
atomically rewrites the cache file.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.atomic import atomic_write_json
from app.core.config import Config
from app.core.errors import ApiError, validation
from app.core.secrets import KeyResolutionError, resolve_secret
from app.models.enums import Provider
from app.models.settings import ProviderModelCatalog, ProviderModelInfo, ProviderModelSyncRequest
from app.services.model_factory import DEFAULT_ENV

log = logging.getLogger("authority.provider_models")

_TIMEOUT = httpx.Timeout(30.0)
_ANTHROPIC_VERSION = "2023-06-01"


def catalog_cache_key(provider: Provider, base_url: str | None) -> str:
    if provider.requires_base_url:
        normalized = (base_url or "").strip().rstrip("/")
        return f"{provider.value}|{normalized}"
    return provider.value


class ProviderModelCatalogService:
    """Read/write the disposable model catalog cache. Never touches app.json."""

    def __init__(self, config: Config) -> None:
        self._path = config.provider_models_cache
        self._lock = asyncio.Lock()

    def get(self, provider: Provider, base_url: str | None = None) -> ProviderModelCatalog:
        key = catalog_cache_key(provider, base_url)
        raw = self._load_file()
        entry = raw.get(key)
        if not isinstance(entry, dict):
            return ProviderModelCatalog()
        try:
            return ProviderModelCatalog.model_validate(entry)
        except Exception:
            return ProviderModelCatalog()

    async def sync(self, body: ProviderModelSyncRequest) -> ProviderModelCatalog:
        provider = body.provider
        base_url = (body.baseUrl or "").strip() or None

        if provider.requires_base_url:
            if not base_url:
                raise validation({"baseUrl": "This provider requires a base URL to list models."})
            parsed = urlparse(base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise validation({"baseUrl": "Base URL must be a valid http(s) URL."})

        try:
            models = await asyncio.to_thread(self._fetch, provider, base_url, body.apiKey)
        except KeyResolutionError as exc:
            raise ApiError(422, str(exc), {"code": "no-key"}) from exc
        except ApiError:
            raise
        except Exception as exc:
            log.exception("provider model sync failed for %s", provider.value)
            raise ApiError(
                502,
                f"Couldn't list models from {provider.value}: {_short(exc)}",
                {"code": "sync-failed"},
            ) from exc

        catalog = ProviderModelCatalog(
            syncedAt=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            models=models,
        )
        key = catalog_cache_key(provider, base_url)
        async with self._lock:
            raw = self._load_file()
            raw[key] = catalog.model_dump()
            atomic_write_json(self._path, raw)
        return catalog

    def _load_file(self) -> dict[str, Any]:
        path = self._path
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("provider-models-cache unreadable (%s); treating as empty", exc)
            return {}
        return data if isinstance(data, dict) else {}

    def _fetch(
        self, provider: Provider, base_url: str | None, draft_key: str | None
    ) -> list[ProviderModelInfo]:
        if provider == Provider.openrouter:
            key = self._resolve_key(provider, draft_key)
            return self._fetch_openrouter(key)
        if provider == Provider.openai:
            key = self._resolve_key(provider, draft_key)
            return self._fetch_openai(key)
        if provider == Provider.anthropic:
            key = self._resolve_key(provider, draft_key)
            return self._fetch_anthropic(key)
        if provider == Provider.gemini:
            key = self._resolve_key(provider, draft_key)
            return self._fetch_gemini(key)
        if provider == Provider.ollama:
            assert base_url
            return self._fetch_ollama(base_url)
        if provider == Provider.openai_compatible:
            assert base_url
            key = None
            text = (draft_key or "").strip()
            if text:
                key = resolve_secret(text, default_env=None)
            return self._fetch_openai_compatible(base_url, key)
        raise ApiError(422, f"Unsupported provider: {provider.value}")

    @staticmethod
    def _resolve_key(provider: Provider, draft_key: str | None) -> str:
        default_env = DEFAULT_ENV.get(provider)
        key = resolve_secret(draft_key, default_env=default_env)
        if not key:
            env = default_env or "the provider API key"
            raise KeyResolutionError(f"No API key set — enter a key or set {env}.")
        return key

    def _fetch_openrouter(self, key: str) -> list[ProviderModelInfo]:
        with httpx.Client(timeout=_TIMEOUT) as client:
            res = client.get(
                "https://openrouter.ai/api/v1/models",
                params={"output_modalities": "text"},
                headers={"Authorization": f"Bearer {key}"},
            )
            res.raise_for_status()
            data = res.json().get("data") or []
        out: list[ProviderModelInfo] = []
        for row in data:
            mid = str(row.get("id") or "").strip()
            if not mid:
                continue
            name = str(row.get("name") or mid).strip() or mid
            out.append(ProviderModelInfo(id=mid, name=name))
        return out

    def _fetch_openai(self, key: str) -> list[ProviderModelInfo]:
        with httpx.Client(timeout=_TIMEOUT) as client:
            res = client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            res.raise_for_status()
            data = res.json().get("data") or []
        out: list[ProviderModelInfo] = []
        for row in data:
            mid = str(row.get("id") or "").strip()
            if not mid:
                continue
            out.append(ProviderModelInfo(id=mid, name=mid))
        out.sort(key=lambda m: m.id)
        return out

    def _fetch_anthropic(self, key: str) -> list[ProviderModelInfo]:
        out: list[ProviderModelInfo] = []
        after: str | None = None
        with httpx.Client(timeout=_TIMEOUT) as client:
            while True:
                params: dict[str, Any] = {"limit": 100}
                if after:
                    params["after_id"] = after
                res = client.get(
                    "https://api.anthropic.com/v1/models",
                    params=params,
                    headers={
                        "x-api-key": key,
                        "anthropic-version": _ANTHROPIC_VERSION,
                    },
                )
                res.raise_for_status()
                body = res.json()
                for row in body.get("data") or []:
                    mid = str(row.get("id") or "").strip()
                    if not mid:
                        continue
                    name = str(row.get("display_name") or mid).strip() or mid
                    out.append(ProviderModelInfo(id=mid, name=name))
                if not body.get("has_more"):
                    break
                after = body.get("last_id")
                if not after:
                    break
        return out

    def _fetch_gemini(self, key: str) -> list[ProviderModelInfo]:
        with httpx.Client(timeout=_TIMEOUT) as client:
            res = client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key},
            )
            res.raise_for_status()
            data = res.json().get("models") or []
        out: list[ProviderModelInfo] = []
        for row in data:
            methods = row.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            raw_name = str(row.get("name") or "").strip()
            mid = raw_name.removeprefix("models/")
            if not mid:
                continue
            name = str(row.get("displayName") or mid).strip() or mid
            out.append(ProviderModelInfo(id=mid, name=name))
        return out

    def _fetch_ollama(self, base_url: str) -> list[ProviderModelInfo]:
        root = base_url.rstrip("/")
        with httpx.Client(timeout=_TIMEOUT) as client:
            res = client.get(f"{root}/api/tags")
            res.raise_for_status()
            data = res.json().get("models") or []
        out: list[ProviderModelInfo] = []
        for row in data:
            mid = str(row.get("name") or row.get("model") or "").strip()
            if not mid:
                continue
            out.append(ProviderModelInfo(id=mid, name=mid))
        return out

    def _fetch_openai_compatible(self, base_url: str, key: str | None) -> list[ProviderModelInfo]:
        root = base_url.rstrip("/")
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=_TIMEOUT) as client:
            res = client.get(f"{root}/models", headers=headers)
            res.raise_for_status()
            data = res.json().get("data") or []
        out: list[ProviderModelInfo] = []
        for row in data:
            mid = str(row.get("id") or "").strip()
            if not mid:
                continue
            out.append(ProviderModelInfo(id=mid, name=mid))
        return out


def _short(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:300]
