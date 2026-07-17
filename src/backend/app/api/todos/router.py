"""Todos router (doc 04 §8). Thin: validate via Pydantic, delegate to
TodoService. Book-level todos (chapter/part/book-parented) live here;
scene-parented todos are created/listed via ``/scenes/{id}/todos``
(``api/scenes/router.py``) but share this router's PATCH/DELETE-by-id, since
``TodoService`` resolves either tier from a flat id — the same shape as
``DELETE /relationships/{id}``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_todo_service
from app.core.errors import validation
from app.models.enums import ParentType
from app.models.todo import Todo, TodoCreate, TodoUpdate
from app.services.todo_service import TodoService

router = APIRouter(prefix="/books/{book_id}/todos", tags=["todos"])

Service = Depends(get_todo_service)


@router.get("", response_model=list[Todo])
async def list_todos(
    book_id: str, includeScenes: bool = Query(False), svc: TodoService = Service
) -> list[Todo]:
    if includeScenes:
        return svc.list_all_including_scenes(book_id)
    return svc.list_book_level(book_id)


@router.post("", response_model=Todo, status_code=201)
async def create_todo(book_id: str, body: TodoCreate, svc: TodoService = Service) -> Todo:
    if body.parentType == ParentType.scene:
        raise validation({"parentType": "Create scene todos via POST /scenes/{id}/todos."})
    return await svc.create(book_id, body.parentType, body.parentId, body.action)


@router.patch("/{todo_id}", response_model=Todo)
async def update_todo(book_id: str, todo_id: str, body: TodoUpdate, svc: TodoService = Service) -> Todo:
    return await svc.patch(
        book_id, todo_id, status=body.status, action=body.action, conversation_id=body.conversationId
    )


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(book_id: str, todo_id: str, svc: TodoService = Service) -> Response:
    await svc.delete(book_id, todo_id)
    return Response(status_code=204)
