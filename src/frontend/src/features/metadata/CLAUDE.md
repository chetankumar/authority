# features/metadata — `/book/{id}/metadata`

The book's structural workshop. Sub-nav tabs **Parts · Chapters · Plotlines · Book**; 720px column. A **readiness strip** persists above all tabs (Phase 9 — not yet implemented). Parent: [features](../CLAUDE.md). Spec: [doc 06 §12](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Readiness strip (Phase 9)

`GET /compile/check` → "Ready to compile" or "3 errors · 5 warnings" (expandable report, every item a deep link — scene → Scene Modal; chapter/part → its tab) + [Compile book] primary.

## Tabs

- **Parts:** ordered rows sorted by `seq`, drag-and-drop to reorder (`POST /parts/reorder`), inline title edit, delete (409 → BlockedDeletionDialog), [+ Add part].
- **Chapters:** rows grouped under part headings + "Unassigned"; each row has a Part select (`PATCH {partId}`); drag-and-drop global reorder (`POST /chapters/reorder`); same CRUD pattern.
- **Plotlines:** rows with computed scene-count badges (from `primaryPlotlineId`/`secondaryPlotlineIds` on scenes); CRUD inline (title, description); `DELETE` 409-blocked while any scene references the plotline.
- **Book:** Story summary textarea · System prompt textarea (hint "Prepended to every AI request for this book") · Bookkeeping toggles (summaryOnSave, charactersOnSave) · [Save] → `PATCH /books/{id}`.

## Implementation status

- Parts/Chapters/Plotlines/Book tabs: implemented
- Readiness strip + compile: deferred to Phase 9
