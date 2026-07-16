# worker — background asyncio tasks

The background execution layer. Independent standing asyncio tasks started at app startup: the job worker drains per-book job queues; the git-status worker keeps the top-bar badge honest. Per-scene settle timers coalesce enrichment after content saves.

Parent: [app](../CLAUDE.md). Spec: [05 AI System](../../../../docs/claude-tech-specs/05-ai-system.md) (worker + enrichment), [04 §11 Jobs](../../../../docs/claude-tech-specs/04-api-reference.md), [02 §backend-internal-architecture](../../../../docs/claude-tech-specs/02-architecture-and-launcher.md) (git-status worker).

## Files here

- **`git_status_worker.py`** — `GitStatusWorker`: one standing asyncio task for the whole process (**not** per-book, **not** a separate OS process — doc 07 §25). Subscribes to [EventHub](../core/CLAUDE.md)'s global channel (`subscribe_all`) and consumes the internal `book-changed` signal. Holds a **pure 5s debounce per book** in a `{bookId: asyncio.Task}` dict: each `book-changed` cancels the pending timer and starts a fresh one, so the check only runs once writes go quiet for 5s (doc 07 §26 — a throttle was considered and rejected). On fire → `GitService.status(bookId)` → emit `git-status`. **Why it exists:** running `git status` inline on every autosave would add subprocess latency to the one path that must never stutter — typing.
- **Job worker** — one asyncio task; polls loaded books' in-memory queues. Concurrency **1 per book, ≤2 global**, per-book FIFO. Persists status transitions to `db/jobs.json` and emits `job` SSE events. Failures → status `failed` + error string (visible in the AI Jobs pane; no auto-retry).
- **Settle timers** — per-scene asyncio timers. Every content save with a changed hash (re)sets a 60s timer. On fire → queue one `system` enrichment job scoped by the book's bookkeeping toggles (`summaryOnSave`, `charactersOnSave`; both off → nothing). A save while queued replaces the queued job (never two per scene). Navigation away settles immediately.

Both the git-status debounce and the enrichment settle timer follow the same discipline: expensive work is deferred behind a quiet period and never blocks the save.

## What the git-status worker does *not* handle

Explicit git actions (stage/unstage/commit/push/pull) recompute status and emit `git-status` **immediately, in-request** from [GitService](../services/CLAUDE.md) — they never touch this worker (doc 07 §27). The worker exists only for *incidental* dirtying from unrelated writes, where nobody is watching a screen.

## Job types

- **User jobs** — AI-Job runs (scope `full`/`selection`), linked to a conversation. Worker resolves the prompt template (PlaceholderRegistry), appends format instructions for `edit`/`metadata` output types, posts a system-authored first message, streams the model with tools into the conversation, parses fenced JSON into proposals. See [conversations API](../api/conversations/CLAUDE.md).
- **System jobs** — enrichment (scope `summary`/`characters`/`both`), utility model. Summary → overwrite `scene.summary`. Characters → set `characterIds` to matched **existing** characters only (never creates records; unmatched names → `result.unrecognizedNames`). Emits `scene-updated`. On-demand `POST /scenes/{id}/enrich` runs regardless of toggles.

## Toggle semantics (doc 05)

Toggle ON = AI owns the field and always wins on save (no freeze flags). Want a hand-written summary? Flip it off.
