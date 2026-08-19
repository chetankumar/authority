# api/search — book Q&A over a derived Chroma index

Parent: [api](../CLAUDE.md). Spec: doc 04 Search, doc 05 (chunk summaries + answer one-shot).

Ask is in-request. Index / rebuild / delete go through `SearchIndexWorker`.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/search` | `{ question }` → `{ answer, hits, indexedSceneCount }` |
| GET | `/api/books/{b}/search/index` | Status + per-scene catalog |
| POST | `/api/books/{b}/search/index/rebuild` | Enqueue all active scenes; 202 |
| DELETE | `/api/books/{b}/search/index` | Enqueue wipe of `search-index/`; 204 |

Scene-scoped index: `POST /api/books/{b}/scenes/{id}/index` on the scenes router.
