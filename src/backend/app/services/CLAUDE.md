# services — business logic

All logic lives here. Routers delegate; services enforce business rules, own the per-book asyncio mutation lock, and drive persistence via BookDataManager. Reads take no lock; mutations replace collections rather than tweaking in place so readers never see half-mutated state.

Parent: [app](../CLAUDE.md). Spec: [04 API §1.3](../../../../docs/claude-tech-specs/04-api-reference.md) (service table), plus docs 03/05.

## Service catalog

| Service | Responsibility |
|---|---|
| `SettingsService` | `app.json` read/write; model-config + AI-Job validation |
| `PlaceholderRegistry` | Defines placeholders; validates prompts; resolves `@tokens` at run time against an explicit `scene_id` (doc 05) |
| `ContextAssembler` | Builds LangChain message lists; injects CURRENT SCENE when callers pass parent scene; resolves `@tokens` in user messages for the model only (doc 05) |
| `BookScanner` | Scans `booksHome`; caches shelf; reads each `config/book.json` |
| `BookService` | Book creation (scaffold, git init, initial commit), rename/cover, folder rename |
| `BookDataManager` | One per open book. Loads `db/*.json` + `config/book.json` into memory; owns the book's asyncio mutation lock; atomic write-through; conversation files + derived index; `ui.json`. Also owns the per-scene folder (`scenes/{id}/meta.json` / `bookkeeping.json` / `dependencies.json` / `relationships.json`) — lazy-loaded and cached per scene, with a live in-memory reverse index for dependencies, and transparent one-time migration of old-shape (pre-split) `db/scenes.json`. Every `save_*` fires `book-changed` on the EventHub — the single chokepoint every mutating service already funnels through, so no service needs its own post-write hook |
| `ChainService` | Hard-chain algebra: splice, heal, walk, seq/placement computation, contiguity + completeness checks. Reads only `id`/`status`/`previousSceneId`/`nextSceneId` off scenes — unaffected by the master/per-scene split |
| `SceneService` | Scene CRUD; routes each field of a `SceneUpdate` to the master table, `meta.json`, or `bookkeeping.json` depending on which it belongs to, and assembles the flat `Scene` API response back out of the three (doc 03); content saves (hash, word count — bookkeeping.json only, never touches the master table); dependency-todo fanout; enrichment settle timers; file naming/renames |
| `StructureService` | Parts/chapters linked lists; move-before/after rewiring; blocked deletions; plotlines; characters (uniqueness) |
| `ConversationService` | Conversation lifecycle; message append; utility-model title when Untitled (dedicated prompt; reply stored as-is); passes parent scene into ContextAssembler; SSE streaming via AIOrchestrator; hard delete |
| `ProposalService` | Locate/apply/reject proposals — the **only** code path that mutates on behalf of AI output (plus enrichment exact-match writes) |
| `JobService` + `JobWorker` | `jobs.json` queue; resolve job placeholders → ContextAssembler → AIOrchestrator; standing worker (per-book FIFO, ≤2 global) |
| `EnrichmentService` | Settle timer + clear/unclear bookkeeping. Scene-summary and character-parsing are two independent model calls against independently-configured models, each writing straight to `scenes/{id}/bookkeeping.json` — never the master table. Unclear → EscalationService, defaulting to the character-parsing model |
| `EscalationService` | Unclear → seeded chat conversation |
| `AIOrchestrator` / `ModelFactory` | Model invoke_once / structured / stream + tool loop |
| `ToolRegistry` | Read tools (execute) + propose tools (accumulate proposals) |
| `GitService` | GitPython wrapper: status/stage/unstage/diff/commit/push/pull/log. `status()` builds the badge's `summary` string (`"all-changes-synced"` / `"7-new, 1-updated, 3-deleted"`) and emits nothing — callers decide when to broadcast. Mutating ops emit `git-status` immediately in-request; incidental dirtying is picked up by the [git-status worker](../worker/CLAUDE.md) instead. Never run inline on a write path |
| `CompileService` | Completeness check (errors/warnings); build to `compiled-book/` |
| `EventHub` | Per-book SSE pub/sub (lives in [core](../core/CLAUDE.md)); all services emit through it |

## Key invariants

- **Prose hard rule:** only `SceneService` content path and `ProposalService` (edit apply, author-triggered) write scene `.md` files. AI write-tools only emit proposal objects.
- **Single writer / lock:** every mutation runs under the target book's asyncio lock (`app.json` has its own).
- **Atomic persistence:** serialize → `{file}.tmp` → flush + fsync → `os.replace`; POSIX also fsyncs the directory. Never overwrite a file that failed to parse at load (quarantine to `{file}.corrupt-{ts}`).
