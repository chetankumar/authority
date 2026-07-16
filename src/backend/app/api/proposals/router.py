"""Proposals router (doc 04 §10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_proposal_service
from app.models.proposal import Proposal, ProposalAcceptResult
from app.services.proposal_service import ProposalService

router = APIRouter(prefix="/books/{book_id}/proposals", tags=["proposals"])

Service = Depends(get_proposal_service)


@router.post("/{proposal_id}/accept", response_model=ProposalAcceptResult)
async def accept_proposal(
    book_id: str, proposal_id: str, svc: ProposalService = Service
) -> ProposalAcceptResult:
    return await svc.accept(book_id, proposal_id)


@router.post("/{proposal_id}/reject", response_model=Proposal)
async def reject_proposal(
    book_id: str, proposal_id: str, svc: ProposalService = Service
) -> Proposal:
    return svc.reject(book_id, proposal_id)
