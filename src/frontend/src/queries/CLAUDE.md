# queries — TanStack Query hooks

Server-state hooks over the [api client](../api/CLAUDE.md), plus the query-key factory. This is where caching, invalidation, and optimistic patches live.

Parent: [src](../CLAUDE.md). Spec: [doc 06 §2](../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Query keys (single factory)

`['book', id]` · `['scenes', bookId]` · `['todos', bookId]` · `['conversations', bookId, sceneId]` · `['jobs', bookId, sceneId]` · `['git', bookId]` · `['compileCheck', bookId]` · `['settings', section]`.

## Guidelines

- One hook per read (e.g. `useScenes(bookId)`, `useBook(id)`, `useTodos(bookId)`, `useCompileCheck(bookId)`) and per mutation (with cache updates on success).
- Mutations update caches directly where the API returns the affected objects (e.g. scenes POST/PATCH return `affectedScenes` → patch `['scenes']` without refetch).
- SSE-driven patches are applied by [events](../events/CLAUDE.md) against these same keys; keep key usage consistent so both paths agree.
