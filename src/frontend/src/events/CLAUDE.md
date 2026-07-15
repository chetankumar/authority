# events — book SSE integration

`useBookEvents(bookId)`: opens exactly one `EventSource` per open book against `GET /books/{id}/events` and translates events into TanStack Query cache patches.

Parent: [src](../CLAUDE.md). Spec: [doc 06 §2](../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [events](../../../backend/app/api/events/CLAUDE.md).

## Event → cache mapping

| event | action |
|---|---|
| `scene-updated` | patch `['scenes', bookId]` (live summary/characterIds updates) |
| `job` | patch `['jobs', bookId, sceneId]` + streaming modal state |
| `todos-created` | invalidate `['todos', bookId]` |
| `git-status` | patch `['git', bookId]` (drives the top-bar amber badge) |
| `compile-done` | invalidate `['compileCheck', bookId]` |

## Reconnect

The channel is stateless: reconnect with exponential backoff and refetch active queries on reconnect. One connection per open book, closed on leaving the book.
