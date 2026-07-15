# api/books

The bookshelf and per-book lifecycle: live folder scan, creation (scaffold + git init), rename/cover, and the per-book `ui.json`. Handled by `BookScanner`, `BookService`, `BookDataManager`. Spec: [doc 04 §4](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books` | 422 `books-home-unset` if unconfigured. Scans booksHome subdirs; each with a parseable `config/book.json` → `BookSummary`; unparseable → entry with `error` flag (broken-book card). Others silently ignored |
| POST | `/api/books` | **multipart** `title` (req), `cover?`. Generate `bok-{6hex}`, slugify, mkdir `{6hex}-{slug}/`, scaffold (book.json with bookkeeping both true, `scenes/.gitkeep`, seeded empty `db/*.json` + `conversations/index.json`, cover, `compiled-book/.gitkeep`, `.gitignore *.tmp`), `git init` → `add -A` → commit "initialized". 201 BookSummary |
| GET | `/api/books/{id}` | Full `Book`. First request triggers BookDataManager load; ChainService pre-orders parts/chapters |
| PATCH | `/api/books/{id}` | **multipart** `title?`, `cover?`, `removeCover?`, `systemPrompt?`, `storySummary?`, `bookkeeping?` (JSON, shallow-merge). Title change renames the folder (403 on failure, rolled back) **and auto-commits** "renamed to {title}" |
| GET | `/api/books/{id}/cover` | Streams cover; 404 if none (client renders placeholder) |
| GET / PATCH | `/api/books/{id}/ui` | `ui.json` verbatim (client-defined shape); PATCH shallow-merges, client debounces ~1s |

## Notes

- **No bookshelf registry** — the shelf is a live scan. Discovered/cloned books are never re-initialized (existing `.git` and settings untouched).
- Book folder `{6hex}-{slug}/`; hash prefix is permanent identity; slug follows title renames.

## Implementation status & decisions

- **Implemented:** `GET /api/books`, `POST /api/books` (multipart, optional cover), `GET /api/books/{id}` (full `Book` context), `GET /api/books/{id}/cover`. `PATCH /api/books/{id}` and `.../ui` are still forward spec (later phases).
- **`GET /api/books/{id}`** resolves the book via `BookRegistry` (lazy per-book `BookDataManager`, cached by id; 404 if no folder has that id) → `BookDataManager.get_book()`. The manager loads `config/book.json` on first touch and owns the book's `asyncio` mutation lock; a config that fails to parse is quarantined to `book.json.corrupt-{ts}` (never overwritten) and the read returns 422 `book-unreadable`. `db/*.json` collections load with the Scenes phase.
- **Scanner cache** is keyed on `(booksHome, dir mtime_ns)`, so a folder added or removed in books-home is picked up on the next scan without a restart; `BookService.create_book` also calls `scanner.invalidate()`.
- **Windows handle release:** `BookService` calls `repo.close()` after the init commit. GitPython keeps persistent `git cat-file` helper processes alive while a `Repo` object lives; on Windows those handles would block the later folder rename/delete.
- **Rollback:** any failure during scaffold or git init `rmtree`s the folder so a half-created book never reaches the shelf.
- **Cover extension** taken from the uploaded filename suffix, else mapped from content-type (default `.png`); bytes stored as-is under `assets/cover.{ext}`.
- **Commit identity:** the init commit is authored with the settings `user.name` (fallback `Authority`) via an explicit `Actor`, so creation never depends on a global git identity being configured.
