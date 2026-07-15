"""Soft-relationships router (doc 04 §6). Create is idempotent (returns the
existing edge on an exact duplicate); delete is a plain removal.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_scene_service
from app.models.scene import RelationshipCreate, SoftRelationship
from app.services.scene_service import SceneService

router = APIRouter(prefix="/books/{book_id}/relationships", tags=["relationships"])

Service = Depends(get_scene_service)


@router.post("", response_model=SoftRelationship, status_code=201)
async def create_relationship(book_id: str, body: RelationshipCreate, svc: SceneService = Service) -> SoftRelationship:
    return await svc.create_relationship(book_id, body)


@router.delete("/{rel_id}", status_code=204)
async def delete_relationship(book_id: str, rel_id: str, svc: SceneService = Service) -> Response:
    await svc.delete_relationship(book_id, rel_id)
    return Response(status_code=204)
