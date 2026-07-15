# features/bookshelf — `/`

Choose or create a book. Responsive card grid (200px covers, 3:4 ratio, 24px gutter). Parent: [features](../CLAUDE.md). Spec: [doc 06 §4](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Controls

- **Book card** (cover/title) → `/book/{id}`. Kebab (hover) → Edit Book modal.
- **+ Add book** card (dashed, last position) → Add Book modal.
- **Broken-book card** — non-clickable, danger tint, "Couldn't read this book's config" (scan returned `error` flag).
- **Empty states** — booksHome unset → "Set your books folder to get started" + [Open settings]; set but empty → "Your shelf is empty" + [Add book].

## Modals

- **Add Book** (560px): Title* · cover drop-zone (preview, Remove) · [Cancel] [Create book] → `POST /books` (multipart) → toast "Book created" → navigate in. booksHome errors render inline with a settings link.
- **Edit Book**: same fields prefilled + hint "Renaming also renames the book's folder." → `PATCH /books/{id}`.

## APIs

`GET /books`, `POST /books`, `PATCH /books/{id}`, `GET /books/{id}/cover`.
