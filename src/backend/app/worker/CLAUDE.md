# worker — job worker, settle timers, enrichment execution

The background execution layer. A single asyncio task started at app startup drains per-book job queues; per-scene settle timers coalesce enrichment after content saves.

Parent: [app](../CLAUDE.md). Spec: [05 AI System](../../../../docs/claude-tech-specs/05-ai-system.md) (worker + enrichment), [04 §11 Jobs](../../../../docs/claude-tech-specs/04-api-reference.md).

## Files to create here

- **Job worker** — one asyncio task; polls loaded books' in-memory queues. Concurrency **1 per book, ≤2 global**, per-book FIFO. Persists status transitions to `db/jobs.json` and emits `job` SSE events. Failures → status `failed` + error string (visible in the AI Jobs pane; no auto-retry).
- **Settle timers** — per-scene asyncio timers. Every content save with a changed hash (re)sets a 60s timer. On fire → queue one `system` enrichment job scoped by the book's bookkeeping toggles (`summaryOnSave`, `charactersOnSave`; both off → nothing). A save while queued replaces the queued job (never two per scene). Navigation away settles immediately.

## Job types

- **User jobs** — AI-Job runs (scope `full`/`selection`), linked to a conversation. Worker resolves the prompt template (PlaceholderRegistry), appends format instructions for `edit`/`metadata` output types, posts a system-authored first message, streams the model with tools into the conversation, parses fenced JSON into proposals. See [conversations API](../api/conversations/CLAUDE.md).
- **System jobs** — enrichment (scope `summary`/`characters`/`both`), utility model. Summary → overwrite `scene.summary`. Characters → set `characterIds` to matched **existing** characters only (never creates records; unmatched names → `result.unrecognizedNames`). Emits `scene-updated`. On-demand `POST /scenes/{id}/enrich` runs regardless of toggles.

## Toggle semantics (doc 05)

Toggle ON = AI owns the field and always wins on save (no freeze flags). Want a hand-written summary? Flip it off.
