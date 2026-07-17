# api/todos

Todos — everything owed, attached to a scene/chapter/part/book. Origin `user` (manual), `dependency` (mechanical, from content changes), or `ai` (accepted todo-create proposal). Spec: [doc 04 §8](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Storage split (doc 03 §Todos storage split)

Not a single flat file. Scene-parented todos (`parentType: "scene"`) persist in the owning scene's own `scenes/{id}/todos.json` — same corruption-blast-radius reasoning as the existing meta/bookkeeping/dependencies/relationships per-scene split. Everything else (`chapter`/`part`/`book`) persists in the book-level `db/todos.json`, which this router owns. `TodoService` (`app/services/todo_service.py`) is the only code that routes between the two tiers; `BookDataManager.find_todo(id)` resolves a bare id to whichever tier it lives in, so PATCH/DELETE work without the caller knowing which one — the same pattern `DELETE /relationships/{id}` already uses.

Scene-parented todos are created/listed via `GET`/`POST /books/{b}/scenes/{id}/todos` (see [api/scenes](../scenes/CLAUDE.md)), not this router's POST.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/todos` | `[Todo]` — book-level only (chapter/part/book-parented), `parentTitle` resolved. Filtering/sorting client-side (AG Grid) |
| GET | `/api/books/{b}/todos?includeScenes=true` | The above **plus** every scene's todos, flattened. Read fresh on each call (`BookDataManager.get_all_scene_todos`) — no maintained reverse index, since this is a rare Tasks-page-toggle read, not a hot path like autosave |
| POST | `/api/books/{b}/todos` | `{ parentType, parentId, action (req) }`, `parentType` must not be `scene` (422 — use the scene-scoped route) → origin `user`, status `open`. 422 unknown parent. 201 |
| PATCH | `/api/books/{b}/todos/{id}` | `{ status?, action?, conversationId? }`. Resolves either tier. `conversationId` is set-once — links the todo to a discussion (💬 in the UI); no way to clear it back to null |
| DELETE | `/api/books/{b}/todos/{id}` | Hard delete (for mistakes; normal lifecycle is `closed`). Resolves either tier. 204 |

## Statuses

`open · done · closed`. done = accomplished; closed = dismissed (the dependency-review "not applicable" verdict). No in-progress state. Dependency-origin todos carry `sourceDependencyId` and a ⛓ icon in the UI.

## Where todos get created from

- Manually — this router's POST (chapter/part/book) or the scene-scoped POST (scene).
- Dependency fanout — `SceneService._fanout_dependency_todos` on content save (see [api/dependencies](../dependencies/CLAUDE.md)), always scene-parented.
- Accepted `todo-create` proposal — `ProposalService._apply_todo` (see [api/proposals](../proposals/CLAUDE.md)), routed by whatever `parentType` the AI's `propose_todo` tool call specified; `conversationId` is set automatically to the proposing conversation.
