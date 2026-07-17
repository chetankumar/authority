# api/events — book SSE channel

One SSE connection per open book. Any service emits through the [EventHub](../../core/CLAUDE.md); clients patch their TanStack Query caches from events and refetch on reconnect (channel is stateless). Spec: [doc 04 §12](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoint

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/events` | SSE stream; stays open for the session |

## Event types

| event | data | emitted when |
|---|---|---|
| `conversation` | `{ id, kind, parentType, parentId, status }` (or `{ id, status:"deleted" }`) | a conversation is created or changes status (an AI run starting, finishing, or landing in `waiting`), or is deleted. `parentType` is whatever the conversation's parent is — `scene` for the editor's notes/chats, `book` for the Resources page's chats — clients branch on it to invalidate the right cache slice |
| `scene-updated` | `{ id, changed:[...] }` | any scene metadata write (author, enrichment via execute tools, accepted proposal) |
| `todos-created` | `{ todos:[Todo] }` | dependency fanout or accepted todo-create |
| `git-status` | `GitStatus` (incl. `summary`) | the [git-status worker](../../worker/CLAUDE.md)'s 5s debounce fired, **or** an explicit stage/unstage/commit/push/pull emitted in-request |
| `compile-done` | `{ report: CompileReport }` | successful compile |

Frame format: `event: {type}\ndata: {json}\n\n`.

## Internal events

`book-changed` `{}` — fired by BookDataManager after any `db/*.json` / `config/book.json` write. Server-side signal only (the git-status worker consumes it via the hub's `subscribe_all` channel). It reaches per-book subscribers too, but clients ignore event types they don't recognize, so the channel needs no filtering.

## Not the only path

SSE is the fast path, not the source of truth. Clients that render git state also poll `GET /git/status` every 10s, so a dropped event still self-corrects within ~10s (doc 07 §28). Statelessness is what makes that safe: poll and event write identical server truth into the same cache entry.
