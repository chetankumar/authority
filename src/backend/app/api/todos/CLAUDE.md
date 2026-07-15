# api/todos

Todos — everything owed, attached to a scene/chapter/part/book. Origin `user` (manual), `dependency` (mechanical, from content changes), or `ai` (accepted todo-create proposal). Spec: [doc 04 §8](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/todos` | `[Todo]` (all in book, `parentTitle` resolved). Filtering/sorting client-side (AG Grid) |
| POST | `/api/books/{b}/todos` | `{ parentType, parentId, action (req) }` → origin `user`, status `open`. 422 unknown parent. 201 |
| PATCH | `/api/books/{b}/todos/{id}` | `{ status?, action? }` |
| DELETE | `/api/books/{b}/todos/{id}` | Hard delete (for mistakes; normal lifecycle is `closed`). 204 |

## Statuses

`open · done · closed`. done = accomplished; closed = dismissed (the dependency-review "not applicable" verdict). No in-progress state. Dependency-origin todos carry `sourceDependencyId` and a ⛓ icon in the UI.
