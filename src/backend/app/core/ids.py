"""Shared ID generation (doc 03)."""

from __future__ import annotations

import secrets


def new_id(prefix: str, existing: set[str] | None = None) -> str:
    existing = existing or set()
    while True:
        candidate = f"{prefix}-{secrets.token_hex(3)}"
        if candidate not in existing:
            return candidate
