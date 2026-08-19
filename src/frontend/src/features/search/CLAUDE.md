# features/search — header Q&A (component, not a route)

Ask the current book a question. Parent: [features](../CLAUDE.md).

[`SearchBox.tsx`](SearchBox.tsx) lives in the top bar while a book is open. Submit → `POST /search` → results panel: AI answer on top, clickable hits below (open the scene). Not a saved conversation.

Index / rebuild / delete are on the editor and Metadata → Book, not here.
