"""Git router (doc 04 §13) — status, staging, discard, diff, suggest-message, commit, remotes, log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_git_service
from app.models.git import (
    CommitInfo,
    CommitRequest,
    GitDiff,
    GitStatus,
    RemoteResult,
    StageRequest,
    SuggestedMessage,
)
from app.services.git_service import GitService

router = APIRouter(prefix="/books/{book_id}/git", tags=["git"])

Service = Depends(get_git_service)


@router.get("/status", response_model=GitStatus)
async def git_status(book_id: str, svc: GitService = Service) -> GitStatus:
    return await svc.status(book_id)


@router.post("/stage", response_model=GitStatus)
async def stage(book_id: str, body: StageRequest, svc: GitService = Service) -> GitStatus:
    return await svc.stage(book_id, body.paths, body.all)


@router.post("/unstage", response_model=GitStatus)
async def unstage(book_id: str, body: StageRequest, svc: GitService = Service) -> GitStatus:
    return await svc.unstage(book_id, body.paths, body.all)


@router.post("/discard", response_model=GitStatus)
async def discard(book_id: str, body: StageRequest, svc: GitService = Service) -> GitStatus:
    return await svc.discard(book_id, body.paths, body.all)


@router.get("/diff", response_model=GitDiff)
async def diff(book_id: str, path: str = Query(...), svc: GitService = Service) -> GitDiff:
    return await svc.diff(book_id, path)


@router.post("/suggest-message", response_model=SuggestedMessage)
async def suggest_message(book_id: str, svc: GitService = Service) -> SuggestedMessage:
    return await svc.suggest_message(book_id)


@router.post("/commit", response_model=CommitInfo)
async def commit(book_id: str, body: CommitRequest, svc: GitService = Service) -> CommitInfo:
    return await svc.commit(book_id, body.message)


@router.post("/push", response_model=RemoteResult)
async def push(book_id: str, svc: GitService = Service) -> RemoteResult:
    return await svc.push(book_id)


@router.post("/pull", response_model=RemoteResult)
async def pull(book_id: str, svc: GitService = Service) -> RemoteResult:
    return await svc.pull(book_id)


@router.get("/log", response_model=list[CommitInfo])
async def git_log(book_id: str, limit: int = Query(20, ge=1, le=200), svc: GitService = Service) -> list[CommitInfo]:
    return await svc.log(book_id, limit)
