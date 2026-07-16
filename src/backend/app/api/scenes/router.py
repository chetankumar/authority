"""Scenes router (doc 04 §5). Thin: validate via Pydantic, delegate to
SceneService. ``seq``/``placement`` are computed server-side on read.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.responses import Response

from app.api.deps import get_conversation_service, get_enrichment_service, get_scene_service
from app.models.conversation import ConversationSummary
from app.models.job import EnrichRequest
from app.models.scene import (
    ContentSaveResult,
    ContentUpdate,
    SceneCreate,
    SceneMutationResult,
    SceneUpdate,
    SceneWithContent,
    ScenesResponse,
)
from app.services.conversation_service import ConversationService
from app.services.enrichment_service import EnrichmentService
from app.services.scene_service import SceneService

router = APIRouter(prefix="/books/{book_id}/scenes", tags=["scenes"])

Service = Depends(get_scene_service)


@router.get("", response_model=ScenesResponse)
async def list_scenes(book_id: str, svc: SceneService = Service) -> ScenesResponse:
    return svc.list_scenes(book_id)


@router.post("", response_model=SceneMutationResult, status_code=201)
async def create_scene(book_id: str, body: SceneCreate, svc: SceneService = Service) -> SceneMutationResult:
    return await svc.create_scene(book_id, body)


@router.get("/{scene_id}", response_model=SceneWithContent)
async def get_scene(book_id: str, scene_id: str, svc: SceneService = Service) -> SceneWithContent:
    return svc.get_scene(book_id, scene_id)


@router.patch("/{scene_id}", response_model=SceneMutationResult)
async def update_scene(book_id: str, scene_id: str, body: SceneUpdate, svc: SceneService = Service) -> SceneMutationResult:
    return await svc.update_scene(book_id, scene_id, body)


@router.delete("/{scene_id}", status_code=204)
async def delete_scene(book_id: str, scene_id: str, svc: SceneService = Service) -> Response:
    await svc.delete_scene(book_id, scene_id)
    return Response(status_code=204)


@router.put("/{scene_id}/content", response_model=ContentSaveResult)
async def save_content(book_id: str, scene_id: str, body: ContentUpdate, svc: SceneService = Service) -> ContentSaveResult:
    return await svc.save_content(book_id, scene_id, body.content)


@router.post("/{scene_id}/enrich", status_code=202)
async def enrich_scene(
    book_id: str,
    scene_id: str,
    body: EnrichRequest,
    enrich: EnrichmentService = Depends(get_enrichment_service),
) -> dict:
    job = await enrich.enrich_on_demand(book_id, scene_id, body.scope)
    return {"jobId": job.id}


@router.get("/{scene_id}/conversations", response_model=list[ConversationSummary])
async def scene_conversations(
    book_id: str,
    scene_id: str,
    svc: ConversationService = Depends(get_conversation_service),
) -> list[ConversationSummary]:
    return svc.list_for_scene(book_id, scene_id)
