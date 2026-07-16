"""Jobs list router (doc 04 §11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_job_service
from app.models.enums import JobStatus, JobType
from app.models.job import Job
from app.services.job_service import JobService

router = APIRouter(prefix="/books/{book_id}/jobs", tags=["jobs"])

Service = Depends(get_job_service)


@router.get("", response_model=list[Job])
async def list_jobs(
    book_id: str,
    scene: str | None = Query(None),
    status: JobStatus | None = Query(None),
    type: JobType | None = Query(None, alias="type"),
    svc: JobService = Service,
) -> list[Job]:
    return svc.list_jobs(book_id, scene_id=scene, status=status, type_=type)
