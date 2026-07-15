# features/tasks — `/book/{id}/tasks`

Everything owed, in one ledger. Toolbar (status filter segmented **Open / All** · [＋ Add task]) over a full-height AG Grid: Status · Action · Parent (link chip) · Origin (icon 👤 user / ⛓ dependency / ✦ ai) · Created · Updated. Parent: [features](../CLAUDE.md). Spec: [doc 06 §13](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Controls

- **Parent chip** navigates: scene → editor; chapter/part → Metadata tab; book → Metadata Book tab.
- **Status controls:** checkbox → done; row-menu Close → closed; both `PATCH /todos/{id}`. (done = accomplished; closed = dismissed / "not applicable".)
- **Row menu:** Open conversation (💬 → Conversation Modal); Delete → confirm → `DELETE` (for mistakes only).
- **[＋ Add task]** → inline row: action text + parent picker (defaults book) → `POST /todos`.
- Origin icons are static provenance — the ⛓ rows are the dependency system talking.

## APIs

`GET /books/{b}/todos`, `POST /todos`, `PATCH /todos/{id}`, `DELETE /todos/{id}`.
