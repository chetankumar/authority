# app — FastAPI application package

The FastAPI app. Routers hold no logic — they validate via Pydantic and delegate to services. Services own the per-book asyncio mutation lock and are the only code that mutates state.

Parent: [backend](../CLAUDE.md). Specs: [04 API §1.3](../../../docs/claude-tech-specs/04-api-reference.md).

## Files to create here

- `main.py` (or `app.py`) — FastAPI instance, router registration, static SPA mount + index fallback, startup/shutdown (filelock, app.json load, worker start), logging setup.

## Package map

| Directory | Responsibility |
|---|---|
| [`api/`](api/CLAUDE.md) | Routers per resource area + shared API conventions (error envelope, SSE, mutation lifecycle) |
| [`services/`](services/CLAUDE.md) | Business logic: SettingsService, BookScanner, BookService, BookDataManager, ChainService, SceneService, StructureService, ConversationService, AiJobService, ProposalService, ResourceService, EnrichmentService, AIOrchestrator/ModelFactory, GitService, CompileService, PlaceholderRegistry |
| [`models/`](models/CLAUDE.md) | Pydantic shared objects + enums (doc 04 §2) and on-disk schemas (doc 03) |
| [`core/`](core/CLAUDE.md) | Config, logging, single-instance lock, atomic write helper, per-book asyncio locks, EventHub (SSE pub/sub) |
| [`worker/`](worker/CLAUDE.md) | The single asyncio job worker; per-scene settle timers; enrichment run |

## Mutation lifecycle (every write endpoint, doc 04 §1.3)

router → Pydantic validation → service acquires the book's asyncio lock → read in-memory state → validate business rules → mutate copies → BookDataManager persists changed files atomically (`.tmp` + fsync + `os.replace`) → BookDataManager emits `book-changed` → release lock → response. **Reads take no lock.**

Git is **not** in that path. `book-changed` is a payload-free signal; the [git-status worker](worker/CLAUDE.md) picks it up and re-checks git after a 5s debounce, off the request (doc 07 §25). Only explicit git actions emit `git-status` in-request.
