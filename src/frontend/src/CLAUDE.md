# frontend/src — application source

Parent: [frontend](../CLAUDE.md). Spec: [06 Frontend §2](../../../docs/claude-tech-specs/06-frontend-pages.md).

## Files to create here

- `App.tsx` — app shell (top bar, left nav, disconnected banner, outlet).
- `router.tsx` — routes (see per-feature docs); unknown ids → friendly 404 panel with "Back to bookshelf".

## Directory map

| Directory | Responsibility |
|---|---|
| [`api/`](api/CLAUDE.md) | Typed client: one function per endpoint (doc 04); SSE helpers |
| [`queries/`](queries/CLAUDE.md) | TanStack Query hooks + key factory |
| [`events/`](events/CLAUDE.md) | `useBookEvents(bookId)`: one EventSource per open book → cache patches |
| [`components/`](components/CLAUDE.md) | Shared UI: Modal, Popover, Toast, Badge, BlockedDeletionDialog, SearchableSelect, … |
| [`features/`](features/CLAUDE.md) | Per-page folders (bookshelf, settings, graph, table, editor, conversation, sceneModal, characters, metadata, tasks, git) |
| [`styles/`](styles/CLAUDE.md) | `tokens.css` (the §1.2 variables) + Tailwind config mapping |

## Query keys (doc 06 §2)

`['book', id]` · `['scenes', bookId]` · `['todos', bookId]` · `['conversations', bookId, sceneId]` · `['jobs', bookId, sceneId]` · `['git', bookId]` · `['compileCheck', bookId]` · `['settings', section]`.

## SSE integration

`useBookEvents` subscribes to `GET /books/{id}/events` and translates events → cache updates: `scene-updated` patches `['scenes']`; `job` patches `['jobs']` + streaming modal state; `todos-created` invalidates `['todos']`; `git-status` patches `['git']` (drives the top-bar badge); `compile-done` invalidates `['compileCheck']`. On reconnect: refetch active queries.

## Editor autosave

Local dirty buffer → debounce 2s → `PUT content`; never blocks typing; failures show a persistent "Not saved — retrying" state, retry with backoff.
