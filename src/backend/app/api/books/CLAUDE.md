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
