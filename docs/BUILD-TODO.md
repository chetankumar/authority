# Authority — Master Build TODO

Living checklist for the full Authority v1 spec (`docs/claude-tech-specs/`). Every item has a **user story**, a **status**, and the **files to touch / read**.

**Status legend**

| Status | Meaning |
|---|---|
| ✅ **DONE** | Implemented and wired end-to-end |
| 🔄 **IN PROGRESS** | Started but incomplete / stubbed / hooks only |
| ⬜ **NOT STARTED** | No implementation yet |

**Spec docs (read-order 01→02→03→05→04→06→07→08):**

| Shorthand | File |
|---|---|
| doc 01 | `docs/claude-tech-specs/01-overview-and-principles.md` |
| doc 02 | `docs/claude-tech-specs/02-architecture-and-launcher.md` |
| doc 03 | `docs/claude-tech-specs/03-data-storage.md` |
| doc 04 | `docs/claude-tech-specs/04-api-reference.md` |
| doc 05 | `docs/claude-tech-specs/05-ai-system.md` |
| doc 06 | `docs/claude-tech-specs/06-frontend-pages.md` |
| doc 07 | `docs/claude-tech-specs/07-decisions-and-deferred.md` |
| doc 08 | `docs/claude-tech-specs/08-user-journey.md` |

**Last audited:** 2026-07-18 (**Phase 12 docs closed.** `docs/audio-system.md` marked ✅ implemented; Phase 12 BUILD-TODO all ✅; doc 02 / root `CLAUDE.md` build phases list Phase 12; J19 marked shipped. Implementation: models/secrets, book `.gitignore` + Metadata editor, ElevenLabs settings + voice casting, AI-Job `audio-script` + Accept merge, AudioService/Worker + APIs, Editor Audio Modal + playlist, proposal card, SSE `audio-progress`.)

