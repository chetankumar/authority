# features/metadata — `/book/{id}/metadata`

The book's structural workshop. Sub-nav tabs **Parts · Chapters · Plotlines · Book**; 720px column. A **readiness strip** persists above all tabs. Parent: [features](../CLAUDE.md). Spec: [doc 06 §12](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Readiness strip

`GET /compile/check` → "✅ Ready to compile" or "⚠ 3 errors · 5 warnings" (amber, expandable to the grouped report, every item a deep link — scene → Scene Modal; chapter/part → its tab) + [Compile book] primary. Standing instrument, not a compile-time surprise.

- **[Compile book]** → `POST /compile`; 409 → auto-expands the report; success → build-report dialog + toast "Book compiled — output is uncommitted" (links to Git).

## Tabs

- **Parts:** ordered rows, ↑↓ arrows (`PATCH {moveBefore/moveAfter}` → full ordered list re-rendered), ✎, 🗑 (`DELETE`, 409 → BlockedDeletionDialog), [＋ Add part].
- **Chapters:** rows grouped under part headings + "Unassigned"; each row a Part select (`PATCH {partId}`); same CRUD.
- **Plotlines:** rows with scene-count badges; CRUD modal (title*, description); `DELETE` 409-blocked while scenes linked.
- **Book:** Story summary textarea · Book system prompt textarea (hint "Prepended to every AI request for this book — genre, voice, style rules") · [Save] → `PATCH /books/{id}`.
