"""Shared secret / API-key resolution.

Extracted so ModelFactory (LangChain providers) and AudioService / Settings
(ElevenLabs) share one ``${ENV_VAR}`` / empty→default-env rule.
"""

from __future__ import annotations

import os
import re
import sys

_ENV_RE = re.compile(r"^\$\{(\w+)\}$")


class KeyResolutionError(Exception):
    """A key reference couldn't be resolved (unset ``${VAR}`` or missing default)."""


def _environ_get(name: str) -> str | None:
    """Read ``name`` from the process env, with a Windows registry fallback.

    On Windows, System/User variables written via Settings only appear in
    *new* process trees. IDEs and terminals started before the change keep
    their old environment block, so ``os.environ`` misses Machine/User keys
    that are clearly set in the registry. Fall back to HKCU then HKLM and
    cache a hit into ``os.environ`` for the rest of the process.
    """
    value = os.environ.get(name)
    if value:
        return value

    if sys.platform != "win32":
        return None

    import winreg

    for hive, path in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ):
        try:
            with winreg.OpenKey(hive, path) as key:
                raw, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(raw, str) and raw.strip():
            os.environ[name] = raw
            return raw
    return None


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
        value = _environ_get(match.group(1))
        if not value:
            raise KeyResolutionError(f"Environment variable {match.group(1)} is not set.")
        return value

    if default_env:
        value = _environ_get(default_env)
        if not value:
            raise KeyResolutionError(f"No API key set — enter a key or set {default_env}.")
        return value
    return None
