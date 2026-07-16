# features/characters — `/book/{id}/characters` (Character Sheet)

The who's-who dictionary; also the enrichment matcher's vocabulary. 640px column; rows = name + first line of personality + scene-count badge; click expands inline to the edit form. Parent: [features](../CLAUDE.md). Spec: [doc 06 §11](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Controls

- Row expands to edit form, grouped **Identity** (Name*, **Aliases** tag-input — hint "Nicknames and titles the prose uses — 'the Widow', 'Marlow'" — Age, Gender, Nationality, Ethnicity, Occupation), **Craft** (Want, Need, Flaw, Arc, Personality / History / Notes textareas), **Relationships** (below), [Delete] (ghost-danger, left), [Save] (right).
- **[＋ Add character]** (primary, top-right) — a lightweight form (name + aliases only); the rest is filled in after saving.
- Aliases → `POST/PATCH /characters`; 422 uniqueness conflict → inline "Already used by {name}".
- Delete → `DELETE`; 409 → BlockedDeletionDialog listing referencing scenes **and** character-relationship rows as links.
- Scene-count badge from computed `sceneCount`.

## Relationships section

Lists this character's relationships to others ("*{this character} is {aToB} {other}*" + category chip + description), each editable/removable inline. **[+ Add relationship]** uses `SearchableSelect` to pick the other character, a category select, and two direction-label inputs (`aToB`/`bToA`) since relationships are rarely symmetric. `POST/PATCH/DELETE /character-relationships` via `queries/characters.ts`.

## Why aliases matter

They're how enrichment recognizes characters in prose; uniqueness across all names + aliases keeps the matcher unambiguous.
