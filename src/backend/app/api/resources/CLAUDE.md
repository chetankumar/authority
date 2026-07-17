# api/resources — files beside the book

Research PDFs, reference images, worldbuilding notes: material that surrounds the novel without being the novel. Stored in the book folder's `resources/`, committed with it, and reachable by the AI. Handled by `ResourceService`. Spec: [doc 04 §Resources](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/resources` | `ResourceFile[]`, newest first. A fresh `resources/` scan every call — no cache, no index |
| POST | `/api/books/{b}/resources` | **multipart** `file` (req). Any type. 422 over 25 MB. Name collision → `-2` suffix, never an overwrite. 201 `ResourceFile` (`filename` may differ from what was sent) |
| GET | `/api/books/{b}/resources/{filename}/content` | Streams the file with `Content-Disposition: attachment`. 404 if absent |
| DELETE | `/api/books/{b}/resources/{filename}` | Moves to `.trash/`, never unlinks. 204 |

## Notes

- **No id, no index.** The filename is the key; `resources/` is the only source of truth. Same reasoning as `BookScanner` and the bookshelf: a book folder must survive being zipped, cloned, or hand-edited (doc 01 hard rule 4). Drop a file in outside the app and it appears on the next list.
- **`{filename}`, not `{filename:path}`** — a name containing a slash fails to match the route at all. That's a free traversal guard on top of `safe_resource_path`, which rejects separators, `..`, and leading dots outright rather than sanitizing them.
- **Leading dots are rejected** because the scan skips dotfiles; accepting one would write a file that never appears in the list.
- **25 MB cap** — the router reads the whole upload into memory (as the book cover already does). Nothing else in the codebase caps an upload.
- Writes go through `mgr.notify_changed()`, so an upload dirties the git badge within the worker's 5s debounce like any other change.

## AI access

- **Read:** `list_resources()` and `get_resource(filename)` are ordinary read tools, ungated, available in every conversation. Text-ish extensions only (`.md .markdown .txt .csv .json .yml .yaml`); anything else reports as binary rather than erroring. Content is truncated at 100k chars so one file can't eat the context window.
- **Write:** never directly. `propose_resource_create` emits a proposal; the author accepts and `ProposalService` calls `ResourceService.create_text_file`. That is doc 01's "AI proposes → author confirms" row — a resource file is neither prose (hard rule 1) nor bookkeeping (the one standing-consent carve-out), so it gets no execute tool.
