"""Authority FastAPI application (doc 02).

Serves ``/api/*`` (the JSON API) and everything else as the built SPA with an
index fallback so client-side routes survive a refresh. Single-origin in
production, so no CORS configuration.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.books.router import router as books_router
from app.api.conversations.router import router as conversations_router
from app.api.deps import get_git_status_worker, get_job_worker
from app.api.events.router import router as events_router
from app.api.git.router import router as git_router
from app.api.health.router import router as health_router
from app.api.jobs.router import router as jobs_router
from app.api.plotlines.router import router as plotlines_router
from app.api.proposals.router import router as proposals_router
from app.api.relationships.router import router as relationships_router
from app.api.scenes.router import router as scenes_router
from app.api.settings.router import router as settings_router
from app.api.structure.router import router as structure_router
from app.core.config import load_config
from app.core.errors import ApiError
from app.core.logging import setup_logging

config = load_config()
setup_logging(config.log_file)
log = logging.getLogger("authority")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Authority %s starting on port %s", __version__, config.port)
    dist = config.frontend_dist
    if dist.exists():
        log.info("Serving SPA from %s", dist)
    else:
        log.warning("Frontend build not found at %s — run the frontend build.", dist)

    # Standing background task: keeps the git badge current without ever putting
    # git on a write path (doc 02 §backend-internal-architecture, doc 07 §25).
    git_worker = asyncio.create_task(get_git_status_worker().run())
    job_worker = asyncio.create_task(get_job_worker().run())

    try:
        yield
    finally:
        job_worker.cancel()
        git_worker.cancel()
        try:
            await job_worker
        except asyncio.CancelledError:
            pass
        try:
            await git_worker
        except asyncio.CancelledError:
            pass
        log.info("Authority shutting down")


app = FastAPI(title="Authority", version=__version__, lifespan=lifespan)


@app.exception_handler(ApiError)
async def _api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Reshape FastAPI's default 422 into the app's error envelope (doc 04 §1.2).
    fields = {".".join(str(p) for p in err["loc"][1:]): err["msg"] for err in exc.errors()}
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "detail": {"fields": fields}},
    )


app.include_router(health_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(books_router, prefix="/api")
app.include_router(scenes_router, prefix="/api")
app.include_router(relationships_router, prefix="/api")
app.include_router(structure_router, prefix="/api")
app.include_router(plotlines_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(proposals_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(git_router, prefix="/api")
app.include_router(events_router, prefix="/api")

_DIST = config.frontend_dist

# Built assets (hashed JS/CSS) live under dist/assets; mount them if present so
# StaticFiles can set correct content types and caching.
if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Return a real file under dist when it exists, else index.html.

    Any unmatched ``/api/*`` path is a genuine 404 (never the SPA shell).
    """
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "detail": {"path": f"/{full_path}"}},
        )

    if _DIST.exists():
        candidate = (_DIST / full_path).resolve()
        # Guard against path traversal outside dist.
        if candidate.is_file() and _DIST.resolve() in candidate.parents:
            return FileResponse(candidate)

        index = _DIST / "index.html"
        if index.is_file():
            return FileResponse(index)

    return JSONResponse(
        status_code=503,
        content={
            "error": "Frontend not built",
            "detail": {"hint": "Run `npm install && npm run build` in src/frontend."},
        },
    )
