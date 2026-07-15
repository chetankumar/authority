# core — cross-cutting infrastructure

Foundational utilities used by every service: configuration, logging, the single-instance lock, the hardened atomic-write helper, per-book asyncio locks, and the SSE EventHub.

Parent: [app](../CLAUDE.md). Specs: [02 Architecture](../../../../docs/claude-tech-specs/02-architecture-and-launcher.md), [03 Data Safety](../../../../docs/claude-tech-specs/03-data-storage.md), [04 §12 Events](../../../../docs/claude-tech-specs/04-api-reference.md), [05 SSE](../../../../docs/claude-tech-specs/05-ai-system.md).

## Files to create here

- **Config** — read/write `launcher.config.json` (`port`, `appDataRoot`, `envName`); create defaults on first run.
- **Logging** — two handlers (console + `logs/api.log`); log file truncated at each launch.
- **Single-instance lock** — `filelock` exclusive lock on `{appDataRoot}/.lock` at startup; second instance exits "Authority is already running".
- **Atomic write** — the hardened helper (~15 lines, stdlib): serialize → `tempfile` in same dir → `flush()` + `os.fsync()` → `os.replace()`; on POSIX also fsync the directory handle. `.tmp` gitignored. **Do not** use the deprecated `atomicwrites` package.
- **Locks** — a registry of per-book `asyncio.Lock`s (plus one for `app.json`). Every mutation acquires its book's lock; reads take none.
- **EventHub** — per-book SSE pub/sub. Any service emits; `GET /api/books/{id}/events` subscribes a client. Event types: `job`, `scene-updated`, `todos-created`, `git-status`, `compile-done` (doc 04 §12). Channel is stateless (clients refetch on reconnect).

## Data-safety layers (doc 03)

1. Torn-write protection (atomic write helper). 2. In-process races (`workers=1` + per-book lock; replace collections, never mutate in place). 3. Double-instance protection (`filelock`). 4. Corrupt-load recovery (quarantine to `{file}.corrupt-{ts}`, load degraded, never overwrite; derived files rebuilt by folder scan; git is the restore mechanism). 5. Load-time Pydantic schema validation.
