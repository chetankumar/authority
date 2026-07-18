# worker — background tasks

Parent: [backend](../../CLAUDE.md). Spec: [doc 05](../../../../docs/claude-tech-specs/05-ai-system.md).

## Conversation worker

Single asyncio task started in `main.py` lifespan (`conversation_worker.py`). Per-book FIFO, concurrency 1 per book (≤2 global). Drains conversations sitting at status `queued` — oldest first, found by an in-memory scan of the derived index (`BookDataManager.list_conversations_by_status`, no files opened) — and runs each by calling `ConversationService.send_message(book_id, id)` with **no body**, so it generates against the thread's existing prompt rather than inventing a user turn. Nobody is watching, so the SSE events are drained to nowhere; the conversation itself is where the result lands. `ConversationService` sets terminal status (`done`/`failed`/`waiting`); the worker adds no retry.

This exists because automatic leave-scene enrichment is fire-and-forget: the author has navigated away, no modal is open. Explicit AI-Job runs do **not** come through here — they run in-request when the author sends in the open modal.

## Enrichment

- **No settle timers.** Content autosave never schedules enrichment.
- **Leave-scene:** `POST /scenes/{id}/enrich/auto` → `EnrichmentService` opens 0/1/2 `queued` bookkeeping conversations, toggle- and model-availability-aware (`summaryOnSave` / `charactersOnSave`).
- **On-demand:** `POST /scenes/{id}/enrich` ignores toggles (Scene Modal ↻ AI-redo).
- **`both` → two conversations.** Summary and character parsing are two independent runs against two independently-configured models, so `both` opens two threads ("Scene summarization", "Character enrichment"), never one combined call.
- **How a bookkeeping run works.** Its prompt (the conversation's first, system-authored message) tells the model to call an execute tool — `set_scene_summary` or `set_scene_characters` — to record what it finds, and to **ask instead** when it can't tell who a character is. The execute tool writes through `SceneService.update_scene` (which fires `scene-updated`). A run that calls no tool asked a question → conversation lands at `waiting` for the author to answer in-thread. There is no separate escalation entity and no JSON-parsing step.

## Git status worker

Separate standing task: consumes `book-changed`, 5s debounce, emits `git-status`. See `git_status_worker.py`.

## Audio worker

Standing task (`audio_worker.py`): drains batch / single-line synthesis jobs for scene audio drama (doc [`audio-system.md`](../../../../docs/audio-system.md), doc 04 §16). Calls `AudioService.synthesize_line` (and optional stitch); emits `audio-progress` SSE. Accept of an `audio-script-create` proposal never goes through this worker — that only merges `manifest.json`.
