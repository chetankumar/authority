# api — typed client

One typed function per backend endpoint, plus SSE helpers. This is the only place that knows about HTTP; the rest of the app calls these functions (usually via [queries](../queries/CLAUDE.md)).

Parent: [src](../CLAUDE.md). Endpoint contracts: [doc 04](../../../../docs/claude-tech-specs/04-api-reference.md) (mirrored per area under [`src/backend/app/api/`](../../../backend/app/api/CLAUDE.md)).

## Guidelines

- One function per endpoint, grouped by resource area (settings, books, scenes, relationships, dependencies, structure, plotlines, characters, todos, conversations, proposals, resources, git, compile, events). No `jobs` module — AI runs are conversations.
- Request/response types mirror the backend Pydantic models ([doc 04 §2](../../../../docs/claude-tech-specs/04-api-reference.md)).
- Base path `/api`; same-origin in production.
- **SSE helpers:** the book event channel (`GET /books/{id}/events`) and message streaming (`POST /conversations/{id}/messages`, which returns `token` → `message` → `done` events). Reconnect with exponential backoff.
- Multipart for `POST/PATCH /books` (title, cover) and `POST /books/{id}/resources` (file).
- The frontend never persists — every mutation goes through these functions to the single-writer API.
