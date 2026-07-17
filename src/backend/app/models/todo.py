"""Todo schemas (doc 03 db/todos.json + scenes/{id}/todos.json; doc 04 §8).

Storage is split by ``parentType``: scene-parented todos live in the owning
scene's own folder (``scenes/{id}/todos.json``), matching the dependencies/
relationships split — smaller corruption blast radius, atomic per-scene
writes. Book/chapter/part-parented todos stay in the book-level
``db/todos.json``. ``TodoRecord`` is the same persisted shape either way;
only ``BookDataManager`` knows which file a given todo lives in.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import ParentType, TodoOrigin, TodoStatus


class TodoRecord(BaseModel):
    """Persisted shape, in either ``db/todos.json`` or a scene's ``todos.json``."""

    id: str
    parentType: ParentType
    parentId: str
    action: str
    status: TodoStatus = TodoStatus.open
    origin: TodoOrigin = TodoOrigin.user
    sourceDependencyId: str | None = None
    conversationId: str | None = None
    createdAt: str
    updatedAt: str


class Todo(TodoRecord):
    """API response: record + resolved ``parentTitle`` for grid display."""

    parentTitle: str = ""


class TodoCreate(BaseModel):
    """Book-level create (POST /books/{b}/todos): parentType must not be scene."""

    parentType: ParentType
    parentId: str
    action: str


class SceneTodoCreate(BaseModel):
    """Scene-scoped create (POST /scenes/{id}/todos): parent is the URL's scene id."""

    action: str


class TodoUpdate(BaseModel):
    """Partial PATCH: omitted fields unchanged. ``conversationId`` is set-once —
    the frontend sends it the first time a todo's 💬 is opened with no linked
    conversation yet (doc 04 §8); there's no way to clear it back to null."""

    status: TodoStatus | None = None
    action: str | None = None
    conversationId: str | None = None
