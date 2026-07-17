# features/resources — `/book/{id}/resources`

Files the author keeps beside the manuscript — research, references, worldbuilding notes — plus the book-level AI chat: a conversation whose parent is the *book*, not any scene. Parent: [features](../CLAUDE.md). Spec: [doc 06 §Resources](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [resources](../../../backend/app/api/resources/CLAUDE.md).

## Layout

Header with **[Chat]** and **[Upload file]**, a drag-and-drop dropzone, the file list (name/link → download, size, modified date, 🗑 → `ConfirmDialog`), and below it a **Chats** list of past book-level threads (mirrors the editor's Notes accordion, but there is exactly one parent — the book — so it needs no per-scene filtering).

## Controls

- **Upload file** / drop — any file type, up to 25 MB (422 over that). A name collision is never an overwrite: the server suffixes (`notes.md` → `notes-2.md`) and the toast says so when the saved name differs from what was picked.
- **Delete** → `ConfirmDialog` ("moves to `.trash/`, recoverable from there or from git") → `DELETE`.
- **Chat** → same pattern as the editor's `startChat` ([EditorPage.tsx](../editor/EditorPage.tsx)), except `parentType: "book", parentId: bookId` and no selection excerpt. Opens the existing `ConversationModal` with **no `sceneId`** — the modal needed no changes for this, every scene-keyed branch was already optional.
- **Chat rows** → same modal, by `conversationId`.

## Why the AI can read but not write these files directly

`list_resources()`/`get_resource(filename)` are ordinary read tools, available in every conversation regardless of parent. Creating a file goes through a **proposal** instead (`propose_resource_create` → an amber card in `ConversationModal` → author Accept → `ResourceService.create_text_file`) — a resource file is neither prose nor bookkeeping, so it doesn't qualify for an execute tool under doc 01's write-permission table. This is why Accept in `ConversationModal` also invalidates `['resources', bookId]`.

## APIs

`GET/POST /books/{b}/resources`, `GET /books/{b}/resources/{filename}/content`, `DELETE /books/{b}/resources/{filename}`, `GET /books/{b}/conversations` (book-parented threads).