**Previously:** 2026-07-18 (**`Job` entity collapsed into `Conversation`.** There is no more `Job`/`jobs.json`/`JobService`/`JobWorker`/`EscalationService`/`api/jobs`/frontend `api/jobs.ts` — a *run* (an AI-Job the author triggers, or an automatic bookkeeping pass) is now just a conversation, distinguished by `kind` (`ai-job`/`bookkeeping`) with its lifecycle in `ConversationStatus` (`open·queued·running·waiting·done·failed·archived`). AI-Job runs are *prepared* synchronously by the new `AiJobService` (resolve prompt → open conversation at `open`) and run when the author sends; automatic bookkeeping conversations are created `queued` by `EnrichmentService` and drained by the new `ConversationWorker`. Enrichment writes fields via new **execute tools** (`ai_tools/execute.py`: `set_scene_summary`/`set_scene_characters` through `SceneService.update_scene`), and asks the author in-thread (status `waiting`) instead of escalating to a separate chat. SSE `job` event → `conversation`. Legacy `db/jobs.json` is deleted on load. Rows below mentioning `JobService`/`job_service.py`/`api/jobs.ts`/`GET /jobs`/`EscalationService` are historical — the feature they describe now lives in the conversation surface. Docs 01–08 updated to match. Earlier note follows:) (Todos vertical slice landed — `TDO-API-*`, `TDO-SVC-01`, `SCN-API-08`, `TSK-FE-*`, `EDT-FE-23` — with a storage split that **deviates from doc 03/04's single flat `db/todos.json`**: scene-parented todos now live in `scenes/{id}/todos.json`, joining meta/bookkeeping/dependencies/relationships in the per-scene folder split, while chapter/part/book-parented todos stay in the book-level file; `TodoService` resolves either tier from a flat id, same pattern as soft relationships. The book-level `GET /todos` also takes `?includeScenes=true` to aggregate every scene's todos for the Tasks page's toggle — a plain per-request scan, not a maintained index, since it's a rare human-paced read rather than a hot path. Dependency-todo fanout is implemented (previously stubbed); open todos no longer block scene deletion (previously did). `docs/claude-tech-specs/03-data-storage.md` and `04-api-reference.md` still describe the old single-file design and have not yet been updated to match — flagged here, not fixed, since editing the tech spec wasn't requested.)

**Previously:** 2026-07-16 (`db/scenes.json` split into a lean master table — identity/hard-chain/structure — plus a per-scene `scenes/{id}/` folder — meta.json, bookkeeping.json, dependencies.json, relationships.json — so AI-bookkeeping churn and low-churn structure no longer share a file, a write, or a corruption blast radius; transparent migration for old-shape books; API `Scene` response shape and frontend unchanged. AI task models split: `ai.utilityModelId` fallback + 4 independent slots — commit message, scene summarization, character parsing, chat default; enrichment's `both` scope now runs as two independent model calls instead of one combined call)

---

## Phase 1 — Skeleton & core infrastructure

### Launcher & runtime

> **Read:** doc 02 (full), doc 01 §hard-rules, doc 07 §launcher-config

| ID | Status | Item | User story | Files to create/modify |
|---|---|---|---|---|
| SK-01 | ⬜ | `start.bat` (Windows launcher) | As an author on Windows, I want to double-click a launcher so Authority starts, opens my browser, and tells me if it's already running. | **Create:** `start.bat` |
| SK-02 | ⬜ | `start.sh` (Mac/Linux launcher) | As an author on Mac/Linux, I want a one-command start script with the same behavior. | **Create:** `start.sh` |
| SK-03 | ⬜ | `dev.sh` (API reload + Vite proxy) | As a developer, I want hot-reload dev mode. | **Create:** `dev.sh` |
| SK-04 | ⬜ | `launcher.config.json` (first-run defaults) | As a first-time user, I want sensible defaults created automatically. | **Create:** `launcher.config.json` |
| SK-05 | ⬜ | Already-running detection | As an author, I want a second launch to open the existing session. | **Modify:** `start.bat`, `start.sh` |
| SK-06 | ⬜ | First-run install+build (conda/venv, pip, npm build) | As a first-time user, I want dependencies set up once and skipped later. | **Modify:** `start.bat`, `start.sh` |
| SK-07 | ⬜ | Health poll + browser open | As an author, I want the browser to open only after the API is ready. | **Modify:** `start.bat`, `start.sh` |
| SK-08 | ⬜ | Log file truncation per launch | As a developer, I want a fresh `logs/api.log` each session. | **Modify:** `src/backend/app/core/logging.py` |

### Backend core

> **Read:** doc 02 §process-model, doc 03 §data-safety, doc 04 §1

| ID | Status | Item | User story | Files to create/modify |
|---|---|---|---|---|
| SK-09 | ✅ | FastAPI app + `/api` routing | As an author, I want a local API so the browser never touches disk. | `src/backend/app/main.py` |
| SK-10 | ✅ | SPA static serve + index fallback | As an author, I want to refresh any page without a 404. | `src/backend/app/main.py` |
| SK-11 | ✅ | Health endpoint | As the UI, I want backend alive detection. | `src/backend/app/api/health/router.py` |
| SK-12 | ✅ | Structured error envelope | As an author, I want errors that say what went wrong. | `src/backend/app/core/errors.py`, `src/backend/app/main.py` |
| SK-13 | ✅ | Atomic JSON writes | As an author, I want crashes mid-save to never corrupt data. | `src/backend/app/core/atomic.py` |
| SK-14 | ✅ | Config load | As the server, I need runtime paths resolved. | `src/backend/app/core/config.py` |
| SK-15 | ✅ | Logging (console + file) | As a developer, I want startup and errors logged. | `src/backend/app/core/logging.py` |
| SK-16 | ⬜ | Single-instance filelock (`.lock`) | As an author, I want only one Authority process. | **Modify:** `src/backend/app/main.py`, `src/backend/app/core/config.py`; **Read:** `src/backend/requirements.txt` (filelock dep) |
| SK-17 | ⬜ | `app.json` load at startup into SettingsService | As the server, I want settings in memory before serving. | **Modify:** `src/backend/app/main.py`, `src/backend/app/services/settings_service.py` |
| SK-18 | ✅ | Job worker asyncio task at startup | As an author, I want AI jobs to run in the background. | **Create:** `src/backend/app/worker/worker.py`; **Modify:** `src/backend/app/main.py`; **Pattern to copy:** `src/backend/app/worker/git_status_worker.py` (standing task started/cancelled in `lifespan`) |
| SK-19 | ✅ | EventHub (per-book SSE pub/sub) | As the UI, I want live updates without polling. *(Built in Phase 8 — generic core infra, no AI dependency; see doc 07 §24.)* | `src/backend/app/core/event_hub.py`, `src/backend/app/api/events/router.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py` |
| SK-20 | ✅ | ~~Git dirty-check after every book write~~ → **debounced worker** | As an author, I want the git badge accurate after any save — **without** `git status` running on my autosave. **Superseded (doc 07 §25):** writes fire `book-changed` from `BookDataManager`; `GitStatusWorker` re-checks after a 5s debounce. No per-service dirty-check hooks. | `src/backend/app/services/book_data_manager.py`, `src/backend/app/worker/git_status_worker.py`, `src/backend/app/services/git_service.py` |

---

## Phase 2 — Settings

> **Read:** doc 04 §3, doc 06 §5, doc 05 §provider-abstraction, doc 03 §app-level-data, doc 07 §defaults

### API — SettingsService

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| SET-API-01 | ✅ | `GET /api/health` | Launcher/UI alive check. | `src/backend/app/api/health/router.py` |
| SET-API-02 | ✅ | `GET /api/settings/user` | Author name + books-home for greeting. | `src/backend/app/api/settings/router.py`, `src/backend/app/services/settings_service.py` |
| SET-API-03 | ✅ | `PATCH /api/settings/user` | Set name and books-home (optional folder creation). | Same as above |
| SET-API-04 | ✅ | `GET /api/settings/models` | List models with masked keys. | Same as above + `src/backend/app/models/settings.py` |
| SET-API-05 | ✅ | `POST /api/settings/models` | Add model config. | Same as above |
| SET-API-06 | ✅ | `PATCH /api/settings/models/{id}` | Update model without re-entering key. | Same as above |
| SET-API-07 | ✅ | `DELETE /api/settings/models/{id}` | Remove unused model (blocked if referenced). | Same as above |
| SET-API-08 | ✅ | `POST /api/settings/models/{id}/test` | Verify a model responds. | Same + `src/backend/app/services/model_factory.py` |
| SET-API-09 | ✅ | `GET /api/settings/ai` | Utility model id + 4 task-specific slots (commit message, character parsing, scene summary, chat default). | `src/backend/app/api/settings/router.py`, `src/backend/app/services/settings_service.py` |
| SET-API-10 | ✅ | `PATCH /api/settings/ai` | Pick any of the 5 AI task models independently, each falling back to the utility model when unset. | Same as above |
| SET-API-11 | ✅ | `GET /api/settings/appearance` | Saved theme preference. | Same as above |
| SET-API-12 | ✅ | `PATCH /api/settings/appearance` | Persist theme app-wide. | Same as above |
| SET-API-13 | ✅ | `GET /api/settings/ai-jobs` | AI job definitions. | Same as above |
| SET-API-14 | ✅ | `POST /api/settings/ai-jobs` | Define reusable AI job. | Same + `src/backend/app/services/placeholder_registry.py` |
| SET-API-15 | ✅ | `PATCH /api/settings/ai-jobs/{id}` | Refine job prompt/model. | Same as above |
| SET-API-16 | ✅ | `DELETE /api/settings/ai-jobs/{id}` | Remove job. | Same as above |
| SET-API-17 | ✅ | `GET /api/settings/placeholders` | `@` vocabulary for autocomplete. | `src/backend/app/api/settings/router.py`, `src/backend/app/services/placeholder_registry.py` |
| SET-SVC-01 | ✅ | SettingsService | Single writer for app-level settings. | `src/backend/app/services/settings_service.py` |
| SET-SVC-02 | ✅ | PlaceholderRegistry (list + validate) | Catch unknown `@` tokens at save time. | `src/backend/app/services/placeholder_registry.py` |
| SET-SVC-03 | ✅ | ModelFactory (build + test) | LangChain models from config for test endpoint. | `src/backend/app/services/model_factory.py` |

### Frontend — Settings pages

> **Read:** doc 06 §5, doc 04 §3

| ID | Status | Control / page | User story | Files |
|---|---|---|---|---|
| SET-FE-01 | ✅ | Settings layout + sub-nav | Settings grouped logically. | `src/frontend/src/features/settings/SettingsLayout.tsx`, `src/frontend/src/router.tsx` |
| SET-FE-02 | ✅ | User Settings — name input | Name in greeting. | `src/frontend/src/features/settings/UserSettingsPage.tsx` |
| SET-FE-03 | ✅ | User Settings — books-home path | Point at manuscripts folder. | Same as above |
| SET-FE-04 | ✅ | User Settings — [Create this folder] | Offered folder creation. | Same as above |
| SET-FE-05 | ✅ | User Settings — 403 not-writable | Clear permission error. | Same as above |
| SET-FE-06 | ✅ | AI Settings — models table | All models at a glance. | `src/frontend/src/features/settings/AISettingsPage.tsx` |
| SET-FE-07 | ✅ | [Add model] → Model modal | Guided per-provider form. | `src/frontend/src/features/settings/ModelModal.tsx` |
| SET-FE-08 | ✅ | Provider-driven fields | Form teaches provider requirements. | Same as above |
| SET-FE-09 | ✅ | Edit preserves key | Edit without re-pasting secrets. | Same as above |
| SET-FE-10 | ✅ | Test ↯ (spinner, chip, toast) | Proof model works. | `src/frontend/src/features/settings/AISettingsPage.tsx` |
| SET-FE-11 | ✅ | Model edit ✎ / delete 🗑 | Maintain model list. | Same as above |
| SET-FE-12 | ✅ | Delete 409 → BlockedDeletionDialog | Blocked deletion with fix links. | Same + `src/frontend/src/components/BlockedDeletionDialog.tsx` |
| SET-FE-13 | ✅ | AI task model selects (utility + 4 task-specific) | Explicit, independent model choice per system task. | `src/frontend/src/features/settings/AISettingsPage.tsx`, `src/frontend/src/api/settings.ts` |
| SET-FE-14 | ✅ | AI-Jobs table + [Add] | Library of reusable AI workflows. | `src/frontend/src/features/settings/AIJobsPage.tsx` |
| SET-FE-15 | ✅ | Job modal (name, prompt, output, model) | Define job behavior. | `src/frontend/src/features/settings/JobModal.tsx` |
| SET-FE-16 | ✅ | `@` autocomplete in prompt editor | Placeholder names suggested as typed. | `src/frontend/src/features/settings/PromptEditor.tsx` |
| SET-FE-17 | ✅ | Unknown placeholder warning + [Save anyway] | Save forward-looking prompts. | `src/frontend/src/features/settings/JobModal.tsx` |
| SET-FE-18 | ✅ | Job edit / delete | Maintain job library. | `src/frontend/src/features/settings/AIJobsPage.tsx` |

---

## Phase 3 — Bookshelf

> **Read:** doc 04 §4, doc 06 §4, doc 03 §book-folder, doc 08 J2–J7

### API — BookScanner, BookService, BookDataManager

| ID | Status | Endpoint / method | User story | Files |
|---|---|---|---|---|
| BOOK-API-01 | ✅ | `GET /api/books` | Shelf from live folder scan. | `src/backend/app/api/books/router.py`, `src/backend/app/services/book_scanner.py` |
| BOOK-API-02 | ✅ | `POST /api/books` (multipart) | Create book with scaffold + git init. | `src/backend/app/api/books/router.py`, `src/backend/app/services/book_service.py` |
| BOOK-API-03 | ✅ | `GET /api/books/{id}` | Full book context. | `src/backend/app/api/books/router.py`, `src/backend/app/services/book_data_manager.py`, `src/backend/app/services/book_registry.py` |
| BOOK-API-04 | 🔄 | `PATCH /api/books/{id}` (JSON partial) | Edit summary/prompt, toggle bookkeeping (title rename + cover = future). | `src/backend/app/api/books/router.py`, `src/backend/app/services/book_data_manager.py` |
| BOOK-API-05 | ✅ | `GET /api/books/{id}/cover` | Cover images for shelf. | `src/backend/app/api/books/router.py` |
| BOOK-API-06 | ✅ | `GET /api/books/{id}/ui` | Persisted UI prefs per book. | `src/backend/app/api/books/router.py`, `src/backend/app/services/book_data_manager.py` |
| BOOK-API-07 | ✅ | `PATCH /api/books/{id}/ui` | Remember column/pane state. | Same as above |
| BOOK-SVC-01 | ✅ | BookScanner (scan + cache) | Shelf stays current without registry. | `src/backend/app/services/book_scanner.py` |
| BOOK-SVC-02 | ✅ | BookService.create | New books are portable git repos. | `src/backend/app/services/book_service.py` |
| BOOK-SVC-03 | ⬜ | BookService.patch (rename, cover, metadata) | Book edits consistent on disk and in git. | **Modify:** `src/backend/app/services/book_service.py`, `src/backend/app/services/book_data_manager.py` |
| BOOK-SVC-04 | ✅ | BookDataManager (config + scenes + rels + ui) | One in-memory owner per book. | `src/backend/app/services/book_data_manager.py` |
| BOOK-SVC-05 | 🔄 | BookDataManager — load all `db/*.json` | Parts, chapters, plotlines in memory (characters, todos, jobs pending). | `src/backend/app/services/book_data_manager.py` |
| BOOK-SVC-06 | ✅ | BookDataManager — conversations index | Per-conversation JSON and derived index; delete clears index + unlinks jobs. | `src/backend/app/services/book_data_manager.py` |

### Frontend — Bookshelf & book home

> **Read:** doc 06 §4, doc 06 §3 (global shell)

| ID | Status | Control / page | User story | Files |
|---|---|---|---|---|
| BOOK-FE-01 | ✅ | Bookshelf grid (`/`) | All books as cards. | `src/frontend/src/features/bookshelf/BookshelfPage.tsx` |
| BOOK-FE-02 | ✅ | Book card → book home | Open with one click. | Same as above |
| BOOK-FE-03 | ✅ | + Add book → Create Book modal | Creation where results appear. | `src/frontend/src/features/bookshelf/CreateBookModal.tsx` |
| BOOK-FE-04 | ✅ | Create Book modal | Simple create with optional cover. | Same as above |
| BOOK-FE-05 | ✅ | Create success toast + navigate | Land in new book immediately. | `src/frontend/src/features/bookshelf/BookshelfPage.tsx` |
| BOOK-FE-06 | ✅ | Empty state — books-home unset | Direction to configure. | Same as above |
| BOOK-FE-07 | ✅ | Empty state — shelf empty | Encouragement to create. | Same as above |
| BOOK-FE-08 | ✅ | Broken-book card | Corrupt configs surfaced. | Same as above |
| BOOK-FE-09 | ⬜ | Card kebab → Edit Book modal | Rename or update cover from shelf. | **Modify:** `src/frontend/src/features/bookshelf/BookshelfPage.tsx`; **Create:** `src/frontend/src/features/bookshelf/EditBookModal.tsx`; **Modify:** `src/frontend/src/api/books.ts` (add `patchBook`) |
| BOOK-FE-10 | ⬜ | Edit Book modal | Rename hint, PATCH book. | **Create:** `src/frontend/src/features/bookshelf/EditBookModal.tsx`; **Modify:** `src/frontend/src/api/books.ts`, `src/frontend/src/queries/books.ts` |
| BOOK-FE-11 | ✅ | Book home header | Context when entering a book. | `src/frontend/src/features/book/BookPage.tsx` |
| BOOK-FE-12 | ✅ | Book home — workspace grid | One place for all book tools. | Same as above |
| BOOK-FE-13 | 🔄 | Book home — section links | Entry points; unfinished labeled "soon". | **Modify:** `src/frontend/src/features/book/BookPage.tsx` (add `path` to sections as phases land) |

---

## Phase 4 — Scenes core

> **Read:** doc 04 §5–§6, doc 06 §6–§8, doc 03 §scenes.json/§relationships.json, doc 08 J8–J9

### API — SceneService, ChainService, relationships

| ID | Status | Endpoint / method | User story | Files |
|---|---|---|---|---|
| SCN-API-01 | ✅ | `GET /books/{b}/scenes` | Scenes + rels + sentinels for graph/table. | `src/backend/app/api/scenes/router.py`, `src/backend/app/services/scene_service.py`, `src/backend/app/services/chain_service.py` |
| SCN-API-02 | ✅ | `POST /books/{b}/scenes` | Create with optional splice + soft links. | Same as above |
| SCN-API-03 | ✅ | `GET /books/{b}/scenes/{id}` (+ content) | Metadata and prose for editor. | Same as above |
| SCN-API-04 | ✅ | `PATCH /books/{b}/scenes/{id}` | Edit metadata, chain, chapter/part, archive. | Same as above |
| SCN-API-05 | ✅ | `PUT /books/{b}/scenes/{id}/content` | Autosaved prose with word count/hash. | Same as above + `src/backend/app/core/atomic.py` |
| SCN-API-06 | ✅ | `POST /books/{b}/scenes/{id}/enrich` | On-demand AI redo of summary/characters. | **Modify:** `src/backend/app/api/scenes/router.py`, `src/backend/app/services/scene_service.py`; **Depends on:** Phase 7 (JobService, EnrichmentService) |
| SCN-API-07 | ✅ | `GET /books/{b}/scenes/{id}/conversations` | Notes/chats scoped to scene. | **Modify:** `src/backend/app/api/scenes/router.py`; **Depends on:** Phase 7 (ConversationService) |
| SCN-API-08 | ✅ | `GET`/`POST /books/{b}/scenes/{id}/todos` | Scene-scoped todos — list (open first, newest first) and create; PATCH/DELETE by id are the shared `/books/{b}/todos/{id}` routes (TDO-API-03/04). | `src/backend/app/api/scenes/router.py`, `src/backend/app/services/todo_service.py` |
| SCN-API-09 | ⬜ | `GET /books/{b}/scenes/{id}/dependencies` | Depends-on + depended-on-by. | **Modify:** `src/backend/app/api/scenes/router.py`; **Depends on:** Phase 6 (dependencies) |
| SCN-API-10 | ✅ | `DELETE /books/{b}/scenes/{id}` | As an author, I want to permanently delete an archived scene; if it has references (relationships, dependencies, conversations, plotlines, running jobs) the API returns 409 with `blockedBy` details. Open todos are **not** a blocker (revised 2026-07-17) — they're silently discarded with the rest of the scene's per-scene folder. The `.md` file moves to `.trash/`, never physically deleted. | `src/backend/app/api/scenes/router.py`, `src/backend/app/services/scene_service.py` |
| SCN-API-11 | ✅ | `POST /books/{b}/relationships` | Soft placement edges. | `src/backend/app/api/relationships/router.py`, `src/backend/app/services/scene_service.py` |
| SCN-API-12 | ✅ | `DELETE /books/{b}/relationships/{id}` | Remove obsolete soft links. | Same as above |
| SCN-API-13 | ⬜ | `POST /books/{b}/dependencies` | Declare prerequisites between scenes. | **Create:** `src/backend/app/api/dependencies/router.py`, `src/backend/app/api/dependencies/__init__.py`; **Modify:** `src/backend/app/services/scene_service.py` (or new dep service), `src/backend/app/services/book_data_manager.py`, `src/backend/app/main.py` (register router); **Create model:** `src/backend/app/models/dependency.py` (or add to `scene.py`) |
| SCN-API-14 | ⬜ | `PATCH /books/{b}/dependencies/{id}` | Refine reason. | Same as SCN-API-13 |
| SCN-API-15 | ⬜ | `DELETE /books/{b}/dependencies/{id}` | Remove dependency. | Same as SCN-API-13 |
| SCN-SVC-01 | ✅ | ChainService (splice, heal, seq/placement) | Deterministic story order. Floating/orphan scenes get `seq: null` — only hard-chain scenes are numbered. | `src/backend/app/services/chain_service.py` |
| SCN-SVC-02 | ✅ | SceneService CRUD + content save | Only prose write paths guarded. | `src/backend/app/services/scene_service.py` |
| SCN-SVC-03 | 🔄 | Content save — dependency todo fanout (stub) | Todos when depended-on scene changes. | **Modify:** `src/backend/app/services/scene_service.py` (line ~209, phase 6 hook) |
| SCN-SVC-04 | ✅ | Content save — no enrichment timer | Enrichment is leave-scene / on-demand only. | `scene_service.py`, `enrichment_service.py` |

### Frontend — Scene graph

> **Read:** doc 06 §6

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| GRF-FE-01 | ✅ | Scene Graph page | Story's shape at a glance. | `src/frontend/src/features/graph/GraphPage.tsx` |
| GRF-FE-02 | ✅ | D3 layout | Same data, same map. | `src/frontend/src/features/graph/layout.ts` |
| GRF-FE-03 | ✅ | Pan/zoom | Explore without maintaining layout. | `src/frontend/src/features/graph/GraphPage.tsx` |
| GRF-FE-04 | ✅ | Sentinel pills | Fixed anchors. | Same as above |
| GRF-FE-05 | ✅ | Solid trunk / dotted soft edges | Distinguish hard chain from planning. | Same as above |
| GRF-FE-06 | ✅ | Single-click → Scene Modal | Inspect from the map. | Same as above + `src/frontend/src/features/sceneModal/SceneModal.tsx` |
| GRF-FE-07 | ✅ | Double-click → editor | Heavier gesture for prose. | Same as above |
| GRF-FE-08 | ✅ | [＋ Add scene] floating | Create where imagining placement. | Same as above |
| GRF-FE-09 | ✅ | [⤢ Fit] button | Reset zoom. | Same as above |
| GRF-FE-10 | ✅ | Sequence number on graph nodes | As an author viewing the scene graph, I want each placed scene to show its sequence number (e.g. "#3") before the title, so I can see the reading order at a glance. Unplaced scenes (floating/orphan) show no number. | `src/frontend/src/features/graph/layout.ts`, `src/frontend/src/features/graph/GraphPage.tsx` |
| GRF-FE-11 | ✅ | Soft-relationship arrow direction fix | As an author, I want "definitely after" arrows to point from the earlier scene to this one (reversed from "before"), so the graph arrows match reading order. | `src/frontend/src/features/graph/layout.ts` |
| GRF-FE-12 | ✅ | Empty state | Invitation, not dead end. | Same as above |
| GRF-FE-13 | ✅ | Node hover tooltip | Quick reminder. | Same as above |
| GRF-FE-14 | ✅ | Soft edge hover tooltip | Lines explained. | Same as above |
| GRF-FE-15 | ✅ | Archived hidden | Active story only. | Same as above |

### Frontend — Scene table

> **Read:** doc 06 §7

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| TBL-FE-01 | ✅ | Scene Table page | Sortable ledger. | `src/frontend/src/features/table/ScenesTablePage.tsx` |
| TBL-FE-02 | ✅ | AG Grid + theme tokens | Table matches app theme. | Same as above |
| TBL-FE-03 | ✅ | Filter All / Placed / Floating | Find unplaced scenes. | Same as above |
| TBL-FE-04 | ✅ | Archived toggle | Review archived separately. | Same as above |
| TBL-FE-05 | ✅ | [Columns ▾] chooser | Show/hide columns. | Same as above |
| TBL-FE-06 | ✅ | Column state → `PATCH ui` | Choices remembered per book. | Same + `src/frontend/src/api/books.ts` |
| TBL-FE-07 | ✅ | Default + optional columns | Story-order and metadata columns. | Same as TBL-FE-01 |
| TBL-FE-08 | ✅ | Placement chips | Floating/orphan at a glance. | Same as above |
| TBL-FE-09 | ✅ | Row click → editor | One click to write. | Same as above |
| TBL-FE-10 | ✅ | Row ✎ → Scene Modal | Fix metadata inline. | Same as above |
| TBL-FE-11 | ✅ | Row archive / unarchive | Set aside for compile hygiene. | Same as above |
| TBL-FE-12 | ✅ | Row delete (archived only) | As an author, I want a delete button on archived table rows that shows a confirm dialog, with a 409 blocked-deletion error toast if references exist. | `src/frontend/src/features/table/ScenesTablePage.tsx`, `src/frontend/src/components/ConfirmDialog.tsx` |
| TBL-FE-13 | 🔄 | Archive toast | Confirmation on archive. | **Modify:** `src/frontend/src/features/table/ScenesTablePage.tsx` (add `useToast` call) |
| TBL-FE-14 | ⬜ | Seq header click → story order | One click to return to story sequence. | **Modify:** `src/frontend/src/features/table/ScenesTablePage.tsx` |

### Frontend — Scene Modal

> **Read:** doc 06 §8

| ID | Status | Tab / control | User story | Files |
|---|---|---|---|---|
| MOD-FE-01 | ✅ | Modal shell (720px, tabs, footer) | One place for scene facts. | `src/frontend/src/features/sceneModal/SceneModal.tsx`, `src/frontend/src/components/Modal.tsx` |
| MOD-FE-02 | ✅ | **Basics** — fields | Scene metadata. | `src/frontend/src/features/sceneModal/SceneModal.tsx` |
| MOD-FE-03 | ✅ | **Basics** — Sequence | Place in hard chain. | Same as above + `src/frontend/src/components/SearchableSelect.tsx` |
| MOD-FE-04 | ✅ | **Basics** — Soft placement | Planning links. | Same as above |
| MOD-FE-05 | ✅ | **Basics** — Structure | Chapter/Part picks. | Same as above |
| MOD-FE-06 | ✅ | Save scene | Single Save for Basics. | Same + `src/frontend/src/api/scenes.ts`, `src/frontend/src/api/relationships.ts`, `src/frontend/src/queries/scenes.ts` |
| MOD-FE-07 | ✅ | Archive / Unarchive scene | As an author, I want to archive a scene (reversible, no confirm) or unarchive an archived scene from the modal, so I can manage scene lifecycle without switching to the table. | Same as above |
| MOD-FE-08 | ✅ | Delete scene (archived only) | As an author, I want to permanently delete an archived scene from the modal with a confirm dialog; if it has references, a blocked-deletion error tells me what to clean up first. The prose file moves to `.trash/`. | Same + `src/frontend/src/components/ConfirmDialog.tsx` |
| MOD-FE-09 | ✅ | Autofill nodes toggle | As an author, I want a toggle to disable the automatic Previous↔Next coupling in the Sequence section, so I can manually set both endpoints independently when needed. | `src/frontend/src/features/sceneModal/SceneModal.tsx` |
| MOD-FE-10 | ✅ | Create mode — Basics only | Focused first save. | Same as above |
| MOD-FE-11 | ✅ | **Characters** tab — rows + involvement + add/remove | Tag characters and what they do in the scene. | `src/frontend/src/features/sceneModal/SceneModal.tsx`; `src/frontend/src/api/characters.ts`; `src/frontend/src/queries/characters.ts` |
| MOD-FE-12 | ✅ | **Characters** — ↻ AI-redo + unrecognized | Refresh from prose. | Same + `enrichScene` in `api/scenes.ts` |
| MOD-FE-13 | ✅ | **Summary** tab — textarea + Save | Hand-write/edit summary. | `SceneModal.tsx` |
| MOD-FE-14 | ✅ | **Summary** — ↻ AI-redo + hint | Leave-scene toggle visibility. | Same + `useBook` bookkeeping |
| MOD-FE-15 | ⬜ | **Dependencies** tab — list + add/edit/delete | Record scene prerequisites. | **Modify:** `src/frontend/src/features/sceneModal/SceneModal.tsx`; **Create:** `src/frontend/src/api/dependencies.ts`; **Create:** `src/frontend/src/queries/dependencies.ts`; **Depends on:** SCN-API-09, SCN-API-12 |
| MOD-FE-16 | ⬜ | **Dependencies** — depended-on-by (amber) | Warning before rewriting load-bearing scene. | Same as above |

---

## Phase 5 — Editor

> **Read:** doc 06 §9, doc 04 §5 (content PUT), doc 08 J11

### Frontend — Scene editor

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| EDT-FE-01 | ✅ | Editor page | Dedicated writing room. | `src/frontend/src/features/editor/EditorPage.tsx` |
| EDT-FE-02 | ✅ | Auto-collapsed left nav | Max width for prose. | `src/frontend/src/App.tsx` (LeftNav `collapsed` prop) |
| EDT-FE-03 | ✅ | TipTap + markdown | Rich text that saves as markdown. | `src/frontend/src/features/editor/EditorPage.tsx` |
| EDT-FE-04 | ✅ | TipTap toolbar | Basic formatting. | Same as above |
| EDT-FE-05 | ✅ | 68ch Literata sheet | Serious readable measure. | Same + `src/frontend/src/styles/index.css` |
| EDT-FE-06 | ✅ | Inline editable title | Rename without modal. | `src/frontend/src/features/editor/EditorPage.tsx` |
| EDT-FE-07 | ✅ | Autosave 2s + blur + route-leave | Words on disk without thinking. | Same as above |
| EDT-FE-08 | ✅ | Ctrl/Cmd+S immediate | Familiar save shortcut. | Same as above |
| EDT-FE-09 | ✅ | Save indicator | Trust persistence. | Same as above |
| EDT-FE-10 | ✅ | Live word count | Drafting odometer. | Same as above |
| EDT-FE-11 | ✅ | [← Prev] [Next →] | Chain navigation. | Same as above |
| EDT-FE-12 | ✅ | Next → create modal (prev prefilled) | "What comes next?" gesture. | Same + `src/frontend/src/features/sceneModal/SceneModal.tsx` |
| EDT-FE-13 | ✅ | Prev disabled at start | Clear chain start boundary. | `src/frontend/src/features/editor/EditorPage.tsx` |
| EDT-FE-14 | ✅ | [Metadata] → Scene Modal | Scene facts adjacent to prose. | Same + `src/frontend/src/features/sceneModal/SceneModal.tsx` |
| EDT-FE-15 | ✅ | ◫ pane toggle + ui.json | Zen or side context, remembered. | `src/frontend/src/features/editor/EditorPage.tsx`, `src/frontend/src/api/books.ts` |
| EDT-FE-16 | ✅ | Right pane shell (accordion, "soon") | Notes/Todos/AI Jobs beside prose. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx` |
| EDT-FE-17 | ✅ | **AI-Jobs ▾** menu → run job | Job library one click from prose. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Create:** `src/frontend/src/api/jobs.ts`; **Modify:** `src/frontend/src/queries/keys.ts`; **Depends on:** AI-API-05 |
| EDT-FE-18 | ✅ | AI-Jobs — selection scope | "Fix this paragraph" vs "review whole scene". | Same as above |
| EDT-FE-19 | ✅ | **Bookkeeping** popover | Standing consent for leave-scene enrichment. | `EditorPage.tsx` + `usePatchBook` |
| EDT-FE-20 | ✅ | Bookkeeping → PATCH bookkeeping | Toggles persist at book level. | Same |
| EDT-FE-21 | ✅ | **Chat** → Conversation Modal | Help when stuck, selection as context; AI on with the chat default model preselected (falls back to utility, then first model). | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Create:** `src/frontend/src/features/conversation/ConversationModal.tsx`; **Create:** `src/frontend/src/api/conversations.ts`; **Depends on:** AI-API-01 |
| EDT-FE-22 | ✅ | **Notes** accordion | Past threads for scene. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Depends on:** SCN-API-07, Phase 7 |
| EDT-FE-23 | ✅ | **To-dos** accordion | Open obligations while writing: checkbox → done, ✕ → closed, 🗑 → delete (confirm), 💬 → linked conversation (created on first use), ⛓ amber row for dependency-origin, plus an inline add-task field (not in the original spec — see doc 03 deviation note at TDO-API-02). | `src/frontend/src/features/editor/EditorPage.tsx`, `src/frontend/src/api/todos.ts`, `src/frontend/src/queries/todos.ts` |
| EDT-FE-24 | ✅ | **AI Jobs** accordion — SSE status | Running/done jobs visible. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Depends on:** SSE-FE-01, Phase 7 |
| EDT-FE-25 | ⬜ | Amber count badges | Pending items use attention color. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Create:** `src/frontend/src/components/Badge.tsx` |
| EDT-FE-26 | 🔄 | Toast on job completion | Know when background job finishes. | **Modify:** `src/frontend/src/features/editor/EditorPage.tsx`; **Depends on:** SSE |

---

## Phase 6 — Structure & metadata

> **Read:** doc 04 §7, doc 06 §11–§13, doc 03 §book.json/§characters.json/§plotlines.json/§dependencies.json/§todos.json, doc 07 §16 (blocked deletions), doc 08 J10/J16

### API — Structure (parts, chapters, plotlines, characters)

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| STR-API-01 | ✅ | `GET /books/{b}/parts` | Ordered parts for metadata/picks. | `src/backend/app/api/structure/router.py`, `src/backend/app/services/structure_service.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py` |
| STR-API-02 | ✅ | `POST /books/{b}/parts` | Add parts to structure book. | Same files as STR-API-01 |
| STR-API-02a | ✅ | `POST /books/{b}/parts/reorder` | Reorder parts via drag-and-drop (seq-based). | Same files |
| STR-API-03 | ✅ | `PATCH /books/{b}/parts/{id}` | Update part metadata. | Same files |
| STR-API-04 | ✅ | `DELETE /books/{b}/parts/{id}` (409) | Blocked until unassigned. | Same files |
| STR-API-05 | ✅ | `GET /books/{b}/chapters` | Chapters with partId grouping. | Same files as STR-API-01 |
| STR-API-06 | ✅ | `POST /books/{b}/chapters` | Create chapters. | Same files |
| STR-API-06a | ✅ | `POST /books/{b}/chapters/reorder` | Reorder chapters via drag-and-drop (seq-based). | Same files |
| STR-API-07 | ✅ | `PATCH /books/{b}/chapters/{id}` | Assign/update chapter metadata. | Same files |
| STR-API-08 | ✅ | `DELETE /books/{b}/chapters/{id}` (409) | Blocked while scenes reference. | Same files |
| STR-API-09 | ✅ | `GET /books/{b}/plotlines` | Plot threads + computed scene counts. | `src/backend/app/api/plotlines/router.py`, `src/backend/app/services/structure_service.py`, `src/backend/app/models/plotline.py` |
| STR-API-10 | ✅ | `POST /books/{b}/plotlines` | Named plotlines. | Same as STR-API-09 |
| STR-API-11 | ✅ | `PATCH /books/{b}/plotlines/{id}` | Update plotline metadata. | Same files |
| STR-API-12 | ✅ | `DELETE /books/{b}/plotlines/{id}` (409) | Unlink scenes before deleting. | Same files |
| STR-API-13 | ✅ | `GET /books/{b}/characters` | Cast list + computed scene counts (identity + craft fields: age, gender, nationality, ethnicity, occupation, want, need, flaw, arc). | `src/backend/app/api/characters/router.py`, `src/backend/app/services/structure_service.py`, `src/backend/app/services/book_data_manager.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py`, `src/backend/app/models/character.py` |
| STR-API-14 | ✅ | `POST /books/{b}/characters` | Add characters for enrichment. | Same as STR-API-13 |
| STR-API-15 | ✅ | `PATCH /books/{b}/characters/{id}` | Maintain any field, partial update. | Same files |
| STR-API-16 | ✅ | `DELETE /books/{b}/characters/{id}` (409) | Blocked while scenes or character-relationships reference it. | Same files |
| STR-API-17 | ✅ | `GET /books/{b}/character-relationships` | List all relationships in the book. | Same files |
| STR-API-18 | ✅ | `POST /books/{b}/character-relationships` | Directional relationship between two characters (category + `aToB`/`bToA` labels + description); blocked on self-relation or duplicate pair. | Same files |
| STR-API-19 | ✅ | `PATCH /books/{b}/character-relationships/{id}` | Edit category/labels/description. | Same files |
| STR-API-20 | ✅ | `DELETE /books/{b}/character-relationships/{id}` | Unblocked. | Same files |
| STR-SVC-01 | ✅ | StructureService | Seq-based ordering + blocked deletions; character uniqueness (name+aliases, case-insensitive); character-relationship pair-uniqueness. | `src/backend/app/services/structure_service.py` |

### API — Dependencies & Todos

> **Read:** doc 04 §6, doc 04 §8, doc 03 §dependencies.json/§todos.json

| ID | Status | Endpoint / mechanism | User story | Files |
|---|---|---|---|---|
| DEP-API-01 | ⬜ | `POST /books/{b}/dependencies` | Declare prerequisites. | **Create:** `src/backend/app/api/dependencies/router.py`, `__init__.py`; **Modify:** `src/backend/app/services/book_data_manager.py` (load/save deps); **Modify:** `src/backend/app/main.py`, `src/backend/app/api/deps.py`; **Add model in:** `src/backend/app/models/scene.py` (or new file) |
| DEP-API-02 | ⬜ | `PATCH /books/{b}/dependencies/{id}` | Edit reason only. | Same files |
| DEP-API-03 | ⬜ | `DELETE /books/{b}/dependencies/{id}` | Remove dependency. | Same files |
| TDO-API-01 | ✅ | `GET /books/{b}/todos` (book-level; `?includeScenes=true` aggregates every scene too) | All todos with parent titles. | `src/backend/app/api/todos/router.py`, `src/backend/app/services/todo_service.py`, `src/backend/app/models/todo.py` |
| TDO-API-02 | ✅ | `POST /books/{b}/todos` (chapter/part/book) + `POST /books/{b}/scenes/{id}/todos` (scene) | Manual book-level or scene-scoped todos. **Storage deviates from doc 03/04's single flat `db/todos.json`:** scene-parented todos persist in `scenes/{id}/todos.json` (own folder, same corruption-blast-radius reasoning as dependencies/relationships), not the book-level file — see `TodoService`/`BookDataManager` docstrings. | `src/backend/app/api/todos/router.py`, `src/backend/app/api/scenes/router.py`, `src/backend/app/services/todo_service.py`, `src/backend/app/services/book_data_manager.py` |
| TDO-API-03 | ✅ | `PATCH /books/{b}/todos/{id}` | Mark done/closed or edit action; resolves either storage tier from a flat id (mirrors `DELETE /relationships/{id}`). Also accepts a set-once `conversationId` (the 💬 link). | Same files |
| TDO-API-04 | ✅ | `DELETE /books/{b}/todos/{id}` | Delete mistaken todos. | Same files |
| TDO-SVC-01 | ✅ | Dependency fanout → todo (dedup) | One reminder when dep source changes; creates a scene-level todo on each dependent scene, deduped by open `sourceDependencyId`. Open todos no longer block scene deletion (deviates from the original doc 04 §5 delete-blockers list — the folder just moves to `.trash/` with its todos). | `src/backend/app/services/scene_service.py` (`_fanout_dependency_todos`, `save_content`, `delete_scene`) |

### Frontend — Metadata page

> **Read:** doc 06 §12

| ID | Status | Control / tab | User story | Files |
|---|---|---|---|---|
| META-FE-01 | ✅ | Metadata route + nav live | Structural workshop. | `src/frontend/src/features/metadata/MetadataPage.tsx`, `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx`, `src/frontend/src/api/structure.ts`, `src/frontend/src/queries/structure.ts`, `src/frontend/src/queries/keys.ts` |
| META-FE-02 | ⬜ | Readiness strip | Standing "how ready?" gauge. | **Modify:** `src/frontend/src/features/metadata/MetadataPage.tsx`; **Create:** `src/frontend/src/api/compile.ts`; **Modify:** `src/frontend/src/queries/keys.ts`; **Depends on:** CMP-API-01 |
| META-FE-03 | ⬜ | Readiness expand → deep links | Every violation links to fix. | Same as above |
| META-FE-04 | ⬜ | [Compile book] | Compile one click away. | Same; **Depends on:** CMP-API-02 |
| META-FE-05 | ✅ | **Parts** tab — drag-and-drop reorder, CRUD | Define and reorder parts. | `src/frontend/src/features/metadata/MetadataPage.tsx`, `src/frontend/src/api/structure.ts`, `src/frontend/src/queries/structure.ts` |
| META-FE-06 | ✅ | **Chapters** tab — grouped by part | Table of contents takes shape. | Same files |
| META-FE-07 | ✅ | Chapter Part select → PATCH | Assign chapters to parts inline. | Same files |
| META-FE-08 | ✅ | **Plotlines** tab — CRUD + scene counts | Track narrative threads. | Same files (plotlines API in `src/frontend/src/api/structure.ts`) |
| META-FE-09 | ✅ | **Book** tab — summary + system prompt | Book-level texts for AI. | `src/frontend/src/features/metadata/MetadataPage.tsx`, `src/frontend/src/api/books.ts`, `src/frontend/src/queries/structure.ts` |
| META-FE-10 | ✅ | Book tab Save → PATCH | Book metadata persisted. | Same as META-FE-09 |

### Frontend — Character Sheet page

> **Read:** doc 06 §11

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| CHR-FE-01 | ✅ | Characters route + nav live | Cast dictionary. | `src/frontend/src/features/characters/CharactersPage.tsx`, `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx` (nav `soon` removed), `src/frontend/src/api/characters.ts`, `src/frontend/src/queries/characters.ts`, `src/frontend/src/queries/keys.ts` |
| CHR-FE-02 | ✅ | Character list rows | Scan who's in the story. | `src/frontend/src/features/characters/CharactersPage.tsx` |
| CHR-FE-03 | ✅ | Row expand → edit form (Identity / Craft groups) | Inline editing of the full schema. | Same as above |
| CHR-FE-04 | ✅ | Aliases tag-input + uniqueness error | Nicknames for enrichment. | Same as above |
| CHR-FE-05 | ✅ | [＋ Add character] | Register new cast member (lightweight name+aliases form). | Same as above |
| CHR-FE-06 | ✅ | Delete → 409 BlockedDeletionDialog | Unlink scenes/relationships before deleting. | Same + `src/frontend/src/components/BlockedDeletionDialog.tsx` |
| CHR-FE-07 | ✅ | Relationships section (within expanded row) | List/add/edit/remove directional relationships to other characters. | `src/frontend/src/features/characters/CharactersPage.tsx`, `src/frontend/src/components/SearchableSelect.tsx` |

### Frontend — Tasks page

> **Read:** doc 06 §13

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| TSK-FE-01 | ✅ | Tasks route + nav live | One ledger of everything owed. | `src/frontend/src/features/tasks/TasksPage.tsx`, `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx`, `src/frontend/src/api/todos.ts`, `src/frontend/src/queries/todos.ts`, `src/frontend/src/queries/keys.ts` |
| TSK-FE-02 | ✅ | AG Grid (Status, Action, Parent, Origin) | Scan todos book-wide. | `src/frontend/src/features/tasks/TasksPage.tsx` |
| TSK-FE-03 | ✅ | Filter Open / All | Focus on open work. | Same as above |
| TSK-FE-04 | ✅ | Parent chip → navigate | Jump to what a todo is about. | Same as above |
| TSK-FE-05 | ✅ | Checkbox → done; menu → closed | Done vs dismissed. | Same as above |
| TSK-FE-06 | ✅ | Origin icons (user / ⛓ / ✦) | Provenance at a glance. | Same as above |
| TSK-FE-07 | ✅ | [＋ Add task] inline (chapter/part/book — scene todos are added from the editor's To-dos accordion instead) | Book-level todos. | Same as above |
| TSK-FE-08 | ✅ | Row menu — conversation / delete | Todos linked to discussions. Plus a persistent "also show scene todos" toggle (`ui.json`), not in the original spec — this book's Tasks page has two storage tiers to surface (doc 03 deviation, see TDO-API-02). | Same as above |

---

## Phase 7 — AI layer

> **Read:** doc 04 §9–§11, doc 05 (full), doc 06 §10, doc 03 §conversations/§jobs.json, doc 08 J12–J15

### API — Conversations, messages, proposals, jobs

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| AI-API-01 | ✅ | `POST /books/{b}/conversations` | Start a note/chat on a scene. | **Create:** `src/backend/app/api/conversations/router.py`, `__init__.py`; **Create:** `src/backend/app/services/conversation_service.py`; **Create model:** `src/backend/app/models/conversation.py`; **Modify:** `src/backend/app/services/book_data_manager.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py`, `src/backend/app/models/enums.py` (add ConversationKind, etc.) |
| AI-API-02 | ✅ | `GET /books/{b}/conversations/{id}` | Full thread + proposals. | Same files as AI-API-01 |
| AI-API-03 | ✅ | `PATCH /books/{b}/conversations/{id}` | Rename, toggle AI, switch model. | Same files |
| AI-API-04 | ✅ | `POST /books/{b}/conversations/{id}/messages` (SSE) | Streaming AI replies; Untitled → utility title + SSE `title`. | Same + `src/backend/app/services/model_factory.py` (streaming), `src/backend/app/core/event_hub.py` |
| AI-API-05 | ✅ | `POST /books/{b}/ai-jobs/run` | Execute saved job against scene; conversation title = job name. | Same + `src/backend/app/worker/job_worker.py`, `src/backend/app/services/placeholder_registry.py` (resolve) |
| AI-API-06 | ✅ | `POST /books/{b}/proposals/{id}/accept` | Apply AI edit after review. | **Create:** `src/backend/app/api/proposals/router.py`, `__init__.py`; **Create:** `src/backend/app/services/proposal_service.py`; **Modify:** `src/backend/app/services/scene_service.py` (content path for applied edits), `src/backend/app/main.py`, `src/backend/app/api/deps.py` |
| AI-API-07 | ✅ | `POST /books/{b}/proposals/{id}/reject` | Dismiss suggestion. | Same files as AI-API-06 |
| AI-API-08 | ✅ | `GET /books/{b}/jobs` | Job history by scene/status. | **Create:** `src/backend/app/api/jobs/router.py`, `__init__.py`; **Modify:** `src/backend/app/services/book_data_manager.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py`; **Create model:** `src/backend/app/models/job.py` |
| AI-API-09 | ✅ | `DELETE /books/{b}/conversations/{id}` | Hard-delete a mistaken thread; clears linked jobs' `conversationId`. | `src/backend/app/api/conversations/router.py`, `src/backend/app/services/conversation_service.py`, `src/backend/app/services/book_data_manager.py` |

### Services — AI layer

| ID | Status | Service | User story | Files |
|---|---|---|---|---|
| AI-SVC-01 | ✅ | ConversationService | Thread primitive for notes/chat/jobs; utility naming when Untitled; hard delete. | `src/backend/app/services/conversation_service.py` |
| AI-SVC-02 | ✅ | ProposalService | AI prose changes only via author accept. | **Create:** `src/backend/app/services/proposal_service.py` |
| AI-SVC-03 | ✅ | JobService + Worker | Background AI work; AI-Job conversation titled with definition name. | `src/backend/app/services/job_service.py`, `src/backend/app/worker/job_worker.py` |
| AI-SVC-04 | ✅ | EnrichmentService | Maintain metadata while writing; summary and character-matching are independent model calls against independent settings slots; escalations pass caller `title` (e.g. `who is {name}?`) and default to the character-parsing model. | `src/backend/app/services/enrichment_service.py` |
| AI-SVC-05 | ✅ | PlaceholderRegistry.resolve | Fill prompts with scene context at run time. | `src/backend/app/services/placeholder_registry.py` |
| AI-SVC-06 | ✅ | ModelFactory — full streaming | All providers usable in chat/jobs. | `src/backend/app/services/model_factory.py` |
| AI-SVC-07 | ✅ | LangChain read tools | AI reads book context during chat. | `src/backend/app/services/ai_tools/` |
| AI-SVC-08 | ✅ | LangChain propose tools → Proposal objects | AI never writes prose directly. | Same as AI-SVC-07 |
| AI-SVC-09 | ✅ | Edit-proposals JSON parse | Structured edit cards from jobs. | `src/backend/app/services/output_parsers.py`, `job_service.py` |
| AI-SVC-10 | ✅ | Metadata-proposals parse | AI-suggested field updates. | Same as above |
| AI-SVC-11 | ✅ | ContextAssembler + CURRENT SCENE | Chat/jobs bind `@current_scene` to editor parent scene; dedicated title prompt skips chat framing. | `src/backend/app/services/context_assembler.py`, `conversation_service.py`, `job_service.py` |
| AI-SVC-12 | ✅ | EscalationService (caller-supplied title) | Generic “ask the author” pipe; title comes from the caller, not hardcoded kinds. | `src/backend/app/services/escalation_service.py` |
| AI-SVC-13 | ✅ | Conversation title rules | Escalation = caller title; AI-Job = job name; chat = utility 3–5 word reply stored as-is (UI truncates). | Same + docs 04/05/06/08 |
| AI-SVC-14 | ✅ | AIOrchestrator | Single entry for invoke_once / stream + tool loop. | `src/backend/app/services/ai_orchestrator.py` |

### Frontend — Conversation Modal

> **Read:** doc 06 §10

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| CNV-FE-01 | ✅ | Conversation Modal shell | One surface for notes/chat/jobs. | **Create:** `src/frontend/src/features/conversation/ConversationModal.tsx`; **Create:** `src/frontend/src/api/conversations.ts`, `src/frontend/src/queries/conversations.ts`; **Modify:** `src/frontend/src/queries/keys.ts` |
| CNV-FE-02 | ✅ | Editable title | Rename threads; controlled field updates on SSE `title`. | Same as above |
| CNV-FE-03 | ✅ | AI switch + model select | Private notes then invite AI. | Same as above |
| CNV-FE-04 | ✅ | Message list | Readable transcript with model attribution. | Same as above |
| CNV-FE-05 | ✅ | Context excerpt quotes | See what selection was sent. | Same as above |
| CNV-FE-06 | ✅ | Streaming tokens + cursor | Read AI output as it arrives. | Same as above; uses SSE helper from `src/frontend/src/api/client.ts` (needs SSE extension) |
| CNV-FE-07 | ✅ | Collapsed job prompt | Long prompts tucked away. | Same as above |
| CNV-FE-08 | ✅ | Proposal cards (edit/meta/todo) | AI suggestions as tactile cards. | Same as above; **Create:** `src/frontend/src/api/proposals.ts` |
| CNV-FE-09 | ✅ | [Accept] / [Reject] per card | Explicit approval. | Same as above |
| CNV-FE-10 | ✅ | [Accept all (n)] sequential | Bulk accept with not-found surfacing. | Same as above |
| CNV-FE-11 | ✅ | Applied/rejected/not-found states | Clear outcomes per proposal. | Same as above |
| CNV-FE-12 | ✅ | Composer — Enter/Shift+Enter | Familiar chat input. | Same as above |
| CNV-FE-13 | ✅ | Close without prompt | No "save conversation?" anxiety. | Same as above |
| CNV-FE-14 | ✅ | Delete conversation | Confirm → DELETE → close modal; Notes/Jobs refresh. | `ConversationModal.tsx`, `api/conversations.ts` |
| CNV-FE-15 | ✅ | Title truncate + hover | Narrow Notes/Jobs lists show `…`; hover reveals full title. | `EditorPage.tsx`, `ConversationModal.tsx` |

### Frontend — SSE client

> **Read:** doc 06 §2, doc 04 §12
>
> **The event channel is not AI infrastructure** (doc 07 §24). `SSE-API-01`, `SSE-FE-01`, `SSE-FE-05`, `SSE-FE-07`, `INF-FE-09`, and `INF-FE-10` were built in **Phase 8** (Git), which was the first feature to need a push channel. They were only ever listed here because AI streaming was *assumed* to be the first consumer. The rows below that remain ⬜ are blocked on their own data layers (scenes enrichment, jobs, todos, compile), not on the channel.

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| SSE-FE-01 | ✅ | `useBookEvents(bookId)` hook | One EventSource per book; unknown event types ignored. *(Built in Phase 8.)* | `src/frontend/src/events/useBookEvents.ts`, `src/frontend/src/api/client.ts` |
| SSE-FE-02 | ✅ | `scene-updated` → patch scenes | Summary/character chips live. | **Modify:** `src/frontend/src/events/useBookEvents.ts`, `src/frontend/src/queries/scenes.ts`; **Depends on:** Phase 7 (enrichment) |
| SSE-FE-03 | ✅ | `job` → patch jobs | Job status live in accordion. | Same + `src/frontend/src/queries/jobs.ts` (create); **Depends on:** Phase 7 |
| SSE-FE-04 | ⬜ | `todos-created` → invalidate todos | New dependency todos immediately. | Same + `src/frontend/src/queries/todos.ts`; **Depends on:** Phase 6 |
| SSE-FE-05 | ✅ | `git-status` → patch git + badge | Commit nudge stays accurate, live. *(Built in Phase 8.)* | `src/frontend/src/events/useBookEvents.ts`, `src/frontend/src/App.tsx` (GitBadge) |
| SSE-FE-06 | ⬜ | `compile-done` → invalidate | Readiness refreshes after compile. | Same; **Depends on:** Phase 9 |
| SSE-FE-07 | ✅ | Reconnect + refetch | Recovery after dropped SSE: exponential backoff (1s→30s), invalidate `['git']` on reconnect since the channel replays nothing. | `src/frontend/src/api/client.ts`, `src/frontend/src/events/useBookEvents.ts` |
| SSE-FE-08 | ✅ | 10s `git/status` poll as a net | As an author, I want the badge to be right even if an event is dropped — a stale amber nudge is worse than none. Redundant with SSE by design; pauses while the tab is hidden (refetch-on-focus covers the return). | `src/frontend/src/queries/git.ts` |

### API — Events (backend)

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| SSE-API-01 | ✅ | `GET /books/{b}/events` (SSE) | Push channel for book changes. Generic per-book pub/sub in `core/` — **no AI dependency**; built in Phase 8. Keepalive frames; bounded queues drop rather than stall a writer. | `src/backend/app/api/events/router.py`, `src/backend/app/core/event_hub.py`, `src/backend/app/main.py`, `src/backend/app/api/deps.py` |
| SSE-API-02 | ✅ | `book-changed` internal event | As the system, I want a payload-free "something was written" signal that server-side consumers can react to, without clients needing to care. Consumed by `GIT-SVC-02` via the hub's global `subscribe_all` channel. | `src/backend/app/core/event_hub.py`, `src/backend/app/services/book_data_manager.py` |

---

## Phase 8 — Git

> **Read:** doc 04 §13, doc 06 §14, doc 06 §3 (badge), doc 07 §5, doc 08 J17

### API — GitService

> **Emission rule (doc 07 §27):** mutating endpoints (stage/unstage/commit/push/pull) recompute status and emit `git-status` **immediately, in-request** — the author is watching the Git page. *Incidental* dirtying from unrelated writes is handled by `GIT-SVC-02` instead. Git never runs on a write path.

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| GIT-API-01 | ✅ | `GET /books/{b}/git/status` | Dirty file list + ahead/behind + `summary`. Also serves the client's 10s poll. | `src/backend/app/api/git/router.py`, `src/backend/app/services/git_service.py` |
| GIT-API-02 | ✅ | `POST /books/{b}/git/stage` | Stage chosen files; emits `git-status`. | Same files |
| GIT-API-03 | ✅ | `POST /books/{b}/git/unstage` | Unstage mistakes; emits `git-status`. | Same files |
| GIT-API-04 | ✅ | `GET /books/{b}/git/diff` | Unified diffs; untracked files render as all-additions; binary → `{binary:true}`. | Same files |
| GIT-API-05 | ✅ | `POST /books/{b}/git/suggest-message` | AI commit message help; no commit-message model resolvable (own slot or utility fallback), or a failed call, → deterministic stats fallback. | Same + `src/backend/app/services/model_factory.py`, `settings_service.py` (`get_commit_message_model`) |
| GIT-API-06 | ✅ | `POST /books/{b}/git/commit` | Deliberate commit; 422 `nothing-staged`; emits `git-status`. | Same files |
| GIT-API-07 | ✅ | `POST /books/{b}/git/push` | Remote backup; 422 `no-remote`; git's own error verbatim. | Same files |
| GIT-API-08 | ✅ | `POST /books/{b}/git/pull` | Pull remote changes; conflicts hand off to the author's git tooling. | Same files |
| GIT-API-09 | ✅ | `GET /books/{b}/git/log` | Recent commit history. | Same files |
| GIT-API-10 | ✅ | `summary` on GitStatus | As an author, I want the badge to say what actually changed ("7-new, 1-updated, 3-deleted" / "all-changes-synced") rather than a bare count. | `src/backend/app/models/git.py`, `src/backend/app/services/git_service.py` (`_summarize`) |
| GIT-API-11 | ✅ | `branch` on GitStatus | As an author, I want to see which branch I'm committing to and where it stands against origin, so I'm never guessing. Read-only orientation — **not** branch management, which stays CLI territory (doc 07 §6). Detached HEAD → short sha. | `src/backend/app/models/git.py`, `src/backend/app/services/git_service.py` (`_branch_name`), `src/frontend/src/features/git/GitPage.tsx` |
| GIT-FIX-01 | ✅ | Untracked directories undercounted in `summary` | **Bug, found by testing against known truth.** `git status --porcelain` collapses an untracked *directory* to one line, so a folder of 5 new scenes read as "1-new" — and the count jumped when staged, because staging expands the directory. A badge whose number changes on staging is incoherent. Fixed with `-uall`; count is now stable across staging. | `src/backend/app/services/git_service.py` (`_read_status`) |
| GIT-SVC-01 | ✅ | GitService | Git ops; `status()` is pure computation and emits nothing, so the request path and the worker each decide when to broadcast. Lazy `git` import + `repo.close()` in `finally` (Windows handle discipline). | `src/backend/app/services/git_service.py` |
| GIT-SVC-02 | ✅ | **GitStatusWorker** (dedicated debounced worker) | As an author, I want the badge to keep itself current while I write, without `git status` ever running on my autosave. One standing asyncio task consumes `book-changed` off the hub's global channel and re-checks git after a **pure 5s debounce** per book (a burst of saves keeps resetting it). | `src/backend/app/worker/git_status_worker.py`, `src/backend/app/main.py` (lifespan start/cancel), `src/backend/app/api/deps.py` |
| GIT-SVC-03 | ✅ | `book-changed` hook in BookDataManager | As the system, I want one integration point for post-write reactions: every mutating service already funnels through `BookDataManager.save_*`, so a single payload-free emit there covers scenes, structure, plotlines, config, and ui.json — no service needs its own hook. | `src/backend/app/services/book_data_manager.py`, `src/backend/app/services/book_registry.py` |

### Frontend — Git page + badge

> **Read:** doc 06 §14, doc 06 §3

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| GIT-FE-01 | ✅ | Git route + nav live | Deliberate commit workspace; 60/40 two-column layout. | `src/frontend/src/features/git/GitPage.tsx`, `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx` (nav live), `src/frontend/src/api/git.ts`, `src/frontend/src/queries/git.ts` |
| GIT-FE-02 | ✅ | **Top-bar git badge** (amber) | Persistent nudge to commit, showing the `summary` ("4-new, 3-updated · Commit now?"). Renders nothing when clean. | `src/frontend/src/App.tsx` (`GitBadge`) |
| GIT-FE-03 | ✅ | Badge click → git page | One click from nudge to ritual. | Same as above |
| GIT-FE-04 | ✅ | Changes list | Per-file staging control; checkbox + status letter + mono path. `staged` means *fully* staged, so a ticked box honestly means "all of this goes in the commit". | `src/frontend/src/features/git/GitPage.tsx` |
| GIT-FE-05 | ✅ | Row click → diff panel | Review before committing (row click ≠ checkbox click). | Same as above |
| GIT-FE-06 | ✅ | [Stage all] | Common single-author case. | Same as above |
| GIT-FE-07 | ✅ | Diff panel | Readable diffs without terminal; additions `--ok`, deletions `--danger`, hunks `--accent`; "Binary file" case. | Same as above |
| GIT-FE-08 | ✅ | Commit message textarea | Own the commit message. | Same as above |
| GIT-FE-09 | ✅ | [✨ Suggest message] | AI draft help; stats fallback arrives with the faint note "Written from file stats". | Same as above |
| GIT-FE-10 | ✅ | [Commit staged files] | Enabled iff ≥1 staged ∧ message non-empty. | Same as above |
| GIT-FE-11 | ✅ | Commit toast with shorthash | Confirmation day is saved; badge clears at once (no debounce on explicit actions). | Same as above |
| GIT-FE-12 | ✅ | History strip | Recent commits: shorthash · message · relative time. | Same as above |
| GIT-FE-13 | ✅ | [Push] / [Pull] when hasRemote | Basic remote sync; git's error verbatim in a danger panel + "Resolve with your git tooling". Buttons carry the counts (`Push ↑2` / `Pull ↓1`) and only render when a remote exists. | Same as above |
| GIT-FE-14 | ✅ | Empty / no-repo states | "Nothing has changed since your last commit"; a book folder without `.git` says so plainly instead of erroring. | Same as above |
| GIT-FE-15 | ✅ | Branch line in page header | As an author, I want "⎇ main · in sync with origin" (or "2 to push · 1 to pull", or "no remote") beside the page title, so I always know which branch I'm on and whether origin has my work. | Same as above |

---

## Phase 9 — Compilation

> **Read:** doc 04 §14, doc 06 §12 (readiness strip on Metadata), doc 07 §17, doc 08 J18

### API — CompileService

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| CMP-API-01 | ⬜ | `GET /books/{b}/compile/check` | Errors/warnings before compile. | **Create:** `src/backend/app/api/compile/router.py`, `__init__.py`; **Create:** `src/backend/app/services/compile_service.py`; **Modify:** `src/backend/app/main.py`, `src/backend/app/api/deps.py`; **Create model:** add `CheckItem`, `CompileReport` to models; **Depends on:** `src/backend/app/services/chain_service.py`, `src/backend/app/services/structure_service.py` |
| CMP-API-02 | ⬜ | `POST /books/{b}/compile` | Gated build to `compiled-book/`. | Same + `src/backend/app/core/event_hub.py` (emit compile-done) |
| CMP-SVC-01 | ⬜ | CompileService — CheckItem validation | Structural rules before output. | **Create:** `src/backend/app/services/compile_service.py` |
| CMP-SVC-02 | ⬜ | Compile — wipe + regenerate | Fresh compiled output. | Same as above |
| CMP-SVC-03 | ⬜ | `***` breaks, heading-only chapters | Readable manuscript structure. | Same as above |

### Frontend — Compile UX

> **Read:** doc 06 §12

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| CMP-FE-01 | ⬜ | CheckItem deep links | Every error jumps to fix. | **Modify:** `src/frontend/src/features/metadata/MetadataPage.tsx`; uses `src/frontend/src/api/compile.ts` |
| CMP-FE-02 | ⬜ | 409 → auto-expand report | Blockers shown on compile fail. | Same as above |
| CMP-FE-03 | ⬜ | Build-report dialog | Summary of generated files. | Same as above |
| CMP-FE-04 | ⬜ | Success toast + link to Git | Compiled output is uncommitted. | Same as above |

---

## Phase 10 — Polish & global shell gaps

> **Read:** doc 06 §1.4–§1.5, doc 06 §3, doc 06 §4, doc 07 §21

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| POL-01 | ✅ | Theme toggle | Comfortable reading in any lighting. | `src/frontend/src/App.tsx`, `src/frontend/src/theme.ts` |
| POL-02 | ✅ | Semantic CSS tokens + dark | One token switch themes the app. | `src/frontend/src/styles/tokens.css`, `src/frontend/tailwind.config.js` |
| POL-03 | ✅ | Disconnected banner | Know when backend stopped. | `src/frontend/src/App.tsx` |
| POL-04 | ✅ | Friendly 404 | Bad URLs offer a way back. | `src/frontend/src/features/NotFound.tsx` |
| POL-05 | ⬜ | Left nav collapse chevron | Reclaim horizontal space. | **Modify:** `src/frontend/src/App.tsx` (LeftNav) |
| POL-06 | ⬜ | Nav tooltips in rail mode | Icons labeled on hover. | Same as above |
| POL-07 | ⬜ | Shared **Popover** component | Consistent anchored panels. | **Create:** `src/frontend/src/components/Popover.tsx` |
| POL-08 | ⬜ | Shared **Badge** component | Consistent count/attention pills. | **Create:** `src/frontend/src/components/Badge.tsx` |
| POL-09 | ⬜ | Confirm dialogs | Confirms only for irreversible acts. | **Modify:** various pages that currently use `window.confirm` |
| POL-10 | ⬜ | `prefers-reduced-motion` respect | Reduced animation when OS requests. | **Modify:** `src/frontend/src/styles/index.css` |
| POL-11 | ⬜ | Book home section links fully live | All workspace cards link to real pages. | **Modify:** `src/frontend/src/features/book/BookPage.tsx` |
| POL-12 | 🔄 | Graph route alignment | Graph as book home per spec. | **Modify:** `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx` (optional) |

---

## Phase 11 — Book Resources & book-level AI chat

> **Read:** doc 01 §write-permission model, doc 03 §resources/ — no index, doc 04 §15

### API — ResourceService, book-level conversations

| ID | Status | Endpoint / item | User story | Files |
|---|---|---|---|---|
| RES-API-01 | ✅ | `GET /books/{b}/resources` | List files kept beside the book. | `src/backend/app/api/resources/router.py`, `src/backend/app/services/resource_service.py` |
| RES-API-02 | ✅ | `POST /books/{b}/resources` (multipart) | Upload any file type, up to 25 MB; collision suffixes rather than overwrites. | Same files |
| RES-API-03 | ✅ | `GET /books/{b}/resources/{filename}/content` | Download a resource. | Same files |
| RES-API-04 | ✅ | `DELETE /books/{b}/resources/{filename}` | Remove a resource — moves to `.trash/`, never unlinks. | Same files |
| RES-API-05 | ✅ | `GET /books/{b}/conversations` | List book-parented chat threads (the gap that made a book-level chat possible — everything else in the conversation stack was already parent-agnostic). | `src/backend/app/api/conversations/router.py`, `src/backend/app/services/conversation_service.py` (`list_for_book`) |
| RES-SVC-01 | ✅ | `ResourceService` | CRUD for `resources/`; module-level helpers (`safe_resource_path`, `scan_resources`, `is_text_resource`) reused by the AI read tools with no new tool-registry dependency. | `src/backend/app/services/resource_service.py` |
| RES-SVC-02 | ✅ | `propose_resource_create` + `list_resources`/`get_resource` tools | AI can read resources freely; creating one requires an author-accepted proposal — a resource file is neither prose nor bookkeeping, so no execute tool exists for it. | `src/backend/app/services/ai_tools/propose.py`, `src/backend/app/services/ai_tools/read.py`, `src/backend/app/services/proposal_service.py` (`_apply_resource_create`) |

### Frontend — Resources page

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| RES-FE-01 | ✅ | Resources route + nav live | A home for research/reference files and the book-level chat. | `src/frontend/src/features/resources/ResourcesPage.tsx`, `src/frontend/src/router.tsx`, `src/frontend/src/App.tsx`, `src/frontend/src/features/book/BookPage.tsx` |
| RES-FE-02 | ✅ | File list + upload dropzone + delete | Upload, browse, download, delete files beside the book. | `src/frontend/src/features/resources/ResourcesPage.tsx`, `src/frontend/src/api/resources.ts`, `src/frontend/src/queries/resources.ts` |
| RES-FE-03 | ✅ | [Chat] → book-level `ConversationModal` | Ask the AI about the whole book, no scene in context — reuses the existing modal unchanged (`sceneId` was already optional). | Same + `src/frontend/src/api/conversations.ts` (`listBookConversations`), `src/frontend/src/queries/conversations.ts` (`useBookConversations`) |
| RES-FE-04 | ✅ | `resource-create` proposal card | See the AI's drafted file (name + full content preview) before it's written. | `src/frontend/src/features/conversation/ConversationModal.tsx` |

---

## Phase 12 — Scene Audio Drama ✅

> **Status:** complete (2026-07-18). **Read:** [`docs/audio-system.md`](audio-system.md) (authoritative behavior spec — status ✅ implemented), doc 01 §write-permission, doc 03 §audio/, doc 04 §16, doc 05 placeholders + `audio-script` output type, doc 06 Editor / Characters / Metadata Book / Conversation Modal.

### Data model & settings

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| AUD-MODEL-01 | ✅ | `models/audio.py` — AudioManifest, Speaker, AudioSequenceItem, VoiceSettings | Persist a scene's audio script + synthesis links. | `src/backend/app/models/audio.py` |
| AUD-MODEL-02 | ✅ | Enums: `OutputType.audio_script`, `ProposalType.audio_script_create`, line/synth status enums | Wire script jobs into existing AI output parsing. | `src/backend/app/models/enums.py` |
| AUD-MODEL-03 | ✅ | `AudioScriptCreatePayload` | Accept a whole-script proposal. | `src/backend/app/models/proposal.py` |
| AUD-MODEL-04 | ✅ | `voiceId`/`voiceName` on Character models | Cast each character once for the book. | `src/backend/app/models/character.py` |
| AUD-MODEL-05 | ✅ | `narratorVoiceId`/`narratorVoiceName` on book config | Cast the narrator at book level. | `src/backend/app/models/book.py` |
| AUD-SET-01 | ✅ | ElevenLabs fields on `AppData` + `VoiceInfo` | Store optional key + cached voice library. | `src/backend/app/models/settings.py` |
| AUD-SET-02 | ✅ | `core/secrets.py` — `resolve_secret(..., default_env="ELEVENLABS_API_KEY")` | Env key works without UI paste; models still resolve `${ENV_VAR}`. | `src/backend/app/core/secrets.py`, `model_factory.py` |

### Gitignore (book)

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| AUD-GIT-01 | ✅ | Scaffold `.gitignore` with `*.tmp` + `*.mp3`; ensure-on-open | Generated mp3s never enter the book repo. | `book_service.py` |
| AUD-GIT-02 | ✅ | `GET/PUT /books/{b}/gitignore` + Metadata Book UI | Author can see/edit ignore patterns; `*.mp3`/`*.tmp` always re-injected if missing. | books API, `MetadataPage.tsx` |

### Services & worker

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| AUD-SVC-01 | ✅ | `AudioService` — paths, merge `save_manifest`, synthesize_line, stitch, update_line | Single writer for ElevenLabs + audio folder. | `audio_service.py` |
| AUD-SVC-02 | ✅ | `parse_audio_script` + `AUDIO_SCRIPT_FORMAT_INSTRUCTIONS` | Model reply → one script proposal. | `output_parsers.py` |
| AUD-SVC-03 | ✅ | `AiJobService.prepare` audio-script branch | Format instructions appended like edit/metadata jobs. | `ai_job_service.py` |
| AUD-SVC-04 | ✅ | Placeholders `@scene_speakers` + `@existing_audio_script` | Directing prompt gets casting ids + prior manifest. | `placeholder_registry.py` |
| AUD-SVC-05 | ✅ | ConversationService dispatch for `audio_script` | Scene-parented job parses into proposals. | `conversation_service.py` |
| AUD-SVC-06 | ✅ | `ProposalService._apply_audio_script_create` (merge) | Accept diff-applies; preserves unchanged `renderedFile`. | `proposal_service.py` |
| AUD-SVC-07 | ✅ | SettingsService ElevenLabs key + voice sync | Sync library once; GET voices is cached. | `settings_service.py`, settings router |
| AUD-SVC-08 | ✅ | `suggest_voice` one-shot | AI suggests a voice; author still Saves. | structure/characters API |
| AUD-WRK-01 | ✅ | `AudioWorker` + SSE `audio-progress` | Batch/single-line synth with progress. | `audio_worker.py`, `main.py`, `deps.py` |
| AUD-DEP-01 | ✅ | `elevenlabs`, `pydub` + ffmpeg warning | TTS + stitch deps; missing ffmpeg is legible. | `requirements.txt`, `main.py` |

### API

| ID | Status | Endpoint | User story | Files |
|---|---|---|---|---|
| AUD-API-01 | ✅ | Scene audio CRUD/generate/serve | Manifest, line edit, generate, FileResponse mp3s. | `api/audio/router.py` |
| AUD-API-02 | ✅ | `/settings/elevenlabs` + voices sync/list | Configure key and sync library. | settings router |
| AUD-API-03 | ✅ | `POST .../characters/{id}/voice/suggest` | Suggest without writing. | characters router |

### Frontend

| ID | Status | Control | User story | Files |
|---|---|---|---|---|
| AUD-FE-01 | ✅ | Editor toolbar **Audio** → Audio Modal | Listen/edit on the scene itself (not Scene Modal). | `EditorPage.tsx`, `features/audio/AudioModal.tsx` |
| AUD-FE-02 | ✅ | `api/audio.ts` + `queries/audio.ts` + `keys.audio` | Typed client + cache. | frontend api/queries |
| AUD-FE-03 | ✅ | Audio Modal: edit rows, per-line play/regen, Play scene playlist | Edit script; regen one line; playlist with gaps. | `features/audio/` |
| AUD-FE-04 | ✅ | `audio-script-create` proposal card | Review merge preview before Accept. | `ConversationModal.tsx` |
| AUD-FE-05 | ✅ | `audio-progress` in `useBookEvents` | Progress without refetch spam. | `useBookEvents.ts` |
| AUD-FE-06 | ✅ | Character Sheet voice picker + preview + Suggest | Cast voices before Accept can succeed. | `CharactersPage.tsx` |
| AUD-FE-07 | ✅ | Metadata Book — narrator voice + gitignore | Narrator casting + ignore editor. | `MetadataPage.tsx` |
| AUD-FE-08 | ✅ | AI Settings — ElevenLabs + Sync | Optional key + voice library. | `AISettingsPage.tsx` |
| AUD-FE-09 | ✅ | AI-Jobs — `audio-script` output type | Author can define the directing job. | `JobModal.tsx` |

---

## Shared frontend infrastructure

| ID | Status | Item | User story | Files |
|---|---|---|---|---|
| INF-FE-01 | ✅ | Typed API client | One function per endpoint. | `src/frontend/src/api/client.ts` |
| INF-FE-02 | ✅ | TanStack Query + key factory | Consistent cache keys. | `src/frontend/src/queries/keys.ts` |
| INF-FE-03 | ✅ | Modal component | Consistent modal behavior. | `src/frontend/src/components/Modal.tsx` |
| INF-FE-04 | ✅ | Toast provider | Brief confirmations, persistent errors. | `src/frontend/src/components/Toast.tsx` |
| INF-FE-05 | ✅ | SearchableSelect | Searchable dropdowns. | `src/frontend/src/components/SearchableSelect.tsx` |
| INF-FE-06 | ✅ | BlockedDeletionDialog | 409 blockers mapped to fix locations. | `src/frontend/src/components/BlockedDeletionDialog.tsx` |
| INF-FE-07 | ✅ | UI primitives (Button, Field, Input) | Consistent form controls. | `src/frontend/src/components/ui.tsx` |
| INF-FE-08 | ✅ | ConfirmDialog | Reusable confirm dialog for destructive/irreversible acts (doc 06 §1.5). Danger-styled confirm button. | `src/frontend/src/components/ConfirmDialog.tsx` |
| INF-FE-08a | ✅ | `ApiError.blockedByMessage` | As an author, when a delete is blocked by references (409), I want the error to tell me exactly what's blocking it (e.g. "Blocked by: 2 soft relationships, 1 conversation") instead of a generic message. | `src/frontend/src/api/client.ts` |
| INF-FE-09 | ✅ | SSE helpers in `api/` | Typed EventSource wrapper (`subscribeToBookEvents`) with exponential-backoff reconnect. *(Built in Phase 8.)* | `src/frontend/src/api/client.ts` |
| INF-FE-10 | ✅ | `events/useBookEvents` | SSE wired on book entry, from `App.tsx`. *(Built in Phase 8.)* | `src/frontend/src/events/useBookEvents.ts` |

---

## User journey traceability (doc 08)

| Journey | Title | Status | Blocked by (phase) |
|---|---|---|---|
| J1 | Launch | ⬜ | Phase 1 (launchers, filelock, worker) |
| J2 | Home page loads | ✅ | — |
| J3 | User Settings | ✅ | — |
| J4 | AI Settings | ✅ | — |
| J5 | AI-Jobs | ✅ | — |
| J6 | Add a book | ✅ | — |
| J7 | Entering the book | 🔄 | Full nav / unfinished sections |
| J8 | First scene | ✅ | — |
| J9 | Second scene, soft | ✅ | — |
| J10 | Structure (part + chapter) | 🔄 | Phase 6 (parts/chapters/plotlines done; characters/deps/todos pending) |
| J11 | Editor + autosave | ✅ | — |
| J12 | Enrichment fires | ✅ | Phase 7 |
| J13 | Chat from selection | ✅ | Phase 7 |
| J14 | Editorial Review job | ✅ | Phase 7 |
| J15 | Accepting an edit | ✅ | Phase 7 |
| J16 | Dependency + todo | ⬜ | Phase 6 |
| J16.5 | Ambient — the badge keeps itself honest | ✅ | — |
| J17 | Git deliberate save | ✅ | — |
| J18 | Compilation | ⬜ | Phase 9 |
| J19 | Scene audio drama | ✅ | Phase 12 |

---

## Recommended build order (next sessions)

**Done:** ~~Phase 6a~~ · ~~Phase 8~~ · ~~Phase 11~~ (Resources + book chat) · ~~Phase 12~~ (Scene Audio Drama).

1. **Phase 9** — CompileService + readiness strip + compile flow
2. **Phase 1 finish** — Launchers + filelock
3. **Phase 10** — Polish (nav collapse, Popover, Badge, confirm dialogs, reduced motion)

> Older Phase 6b/7 items that remain open stay tracked in their phase tables above.

---

*Update this file when items change status. ✅ = end-to-end for that layer (API + UI where applicable).*
