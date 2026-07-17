# events — book SSE integration

`useBookEvents(bookId)`: opens exactly one `EventSource` per open book against `GET /books/{id}/events` and translates events into TanStack Query cache patches.

Parent: [src](../CLAUDE.md). Spec: [doc 06 §2](../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [events](../../../backend/app/api/events/CLAUDE.md).

## Event → cache mapping

| event | action |
|---|---|
| `scene-updated` | patch `['scenes', bookId]` (live summary/characters updates) |
| `job` | patch `['jobs', bookId, sceneId]` + streaming modal state |
| `todos-created` | invalidate `['todos', bookId]` **and** `['sceneTodos', bookId]` (prefix match — dependency fanout and accepted `todo-create` proposals can land in either storage tier, doc 03 §Todos storage split) |
| `git-status` | patch `['git', bookId]` (drives the top-bar amber badge) |
| `compile-done` | invalidate `['compileCheck', bookId]` |

Unrecognized event types are ignored (the backend also emits an internal `book-changed` signal on this channel that no client acts on).

## Reconnect

The channel is stateless: reconnect with exponential backoff and refetch active queries on reconnect. One connection per open book, closed on leaving the book.

## Not the only path

This hook is the fast path, not the safety net. `useGitStatus` independently polls `GET /git/status` every 10s (doc 07 §28), so a dropped `git-status` — a flaky reconnect, a bug in the server-side debounce — still self-corrects within ~10s. Both write identical server truth into `['git', bookId]`, so they can't conflict. While the tab is hidden the interval pauses and refetch-on-focus covers the return instead. When adding a new event mapping here, ask what catches it if the event never arrives.
