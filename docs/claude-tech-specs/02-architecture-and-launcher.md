# 02 — Architecture & Launcher

## Process model

One Python process at runtime, **always a single Uvicorn worker** (`workers=1` — the single-writer guarantee depends on it; never scale workers). At startup the process takes an exclusive instance lock on `{appDataRoot}/.lock` via `filelock`; a second instance exits with "Authority is already running". FastAPI serves:

- `/api/*` — the JSON API (OpenAPI docs auto-exposed at `/docs`)
- everything else — the built SPA static files, with **index fallback**: any non-`/api/*`, non-asset path returns `index.html` so client-side routes survive refresh.

The frontend is a Vite-built SPA. Node is required only at install/build time, never at runtime. Same-origin, so no CORS configuration in production mode.

## Repository layout

```
authority/
  start.sh          # Mac/Linux launcher
  start.bat         # Windows launcher
  dev.sh            # development mode (Vite dev server + API, hot reload, /api proxied)
  launcher.config.json
  backend/
    requirements.txt
    app/            # FastAPI application (routers, services, data manager, worker)
  frontend/
    package.json
    src/
    dist/           # build output, served by the backend
  logs/
    api.log
```

## launcher.config.json

```json
{
  "port": 8700,
  "appDataRoot": "./data",     // where app.json lives
  "envName": "authority"        // conda/venv environment name
}
```

Created with defaults on first run if absent.

## Launcher behavior (start.sh / start.bat)

1. **Already running?** Poll `GET http://localhost:{port}/api/health`; if it answers, skip startup and just open the browser.
2. **Environment resolution:** prefer conda — if `conda` is on PATH, use/create env `{envName}`; otherwise fall back to `python -m venv .venv`. First run: create env, `pip install -r backend/requirements.txt`, verify `git` is installed (warn loudly if not), `cd frontend && npm install && npm run build`. Subsequent runs skip via a marker file (`.setup-complete` recording dependency hashes; re-run setup if requirements.txt/package.json changed).
3. **Start backend:** Uvicorn on the configured port. Logging: console **and** `logs/api.log` (two handlers; log file truncated at each launch).
4. **Readiness:** poll `/api/health` until 200 (timeout ~60s; on failure print a readable error pointing at `logs/api.log`).
5. **Open browser:** `open` / `start` / `xdg-open` → `http://localhost:{port}`.
6. **Shutdown:** Ctrl+C (or closing the terminal on Windows) traps and terminates the child process cleanly.

`dev.sh`: starts Uvicorn (API only, `--reload`) and Vite's dev server with `/api` proxied to the backend. For working on Authority itself, never for writing.

## Backend internal architecture

- **Routers** per resource area: settings, books, scenes, relationships, dependencies, structure (parts/chapters), plotlines, characters, todos, conversations, proposals, jobs, git, compile, events, health.
- **Per-book data manager:** loaded lazily on the first request naming a `bookId`; loads all `db/*.json` + `config/book.json` into memory; every mutation writes through to disk atomically (serialize → `file.json.tmp` → `os.rename`). Conversations load per-file on demand; `conversations/index.json` is derived data, rewritten on any conversation change and rebuildable by folder scan.
- **Job worker:** a single asyncio background task started at app startup; polls the in-memory job queues of loaded books (concurrency 1 per book, ≤2 global). Executes system jobs (enrichment) and user jobs (AI-Jobs). Persists status transitions to `db/jobs.json`.
- **Settle timers:** per-scene asyncio timers for enrichment coalescing (see 05).
- **SSE hub:** per-book pub/sub; any service can emit events; `GET /api/books/{id}/events` subscribes a client.
- **Git service:** thin GitPython wrapper (status, stage, unstage, diff, commit, push, pull, log). After every disk write in a book, git status is re-checked (cheap, local) and a `git-status` SSE event is emitted if the dirty-file count changed.

## Error conventions

- Validation failures → 422 with field-level messages.
- Reference-blocked deletions → **409** with structured body: `{ "blockedBy": { "chapters": [{id,title}], "scenes": [{id,title}], ... } }`.
- Not found → 404. Filesystem permission problems → 403 with the offending path.
- All error bodies: `{ "error": "human-readable", "detail": {...} }`.

## Build phases (implementation order for Claude Code)

1. **Skeleton:** launcher scripts, config, FastAPI app, health, static serving, logging.
2. **Settings:** app.json store; user/models/ai-jobs/placeholders endpoints; Settings pages.
3. **Bookshelf:** books-home scan, book creation with scaffold + git init, cover handling; Home page + modals.
4. **Scenes core:** scene CRUD, hard-chain splice/heal, soft relationships, sentinels, seq computation; graph view + table view + Add/Edit Scene modal (Basics tab).
5. **Editor:** TipTap page, autosave, content endpoint, word count/hash, prev/next navigation.
6. **Structure & metadata:** parts/chapters/plotlines/characters CRUD pages with blocked deletions; Scene Modal full tabs; dependencies + dependency-todo mechanism; Tasks page.
7. **AI layer:** LangChain factory, placeholder resolution, job worker, SSE hub, enrichment + bookkeeping toggles, conversations + streaming chat, proposals + accept/reject, AI-Jobs end to end.
8. **Git:** service + page + top-bar badge + suggest-message.
9. **Compilation:** completeness check, readiness report, compile, standing indicator.
10. **Polish:** ui.json persistence, empty states, keyboard shortcuts (Ctrl+S), fit-to-view, archived filter.
