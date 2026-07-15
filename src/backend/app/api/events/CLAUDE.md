# api/events — book SSE channel

One SSE connection per open book. Any service emits through the [EventHub](../../core/CLAUDE.md); clients patch their TanStack Query caches from events and refetch on reconnect (channel is stateless). Spec: [doc 04 §12](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoint

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/events` | SSE stream; stays open for the session |

## Event types

| event | data | emitted when |
|---|---|---|
| `job` | `{ id, type, sceneId, status, result? }` | any job status transition |
| `scene-updated` | `{ id, changed:[...] }` | any scene metadata write (author, enrichment, accepted proposal) |
| `todos-created` | `{ todos:[Todo] }` | dependency fanout or accepted todo-create |
| `git-status` | `{ dirtyCount, ahead, behind }` | dirty-file count changed after any write, or commit/push/pull |
| `compile-done` | `{ report: CompileReport }` | successful compile |

Frame format: `event: {type}\ndata: {json}\n\n`.
