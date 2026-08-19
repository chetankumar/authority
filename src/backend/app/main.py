"""Authority FastAPI application (doc 02).

Serves ``/api/*`` (the JSON API) and everything else as the built SPA with an
index fallback so client-side routes survive a refresh. Single-origin in
production, so no CORS configuration.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from app import __version__
from app.api.audio.router import router as audio_router
from app.api.books.router import router as books_router
from app.api.characters.router import rel_router as character_relationships_router
from app.api.characters.router import router as characters_router
from app.api.conversations.router import router as conversations_router
from app.api.deps import (
    get_audio_worker,
    get_conversation_worker,
    get_git_status_worker,
    get_search_index_worker,
)
from app.api.events.router import router as events_router
from app.api.git.router import router as git_router
from app.api.health.router import router as health_router
from app.api.plotlines.router import router as plotlines_router
from app.api.proposals.router import router as proposals_router
from app.api.resources.router import router as resources_router
from app.api.relationships.router import router as relationships_router
from app.api.scenes.router import router as scenes_router
from app.api.search.router import router as search_router
from app.api.settings.router import router as settings_router
from app.api.structure.router import router as structure_router
from app.api.todos.router import router as todos_router
from app.core.config import load_config
from app.core.errors import ApiError
from app.core.logging import setup_logging

config = load_config()
setup_logging(config.log_file)
log = logging.getLogger("authority")

# Set by start.bat / start.sh so a fresh `npm run build` reloads the open tab
# without restarting the API. dev.bat uses Vite HMR instead.
_UI_LIVE_RELOAD = os.environ.get("AUTHORITY_UI_RELOAD", "").strip().lower() in {"1", "true", "yes"}

_LIVE_RELOAD_SNIPPET = """
<script>
(function () {
  var prev = null;
  function check() {
    fetch("/__authority_ui_build", { cache: "no-store" })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        if (!t || t === "0") return;
        if (prev !== null && t !== prev) location.reload();
        prev = t;
      })
      .catch(function () {});
  }
  check();
  setInterval(check, 1500);
})();
</script>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Authority %s starting on port %s", __version__, config.port)
    dist = config.frontend_dist
    if dist.exists():
        log.info("Serving SPA from %s", dist)
    else:
        log.warning("Frontend build not found at %s — run the frontend build.", dist)
    if _UI_LIVE_RELOAD:
        log.info("UI live-reload on: rebuild frontend, open tab refreshes automatically")

    import shutil

    if shutil.which("ffmpeg") is None:
        log.warning(
            "ffmpeg not found on PATH — scene audio stitching (pydub) will fail until it is installed."
        )

    # Standing background task: keeps the git badge current without ever putting
    # git on a write path (doc 02 §backend-internal-architecture, doc 07 §25).
    git_worker = asyncio.create_task(get_git_status_worker().run())
    conversation_worker = asyncio.create_task(get_conversation_worker().run())
    audio_worker = asyncio.create_task(get_audio_worker().run())
    search_worker = asyncio.create_task(get_search_index_worker().run())

    try:
        yield
    finally:
        search_worker.cancel()
        audio_worker.cancel()
        conversation_worker.cancel()
        git_worker.cancel()
        for task in (search_worker, audio_worker, conversation_worker, git_worker):
            try:
                await task
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
app.include_router(characters_router, prefix="/api")
app.include_router(character_relationships_router, prefix="/api")
app.include_router(todos_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(proposals_router, prefix="/api")
app.include_router(resources_router, prefix="/api")
app.include_router(audio_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(git_router, prefix="/api")
app.include_router(events_router, prefix="/api")

_DIST = config.frontend_dist

# Serve dist/ from disk on every request (no StaticFiles mount). That way a
# fresh `npm run build` is visible without an API restart. index.html must not
# be cached: it points at the current hashed asset names.
_NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _spa_headers(path: Path) -> dict[str, str]:
    return _IMMUTABLE if path.parent.name == "assets" else _NO_CACHE


def _index_response(index: Path) -> FileResponse | HTMLResponse:
    headers = _NO_CACHE
    if not _UI_LIVE_RELOAD:
        return FileResponse(index, headers=headers)
    html = index.read_text(encoding="utf-8")
    if "</body>" in html:
        html = html.replace("</body>", _LIVE_RELOAD_SNIPPET + "</body>", 1)
    else:
        html = html + _LIVE_RELOAD_SNIPPET
    return HTMLResponse(html, headers=headers)


@app.get("/__authority_ui_build", include_in_schema=False)
async def authority_ui_build_token():
    """mtime token for the live-reload poller injected into index.html."""
    index = _DIST / "index.html"
    try:
        return PlainTextResponse(str(index.stat().st_mtime_ns), headers=_NO_CACHE)
    except OSError:
        return PlainTextResponse("0", headers=_NO_CACHE)


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
            if candidate.name == "index.html":
                return _index_response(candidate)
            return FileResponse(candidate, headers=_spa_headers(candidate))

        index = _DIST / "index.html"
        if index.is_file():
            return _index_response(index)

    return JSONResponse(
        status_code=503,
        content={
            "error": "Frontend not built",
            "detail": {"hint": "Run `npm install && npm run build` in src/frontend."},
        },
    )
