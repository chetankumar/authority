# features/book — `/book/:bookId`

The book home: the landing when an author clicks into a book (doc 08 J7). Parent: [features](../CLAUDE.md). Spec: [doc 06](../../../../../docs/claude-tech-specs/06-frontend-pages.md), [doc 08 J7](../../../../../docs/claude-tech-specs/08-user-journey.md).

## `BookPage`

- Fetches the full context via `useBook(bookId)` → `GET /api/books/{id}` (cached under `keys.book(id)`).
- **States:** loading ("Opening the book…"), 404 → "That book couldn't be found." + back link, other error → generic message.
- **Header:** cover thumbnail (or title placeholder), title (Literata), story summary, part/chapter counts.
- **Workspace:** a grid of the book's sections (Scenes, Metadata, Characters, Tasks, Notes, Version control, Compile). Rendered as upcoming entry points ("soon") until each section phase lands.
- **Back:** "← All books" → `/`.

## Status

- **Built:** the book context load + home shell + navigation (shelf card → here; create-book navigates in).
- **Not yet:** the section pages themselves (Scenes graph/table, Metadata, Tasks, Notes, Git, Compile), the per-book SSE event channel (`GET /api/books/{id}/events`), and switching the global left nav to book context. These arrive with their respective build phases.
