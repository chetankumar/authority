"""Structure router (doc 04 §7) — parts and chapters CRUD + reorder."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from starlette.responses import Response

from app.api.deps import get_structure_service
from app.models.book import Chapter, Part
from app.services.structure_service import StructureService

router = APIRouter(prefix="/books/{book_id}", tags=["structure"])

Service = Depends(get_structure_service)


# ---- request bodies ---------------------------------------------------------

class PartCreate(BaseModel):
    title: str
    description: str = ""


class PartUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class ReorderRequest(BaseModel):
    ids: list[str]


class ChapterCreate(BaseModel):
    title: str
    description: str = ""
    partId: str | None = None


class ChapterUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    partId: str | None = None

    model_config = {"extra": "forbid"}


# ---- parts ------------------------------------------------------------------

@router.get("/parts", response_model=list[Part])
async def list_parts(book_id: str, svc: StructureService = Service) -> list[Part]:
    return await svc.list_parts(book_id)


@router.post("/parts", response_model=Part, status_code=201)
async def create_part(book_id: str, body: PartCreate, svc: StructureService = Service) -> Part:
    return await svc.create_part(book_id, body.title, body.description)


@router.patch("/parts/{part_id}", response_model=Part)
async def update_part(book_id: str, part_id: str, body: PartUpdate, svc: StructureService = Service) -> Part:
    return await svc.update_part(book_id, part_id, body.title, body.description)


@router.post("/parts/reorder", response_model=list[Part])
async def reorder_parts(book_id: str, body: ReorderRequest, svc: StructureService = Service) -> list[Part]:
    return await svc.reorder_parts(book_id, body.ids)


@router.delete("/parts/{part_id}", status_code=204)
async def delete_part(book_id: str, part_id: str, svc: StructureService = Service) -> Response:
    await svc.delete_part(book_id, part_id)
    return Response(status_code=204)


# ---- chapters ---------------------------------------------------------------

@router.get("/chapters", response_model=list[Chapter])
async def list_chapters(book_id: str, svc: StructureService = Service) -> list[Chapter]:
    return await svc.list_chapters(book_id)


@router.post("/chapters", response_model=Chapter, status_code=201)
async def create_chapter(book_id: str, body: ChapterCreate, svc: StructureService = Service) -> Chapter:
    return await svc.create_chapter(book_id, body.title, body.description, body.partId)


@router.patch("/chapters/{chp_id}", response_model=Chapter)
async def update_chapter(book_id: str, chp_id: str, body: ChapterUpdate, svc: StructureService = Service) -> Chapter:
    fields = body.model_fields_set
    kwargs: dict = {}
    if "title" in fields:
        kwargs["title"] = body.title
    if "description" in fields:
        kwargs["description"] = body.description
    if "partId" in fields:
        kwargs["part_id"] = body.partId
    return await svc.update_chapter(book_id, chp_id, **kwargs)


@router.post("/chapters/reorder", response_model=list[Chapter])
async def reorder_chapters(book_id: str, body: ReorderRequest, svc: StructureService = Service) -> list[Chapter]:
    return await svc.reorder_chapters(book_id, body.ids)


@router.delete("/chapters/{chp_id}", status_code=204)
async def delete_chapter(book_id: str, chp_id: str, svc: StructureService = Service) -> Response:
    await svc.delete_chapter(book_id, chp_id)
    return Response(status_code=204)
