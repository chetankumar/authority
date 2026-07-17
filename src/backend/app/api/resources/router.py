"""Resources router (doc 04 §Resources). Validates/normalizes multipart input and
delegates to ResourceService; holds no business logic.
"""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_resource_service
from app.models.resource import ResourceFile
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/books/{book_id}", tags=["resources"])

Service = Depends(get_resource_service)


@router.get("/resources", response_model=list[ResourceFile])
async def list_resources(book_id: str, svc: ResourceService = Service) -> list[ResourceFile]:
    return svc.list(book_id)


@router.post("/resources", response_model=ResourceFile, status_code=201)
async def upload_resource(
    book_id: str,
    file: UploadFile = File(...),
    svc: ResourceService = Service,
) -> ResourceFile:
    return await svc.upload(book_id, file.filename or "", await file.read())


@router.get("/resources/{filename}/content")
async def get_resource_content(
    book_id: str, filename: str, svc: ResourceService = Service
) -> FileResponse:
    # Plain {filename} rather than {filename:path}: a name containing a slash
    # fails to match this route at all, which is a free traversal guard on top
    # of the service's own check.
    path = svc.path_for(book_id, filename)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/resources/{filename}", status_code=204)
async def delete_resource(book_id: str, filename: str, svc: ResourceService = Service) -> Response:
    await svc.delete(book_id, filename)
    return Response(status_code=204)
