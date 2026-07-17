# api/scenes

Scene CRUD, prose content saves, on-demand enrichment, and per-scene sub-lists. The heart of the book. Handled by `SceneService` + `ChainService`. Spec: [doc 04 §5](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/scenes` | `{ scenes:[Scene], relationships:[SoftRelationship], sentinels:["scn-START","scn-END"] }`. ChainService computes `seq`/`placement` per active scene (trunk → unanchored → floating → orphan); archived included with `placement:"archived"`, `seq:null`. Powers graph + table |
| POST | `/api/books/{b}/scenes` | Requires title+description. Creates empty `.md`, splices into the hard chain (prev/next; both → must be adjacent), creates soft relations. 201 `{ scene, affectedScenes }` |
| GET | `/api/books/{b}/scenes/{id}` | `{ ...Scene, content }` — the **only** read including prose (editor load) |
| PATCH | `/api/books/{b}/scenes/{id}` | Metadata only (title slug-renames the file). `chapterId` XOR `partId` enforced on merged result. prev/next → detach-heal + splice. `status` archive/active. **Never touches prose or contentHash**. Returns `{ scene, affectedScenes }` |
| PUT | `/api/books/{b}/scenes/{id}/content` | `{ content }` full-document replacement (autosave). Atomic write → recompute wordCount + sha256 → if hash changed: dependency-todo fanout (dedup open todos). **No enrichment timer.** Returns `{ wordCount, contentHash, todosCreated }` |
| POST | `/api/books/{b}/scenes/{id}/enrich` | `{ scope: summary\|characters\|both }` on-demand AI-redo; **ignores** bookkeeping toggles. 422 `no-utility-model` if no model resolves for any requested field. Opens one `queued` bookkeeping conversation per field (`both` → two). 202 `{ conversationIds }` |
| POST | `/api/books/{b}/scenes/{id}/enrich/auto` | Leave-scene; respects toggles. 202 `{ queued:true, conversationIds }` or 200 `{ queued:false, conversationIds:[] }` when every enabled toggle lacks a configured model |
| GET | `/api/books/{b}/scenes/{id}/conversations` | `[ConversationSummary]` from derived index, newest first. Book-parented threads (no scene) list instead from `GET /books/{b}/conversations` — see [api/conversations](../conversations/CLAUDE.md) |
| GET | `/api/books/{b}/scenes/{id}/todos` | `[Todo]` for this scene, open first then createdAt desc. Persisted in the scene's own `scenes/{id}/todos.json`, not the book-level `db/todos.json` (doc 03 §Todos storage split — see [api/todos](../todos/CLAUDE.md)) |
| POST | `/api/books/{b}/scenes/{id}/todos` | `{ action (req) }` — `parentType`/`parentId` implied by the URL. Origin `user`, status `open`. 201 Todo. PATCH/DELETE by id use the shared `/books/{b}/todos/{id}` routes |
| GET | `/api/books/{b}/scenes/{id}/dependencies` | `{ dependsOn:[...], dependedOnBy:[...] }` with titles resolved server-side |

## Hard rules & invariants

- **Prose is sacred**: content only changes via this PUT (author autosave) or an applied edit proposal (author-triggered). No AI path writes here.
- Sentinels `scn-START`/`scn-END`: nothing before Start, nothing after The End.
- Splice/splice-heal is ChainService's job; `seq`/`placement` are computed on read, never stored.
