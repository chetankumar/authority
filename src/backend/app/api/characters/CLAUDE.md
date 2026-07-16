# api/characters

Characters — the who's-who master list and the enrichment matcher's vocabulary (names + aliases) — plus character-to-character relationships. Handled by `StructureService` (uniqueness enforcement for characters; pair-uniqueness + validation for relationships). Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md), [doc 05 enrichment](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/characters` | `[Character]` with computed `sceneCount` |
| POST | `/api/books/{b}/characters` | `{ name (req), aliases?, age?, gender?, nationality?, ethnicity?, occupation?, want?, need?, flaw?, arc?, personality?, history?, notes? }`. **Uniqueness:** name + every alias must not collide case-insensitively with any existing name/alias → 422 `{conflict:{value, existingCharacter}}` |
| PATCH | `/api/books/{b}/characters/{id}` | Same fields (partial); same uniqueness on merged result |
| DELETE | `/api/books/{b}/characters/{id}` | 409 `{blockedBy:{scenes?, relationships?}}` — scenes whose `characters` reference it and/or `character_relationships` rows involving it; unassign/remove first |
| GET | `/api/books/{b}/character-relationships` | `[CharacterRelationship]` |
| POST | `/api/books/{b}/character-relationships` | `{ characterAId, characterBId, category, aToB, bToA, description? }`. Validates both ids exist, non-self, and no existing record covers this unordered pair |
| PATCH | `/api/books/{b}/character-relationships/{id}` | `{ category?, aToB?, bToA?, description? }` |
| DELETE | `/api/books/{b}/character-relationships/{id}` | Unblocked — like scene relationships |

## Why uniqueness matters

Aliases feed the enrichment matcher; it must never face ambiguity. Enrichment matches prose to **existing** characters only — it never creates records (unmatched names surface as `result.unrecognizedNames`).

## Why relationships are directional

Most character relationships aren't symmetric (mother/daughter, mentor/student, unrequited love) — `aToB` and `bToA` are independent free-text labels on the same record, plus a `category` enum for future filtering/visualization.

## Persistence

`db/characters.json`: `{ id, name, aliases:[], age, gender, nationality, ethnicity, occupation, want, need, flaw, arc, personality, history, notes, createdAt, updatedAt }`.

`db/character_relationships.json`: `{ id, characterAId, characterBId, category, aToB, bToA, description, createdAt, updatedAt }`.
