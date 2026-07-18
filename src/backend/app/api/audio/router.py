"""Scene audio API (doc 04 §16)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse

from app.api.deps import get_audio_service, get_audio_worker, get_book_registry
from app.core.errors import ApiError
from app.models.audio import AudioLinePatch, AudioManifest, GitignoreBody
from app.models.enums import AudioSynthesisStatus
from app.services.audio_service import AudioService, read_manifest_if_exists
from app.services.book_registry import BookRegistry
from app.worker.audio_worker import AudioWorker

router = APIRouter(prefix="/books/{book_id}/scenes/{scene_id}/audio", tags=["audio"])

Audio = Depends(get_audio_service)
Worker = Depends(get_audio_worker)
Registry = Depends(get_book_registry)


@router.get("", response_model=AudioManifest)
async def get_audio(book_id: str, scene_id: str, svc: AudioService = Audio) -> AudioManifest:
    return svc.get_manifest(book_id, scene_id)


@router.patch("/lines/{item_id}", response_model=AudioManifest)
async def patch_line(
    book_id: str,
    scene_id: str,
    item_id: str,
    body: AudioLinePatch,
    svc: AudioService = Audio,
) -> AudioManifest:
    return await svc.update_line(book_id, scene_id, item_id, body)


@router.post("/lines/{item_id}/generate", response_model=AudioManifest)
async def generate_line(
    book_id: str,
    scene_id: str,
    item_id: str,
    svc: AudioService = Audio,
    worker: AudioWorker = Worker,
) -> AudioManifest:
    manifest = svc.get_manifest(book_id, scene_id)
    if not any(it.id == item_id for it in manifest.sequence):
        from app.core.errors import not_found

        raise not_found("audio-line", item_id)
    if manifest.synthesisStatus == AudioSynthesisStatus.running:
        raise ApiError(409, "Audio generation already running.", {"code": "already-running"})
    manifest.synthesisStatus = AudioSynthesisStatus.running
    manifest.lastError = None
    await svc.write_manifest_status(book_id, scene_id, manifest)
    worker.enqueue(book_id, scene_id, line_id=item_id)
    return svc.get_manifest(book_id, scene_id)


@router.post("/generate", response_model=AudioManifest)
async def generate_all(
    book_id: str,
    scene_id: str,
    svc: AudioService = Audio,
    worker: AudioWorker = Worker,
) -> AudioManifest:
    manifest = svc.get_manifest(book_id, scene_id)
    if manifest.synthesisStatus == AudioSynthesisStatus.running:
        raise ApiError(409, "Audio generation already running.", {"code": "already-running"})
    manifest.synthesisStatus = AudioSynthesisStatus.running
    manifest.lastError = None
    await svc.write_manifest_status(book_id, scene_id, manifest)
    worker.enqueue(book_id, scene_id)
    return svc.get_manifest(book_id, scene_id)


@router.get("/lines/{filename}")
async def get_line_file(
    book_id: str, scene_id: str, filename: str, svc: AudioService = Audio
) -> FileResponse:
    path = svc.path_for_line(book_id, scene_id, filename)
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.get("/stitched")
async def get_stitched(book_id: str, scene_id: str, svc: AudioService = Audio) -> FileResponse:
    path = svc.path_for_stitched(book_id, scene_id)
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.delete("", status_code=204, response_class=Response)
async def delete_audio(book_id: str, scene_id: str, svc: AudioService = Audio) -> Response:
    await svc.delete_audio(book_id, scene_id)
    return Response(status_code=204)


# Book-level gitignore lives on the books router; keep a thin helper here unused.
# (gitignore endpoints are registered on books/router.py)
