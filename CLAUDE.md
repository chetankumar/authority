# Authority — Project Root

Authority is a local, browser-based, AI-assisted **novel-writing studio**. The author writes prose in a zen markdown editor; Authority manages structure (parts, chapters, scene chain), metadata (characters, plotlines, summaries), tasks, notes-as-conversations, git version control, and AI assistance. **The AI does everything except write the book.**

This file is the always-loaded entry point for Claude Code. It maps the repository and points to the authoritative specs. Every directory below carries its own `CLAUDE.md`; read the one for the area you are working in.

## The specification is the source of truth

The complete build spec lives in [`docs/claude-tech-specs/`](docs/claude-tech-specs/README.md). Read it in this order before building: 01 → 02 → 03 → 05 → 04 → 06, then build in the phase order at the end of doc 02.

| Doc | Contents |
|---|---|
| [01 — Overview & Principles](docs/claude-tech-specs/01-overview-and-principles.md) | Vision, hard rules, write-permission model, tech stack |
| [02 — Architecture & Launcher](docs/claude-tech-specs/02-architecture-and-launcher.md) | Process model, launcher, ports, logging, repo layout, build phases |
| [03 — Data & Storage](docs/claude-tech-specs/03-data-storage.md) | Every JSON file + schema, ID scheme, atomic writes, data safety |
| [04 — API Reference](docs/claude-tech-specs/04-api-reference.md) | Every endpoint: request, response, behavior, errors |
| [05 — AI System](docs/claude-tech-specs/05-ai-system.md) | LangChain, models, placeholders, AI-Jobs, enrichment, proposals, worker, SSE |
| [06 — Frontend Pages](docs/claude-tech-specs/06-frontend-pages.md) | Design system, every page and modal, control behaviors |
| [07 — Decisions & Deferred](docs/claude-tech-specs/07-decisions-and-deferred.md) | Closed decisions, chosen defaults, deferred scope, glossary |

## Non-negotiable hard rules (see doc 01)

1. **Prose is sacred.** No AI code path may write to a scene `.md` file. Prose changes only via (a) the author typing (autosave) or (b) the author applying an edit proposal. AI emits find/replace *proposals* only.
2. **JSON files are the only persistence.** No SQLite, Redis, or external DB. All writes are atomic (temp file + fsync + `os.replace`).
3. **Single writer.** Only the Python API touches disk. The frontend never does. Exactly one Uvicorn worker (`workers=1`).
4. **Portability.** Each book is a self-contained folder and a git repository. No book data is ever stored at app level (API keys live only in app-level `app.json`).
5. **Local, single-user, no auth.** The API binds to localhost, single port (default 8700).

## Repository map

```
CLAUDE.md            # this file — project entry point
.gitignore           # ignores logs/, runtime data/, build artifacts, caches
logs/                # runtime logs (api.log); gitignored, dir kept via logs/.gitignore
docs/                # the technical specification (source of truth)
src/
  backend/           # Python 3.11+ / FastAPI API — the single writer   → src/backend/CLAUDE.md
  frontend/          # React + TypeScript + Vite SPA                     → src/frontend/CLAUDE.md
```

## Root-level files to be created later (not yet)

Per doc 02, these launcher files belong at the repository root and are created during the "Skeleton" build phase:

- `start.sh` / `start.bat` — Mac/Linux and Windows launchers (env resolution, first-run install+build, health poll, open browser, single-instance).
- `dev.sh` — development mode: Uvicorn `--reload` (API only) + Vite dev server with `/api` proxied. For working on Authority itself, never for writing.
- `launcher.config.json` — `{ "port": 8700, "appDataRoot"?: "...", "envName": "authority" }`; created with defaults on first run if absent.

## Runtime data (not in the repo)

- `appDataRoot` — holds app-level `app.json` (user, models, AI-Jobs, utility model, API keys). Defaults to an **OS-standard per-user directory outside the repo** (`%LOCALAPPDATA%\Authority` on Windows, `~/Library/Application Support/Authority` on macOS, `~/.local/share/authority` on Linux), computed at runtime — never hardcoded into the committed `launcher.config.json`. This is deliberate: it must not live somewhere a repo-wide `git clean`/`rm -rf`/working-tree operation could delete it as if it were disposable build output. A relative override (e.g. `"./data"`) is still honored for local dev but is opt-in. Created by the app on first write.
- Book folders live under the author-configured `booksHome` (outside this repo). Each is `{6hex}-{slug}/` with its own `.git`, `config/`, `scenes/`, `db/`, `assets/`, `compiled-book/`.

## Build phases (implementation order, doc 02)

1. Skeleton (launchers, config, FastAPI app, health, static serving, logging)
2. Settings (app.json store; user/models/ai-jobs/placeholders; Settings pages)
3. Bookshelf (books-home scan, book creation + git init, cover; Home page)
4. Scenes core (CRUD, hard-chain splice/heal, soft relationships, sentinels, seq; graph + table + modal Basics)
5. Editor (TipTap, autosave, content endpoint, word count/hash, prev/next)
6. Structure & metadata (parts/chapters/plotlines/characters, blocked deletions; full Scene Modal; dependencies + dependency-todos; Tasks)
7. AI layer (LangChain factory, placeholders, worker, SSE hub, enrichment + toggles, conversations + streaming, proposals, AI-Jobs)
8. Git (service + page + top-bar badge + suggest-message)
9. Compilation (completeness check, readiness report, compile, standing indicator)
10. Polish (ui.json persistence, empty states, keyboard shortcuts, fit-to-view, archived filter)
