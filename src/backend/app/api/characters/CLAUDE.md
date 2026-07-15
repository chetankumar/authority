# api/characters

Characters — the who's-who master list and the enrichment matcher's vocabulary (names + aliases). Handled by `StructureService` (uniqueness enforcement). Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md), [doc 05 enrichment](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/characters` | `[Character]` with computed `sceneCount` |
| POST | `/api/books/{b}/characters` | `{ name (req), aliases?, personality?, history?, notes? }`. **Uniqueness:** name + every alias must not collide case-insensitively with any existing name/alias → 422 `{conflict:{value, existingCharacter}}` |
| PATCH | `/api/books/{b}/characters/{id}` | Same fields; same uniqueness on merged result |
| DELETE | `/api/books/{b}/characters/{id}` | 409 listing scenes whose `characterIds` reference it; remove from those scenes first |

## Why uniqueness matters

Aliases feed the enrichment matcher; it must never face ambiguity. Enrichment matches prose to **existing** characters only — it never creates records (unmatched names surface as `result.unrecognizedNames`).

## Persistence

`db/characters.json`: `{ id, name, aliases:[], personality, history, notes }`.
