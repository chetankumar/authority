# worker — background jobs

Parent: [backend](../../CLAUDE.md). Spec: [doc 05](../../../../docs/claude-tech-specs/05-ai-system.md).

## Job worker

Single asyncio task started in `main.py` lifespan. Per-book FIFO, concurrency 1 per book (≤2 global). Failures → `failed` with error string; no automatic retry.

## Enrichment

- **No settle timers.** Content autosave never schedules enrichment.
- **Leave-scene:** `POST /scenes/{id}/enrich/auto` → toggle-aware enqueue (`summaryOnSave` / `charactersOnSave`).
- **On-demand:** `POST /scenes/{id}/enrich` ignores toggles (Scene Modal ↻ AI-redo).
- **System jobs** — enrichment (scope `summary`/`characters`/`both`). `both` runs as **two independent model calls**, each against its own configured slot. Summary → overwrite `scene.summary`. Characters → prompt gets cast directory + **current scene `characters` rows** + prose, then sets `characters` to matched **existing** cast with `involvement` (preserve/refine author edits; never creates records; unmatched names → `result.unrecognizedNames` + escalation). Emits `scene-updated`.

## Git status worker

Separate standing task: consumes `book-changed`, 5s debounce, emits `git-status`. See `git_status_worker.py`.
