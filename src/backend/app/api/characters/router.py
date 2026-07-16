"""Characters router (doc 04 §7) — character CRUD + character relationships."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.responses import Response

from app.api.deps import get_structure_service
from app.models.character import (
    Character,
    CharacterCreate,
    CharacterRelationship,
    CharacterRelationshipCreate,
    CharacterRelationshipUpdate,
    CharacterUpdate,
)
from app.services.structure_service import StructureService

router = APIRouter(prefix="/books/{book_id}/characters", tags=["characters"])
rel_router = APIRouter(prefix="/books/{book_id}/character-relationships", tags=["character-relationships"])

Service = Depends(get_structure_service)


@router.get("", response_model=list[Character])
async def list_characters(book_id: str, svc: StructureService = Service) -> list[Character]:
    return await svc.list_characters(book_id)


@router.post("", response_model=Character, status_code=201)
async def create_character(book_id: str, body: CharacterCreate, svc: StructureService = Service) -> Character:
    return await svc.create_character(book_id, body)


@router.patch("/{chr_id}", response_model=Character)
async def update_character(
    book_id: str, chr_id: str, body: CharacterUpdate, svc: StructureService = Service
) -> Character:
    return await svc.update_character(book_id, chr_id, body)


@router.delete("/{chr_id}", status_code=204)
async def delete_character(book_id: str, chr_id: str, svc: StructureService = Service) -> Response:
    await svc.delete_character(book_id, chr_id)
    return Response(status_code=204)


@rel_router.get("", response_model=list[CharacterRelationship])
async def list_character_relationships(
    book_id: str, svc: StructureService = Service
) -> list[CharacterRelationship]:
    return await svc.list_character_relationships(book_id)


@rel_router.post("", response_model=CharacterRelationship, status_code=201)
async def create_character_relationship(
    book_id: str, body: CharacterRelationshipCreate, svc: StructureService = Service
) -> CharacterRelationship:
    return await svc.create_character_relationship(
        book_id, body.characterAId, body.characterBId, body.category, body.aToB, body.bToA, body.description
    )


@rel_router.patch("/{rel_id}", response_model=CharacterRelationship)
async def update_character_relationship(
    book_id: str, rel_id: str, body: CharacterRelationshipUpdate, svc: StructureService = Service
) -> CharacterRelationship:
    return await svc.update_character_relationship(
        book_id, rel_id, body.category, body.aToB, body.bToA, body.description
    )


@rel_router.delete("/{rel_id}", status_code=204)
async def delete_character_relationship(book_id: str, rel_id: str, svc: StructureService = Service) -> Response:
    await svc.delete_character_relationship(book_id, rel_id)
    return Response(status_code=204)
