# features/characters — `/book/{id}/characters` (Character Sheet)

The who's-who dictionary; also the enrichment matcher's vocabulary. 640px column; rows = name + first line of personality + scene-count badge; click expands inline to the edit form. Parent: [features](../CLAUDE.md). Spec: [doc 06 §11](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Controls

- Row expands to edit form: Name*, **Aliases** tag-input (hint "Nicknames and titles the prose uses — 'the Widow', 'Marlow'"), Personality / History / Notes textareas, [Delete] (ghost-danger, left), [Save] (right).
- **[＋ Add character]** (primary, top-right).
- Aliases → `POST/PATCH /characters`; 422 uniqueness conflict → inline "Already used by {name}".
- Delete → `DELETE`; 409 → BlockedDeletionDialog listing referencing scenes as links.
- Scene-count badge from computed `sceneCount`.

## Why aliases matter

They're how enrichment recognizes characters in prose; uniqueness across all names + aliases keeps the matcher unambiguous.
