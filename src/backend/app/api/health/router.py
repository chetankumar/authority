"""Health probe (doc 04 §3).

Launcher readiness poll and frontend disconnect detection. No services engaged.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str = "ok"
    version: str = __version__


@router.get("/health", response_model=Health)
async def get_health() -> Health:
    return Health()
