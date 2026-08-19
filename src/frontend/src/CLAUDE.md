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
| [`features/`](features/CLAUDE.md) | Per-page folders (bookshelf, settings, graph, table, editor, conversation, sceneModal, characters, metadata, tasks, git, **audio**, **search**) |
| [`styles/`](styles/CLAUDE.md) | `tokens.css` (the §1.2 variables) + Tailwind config mapping |

## Query keys (doc 06 §2)

`['book', id]` · `['scenes', bookId]` · `['todos', bookId, includeScenes]` · `['sceneTodos', bookId, sceneId]` · `['conversations', bookId, sceneId]` · `['conversations', bookId, "book"]` (book-parented threads — deliberately under the same prefix, see below) · `['resources', bookId]` · `['git', bookId]` · `['compileCheck', bookId]` · `['settings', section]` · `['audio', bookId, sceneId]` · `['gitignore', bookId]` · `['searchIndex', bookId]`. Todos are two keys, not one, because storage is split by `parentType` (doc 03): `todos` is the book-level Tasks-page list, `sceneTodos` is one scene's own list (editor accordion). There is no `jobs` key — the editor's AI Jobs pane is just the `conversations` list filtered to `ai-job`/`bookkeeping` kinds.

## SSE integration

Two connections, on purpose:

- **Book events** — `useBookEvents` listens to `GET /books/{id}/events` and patches caches: `scene-updated` → `['scenes']`; `conversation` → the matching conversation list (scene-parented by scene id, otherwise the whole `['conversations', bookId]` prefix, which is why Resources chats live at `['conversations', bookId, "book"]`); `todos-created` → both `['todos', bookId]` and `['sceneTodos', bookId]`; `git-status` → `['git']`; `compile-done` → `['compileCheck']`; `audio-progress` → `['audio', bookId, sceneId]`; `search-index` → `['searchIndex', bookId]`. On reconnect: refetch active queries.
- **Live chat replies** — each generating conversation has its own `POST /conversations/{id}/messages` stream, held by [`ConversationSessionProvider`](features/conversation/ConversationSessionContext.tsx) in App. Reply tokens do not go on the book event channel. Hiding the chat window or changing scene does not stop the reply; closing that chat, or leaving the book, does.

**SSE is the fast path, not the only one.** `useGitStatus` also polls `GET /git/status` every 10s (`refetchInterval`), so a dropped event can't leave the amber badge silently lying (doc 07 §28). Poll and event write identical server truth into the same key — redundant by design.

## Editor autosave

Local dirty buffer → debounce 2s → `PUT content`; never blocks typing; failures show a persistent "Not saved — retrying" state, retry with backoff.
