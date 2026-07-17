# features/book — `/book/:bookId`

The book home: the landing when an author clicks into a book (doc 08 J7). Parent: [features](../CLAUDE.md). Spec: [doc 06](../../../../../docs/claude-tech-specs/06-frontend-pages.md), [doc 08 J7](../../../../../docs/claude-tech-specs/08-user-journey.md).

## `BookPage`

- Fetches the full context via `useBook(bookId)` → `GET /api/books/{id}` (cached under `keys.book(id)`).
- **States:** loading ("Opening the book…"), 404 → "That book couldn't be found." + back link, other error → generic message.
- **Header:** cover thumbnail (or title placeholder), title (Literata), story summary, part/chapter counts.
- **Workspace:** a grid of the book's sections. Live links: Scene Graph, Scene Table, Metadata, Characters, Tasks, Resources, Version control. Still "soon": Notes, Compile.
- **Back:** "← All books" → `/`.

## Status

- **Built:** the book context load + home shell + navigation into live section pages, including Tasks (`TSK-FE-01`) and Resources (research/reference files + the book-level AI chat, [features/resources](../resources/CLAUDE.md)).
- **Not yet:** Notes, Compile entry points; switching those from "soon" when their phases land. (Note: "Notes" here is a distinct future section for scene-chat history browsing — it is not the same thing as Resources' own book-level chat threads.)
