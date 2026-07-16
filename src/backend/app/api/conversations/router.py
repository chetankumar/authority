"""Conversations + AI-Job run router (doc 04 §9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse

from app.api.deps import get_conversation_service
from app.models.conversation import (
    AiJobRunRequest,
    AiJobRunResponse,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    MessageCreate,
)
from app.services.conversation_service import ConversationService, sse_pack

router = APIRouter(prefix="/books/{book_id}", tags=["conversations"])

Service = Depends(get_conversation_service)


@router.post("/conversations", response_model=Conversation, status_code=201)
async def create_conversation(
    book_id: str, body: ConversationCreate, svc: ConversationService = Service
) -> Conversation:
    return svc.create(book_id, body)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    book_id: str, conversation_id: str, svc: ConversationService = Service
) -> Conversation:
    return svc.get(book_id, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=Conversation)
async def patch_conversation(
    book_id: str,
    conversation_id: str,
    body: ConversationPatch,
    svc: ConversationService = Service,
) -> Conversation:
    return svc.patch(book_id, conversation_id, body)


@router.delete("/conversations/{conversation_id}", status_code=204, response_class=Response)
async def delete_conversation(
    book_id: str, conversation_id: str, svc: ConversationService = Service
) -> Response:
    svc.delete(book_id, conversation_id)
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    book_id: str,
    conversation_id: str,
    body: MessageCreate,
    svc: ConversationService = Service,
) -> StreamingResponse:
    async def gen():
        async for evt in svc.send_message(book_id, conversation_id, body):
            yield sse_pack(evt["event"], evt["data"])

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/ai-jobs/run", response_model=AiJobRunResponse, status_code=202)
async def run_ai_job(
    book_id: str, body: AiJobRunRequest, svc: ConversationService = Service
) -> AiJobRunResponse:
    from app.api.deps import get_job_service

    return await get_job_service().run_ai_job(book_id, body)
