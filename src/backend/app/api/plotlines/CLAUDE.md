# api/plotlines

Plotlines — named threads with a set of scene references and computed scene counts. Handled by `StructureService`. Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/plotlines` | `[Plotline]` with computed `sceneCount` |
| POST | `/api/books/{b}/plotlines` | `{ title (req), description? }`. 201 |
| PATCH | `/api/books/{b}/plotlines/{id}` | `{ title?, description?, sceneIds? }` — sceneIds full-replacement (via accepted chat proposals or UI); unknown ids 422 |
| DELETE | `/api/books/{b}/plotlines/{id}` | 409 `{blockedBy:{scenes}}` while sceneIds non-empty; unlink first |

## Persistence

`db/plotlines.json`: `{ id, title, description, sceneIds:[] }`.
