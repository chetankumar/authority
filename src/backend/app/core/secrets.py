"""Shared secret / API-key resolution.

Extracted so ModelFactory (LangChain providers) and AudioService / Settings
(ElevenLabs) share one ``${ENV_VAR}`` / empty→default-env rule.
"""

from __future__ import annotations

import os
import re

_ENV_RE = re.compile(r"^\$\{(\w+)\}$")


class KeyResolutionError(Exception):
    """A key reference couldn't be resolved (unset ``${VAR}`` or missing default)."""


def resolve_secret(raw: str | None, default_env: str | None = None) -> str | None:
    """Resolve a stored secret string to a usable value.

    - A literal value passes through.
    - ``${VAR}`` reads that environment variable (error if unset).
    - Empty / None falls back to ``default_env`` if provided; otherwise None.
      If ``default_env`` is set but missing in the environment, raises.
    """
    text = (raw or "").strip()
    if text:
        match = _ENV_RE.match(text)
        if not match:
            return text
        value = os.environ.get(match.group(1))
        if not value:
            raise KeyResolutionError(f"Environment variable {match.group(1)} is not set.")
        return value

    if default_env:
        value = os.environ.get(default_env)
        if not value:
            raise KeyResolutionError(f"No API key set — enter a key or set {default_env}.")
        return value
    return None
