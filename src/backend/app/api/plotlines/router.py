"""Plotlines router (doc 04 §7) — plotline CRUD with computed sceneCount."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from starlette.responses import Response

from app.api.deps import get_structure_service
from app.models.plotline import Plotline
from app.services.structure_service import StructureService

router = APIRouter(prefix="/books/{book_id}/plotlines", tags=["plotlines"])

Service = Depends(get_structure_service)


class PlotlineCreate(BaseModel):
    title: str
    description: str = ""


class PlotlineUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


@router.get("", response_model=list[Plotline])
async def list_plotlines(book_id: str, svc: StructureService = Service) -> list[Plotline]:
    return await svc.list_plotlines(book_id)


@router.post("", response_model=Plotline, status_code=201)
async def create_plotline(book_id: str, body: PlotlineCreate, svc: StructureService = Service) -> Plotline:
    return await svc.create_plotline(book_id, body.title, body.description)


@router.patch("/{plt_id}", response_model=Plotline)
async def update_plotline(book_id: str, plt_id: str, body: PlotlineUpdate, svc: StructureService = Service) -> Plotline:
    return await svc.update_plotline(book_id, plt_id, body.title, body.description)


@router.delete("/{plt_id}", status_code=204)
async def delete_plotline(book_id: str, plt_id: str, svc: StructureService = Service) -> Response:
    await svc.delete_plotline(book_id, plt_id)
    return Response(status_code=204)
