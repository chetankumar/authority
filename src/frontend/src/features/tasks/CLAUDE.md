# features/tasks — `/book/{id}/tasks`

Everything owed, in one ledger. Toolbar (status filter segmented **Open / All** · "Also show scene todos" toggle · [＋ Add task]) over a full-height AG Grid: Status · Action · Parent (link chip) · Origin (icon 👤 user / ⛓ dependency / ✦ ai) · Created · Updated. Parent: [features](../CLAUDE.md). Spec: [doc 06 §13](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Storage split (doc 03 §Todos storage split)

This page's base list is book-level todos only — `parentType` ∈ `chapter | part | book`, from `db/todos.json`. Scene-parented todos live in each scene's own `scenes/{id}/todos.json` and are normally worked from the [editor](../editor/CLAUDE.md)'s To-dos accordion, not here. The "Also show scene todos" toggle (persisted per book in `ui.json` under `tasksShowSceneTodos`) pulls every scene's todos in too, via `?includeScenes=true` — a plain server-side scan each time, not a maintained index (it's a rare request, not a hot path).

## Controls

- **Also show scene todos** — checkbox; survives reload via `ui.json`.
- **Parent chip** navigates: scene → editor; chapter/part/book → Metadata.
- **Status controls:** checkbox → done; row-menu Close → closed; both `PATCH /todos/{id}` (resolves either storage tier from the flat id, like `DELETE /relationships/{id}`). (done = accomplished; closed = dismissed / "not applicable".)
- **Row menu:** Open conversation (💬 → Conversation Modal; creates a `task-discussion` conversation on first use and links it back via `PATCH {conversationId}`, set-once); Delete → confirm → `DELETE` (for mistakes only).
- **[＋ Add task]** → inline row: action text + parent-type picker (**Book / Chapter / Part only** — `parentType: scene` is rejected here with 422; add scene todos from the editor instead) + parent picker → `POST /todos`.
- Origin icons are static provenance — the ⛓ rows are the dependency system talking.

## APIs

`GET /books/{b}/todos[?includeScenes=true]`, `POST /todos` (parentType ≠ scene), `PATCH /todos/{id}`, `DELETE /todos/{id}`.
