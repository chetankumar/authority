"""TodoService (doc 04 §8) — CRUD for todos, routed to either storage tier by
``parentType``.

Book/chapter/part-parented todos persist in the book-level ``db/todos.json``;
scene-parented todos persist in the owning scene's own
``scenes/{id}/todos.json`` (doc 03) — the same corruption-blast-radius
reasoning as the existing dependencies/relationships split. This service is
the one place that knows which tier a given todo lives in; callers (the
book-level and scene-scoped routers, and ``ProposalService``'s accepted
``todo-create`` proposals — including ones the AI raises from chat via the
``propose_todo`` tool) just pass ``parentType``/``parentId``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.errors import not_found, validation
from app.core.ids import new_id
from app.models.enums import ParentType, TodoStatus
from app.models.todo import Todo, TodoRecord
from app.services.book_registry import BookRegistry


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TodoService:
    def __init__(self, registry: BookRegistry) -> None:
        self._registry = registry

    # ---- reads (no lock) -----------------------------------------------------

    def list_book_level(self, book_id: str) -> list[Todo]:
        mgr = self._registry.get(book_id)
        return [self._decorate(mgr, t) for t in mgr.get_book_todos()]

    def list_scene(self, book_id: str, scene_id: str) -> list[Todo]:
        mgr = self._registry.get(book_id)
        todos = sorted(mgr.get_scene_todos(scene_id), key=lambda t: t.createdAt, reverse=True)
        todos.sort(key=lambda t: t.status != TodoStatus.open)  # stable: open first, newest first within each
        return [self._decorate(mgr, t) for t in todos]

    def list_all_including_scenes(self, book_id: str) -> list[Todo]:
        mgr = self._registry.get(book_id)
        records = [*mgr.get_book_todos(), *mgr.get_all_scene_todos()]
        return [self._decorate(mgr, t) for t in records]

    # ---- mutations (under the book lock) --------------------------------------

    async def create(
        self,
        book_id: str,
        parent_type: ParentType,
        parent_id: str,
        action: str,
        conversation_id: str | None = None,
    ) -> Todo:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            action = action.strip()
            if not action:
                raise validation({"action": "Describe what needs to happen."})
            self._validate_parent(mgr, parent_type, parent_id)
            now = _now()
            record = TodoRecord(
                id=new_id("tdo"),
                parentType=parent_type,
                parentId=parent_id,
                action=action,
                status=TodoStatus.open,
                conversationId=conversation_id,
                createdAt=now,
                updatedAt=now,
            )
            if parent_type == ParentType.scene:
                mgr.save_scene_todos(parent_id, [*mgr.get_scene_todos(parent_id), record])
            else:
                mgr.save_book_todos([*mgr.get_book_todos(), record])
            return self._decorate(mgr, record)

    async def patch(
        self,
        book_id: str,
        todo_id: str,
        status: TodoStatus | None = None,
        action: str | None = None,
        conversation_id: str | None = None,
    ) -> Todo:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            located = mgr.find_todo(todo_id)
            if located is None:
                raise not_found("todo", todo_id)
            scene_id, record = located
            if status is not None:
                record.status = status
            if action is not None:
                action = action.strip()
                if not action:
                    raise validation({"action": "Describe what needs to happen."})
                record.action = action
            if conversation_id is not None:
                # Set-once: links the todo to the conversation the author (or
                # the AI, via an accepted todo-create proposal) is discussing
                # it in. Never cleared back to null.
                record.conversationId = conversation_id
            record.updatedAt = _now()
            self._save_one(mgr, scene_id, todo_id, record)
            return self._decorate(mgr, record)

    async def delete(self, book_id: str, todo_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            located = mgr.find_todo(todo_id)
            if located is None:
                raise not_found("todo", todo_id)
            scene_id, _record = located
            if scene_id is None:
                mgr.save_book_todos([t for t in mgr.get_book_todos() if t.id != todo_id])
            else:
                mgr.save_scene_todos(scene_id, [t for t in mgr.get_scene_todos(scene_id) if t.id != todo_id])

    # ---- helpers ---------------------------------------------------------------

    def _save_one(self, mgr, scene_id: str | None, todo_id: str, record: TodoRecord) -> None:
        if scene_id is None:
            mgr.save_book_todos([record if t.id == todo_id else t for t in mgr.get_book_todos()])
        else:
            mgr.save_scene_todos(
                scene_id, [record if t.id == todo_id else t for t in mgr.get_scene_todos(scene_id)]
            )

    def _validate_parent(self, mgr, parent_type: ParentType, parent_id: str) -> None:
        if parent_type == ParentType.scene:
            if not any(s.id == parent_id for s in mgr.get_scenes()):
                raise validation({"parentId": "Unknown scene."})
        elif parent_type == ParentType.chapter:
            if not any(c.id == parent_id for c in mgr.get_chapters()):
                raise validation({"parentId": "Unknown chapter."})
        elif parent_type == ParentType.part:
            if not any(p.id == parent_id for p in mgr.get_parts()):
                raise validation({"parentId": "Unknown part."})
        # book: exactly one per book, nothing to validate parentId against.

    def _decorate(self, mgr, record: TodoRecord) -> Todo:
        title = ""
        if record.parentType == ParentType.scene:
            title = next((s.title for s in mgr.get_scenes() if s.id == record.parentId), "")
        elif record.parentType == ParentType.chapter:
            title = next((c.title for c in mgr.get_chapters() if c.id == record.parentId), "")
        elif record.parentType == ParentType.part:
            title = next((p.title for p in mgr.get_parts() if p.id == record.parentId), "")
        elif record.parentType == ParentType.book:
            title = mgr.get_book().title
        return Todo(**record.model_dump(), parentTitle=title)
