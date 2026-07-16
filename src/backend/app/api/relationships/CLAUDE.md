# api/relationships

Soft relationships — the planning scaffolding (*definitely before / after / around* another scene), stored separately from the hard chain. Rendered as dotted arrows; checked against the chain at compile time. Handled by `SceneService`/`StructureService`. Spec: [doc 04 §6](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/relationships` | `{ fromSceneId, toSceneId, type }`. 422 identical ids / unknown ids / reversed-sentinel violations. Exact duplicate → 200 returning existing row (idempotent). 201 SoftRelationship |
| DELETE | `/api/books/{b}/relationships/{id}` | Removes the edge. 404 unknown |

## Semantics

`SoftRelationship { id, fromSceneId, toSceneId, type: before\|after\|around, createdAt }` — read as *from is definitely-{type} to*. "around" renders with no arrowhead. Editing lives in the Scene Modal Basics tab (no separate popup).

## Storage (doc 03)

Persisted per-scene at `scenes/{fromSceneId}/relationships.json`, not a flat `db/relationships.json` — each edge lives with the scene that owns it. `BookDataManager.get_relationships()` still returns the flattened aggregate across every scene's file (lazy-loaded once, cached), so this router and `SceneService` are unaffected by where the edge physically lives.
