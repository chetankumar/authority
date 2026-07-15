"""Error envelope (doc 04 §1.2).

All non-2xx responses share the body ``{ "error": ..., "detail": {...} }``.
Services raise :class:`ApiError`; handlers registered in ``main`` reshape both
these and FastAPI's own validation errors into the envelope.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, detail: Any | None = None) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.detail = detail if detail is not None else {}


def not_found(kind: str, id_: str) -> ApiError:
    return ApiError(404, f"{kind.capitalize()} not found", {"kind": kind, "id": id_})


def validation(fields: dict[str, str], **extra: Any) -> ApiError:
    return ApiError(422, "Validation failed", {"fields": fields, **extra})


def blocked(blocked_by: dict[str, Any]) -> ApiError:
    return ApiError(409, "Operation blocked", {"blockedBy": blocked_by})
