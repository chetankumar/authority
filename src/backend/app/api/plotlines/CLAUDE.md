# api/plotlines

Plotlines — named narrative threads. The relationship with scenes is owned by the scene model (via `primaryPlotlineId` and `secondaryPlotlineIds`). `sceneCount` is computed by scanning scenes. Handled by `StructureService`. Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/plotlines` | `[Plotline]` with computed `sceneCount` (scanned from scenes' plotline fields) |
| POST | `/api/books/{b}/plotlines` | `{ title (req), description? }`. 201 |
| PATCH | `/api/books/{b}/plotlines/{id}` | `{ title?, description? }` — metadata only |
| DELETE | `/api/books/{b}/plotlines/{id}` | 409 `{blockedBy:{scenes}}` while any scene references this plotline; unassign from scenes first |

## Persistence

`db/plotlines.json`: `{ id, title, description }`. No scene references stored.
