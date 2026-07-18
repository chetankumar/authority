"""ModelFactory (doc 05).

Turns a :class:`ModelConfig` into a LangChain ``BaseChatModel``. Resolves
``${ENV_VAR}`` API-key references at call time (never at rest). Streaming and
tool-binding are handled by :class:`AIOrchestrator` on the built model.
LangChain adapters are imported lazily so the app starts without touching
provider SDKs.
"""

from __future__ import annotations

from typing import Any

from app.core.secrets import KeyResolutionError, resolve_secret
from app.models.enums import Provider
from app.models.settings import ModelConfig

# Re-export for callers that imported KeyResolutionError from here.
__all__ = ["KeyResolutionError", "ModelFactory", "resolve_api_key"]

# Cloud providers read these environment variables when no key is entered.
_DEFAULT_ENV: dict[Provider, str] = {
    Provider.anthropic: "ANTHROPIC_API_KEY",
    Provider.openai: "OPENAI_API_KEY",
    Provider.gemini: "GOOGLE_API_KEY",
}


def resolve_api_key(cfg: ModelConfig) -> str | None:
    """Resolve the usable key for a config.

    - A literal key passes through.
    - ``${VAR}`` reads that environment variable (error if unset).
    - **Empty** falls back to the provider's default env var (e.g.
      ``ANTHROPIC_API_KEY``); for providers that don't need a key, returns None.
    """
    return resolve_secret(cfg.apiKey, default_env=_DEFAULT_ENV.get(cfg.provider))


class ModelFactory:
    @staticmethod
    def build(cfg: ModelConfig) -> Any:
        key = resolve_api_key(cfg)

        if cfg.provider == Provider.anthropic:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=cfg.modelName, api_key=key, max_retries=0)

        if cfg.provider == Provider.openai:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=cfg.modelName, api_key=key, max_retries=0)

        if cfg.provider == Provider.gemini:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=cfg.modelName, api_key=key, max_retries=0)

        if cfg.provider == Provider.openai_compatible:
            from langchain_openai import ChatOpenAI

            # Local servers (LM Studio, etc.) often ignore the key; the SDK still
            # requires a non-empty value, so pass a placeholder when none is set.
            return ChatOpenAI(
                model=cfg.modelName,
                api_key=key or "not-needed",
                base_url=cfg.baseUrl,
                max_retries=0,
            )

        if cfg.provider == Provider.ollama:
            from langchain_ollama import ChatOllama

            return ChatOllama(model=cfg.modelName, base_url=cfg.baseUrl)

        raise ValueError(f"Unsupported provider: {cfg.provider}")
