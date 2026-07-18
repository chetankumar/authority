# Backend — Python / FastAPI API

The single-writer API for Authority. One Python process, **always one Uvicorn worker** (`workers=1` — the single-writer guarantee depends on it; never scale workers). Serves `/api/*` (JSON + SSE) and everything else as the built SPA with index fallback.

Parent: [project root](../../CLAUDE.md). Specs: [02 Architecture](../../docs/claude-tech-specs/02-architecture-and-launcher.md), [03 Data](../../docs/claude-tech-specs/03-data-storage.md), [04 API](../../docs/claude-tech-specs/04-api-reference.md), [05 AI](../../docs/claude-tech-specs/05-ai-system.md).

## Tech stack (locked)

Python 3.11+, FastAPI + Uvicorn (single worker, pinned), GitPython (requires system `git`), LangChain (`langchain-core`, `langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-ollama`), `python-multipart`, `filelock`, `elevenlabs`, `pydub` (scene audio; system `ffmpeg` recommended for stitch). No ORM, no database engine — a per-book in-memory data manager over JSON files.

## Files to create here

- `requirements.txt` — pinned dependencies (the list above).
- `app/` — the FastAPI application package. See [app/CLAUDE.md](app/CLAUDE.md).

## Process model (doc 02)

- Startup: acquire exclusive `filelock` on `{appDataRoot}/.lock` (second instance exits "Authority is already running"); read `launcher.config.json`; load `app.json`; start the job-worker asyncio task; mount static SPA with index fallback; log to console **and** `logs/api.log` (file truncated each launch).
- `/api/*` → JSON API (OpenAPI docs at `/docs`). All other paths → `index.html` (client routes survive refresh).
- Same-origin in production, so no CORS config.

## Internal architecture

| Layer | Directory | Role |
|---|---|---|
| API routers | [`app/api/`](app/api/CLAUDE.md) | One router per resource area; validate + delegate, no logic |
| Services | [`app/services/`](app/services/CLAUDE.md) | All business logic; own the per-book mutation lock |
| Models | [`app/models/`](app/models/CLAUDE.md) | Pydantic request/response/persistence schemas + enums |
| Core | [`app/core/`](app/core/CLAUDE.md) | Config, logging, filelock, atomic write, asyncio locks, EventHub |
| Worker | [`app/worker/`](app/worker/CLAUDE.md) | Conversation worker, git-status debounce, **AudioWorker** (ElevenLabs synth queue) |

## Error conventions (doc 02 / doc 04 §1.2)

All non-2xx bodies: `{ "error": "human-readable", "detail": {...} }`. 400 malformed · 403 filesystem permission `{path}` · 404 not-found `{kind,id}` · 409 blocked `{blockedBy}` or `{errors}` · 422 validation `{fields}` · 500 `{trace_id}` (full trace to log only).
