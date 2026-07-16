"""Books router (doc 04 §4). Validates/normalizes multipart input, delegates to
BookScanner (shelf) and BookService (creation); holds no business logic.
"""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from pydantic import BaseModel

from app.api.deps import get_book_registry, get_book_scanner, get_book_service
from app.core.errors import not_found
from app.models.book import Book, Bookkeeping, BookSummary
from app.services.book_registry import BookRegistry
from app.services.book_scanner import BookScanner
from app.services.book_service import BookService


class BookPatch(BaseModel):
    systemPrompt: str | None = None
    storySummary: str | None = None
    bookkeeping: Bookkeeping | None = None

router = APIRouter(prefix="/books", tags=["books"])

Scanner = Depends(get_book_scanner)
Service = Depends(get_book_service)
Registry = Depends(get_book_registry)


@router.get("", response_model=list[BookSummary])
async def list_books(scanner: BookScanner = Scanner) -> list[BookSummary]:
    return scanner.list_books()


@router.post("", response_model=BookSummary, status_code=201)
async def create_book(
    title: str = Form(...),
    cover: UploadFile | None = File(None),
    svc: BookService = Service,
) -> BookSummary:
    cover_bytes = await cover.read() if cover is not None else None
    return await svc.create_book(
        title=title,
        cover_bytes=cover_bytes,
        cover_filename=cover.filename if cover is not None else None,
        cover_content_type=cover.content_type if cover is not None else None,
    )


@router.get("/{book_id}", response_model=Book)
async def get_book(book_id: str, registry: BookRegistry = Registry) -> Book:
    return registry.get(book_id).get_book()


@router.patch("/{book_id}", response_model=Book)
async def patch_book(book_id: str, body: BookPatch, registry: BookRegistry = Registry) -> Book:
    """Partial update for Book-tab fields: systemPrompt, storySummary, bookkeeping."""
    mgr = registry.get(book_id)
    async with mgr.lock:
        config = mgr.config
        if body.systemPrompt is not None:
            config.systemPrompt = body.systemPrompt
        if body.storySummary is not None:
            config.storySummary = body.storySummary
        if body.bookkeeping is not None:
            config.bookkeeping = body.bookkeeping
        mgr.save_config()
    return mgr.get_book()


@router.get("/{book_id}/cover")
async def get_cover(book_id: str, scanner: BookScanner = Scanner) -> FileResponse:
    path = scanner.cover_path(book_id)
    if path is None:
        raise not_found("cover", book_id)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/{book_id}/ui")
async def get_ui(book_id: str, registry: BookRegistry = Registry) -> dict[str, Any]:
    """Per-book UI prefs (doc 04 §4): AG Grid column state, right-pane visibility.
    Client-defined shape, returned verbatim."""
    return registry.get(book_id).get_ui()


@router.patch("/{book_id}/ui")
async def patch_ui(book_id: str, patch: dict[str, Any], registry: BookRegistry = Registry) -> dict[str, Any]:
    """Shallow-merge into ui.json; client debounces (~1s). No validation beyond
    JSON-ness — this file is the client's."""
    mgr = registry.get(book_id)
    async with mgr.lock:
        return mgr.merge_ui(patch)
