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
  "appDataRoot": "<OS-standard per-user app-data dir>/Authority",  // where app.json lives; omit to use the OS default
  "envName": "authority"        // conda/venv environment name
}
```

Created with defaults on first run if absent. `appDataRoot` defaults to an OS-standard **per-user directory outside the repo** — `%LOCALAPPDATA%\Authority` on Windows, `~/Library/Application Support/Authority` on macOS, `$XDG_DATA_HOME/authority` (or `~/.local/share/authority`) on Linux — computed at runtime, not hardcoded in the committed file. This is deliberate: `app.json` holds the author's only settings and API keys, and must not sit somewhere a repo-wide `git clean`, `rm -rf`, or other working-tree operation could sweep it up as disposable build output. A relative path (e.g. `"./data"`) is still honored for local dev — it resolves against the repo root as before — but is opt-in, never the default.

## Launcher behavior (start.sh / start.bat)

1. **Already running?** Poll `GET http://localhost:{port}/api/health`; if it answers, skip startup and just open the browser.
2. **Environment resolution:** prefer conda — if `conda` is on PATH, use/create env `{envName}`; otherwise fall back to `python -m venv .venv`. First run: create env, `pip install -r backend/requirements.txt`, verify `git` is installed (warn loudly if not), `cd frontend && npm install && npm run build`. Subsequent runs skip via a marker file (`.setup-complete` recording dependency hashes; re-run setup if requirements.txt/package.json changed).
3. **Start backend:** Uvicorn on the configured port. Logging: console **and** `logs/api.log` (two handlers; log file truncated at each launch).
4. **Readiness:** poll `/api/health` until 200 (timeout ~60s; on failure print a readable error pointing at `logs/api.log`).
5. **Open browser:** `open` / `start` / `xdg-open` → `http://localhost:{port}`.
6. **Shutdown:** Ctrl+C (or closing the terminal on Windows) traps and terminates the child process cleanly.

`dev.sh`: starts Uvicorn (API only, `--reload`) and Vite's dev server with `/api` proxied to the backend. For working on Authority itself, never for writing.

## Backend internal architecture

- **Routers** per resource area: settings, books, scenes, relationships, dependencies, structure (parts/chapters), plotlines, characters, todos, conversations, proposals, git, compile, events, health.
- **Per-book data manager:** loaded lazily on the first request naming a `bookId`; loads all `db/*.json` + `config/book.json` into memory; every mutation writes through to disk atomically (serialize → `file.json.tmp` → `os.rename`). Conversations load per-file on demand; `conversations/index.json` is derived data, rewritten on any conversation change and rebuildable by folder scan.
- **Conversation worker:** a single asyncio background task started at app startup; drains conversations at status `queued` in loaded books (concurrency 1 per book, ≤2 global). These are automatic bookkeeping (enrichment) runs — explicit AI-Job runs never queue; they run in-request when the author sends. Running a conversation = `ConversationService.send_message`, which streams the model and sets terminal status on the conversation itself (there is no separate job record — see doc 05).
- **Git-status worker:** a second, independent asyncio background task started at app startup. Subscribes to the SSE hub's global channel and consumes the internal `book-changed` signal. Per book it holds a **pure 5s debounce** — each new `book-changed` cancels the pending timer and restarts it, so the check only runs once writes go quiet for 5s. On fire: `GitService.status(bookId)` → emit `git-status`. Deliberately off the write path (below).
- **Settle timers:** per-scene asyncio timers for enrichment coalescing (see 05).
- **SSE hub:** per-book pub/sub; any service can emit events; `GET /api/books/{id}/events` subscribes a client. A second, global subscription mode (`subscribe_all`) serves internal consumers such as the git-status worker. The hub is generic core infrastructure with no dependency on the AI layer — it exists as soon as anything needs to push.
- **Git service:** thin GitPython wrapper (status, stage, unstage, diff, commit, push, pull, log). Git is **never** run inline on a write: a disk write only fires the cheap, payload-free `book-changed` signal, and the git-status worker re-checks after its debounce. Explicit git actions (stage/unstage/commit/push/pull) are the exception — the author is waiting on the response, so they recompute status and emit `git-status` immediately, in-request, bypassing the worker entirely.

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
7. **AI layer:** LangChain factory, placeholder resolution, conversation worker, SSE hub, enrichment + bookkeeping toggles, conversations + streaming chat, proposals + accept/reject, AI-Jobs end to end.
8. **Git:** service + page + top-bar badge + suggest-message.
9. **Compilation:** completeness check, readiness report, compile, standing indicator.
10. **Polish:** ui.json persistence, empty states, keyboard shortcuts (Ctrl+S), fit-to-view, archived filter.
11. **Book resources & book-level AI chat:** (Phase 11 — shipped.)
12. **Scene Audio Drama:** ElevenLabs casting, `audio-script` AI-Job + Accept merge, Editor Audio Modal + playlist playback, book `*.mp3` gitignore. Spec: [`../audio-system.md`](../audio-system.md). (**Phase 12 — shipped.**)
