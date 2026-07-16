# features/book — `/book/:bookId`

The book home: the landing when an author clicks into a book (doc 08 J7). Parent: [features](../CLAUDE.md). Spec: [doc 06](../../../../../docs/claude-tech-specs/06-frontend-pages.md), [doc 08 J7](../../../../../docs/claude-tech-specs/08-user-journey.md).

## `BookPage`

- Fetches the full context via `useBook(bookId)` → `GET /api/books/{id}` (cached under `keys.book(id)`).
- **States:** loading ("Opening the book…"), 404 → "That book couldn't be found." + back link, other error → generic message.
- **Header:** cover thumbnail (or title placeholder), title (Literata), story summary, part/chapter counts.
- **Workspace:** a grid of the book's sections. Live links: Scene Graph, Scene Table, Metadata, Characters, Version control. Still "soon": Tasks, Notes, Compile.
- **Back:** "← All books" → `/`.

## Status

- **Built:** the book context load + home shell + navigation into live section pages.
- **Not yet:** Tasks, Notes, Compile entry points; switching those from "soon" when their phases land.
