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
| [`features/`](features/CLAUDE.md) | Per-page folders (bookshelf, settings, graph, table, editor, conversation, sceneModal, characters, metadata, tasks, git, **audio**) |
| [`styles/`](styles/CLAUDE.md) | `tokens.css` (the §1.2 variables) + Tailwind config mapping |

## Query keys (doc 06 §2)

`['book', id]` · `['scenes', bookId]` · `['todos', bookId, includeScenes]` · `['sceneTodos', bookId, sceneId]` · `['conversations', bookId, sceneId]` · `['conversations', bookId, "book"]` (book-parented threads — deliberately under the same prefix, see below) · `['resources', bookId]` · `['git', bookId]` · `['compileCheck', bookId]` · `['settings', section]` · `['audio', bookId, sceneId]` · `['gitignore', bookId]`. Todos are two keys, not one, because storage is split by `parentType` (doc 03): `todos` is the book-level Tasks-page list, `sceneTodos` is one scene's own list (editor accordion). There is no `jobs` key — the editor's AI Jobs pane is just the `conversations` list filtered to `ai-job`/`bookkeeping` kinds.

## SSE integration

`useBookEvents` subscribes to `GET /books/{id}/events` and translates events → cache updates: `scene-updated` patches `['scenes']`; `conversation` invalidates `['conversations', bookId, sceneId]` for a scene-parented event, else the whole `['conversations', bookId]` **prefix** — which is exactly what `['conversations', bookId, "book"]` (the Resources page's threads) sits under, so it gets live updates without its own case; `todos-created` invalidates both `['todos', bookId]` and `['sceneTodos', bookId]` (prefix match — a dependency fanout or accepted `todo-create` proposal can land in either storage tier); `git-status` patches `['git']` (drives the top-bar badge); `compile-done` invalidates `['compileCheck']`; `audio-progress` invalidates `['audio', bookId, sceneId]`. On reconnect: refetch active queries.

**SSE is the fast path, not the only one.** `useGitStatus` also polls `GET /git/status` every 10s (`refetchInterval`), so a dropped event can't leave the amber badge silently lying (doc 07 §28). Poll and event write identical server truth into the same key — redundant by design.

## Editor autosave

Local dirty buffer → debounce 2s → `PUT content`; never blocks typing; failures show a persistent "Not saved — retrying" state, retry with backoff.
