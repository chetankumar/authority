# api — routers per resource area

One router per resource area. Routers hold **no** business logic: validate the request via Pydantic, delegate to a service, return the service result. Each subfolder documents one area's endpoints; full contracts live in [doc 04](../../../../docs/claude-tech-specs/04-api-reference.md).

Parent: [app](../CLAUDE.md).

## Conventions (doc 04 §1)

- Base path `/api`. Bodies are JSON unless marked **multipart** or **SSE**. Timestamps ISO 8601 UTC. IDs `{prefix}-{6hex}`; sentinels `scn-START`/`scn-END` accepted where noted.
- `?` = optional field. PATCH is partial: omitted fields unchanged; explicit `null` clears a nullable field.
- OpenAPI docs auto-served at `/docs`.

## Error envelope

`{ "error": "human-readable summary", "detail": { ... } }`. Codes: 400 malformed · 403 fs permission `{path}` · 404 `{kind,id}` · 409 blocked `{blockedBy}` / `{errors}` · 422 `{fields}` · 500 `{trace_id}`.

## Mutation lifecycle

router → Pydantic validation → service acquires book lock → read memory → validate rules → mutate copies → atomic persist → BookDataManager emits `book-changed` → release lock → response. Reads take no lock.

Git never runs in this path — the [git-status worker](../worker/CLAUDE.md) consumes `book-changed` and re-checks after a 5s debounce. Only [git](git/CLAUDE.md)'s own mutating endpoints emit `git-status` in-request.

## SSE

Two producers: the **book event channel** ([events](events/CLAUDE.md), §12) and **message streaming** ([conversations](conversations/CLAUDE.md), §9.3). Events framed `event: {type}\ndata: {json}\n\n`. Clients reconnect with backoff and refetch (channel is stateless).

## Resource areas

| Folder | Area | Doc 04 |
|---|---|---|
| [`health/`](health/CLAUDE.md) | Health probe | §3 |
| [`settings/`](settings/CLAUDE.md) | User, models, ai (utility model), ai-jobs, placeholders | §3 |
| [`books/`](books/CLAUDE.md) | Shelf scan, create, cover, ui.json | §4 |
| [`scenes/`](scenes/CLAUDE.md) | Scene CRUD, content, enrich, sub-lists | §5 |
| [`relationships/`](relationships/CLAUDE.md) | Soft relationships | §6 |
| [`dependencies/`](dependencies/CLAUDE.md) | Dependencies + todo fanout | §6 |
| [`structure/`](structure/CLAUDE.md) | Parts + chapters | §7 |
| [`plotlines/`](plotlines/CLAUDE.md) | Plotlines | §7 |
| [`characters/`](characters/CLAUDE.md) | Characters | §7 |
| [`todos/`](todos/CLAUDE.md) | Todos | §8 |
| [`conversations/`](conversations/CLAUDE.md) | Conversations, messages (SSE), AI-Job runs | §9 |
| [`proposals/`](proposals/CLAUDE.md) | Accept/reject proposals | §10 |
| [`jobs/`](jobs/CLAUDE.md) | Job list | §11 |
| [`events/`](events/CLAUDE.md) | Book SSE channel | §12 |
| [`git/`](git/CLAUDE.md) | Git operations | §13 |
| [`compile/`](compile/CLAUDE.md) | Completeness check + compile | §14 |
