# services — business logic

All logic lives here. Routers delegate; services enforce business rules, own the per-book asyncio mutation lock, and drive persistence via BookDataManager. Reads take no lock; mutations replace collections rather than tweaking in place so readers never see half-mutated state.

Parent: [app](../CLAUDE.md). Spec: [04 API §1.3](../../../../docs/claude-tech-specs/04-api-reference.md) (service table), plus docs 03/05.

## Service catalog

| Service | Responsibility |
|---|---|
| `SettingsService` | `app.json` read/write; model-config + AI-Job validation |
| `PlaceholderRegistry` | Defines placeholders; validates prompts; resolves `@tokens` at run time (doc 05) |
| `BookScanner` | Scans `booksHome`; caches shelf; reads each `config/book.json` |
| `BookService` | Book creation (scaffold, git init, initial commit), rename/cover, folder rename |
| `BookDataManager` | One per open book. Loads `db/*.json` + `config/book.json` into memory; owns the book's asyncio mutation lock; atomic write-through; conversation files + derived index; `ui.json`. Every `save_*` fires `book-changed` on the EventHub — the single chokepoint every mutating service already funnels through, so no service needs its own post-write hook |
| `ChainService` | Hard-chain algebra: splice, heal, walk, seq/placement computation, contiguity + completeness checks |
| `SceneService` | Scene CRUD; content saves (hash, word count); dependency-todo fanout; enrichment settle timers; file naming/renames |
| `StructureService` | Parts/chapters linked lists; move-before/after rewiring; blocked deletions; plotlines; characters (uniqueness) |
| `ConversationService` | Conversation lifecycle; message append; model context assembly; streaming orchestration; proposal parsing |
| `ProposalService` | Locate/apply/reject proposals — the **only** code path that mutates on behalf of AI output |
| `JobService` + Worker | `jobs.json` queue; single asyncio worker (per-book FIFO, concurrency 1/book, ≤2 global); status transitions |
| `EnrichmentService` | System bookkeeping job: summary + character mapping (never creates characters) |
| `AIService` / `ModelFactory` | `ModelConfig → LangChain BaseChatModel`; tool binding; `${ENV}` key resolution; streaming |
| `GitService` | GitPython wrapper: status/stage/unstage/diff/commit/push/pull/log. `status()` builds the badge's `summary` string (`"all-changes-synced"` / `"7-new, 1-updated, 3-deleted"`) and emits nothing — callers decide when to broadcast. Mutating ops emit `git-status` immediately in-request; incidental dirtying is picked up by the [git-status worker](../worker/CLAUDE.md) instead. Never run inline on a write path |
| `CompileService` | Completeness check (errors/warnings); build to `compiled-book/` |
| `EventHub` | Per-book SSE pub/sub (lives in [core](../core/CLAUDE.md)); all services emit through it |

## Key invariants

- **Prose hard rule:** only `SceneService` content path and `ProposalService` (edit apply, author-triggered) write scene `.md` files. AI write-tools only emit proposal objects.
- **Single writer / lock:** every mutation runs under the target book's asyncio lock (`app.json` has its own).
- **Atomic persistence:** serialize → `{file}.tmp` → flush + fsync → `os.replace`; POSIX also fsyncs the directory. Never overwrite a file that failed to parse at load (quarantine to `{file}.corrupt-{ts}`).
