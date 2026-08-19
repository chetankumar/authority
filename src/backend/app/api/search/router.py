"""Search API — ask/answer plus index status, rebuild, and wipe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_search_index_worker, get_search_service
from app.models.search import SearchAskRequest, SearchAskResponse, SearchIndexStatus
from app.services.search_service import SearchService
from app.worker.search_index_worker import SearchIndexWorker

router = APIRouter(prefix="/books/{book_id}/search", tags=["search"])

Search = Depends(get_search_service)
Worker = Depends(get_search_index_worker)


@router.post("", response_model=SearchAskResponse)
async def ask_search(
    book_id: str,
    body: SearchAskRequest,
    svc: SearchService = Search,
) -> SearchAskResponse:
    return await svc.ask(book_id, body.question)


@router.get("/index", response_model=SearchIndexStatus)
def get_search_index(
    book_id: str,
    svc: SearchService = Search,
    worker: SearchIndexWorker = Worker,
) -> SearchIndexStatus:
    return svc.index_status(book_id, worker.run_snapshot(book_id))


@router.post("/index/rebuild", response_model=SearchIndexStatus, status_code=202)
async def rebuild_search_index(
    book_id: str,
    svc: SearchService = Search,
    worker: SearchIndexWorker = Worker,
) -> SearchIndexStatus:
    svc.require_summary_model()
    worker.enqueue_rebuild(book_id)
    return svc.index_status(
        book_id,
        {
            "status": "running",
            "sceneId": None,
            "done": 0,
            "total": len(svc.list_indexable_scene_ids(book_id)),
            "error": None,
        },
    )


@router.delete("/index", status_code=204)
async def delete_search_index(
    book_id: str,
    worker: SearchIndexWorker = Worker,
) -> Response:
    worker.enqueue_delete(book_id)
    return Response(status_code=204)
