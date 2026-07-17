# 04 — API Reference

Complete contract for every endpoint: request schema, response schema, field semantics, execution logic (which services engage and in what order), and error behavior. Shared objects and enums are defined once in §2 and referenced throughout — treat §2 as the components section of an OpenAPI document.

---

## 1. Conventions

### 1.1 General

- Base path `/api`. Request/response bodies are JSON (`application/json`) unless marked **multipart** or **SSE**.
- Timestamps: ISO 8601 UTC strings (`"2026-07-15T09:30:00Z"`).
- IDs: `{prefix}-{6hex}` per doc 03. Sentinel scene IDs `scn-START` / `scn-END` are accepted wherever noted.
- Field marked `?` = optional. PATCH endpoints are partial: omitted fields are unchanged; explicit `null` clears a nullable field.
- FastAPI + Pydantic: every request/response below corresponds to a Pydantic model; OpenAPI docs auto-served at `/docs`.

### 1.2 Error envelope

All non-2xx responses:

```json
{ "error": "human-readable summary", "detail": { /* structured, endpoint-specific */ } }
```

| Code | Meaning | `detail` convention |
|---|---|---|
| 400 | Malformed request | — |
| 403 | Filesystem permission failure | `{ "path": "..." }` |
| 404 | Unknown id / book / file | `{ "kind": "scene", "id": "..." }` |
| 409 | Blocked operation (referenced deletion, compile errors, already-exists) | `{ "blockedBy": {...} }` or `{ "errors": [CheckItem] }` |
| 422 | Validation failure | `{ "fields": { "fieldName": "message" }, ... }` |
| 500 | Unexpected server error | `{ "trace_id": "..." }` (full trace to log only) |

### 1.3 Service layer

Routers hold no logic. Every router validates via Pydantic, then delegates:

| Service | Responsibility |
|---|---|
| **SettingsService** | `app.json` read/write; model-config and AI-Job validation (uses PlaceholderRegistry, ModelFactory for reference checks) |
| **PlaceholderRegistry** | Defines placeholders; validates prompts; resolves `@tokens` at run time against an explicit `scene_id` (reads via BookDataManager). Never infers “current” scene. See doc 05. |
| **ContextAssembler** | Builds LangChain message lists from conversations / one-shot prompts; injects CURRENT SCENE when callers pass parent scene id. See doc 05. |
| **BookScanner** | Scans booksHome; caches shelf; reads each book's `config/book.json` |
| **BookService** | Book creation (scaffold, git init, initial commit), rename/cover updates, folder rename |
| **BookDataManager** (one per open book) | Loads `db/*.json` + `config/book.json` into memory; owns the book's **asyncio mutation lock**; atomic write-through persistence; conversation files + derived index; ui.json |
| **ChainService** | Hard-chain algebra: splice, heal, walk, seq/placement computation, contiguity + completeness checks |
| **SceneService** | Scene CRUD orchestration; content saves (hash, word count); dependency-todo fanout; file naming/renames. `update_scene` is also the path the bookkeeping execute tools write through |
| **StructureService** | Parts/chapters linked lists; move-before/after rewiring; blocked deletions; plotlines; characters (uniqueness) + character relationships (directional, category + free text) |
| **ConversationService** | The single run entity: conversation lifecycle + `status` (open→queued→running→waiting/done/failed); message append; streams via AIOrchestrator; binds execute tools for bookkeeping kinds; emits `conversation` SSE |
| **AiJobService** | Prepares an AI-Job run: resolve the definition's prompt, open an `ai-job` conversation with it inside at `open`. No model call, no run record |
| **ProposalService** | Locates a proposal by id (via conversation index); applies/rejects; a code path that mutates on behalf of AI output (after author acceptance) |
| **ConversationWorker** | Standing task draining conversations at `status: queued` (automatic bookkeeping); per-book FIFO, ≤2 global; runs each via `ConversationService.send_message` |
| **EnrichmentService** | Creator only: opens `queued` bookkeeping conversations (summary / characters, `both` → two). Runs no model and writes no fields — the conversation does, via execute tools |
| **AIOrchestrator / ModelFactory** | `ModelConfig → LangChain BaseChatModel`; invoke_once / structured / stream + tool loop; `${ENV}` key resolution |
| **GitService** | GitPython wrapper: status/stage/unstage/discard/diff/commit/push/pull/log; post-write status checks |
| **CompileService** | Completeness check (errors/warnings); build to `compiled-book/` |
| **EventHub** | Per-book SSE pub/sub; all services emit through it |

**Mutation lifecycle (every write endpoint):** router → Pydantic validation → service acquires the book's asyncio lock → read in-memory state → validate business rules → mutate copies → BookDataManager persists changed files atomically (`.tmp` + fsync + `os.replace`) → release lock → GitService dirty-check → EventHub emit → response. Reads take no lock.

### 1.4 SSE conventions

Two SSE producers: the **book event channel** (§12) and **message streaming** (§9.3). Events are `event: {type}\ndata: {json}\n\n`. Clients reconnect with exponential backoff; the book channel is stateless (clients refetch on reconnect).

---

## 2. Shared objects & enums

### 2.1 Enums

**`provider`** — which LangChain adapter ModelFactory constructs:
`anthropic` (ChatAnthropic; apiKey optional — defaults to `ANTHROPIC_API_KEY`) · `openai` (ChatOpenAI; apiKey optional — defaults to `OPENAI_API_KEY`) · `gemini` (ChatGoogleGenerativeAI; apiKey optional — defaults to `GOOGLE_API_KEY`) · `openai-compatible` (ChatOpenAI with `base_url`; baseUrl required, apiKey optional — LM Studio etc.) · `ollama` (ChatOllama; baseUrl required).

**`outputType`** — how an AI-Job's model response is treated by ConversationService after streaming completes:
- `chat` — freeform reply; stored as a plain assistant message; no parsing, no proposals.
- `edit-proposals` — the server appends **format instructions** to the resolved prompt requiring the model to end its reply with a fenced JSON array of `{find, replace, rationale}` objects. The fenced block is parsed into `edit` **Proposal** objects attached to the assistant message (and stripped from the displayed content); the preceding prose remains as commentary. Unparseable → message degrades to `chat` and the job record carries a warning.
- `metadata-proposals` — same mechanism; items are `{field, newValue, rationale}` targeting the job's scene; parsed into `metadata-update` proposals (`oldValue` filled server-side from current state).

**`placement`** — computed scene classification (ChainService): `trunk` (on the chain connected to Start) · `unanchored` (on a hard chain not connected to Start) · `floating` (soft relationships only) · `orphan` (no relationships) · `archived`.

**`sceneStatus`**: `active` · `archived`.
**`relationshipType`** (soft): `before` · `after` · `around` — read as *fromScene is definitely-{type} toScene*.
**`todoStatus`**: `open` · `done` · `closed`. **`todoOrigin`**: `user` · `dependency` · `ai`.
**`conversationKind`**: `note` · `chat` · `ai-job` · `bookkeeping` · `task-discussion`.
**`conversationStatus`**: `open` · `queued` · `running` · `waiting` · `done` · `failed` · `archived`. This *is* the run lifecycle — there is no separate Job. `open` = idle (a note/chat, or an AI-Job whose prompt awaits the author's Send); `queued` = the worker will run it unattended (automatic bookkeeping); `running` = model in flight; `waiting` = a bookkeeping run asked the author something and stopped; `done`/`failed` terminal.
**`enrichScope`** (POST /scenes/{id}/enrich): `summary` · `characters` · `both`. `both` is resolved at creation into two conversations (one per field), never a persisted state.
**`proposalType`**: `edit` · `metadata-update` · `todo-create` · `character-create` · `character-relationship-create` · `resource-create`. **`proposalStatus`**: `pending` · `applied` · `rejected` · `not-found`. **`characterRelationshipCategory`**: `family` · `romantic` · `friendship` · `rivalry` · `professional` · `mentorship` · `other`.
**`parentType`** (conversations, todos): `scene` · `chapter` · `part` · `book`.
**`gitFileStatus`**: `modified` · `added` · `deleted` · `untracked` · `renamed`.

### 2.2 Objects

**ModelConfig**
```json
{ "id": "mdl-a1b2c3", "label": "Sonnet 4.6", "provider": "anthropic",
  "modelName": "claude-sonnet-4-6", "apiKeyMasked": "sk-ant-…x4Kd", "baseUrl": null }
```
`label` display name (UI dropdowns) · `modelName` the provider's model string, passed verbatim to the SDK · `apiKeyMasked` responses never carry the real key; requests carry `apiKey` (literal or `${ENV_VAR}`) · `baseUrl` endpoint override, required per provider rules above.

**ModelTestResult** (live model check)
```json
{ "ok": true, "message": "Hello! How can I help?", "error": null, "latencyMs": 412 }
```
`ok` whether the model answered · `message` a short excerpt of the reply (present when `ok`) · `error` a human-readable failure reason (present when not `ok`) · `latencyMs` round-trip time. Secrets never appear here.

**AIJobDefinition**
```json
{ "id": "aij-9x8y7z", "name": "Check Grammar",
  "prompt": "Proofread @selection_or_scene. Preserve author voice.",
  "defaultModelId": "mdl-a1b2c3", "outputType": "edit-proposals" }
```
`name` shown in the editor dropdown · `prompt` template containing `@placeholders`, resolved per run · `defaultModelId` FK → ModelConfig, preselected when run · `outputType` per §2.1.

**Placeholder** `{ "name": "@current_scene", "description": "Full prose of the target scene" }`

**BookSummary** (shelf) `{ "id", "title", "folderName", "hasCover" }`

**Book** (full context)
```json
{ "id": "bok-a3f9c2", "title": "My Great Novel", "hasCover": true,
  "systemPrompt": "...", "storySummary": "...",
  "bookkeeping": { "summaryOnSave": true, "charactersOnSave": true },
  "parts": [Part], "chapters": [Chapter] }
```
`parts` pre-sorted in chain order; `chapters` pre-sorted and carrying `partId` (grouping is a client concern). `bookkeeping` keys = standing consents for EnrichmentService.

**Part** `{ "id", "title", "description", "seq" }` — `seq` is a simple integer for ordering; no linked-list pointers. The API returns parts sorted by seq.
**Chapter** `{ "id", "title", "description", "partId", "seq" }` — `seq` is global across the book (not per-part). The client groups by `partId` for display.

**Scene** (metadata; prose never included except where noted)
```json
{ "id": "scn-1f2e9b", "title": "The Arrival", "file": "scenes/1f2e9b-the-arrival.md",
  "description": "...", "location": "", "dateTime": "",
  "previousSceneId": "scn-START", "nextSceneId": "scn-7bd210",
  "chapterId": null, "partId": null,
  "primaryPlotlineId": null, "secondaryPlotlineIds": [],
  "mood": "", "emotionalArc": "", "summary": "",
  "characters": [{ "characterId": "chr-x", "involvement": "Finds the key." }], "status": "active",
  "contentHash": "sha256:...", "wordCount": 1240,
  "seq": 1, "placement": "trunk",
  "createdAt": "...", "updatedAt": "..." }
```
`seq`/`placement` are **computed** by ChainService on read, never stored. `chapterId` XOR `partId` (both nullable, never both set). `dateTime`/`location` are free-text *story* values. `summary`/`characters` (each `{ characterId, involvement }`) are system-maintained when the corresponding bookkeeping toggle is on, manually editable regardless.
`primaryPlotlineId` is the scene's main plotline (nullable). `secondaryPlotlineIds` lists additional plotlines. A primary must not also appear in secondaries.

**SoftRelationship** `{ "id", "fromSceneId", "toSceneId", "type", "createdAt" }`
**Dependency** `{ "id", "sceneId", "dependsOnSceneId", "reason", "createdAt" }` — `sceneId` is the *dependent* scene; `reason` required, human text explaining the logical link.
**Character** `{ "id", "name", "aliases": [], "personality", "history", "notes", "sceneCount": 3 }` — `sceneCount` computed. Uniqueness enforced across all names **and** aliases.
**Plotline** `{ "id", "title", "description", "sceneCount": 5 }` — `sceneCount` is computed by scanning scenes (via `primaryPlotlineId` and `secondaryPlotlineIds`). Plotlines do not store scene references.
**Todo** `{ "id", "parentType", "parentId", "parentTitle", "action", "status", "origin", "sourceDependencyId", "conversationId", "createdAt", "updatedAt" }` — `parentTitle` resolved on read for grid display.

**ConversationSummary** (index rows) `{ "id", "kind", "title", "parentType", "parentId", "status", "updatedAt", "messageCount", "pendingProposals" }`

**Conversation** = ConversationSummary + `{ "aiParticipant": { "enabled": bool, "modelId": "mdl-..|null" }, "aiJobId": "aij-..|null", "aiJobName": "…|null", "createdAt", "messages": [Message] }`. The conversation *is* the run: `status` (from `conversationStatus` above) is its lifecycle, `aiJobId` links an AI-Job run back to its definition, `parentId` is its scene. There is no separate Job object.

**Message**
```json
{ "id": "msg-x", "author": "user", "modelId": null,
  "content": "markdown", "context": [ { "sceneId": "scn-..", "excerpt": "snapshot text" } ],
  "proposals": [Proposal], "createdAt": "..." }
```
`author` ∈ `user|assistant|system`; `modelId` set on assistant messages (which model spoke); `context` snapshot excerpts captured at send time (never live anchors).

**Proposal**
```json
{ "id": "prp-x", "type": "edit", "status": "pending", "resolvedAt": null,
  "payload": { "sceneId": "scn-..", "find": "exact current text",
               "replace": "replacement text", "rationale": "why" } }
```
Payload variants — `metadata-update`: `{ "targetType": "scene"|"character", "targetId", "field", "oldValue", "newValue", "rationale" }` (`field` any PATCHable scene or character metadata field; never prose). `todo-create`: `{ "parentType", "parentId", "action" }`. `character-create`: `{ "name", "aliases"?, …, "sceneId"? }` — Accept dedupes case-insensitively against existing name/aliases (reuses the existing character instead of erroring) and, if `sceneId` is set, tags the character onto that scene's `characters` with empty involvement. `character-relationship-create`: `{ "characterAId", "characterBId", "category", "aToB", "bToA", "description"?, "rationale"? }`.

**GitFile** `{ "path", "status": gitFileStatus, "staged": bool }`
**GitStatus** `{ "dirty": bool, "files": [GitFile], "ahead": 0, "behind": 0, "hasRemote": bool, "branch": "main", "summary": "7-new, 1-updated, 3-deleted" }`
**CommitInfo** `{ "hash", "message", "timestamp" }`

`summary` is the human-readable roll-up the top-bar badge renders: `"all-changes-synced"` when clean, otherwise the non-zero segments of `"{n}-new, {m}-updated, {k}-deleted"` (untracked + added → *new*, modified + renamed → *updated*, deleted → *deleted*). Status is read with `--porcelain -uall`: untracked **directories** must be expanded to their files, or a folder of five new scenes reads as one — and the count would then change on staging, which expands it anyway. The number must mean the same thing before and after staging.

`branch` is the current branch (short sha if HEAD is detached) — read-only orientation so the author knows what they're committing to. Branch *management* stays out of scope (doc 07 §6). `ahead`/`behind` reflect the last **fetched** state of the remote, exactly as they would in the author's own git.

**CheckItem** (compile) `{ "type": "scene-no-chapter", "message": "human text", "subjects": [ { "kind": "scene", "id": "scn-..", "title": "..." } ] }` — `type` is a stable machine key (full list §13); `subjects` enable deep-linking.

**CompileReport** `{ "filesWritten": ["compiled-book/part-1-x/chapter-1-y.md"], "sceneCount": 42, "chapterCount": 9, "warnings": [CheckItem] }`

---

## 3. Health & Settings

### GET /api/health
Launcher readiness poll; frontend disconnect detection. **Response** `{ "status": "ok", "version": "1.0.0" }`. No services engaged.

### GET /api/settings/user
**Response** `{ "name": "Chetan", "booksHome": "/Users/chetan/Books" }` (either may be `null` before setup). **Logic:** SettingsService reads app.json.

### PATCH /api/settings/user
**Request** `{ "name"?: string, "booksHome"?: string, "createBooksHome"?: bool }`
- `booksHome` — absolute path that will contain all book folders.
- `createBooksHome` — if true and the path doesn't exist, create it.

**Logic:** 1) If booksHome present: expanduser/normalize; if missing → 422 `path-not-found` unless `createBooksHome` (then `os.makedirs`); must be a directory (422) and writable (403, tested via tempfile probe). 2) SettingsService persists app.json atomically. 3) BookScanner cache invalidated. **Response:** updated settings object.

### GET /api/settings/models
**Response** `[ModelConfig]` (keys masked). SettingsService masks on serialization; real keys never leave the server after entry.

### POST /api/settings/models
**Request** `{ "label": string, "provider": provider, "modelName": string, "apiKey"?: string, "baseUrl"?: string }`
- `apiKey` — literal secret or `${ENV_VAR}`; stored as given, resolved at call time by ModelFactory.

**Logic:** 1) Provider rules: `openai-compatible`/`ollama` require baseUrl (422; baseUrl must parse as http(s) URL). `apiKey` is **optional for every provider** — an empty key means "use the provider's default environment variable" (`anthropic` → `ANTHROPIC_API_KEY`, `openai` → `OPENAI_API_KEY`, `gemini` → `GOOGLE_API_KEY`), resolved by ModelFactory at call time; a `${ENV_VAR}` reference or a literal are also accepted. 2) Generate `mdl-` id; persist. **Response:** the ModelConfig (masked). No connectivity test at save (models may be offline local servers); the model-test endpoint or first real use surfaces a missing/invalid key.

### PATCH /api/settings/models/{id}
**Request:** same fields, all optional. Omitted `apiKey` keeps the stored secret (clients round-trip the masked form by *not* sending the field). Re-validates provider rules against the merged result. 404 unknown id.

### DELETE /api/settings/models/{id}
**Logic:** SettingsService collects references — AI-Job `defaultModelId`s and every `ai.*ModelId` slot. Any → **409** `{ "blockedBy": { "aiJobs": [{id,name}], "utilityModel"?: true, "commitMessageModel"?: true, "characterParsingModel"?: true, "sceneSummaryModel"?: true, "chatDefaultModel"?: true } }` (only the slots actually referencing this model are present). Else remove. (Conversations referencing it historically are unaffected; a later message-send with a deleted model → 422 at send time.)

### POST /api/settings/models/{id}/test
**Logic:** SettingsService loads the stored config and asks ModelFactory to build the LangChain chat model, resolving a `${ENV_VAR}` key at call time; it then sends a single `"hello model"` chat completion (guarded by a ~30s timeout). **Response** 200 `ModelTestResult`: `ok:true` with a short reply excerpt + `latencyMs`, or `ok:false` with a human-readable `error` (unset env var, auth failure, unreachable base URL, timeout). **404** unknown id. This is the only settings endpoint that performs network I/O and it never mutates `app.json`; failures are results, not error responses (still 200), so the client renders them inline. No connectivity test happens on model create/patch — this endpoint is the explicit, on-demand check.

### GET /api/settings/ai
**Response** `{ "utilityModelId": "mdl-..|null", "commitMessageModelId": "mdl-..|null", "characterParsingModelId": "mdl-..|null", "sceneSummaryModelId": "mdl-..|null", "chatDefaultModelId": "mdl-..|null" }`. `utilityModelId` is the general-purpose fallback; each of the other four is a task-specific model that independently resolves to its own value if set, else `utilityModelId`, else unset (doc 05).

### PATCH /api/settings/ai
**Request:** any subset of the five `*ModelId` fields, each `"mdl-.."|null`; omitted fields are unchanged. 422 `{fields:{<field>: "Unknown model."}}` per field if its id is unknown.

### GET /api/settings/appearance
**Response** `{ "theme": "light" | "dark" | "system" }` — the app-wide color theme (doc 06 §1.2). **Logic:** SettingsService reads `app.json.appearance`; missing/unknown → `system`.

### PATCH /api/settings/appearance
**Request** `{ "theme": "light" | "dark" | "system" }`. 422 if not one of the three. Persists `app.json` atomically. **Response** the updated appearance object. App-level only — there is no per-book theme.

### GET /api/settings/ai-jobs
**Response** `[AIJobDefinition]`.

### POST /api/settings/ai-jobs
**Request** `{ "name": string, "prompt": string, "defaultModelId": string, "outputType": outputType, "force"?: bool }`
- `prompt` — the template; may contain `@placeholders` (§2.2 Placeholder / doc 05 registry).
- `force` — save despite unknown-placeholder warnings.

**Logic:** 1) 422 if name empty or defaultModelId unknown or outputType invalid. 2) PlaceholderRegistry scans the prompt with the token grammar `@[a-z0-9_]+`; tokens not in the registry → 422 `{ "detail": { "unknownPlaceholders": ["@charcter_sheet"] } }` **unless** `force:true` (then saved; unknown tokens will pass through literally at run time). 3) Persist with `aij-` id. **Response:** the definition.

### PATCH /api/settings/ai-jobs/{id}
Same fields optional; same validation on merged result.

### DELETE /api/settings/ai-jobs/{id}
Removes the definition. Historical job records/conversations keep the id + a name snapshot taken at run time; no gate.

### GET /api/settings/placeholders
**Response** `[Placeholder]` — the full registry (doc 05). Single source of truth for the frontend's `@` autocomplete; the client never hardcodes the list.

---

## 4. Books

### GET /api/books
**Logic:** 1) 422 `books-home-unset` if unconfigured. 2) BookScanner lists booksHome subdirectories; each containing a parseable `config/book.json` becomes a shelf entry; others silently ignored; unparseable book.json → entry with `"error"` flag (shelf shows a broken-book card) rather than failing the whole scan. **Response** `[BookSummary]`.

### POST /api/books — multipart
**Fields:** `title` (string, required) · `cover` (image file, optional).
**Logic (BookService):** 1) 422 empty title / booksHome unset; 403 booksHome unwritable. 2) Generate `bok-{6hex}`; slugify title; create `{6hex}-{slug}/` (409 `already-exists` on impossible collision). 3) Scaffold: `config/book.json` (id, title, empty systemPrompt/storySummary, bookkeeping both **true**, empty parts/chapters), `scenes/.gitkeep`, `db/` seeded empty collections + `conversations/index.json`, `assets/cover.{ext}` if uploaded (stored as-is), `compiled-book/.gitkeep`, `.gitignore` (`*.tmp`). 4) GitService: `git init` (folder is fresh by construction) → `add -A` → commit `"initialized"`. 5) BookScanner cache add. **Response** BookSummary, 201.

*Discovered books* (folder dropped into booksHome, e.g. cloned): never re-initialized; existing `.git` and settings left completely untouched; they simply appear on the next scan.

### GET /api/books/{id}
**Response** Book (§2.2). **Logic:** first request naming a book triggers BookDataManager load (all db files into memory; per-file corrupt handling per doc 03 Data Safety). ChainService pre-orders parts/chapters. Client caches; SSE keeps it fresh.

### PATCH /api/books/{id} — multipart
**Fields (all optional):** `title` · `cover` (file) · `removeCover` (bool) · `systemPrompt` · `storySummary` · `bookkeeping` (JSON string `{ "summaryOnSave"?, "charactersOnSave"? }`, shallow-merged).
**Logic:** under the book lock — 1) title: update book.json; compute new slug; `os.rename` the book folder (403 on failure, e.g. folder locked by another program; title change rolled back); BookScanner cache update. 2) cover/removeCover: replace or delete `assets/cover.*`. 3) Text/bookkeeping fields merged and persisted. 4) Git dirty-check + `git-status` emit; **title renames additionally auto-commit** `"renamed to {title}"` (folder+config must stay consistent in history). **Response** updated Book.

### PATCH /api/books/{id} — JSON
**Request** `{ "systemPrompt"?, "storySummary"?, "bookkeeping"?: { "summaryOnSave"?, "charactersOnSave"? } }` — JSON-only alternative for the Book tab on the Metadata page (no title rename or cover handling). Same merge/persist logic as the multipart variant for these fields. **Response** updated Book.

### GET /api/books/{id}/cover
Streams the cover with correct content-type; **404** if none (client renders placeholder).

### GET /api/books/{id}/ui · PATCH /api/books/{id}/ui
GET returns `db/ui.json` verbatim (client-defined shape: AG Grid column state, right-pane visibility). PATCH shallow-merges and persists; client debounces (~1s). No validation beyond JSON-ness — this file is the client's.

---

## 5. Scenes

### GET /api/books/{b}/scenes
**Response**
```json
{ "scenes": [Scene], "relationships": [SoftRelationship],
  "sentinels": ["scn-START", "scn-END"] }
```
**Logic:** BookDataManager memory read → ChainService computes `seq`/`placement` for every active scene: walk Start's `nextSceneId` chain → seq 1..n (`trunk`); remaining hard chains (found by scanning for chain heads) numbered after, in stable id order (`unanchored`); soft-only scenes next, ordered by their anchor's seq (`floating`); relationless last (`orphan`). Archived scenes included in the array with `placement:"archived"`, `seq:null` — clients filter. Powers graph + table from one payload.

### POST /api/books/{b}/scenes
**Request**
```json
{ "title": "string (required)", "description": "string (required)",
  "previousSceneId"?: "scn-..|scn-START", "nextSceneId"?: "scn-..|scn-END",
  "softRelations"?: [ { "type": relationshipType, "sceneId": "scn-.." } ],
  "chapterId"?: "chp-..", "partId"?: "prt-..",
  "location"?: "", "dateTime"?: "", "mood"?: "", "emotionalArc"?: "" }
```
**Logic (SceneService, under lock):** 1) 422: empty title/description; both chapterId+partId set (`chapter-xor-part`); unknown FKs; prev/next sentinel violations (nothing precedes Start / follows The End). 2) Generate id; create empty `scenes/{hash}-{slug}.md`; contentHash of empty content, wordCount 0. 3) **Splice** (ChainService): if `previousSceneId=A` and A→B exists → rewire A→New→B (B's previous updated); mirror for nextSceneId; if both given they must be currently adjacent (422 `not-adjacent`) — splice between them. 4) Create SoftRelationship rows (dedup exact duplicates silently). 5) Persist — master `scenes.json` (identity/chain/structure fields) plus the new scene's `meta.json`/`bookkeeping.json`/`relationships.json` (doc 03: everything else, split per-scene); emit `scene-updated`. **Response 201** `{ "scene": Scene, "affectedScenes": [Scene] }` — affected = neighbors whose links changed; client patches the graph without refetch. `Scene` itself is unchanged — still the full assembled shape regardless of the storage split.

### GET /api/books/{b}/scenes/{id}
**Response** `{ ...Scene, "content": "full markdown prose" }` — the only scene read that includes prose (editor load). Reads the .md file directly.

### PATCH /api/books/{b}/scenes/{id}
**Request (all optional):** `title` (slug-renames the .md file; `file` field updated) · `description` · `location` · `dateTime` · `mood` · `emotionalArc` · `summary` (manual edit) · `characters` (full replacement array of `{ characterId, involvement }`; unknown ids 422) · `chapterId` / `partId` (XOR enforced on the merged result; setting one clears the other implicitly? **No** — client sends the clear explicitly as `null`; server 422s if both end up set) · `previousSceneId` / `nextSceneId` (ChainService: detach-heal old links, splice new) · `status` (`archived`: splice-heal chain, soft relations kept dormant; `active`: return floating — old slot not reclaimed).
**Logic:** under lock; sentinel/FK validation as in create; persist; emit `scene-updated` with the changed-field list. **Response** `{ "scene": Scene, "affectedScenes": [Scene] }`. Metadata PATCH never touches prose or contentHash.

### PUT /api/books/{b}/scenes/{id}/content
**Request** `{ "content": "full markdown" }` — full-document replacement (autosave semantics; no patching).
**Logic (SceneService, under lock):** 1) Atomic write of the .md (tmp + fsync + replace). 2) Recompute wordCount (whitespace tokenization) + sha256 contentHash. 3) **If hash changed:** dependency fanout — for every Dependency where `dependsOnSceneId == this`, create a Todo on the dependent scene: action `"'{this.title}' changed — verify dependency: {reason}"`, origin `dependency`, `sourceDependencyId` set; **dedup:** skip if an *open* todo for the same dependency already exists (typing sessions must not stack duplicates); emit `todos-created` if any. Enrichment is **not** scheduled from content save (leave-scene / on-demand only). 4) Persist — `scenes/{id}/bookkeeping.json` **only** (doc 03); the master `db/scenes.json` is never touched by a content save. **Response** `{ "wordCount": 1240, "contentHash": "sha256:..", "todosCreated": [Todo] }`.

### POST /api/books/{b}/scenes/{id}/enrich
**Request** `{ "scope": "summary" | "characters" | "both" }` — the on-demand AI-redo; **ignores** bookkeeping toggles (an explicit request is its own consent).
**Logic:** 422 `no-utility-model` if *neither* task-specific model needed for the requested scope resolves (own slot or its utility-model fallback). EnrichmentService opens one `queued` **bookkeeping conversation** per field in scope (`both` → two, each on its own configured model), each seeded with a resolved prompt; the [conversation worker](05-ai-system.md) runs them. **Response 202** `{ "conversationIds": ["cnv-..", …] }`; results arrive as `conversation` + `scene-updated` SSE events.

### POST /api/books/{b}/scenes/{id}/enrich/auto
Leave-scene path. **No body.** Reads the book's `bookkeeping` toggles and opens a bookkeeping conversation only for enabled halves with a resolvable model. **Response 202** `{ "queued": true, "conversationIds": [...] }` when at least one was created; **200** `{ "queued": false, "conversationIds": [] }` when toggles/models skip.

### GET /api/books/{b}/scenes/{id}/conversations
**Response** `[ConversationSummary]` for `parentType=scene, parentId=id`, from the derived index (no conversation files opened). Newest first.

### GET /api/books/{b}/scenes/{id}/todos
**Response** `[Todo]` for this scene, open first then by createdAt desc. Persisted in the scene's own `scenes/{id}/todos.json`, not the book-level `db/todos.json` (doc 03 §Todos storage split).

### POST /api/books/{b}/scenes/{id}/todos
**Request** `{ "action": required }`. `parentType`/`parentId` are implied by the URL (`scene`/`id`) — origin `user`, status `open`. **201** Todo. PATCH/DELETE by id use the shared `/books/{b}/todos/{id}` routes below regardless of which tier a todo lives in.

### GET /api/books/{b}/scenes/{id}/dependencies
**Response**
```json
{ "dependsOn":    [ { "id": "dep-..", "sceneId": "scn-02", "sceneTitle": "The Cellar", "reason": ".." } ],
  "dependedOnBy": [ { "id": "dep-..", "sceneId": "scn-10", "sceneTitle": "The Reveal", "reason": ".." } ] }
```
`dependsOn`: what this scene requires (editable in the modal). `dependedOnBy`: read-only warning view — what leans on this scene before you rewrite it. Titles resolved server-side.

---

## 6. Soft relationships & Dependencies

### POST /api/books/{b}/relationships
**Request** `{ "fromSceneId", "toSceneId", "type": relationshipType }`. **Logic:** 422: identical ids; unknown ids; `toSceneId==scn-START` with type `after`/`around` reversed-sentinel violations (formally: nothing may be *before* Start or *after* The End in resulting semantics); exact duplicate → 200 returning the existing row (idempotent). **Response 201** SoftRelationship.

### DELETE /api/books/{b}/relationships/{id}
Removes the edge. 404 unknown.

### POST /api/books/{b}/dependencies
**Request** `{ "sceneId": "the dependent scene", "dependsOnSceneId": "the required scene", "reason": "required non-empty" }`. **Logic:** 422 on self-dependency, unknown/archived/sentinel scenes, empty reason, duplicate pair (same sceneId+dependsOnSceneId). Creating fires **no** todo — todos fire on later content change of the depended-on scene (implemented: `SceneService._fanout_dependency_todos`, run on every content save whose hash changed, deduped against any todo already open for the same `sourceDependencyId`). **Response 201** Dependency.

> Note: this endpoint (create/edit/delete a *dependency edge*) is not yet exposed via CRUD API — only the read side (`GET /scenes/{id}/dependencies`) and the fanout above exist today (doc 03 §scenes/{id}/dependencies.json).

### PATCH /api/books/{b}/dependencies/{id}
**Request** `{ "reason": string }` (only the reason is mutable; re-pointing = delete + create).

### DELETE /api/books/{b}/dependencies/{id}
Removes it; existing dependency-generated todos remain (they're the author's to close); no gate.

---

## 7. Parts, Chapters, Plotlines, Characters

### GET /api/books/{b}/parts → `[Part]` sorted by `seq`.

### POST /api/books/{b}/parts
**Request** `{ "title": required, "description"?: "" }`. Assigns `seq = max(existing) + 1`. **201** Part.

### PATCH /api/books/{b}/parts/{id}
**Request** `{ "title"?, "description"? }` — metadata only, no reordering (use the reorder endpoint). **Response** Part.

### POST /api/books/{b}/parts/reorder
**Request** `{ "ids": ["prt-a", "prt-b", ...] }` — the complete ordered list of all part IDs. Validates every existing part is present (422 if missing or extra). Reassigns `seq` 1..n in the given order. **Response** `[Part]` in new order.

### DELETE /api/books/{b}/parts/{id}
**Logic:** collect chapters with this partId + scenes with this partId. Any → **409** `{ "blockedBy": { "chapters": [{id,title}], "scenes": [{id,title}] } }` — the author must manually unassign each before deletion succeeds (strict rule; nothing is auto-unassigned). Else: delete and compact remaining seq numbers. **204**.

### Chapters — same CRUD contract as parts, plus:
- `GET` → `[Chapter]` each carrying `partId`, sorted by global `seq` (client groups by part; part-less chapters group as "unassigned").
- `POST` request adds `"partId"?: "prt-.."` (optional; assignable later — but required for compilation). Auto-assigns next seq.
- `PATCH` also accepts `partId` (or `null` to unassign). Metadata only, no reordering.
- `POST /api/books/{b}/chapters/reorder` — `{ "ids": [...] }` reassigns seq 1..n. Same semantics as parts reorder.
- `DELETE` blocked (409) while any scene has this chapterId, listing them. Compacts seq on success.

### GET /api/books/{b}/plotlines → `[Plotline]` with computed `sceneCount` (scanned from scenes' `primaryPlotlineId` and `secondaryPlotlineIds`).
### POST — `{ "title": required, "description"? }` → 201.
### PATCH /{id} — `{ "title"?, "description"? }`.
### DELETE /{id} — **409** `{ "blockedBy": { "scenes": [{id,title}] } }` while any scene references this plotline (via `primaryPlotlineId` or `secondaryPlotlineIds`); unassign from scenes first.

### GET /api/books/{b}/characters → `[Character]` with computed `sceneCount`.
### POST — `{ "name": required, "aliases"?: [], "age"?, "gender"?, "nationality"?, "ethnicity"?, "occupation"?, "want"?, "need"?, "flaw"?, "arc"?, "personality"?, "history"?, "notes"? }`. **Uniqueness:** the new name and every alias must not collide (case-insensitive) with any existing character's name or aliases → 422 `{ "conflict": { "value": "Marlow", "existingCharacter": {id,name} } }`. The enrichment matcher must never face ambiguity.
### PATCH /{id} — same fields (partial); same uniqueness on the merged result.
### DELETE /{id} — **409** `{ "blockedBy": { "scenes"?: [...], "relationships"?: [...] } }` listing scenes whose `characters` reference it and/or `character_relationships` rows involving it; unassign/remove first.

### GET /api/books/{b}/character-relationships → `[CharacterRelationship]`.
### POST — `{ "characterAId", "characterBId", "category", "aToB", "bToA", "description"? }` → 201. Validates both ids exist, `characterAId != characterBId`, and no existing record already covers this unordered pair → 422 on any violation.
### PATCH /{id} — `{ "category"?, "aToB"?, "bToA"?, "description"? }`.
### DELETE /{id} — unblocked, like scene relationships. **204**.

---

## 8. Todos

Storage is split by `parentType` (doc 03 §Todos storage split): scene-parented
todos persist in the owning scene's own `scenes/{id}/todos.json`; every other
todo (`chapter`/`part`/`book`) persists in the book-level `db/todos.json`.
This router only ever reads/writes the latter tier for create; scene-parented
todos are created via `POST /scenes/{id}/todos` (§5). PATCH/DELETE-by-id work
on either tier transparently — the id resolves to its storage location
server-side (`BookDataManager.find_todo`), the same pattern
`DELETE /relationships/{id}` already uses.

### GET /api/books/{b}/todos → `[Todo]` (book-level: chapter/part/book-parented only, parentTitle resolved). Filtering/sorting is client-side (AG Grid).
### GET /api/books/{b}/todos?includeScenes=true → `[Todo]` — the above **plus** every scene's todos, flattened. Read fresh on each call rather than from a maintained index (doc 03): this is a rare, human-paced request (opening the Tasks page with its toggle on), not a hot path, so there's no reverse index to keep in sync.
### POST — `{ "parentType", "parentId", "action": required }`, `parentType` must not be `scene` (422 — use `POST /scenes/{id}/todos` instead) → origin `user`, status `open`. 422 unknown parent. **201** Todo.
### PATCH /{id} — `{ "status"?: todoStatus, "action"?: string, "conversationId"?: string }`. `conversationId` is set-once (links the todo to the conversation it's discussed in — the 💬 affordance in both the Tasks page and the editor's To-dos accordion); there's no way to clear it back to null via this endpoint.
### DELETE /{id} — hard delete (kept for mistakes; normal lifecycle is `closed`). **204**.

Dependency-fanout todos (§6) and accepted `todo-create` proposals (§10) both
land here through the same `TodoService.create` path, not a separate one —
an AI-raised todo (from `propose_todo` in chat, or an AI-Job's output) has its
`conversationId` set automatically to the conversation it was proposed in, so
its 💬 opens straight back into that discussion.

---

## 9. Conversations, Messages, AI-Job runs

### GET /api/books/{b}/conversations
Book-parented threads only (`parentType: "book"`) — the Resources page's chat list. Scene-parented threads still list from `GET /books/{b}/scenes/{scene_id}/conversations` (§5). **Response** `ConversationSummary[]`.

### POST /api/books/{b}/conversations
**Request**
```json
{ "kind": conversationKind, "parentType": parentType, "parentId": "..",
  "aiParticipant"?: { "enabled": bool, "modelId": "mdl-..|null" },
  "title"?: "optional initial title" }
```
Default aiParticipant: `{enabled:false, modelId:null}` (note-stacking). **Logic:** ConversationService creates `cnv-{hex}.json` with empty messages; title is the optional `title` or `"Untitled"`. Index updated. **201** Conversation. *(AI-Job runs use §9.4; automatic bookkeeping runs are created by EnrichmentService — see [doc 05](05-ai-system.md).)*

### GET /api/books/{b}/conversations/{id}
**Response** full Conversation with messages + proposals (per-file load on demand).

### PATCH /api/books/{b}/conversations/{id}
**Request** `{ "title"?, "status"?: "open"|"archived", "aiParticipant"?: { "enabled"?, "modelId"? } }` — the mid-thread AI toggle and model switch live here. Enabling with no modelId and none previously set → 422 `model-required`.

### DELETE /api/books/{b}/conversations/{id}
Hard delete for mistakes. Removes `cnv-*.json` and the index entry; emits `conversation {status:"deleted"}`. **204**. Rejected **409** `generation-in-progress` if a stream is active.

### 9.3 POST /api/books/{b}/conversations/{id}/messages — **SSE response**
**Request**
```json
{ "content": "markdown (required)",
  "context"?: [ { "sceneId": "scn-..", "excerpt": "selected text snapshot" } ] }
```
**Logic (ConversationService):**
1. Append the user Message (id, timestamp; excerpts stored verbatim). Persist + index update.
2. If title is still `"Untitled"`: call the **utility model** with a dedicated naming prompt (ask for 3–5 words; **not** chat-assistant framing). Persist the model’s reply as returned (trim whitespace only — no sanitizer / word clipping); on missing utility model / failure → first ~5 words of the user message. Emit SSE `title` `{ "title": ".." }`.
3. Emit SSE `message` for the user turn. **aiParticipant.enabled == false:** then `done`. Done (pure note).
4. **enabled == true:** resolve ModelConfig (422 `model-missing`/`model-deleted` if unresolvable). Build the LangChain call: system = book systemPrompt + Authority's assistant framing + CURRENT SCENE (omitted entirely for a `parentType: "book"` conversation — there is no current scene) + tool schemas; history = conversation messages mapped to roles (context excerpts injected as quoted blocks inside user turns; `@placeholders` in user text resolved for the model when a scene is in context); bind read + propose tools (doc 05) — every read tool, including `list_resources`/`get_resource`, is already book-scoped, so a book-level chat has the same read surface as a scene one.
5. Respond as **SSE**: `token` events (`{ "text": ".." }`) as the model streams; tool calls execute server-side mid-stream (read tools answer from BookDataManager; propose tools accumulate Proposal objects; **execute** tools — bound only for `bookkeeping`-kind conversations — write scene bookkeeping via SceneService); on completion, persist the assistant Message (content, modelId, proposals) and send a final `message` event carrying it, then `done`. For run kinds (`ai-job`/`bookkeeping`), also transition `status` (`running` → `done`, or `waiting` when a bookkeeping reply called no tool, i.e. asked a question) and emit `conversation`.
6. Model/tool failure mid-stream → `error` event `{ "error": ".." }`; user message stays persisted; no assistant message written. For run kinds this also sets `status: failed` and appends the error as a visible system message.
- `body` may be omitted (worker path): generate against the thread as it stands, with no new user message.
Concurrent sends to one conversation are rejected 409 `generation-in-progress`.

### 9.4 POST /api/books/{b}/ai-jobs/run
**Request**
```json
{ "aiJobId": "aij-..", "sceneId": "scn-..",
  "scope": "full" | "selection", "selectionText"?: "required when scope=selection" }
```
**Logic (AiJobService.prepare, synchronous — no model call):** 1) 422: unknown job/scene; scope `selection` without selectionText. 2) Resolve the definition's prompt template against the scene (`@placeholders`; selectionText feeds `@selection`), appending format instructions (§2.1) for `edit-proposals`/`metadata-proposals`. 3) Create a Conversation: kind `ai-job`, parent = the scene, title = **definition name**, aiParticipant `{enabled:true, modelId: definition.defaultModelId}`, `aiJobId` + name snapshot, status `open`, with the resolved prompt as its first (system-authored) message. **Response 201** `{ "conversationId" }`. The client opens the modal on it; the prompt is already there to review and **nothing runs** until the author sends. That send is an ordinary §9.3 message; the definition's `outputType` (looked up via `conv.aiJobId`) drives fenced-JSON → proposal parsing (parse failure → plain chat). Follow-ups are plain §9.3 sends.

---

## 10. Proposals

### POST /api/books/{b}/proposals/{id}/accept
**Logic (ProposalService, under book lock):** locate the proposal via the conversation index (404 unknown; 409 `already-resolved` if not pending). By type:
- **edit:** read the target scene's .md; find the *first exact occurrence* of `payload.find` (byte-exact, no normalization). Absent → status `not-found`, nothing changes, response reports it. Present → replace **one** occurrence, save through the standard content path (**PUT semantics: hash recompute → dependency fanout → settle timer** — an applied edit is a content change like any other). This is the sole prose-mutation path besides the editor, and it is author-triggered.
- **metadata-update:** apply `payload.newValue` to `payload.field` on `targetType` `scene` (via SceneService PATCH) or `character` (via StructureService character PATCH). Validation failure → 422, proposal stays pending. `oldValue` filled from current state on accept when missing.
- **todo-create:** create the Todo via `TodoService.create`, origin `ai`, routed to whichever storage tier `parentType` calls for (§8). `conversationId` is set automatically to the proposing conversation, so the todo's 💬 opens straight back into it.
- **character-create:** create the Character via StructureService uniqueness rules; optionally tag `sceneId` on the scene. 422 if Characters layer not loaded.
- **resource-create:** write `payload.content` into `resources/{payload.filename}` via `ResourceService.create_text_file` (§15). Name collision → suffixed, never overwritten; the response's filename may differ from the proposed one. This is the *only* write path for an AI-drafted resource file — there is no execute tool for it (doc 01 write-permission table).
Stamp status `applied` (or `not-found`) + resolvedAt; persist conversation; emit `scene-updated`/`todos-created` as applicable.
**Response** `{ "proposal": Proposal, "result": { "wordCount"?, "contentHash"?, "todo"?: Todo, "resource"?: ResourceFile } }`.

### POST /api/books/{b}/proposals/{id}/reject
Marks `rejected` + resolvedAt; touches nothing else. **Response** the Proposal. *(Accept-all = client loops accept sequentially, stopping to display any `not-found`s; deliberately no batch endpoint — no batch atomicity.)*

---

## 11. Runs are conversations

There is no jobs endpoint. An AI run — an AI-Job the author triggers (§9.4) or an automatic bookkeeping pass ([doc 05](05-ai-system.md)) — is a Conversation with `kind` `ai-job`/`bookkeeping` and a lifecycle `status`. The editor's **AI Jobs** accordion is `GET /scenes/{id}/conversations` (§5) filtered to those two kinds; live transitions arrive via the `conversation` SSE event (§12).

---

## 12. Events — GET /api/books/{b}/events (SSE)

One connection per open book. Event types and payloads:

| event | data | emitted when |
|---|---|---|
| `conversation` | `{ id, kind, parentType, parentId, status }`, or `{ id, status: "deleted" }` | a conversation is created or changes status (an AI run starting, finishing, landing in `waiting`), or is deleted |
| `scene-updated` | `{ id, changed: ["summary","characters"] }` | any scene metadata write (author, enrichment via execute tools, accepted proposal) |
| `todos-created` | `{ todos: [Todo] }` | dependency fanout or accepted todo-create |
| `git-status` | `GitStatus` (§2.2, includes `summary`) | **(a)** the git-status worker's 5s debounce fired after a `book-changed`; **(b)** immediately, in-request, after an explicit stage/unstage/commit/push/pull |
| `compile-done` | `{ report: CompileReport }` | successful compile |

Clients patch TanStack Query caches from these; on reconnect, refetch active queries (channel is stateless).

**Internal events.** `book-changed` `{}` is emitted by BookDataManager after *any* `db/*.json` or `config/book.json` write. It is a payload-free signal for server-side consumers (today: the git-status worker, via the hub's global `subscribe_all` channel) and carries no information a client can act on — clients ignore unrecognized event types, so no server-side filtering is needed on the per-book channel.

**Defense in depth.** SSE is the fast path, not the only path. Clients that render git state also poll `GET /git/status` every 10s, so a dropped `book-changed`, a lost `git-status`, or a silently broken SSE reconnect still self-corrects within ~10s. The channel being stateless is what makes this safe: the poll and the event write identical server truth into the same cache entry.

---

## 13. Git

All endpoints: GitService (GitPython over the system git; the user's credentials/SSH config apply). 404 if the book folder lost its `.git`.

**Emission rule:** every *mutating* endpoint here (stage, unstage, discard, commit, push, pull) recomputes status and emits `git-status` **immediately, in-request** — the author is on the Git page waiting, so these never go through the git-status worker's 5s debounce. The worker exists only for *incidental* dirtying from unrelated writes (scene autosave, structure edits), where nobody is watching. Reads (`status`, `diff`, `log`) emit nothing.

### GET /api/books/{b}/git/status → GitStatus (§2.2). Page load + badge initial state; also the 10s client poll (§12).
### POST /api/books/{b}/git/stage · /unstage — **Request** `{ "paths"?: ["scenes/x.md"], "all"?: true }` (one required). Real `git add` / `git reset` on those paths. **Response** refreshed GitStatus; emits `git-status`.
### POST /api/books/{b}/git/discard — **Request** `{ "paths"?: ["scenes/x.md"], "all"?: true }` (one required). VS Code-style: tracked paths → `git restore --source=HEAD --staged --worktree`; untracked → `git clean -f`. Drops the book's in-memory `BookDataManager` so the next API read reloads from disk (discarded JSON/prose must not keep serving from cache). **Response** refreshed GitStatus; emits `git-status`.
### GET /api/books/{b}/git/diff?path= — **Response** `{ "path", "diff": "unified diff text (staged+unstaged vs HEAD)" }`; binary files → `{ "binary": true }`.
### POST /api/books/{b}/git/suggest-message
**Logic:** staged diff (422 `nothing-staged` if empty) → truncate to a size cap (~20k chars, largest hunks first) → **commit-message model** (`ai.commitMessageModelId`, falling back to the utility model): *"Summarize these changes to a novel manuscript as a single-line git commit message."* No commit-message model resolvable → deterministic fallback from stats (`"3 scenes updated, 1 added"`). **Response** `{ "message": "..." }` — fills the textarea, author edits freely.
### POST /api/books/{b}/git/commit — **Request** `{ "message": required non-empty }`. 422 `nothing-staged`. Commits staged files. **Response** `{ "hash" }`; emits `git-status`.
### POST /api/books/{b}/git/push · /pull — 422 `no-remote` if unconfigured. Errors pass through as readable messages (`detail.gitError`); pull halts on conflicts with guidance *"resolve with your git tooling"* — Authority never attempts conflict resolution. **Response** `{ "ok": true, "summary": "..." }`; emits `git-status`.
### GET /api/books/{b}/git/log?limit=20 → `[CommitInfo]`.

---

## 14. Compilation

### GET /api/books/{b}/compile/check
**Response** `{ "ready": bool, "errors": [CheckItem], "warnings": [CheckItem] }`.
**CheckItem types — errors (block):** `scene-no-chapter` (active scene without chapterId; includes direct-to-part scenes) · `chain-broken` (active scene missing prev or next, sentinels aside) · `chain-not-single-path` (chain from Start doesn't reach The End covering all active scenes; multiple chains) · `chain-cycle` · `scene-floating` / `scene-orphan` (place or archive) · `chapter-no-part` (chapter with scenes but no partId) · `chapter-not-contiguous` (a chapter's scenes are not consecutive in the chain) · `soft-relation-contradicted` (chain order violates a definitely-before/after).
**Warnings (inform):** `chapter-empty` (emitted heading-only) · `part-empty` · `scene-no-summary` · `soft-relation-redundant` (satisfied by the chain; invites cleanup).
**Logic:** ChainService walks Start→End validating path/coverage/cycles; StructureService checks assignments + contiguity (group chain positions by chapterId; each group must be one consecutive run); relationship pass compares each soft edge to chain order. Pure read; also powers the standing indicator on the Metadata page.

### POST /api/books/{b}/compile
**Logic (CompileService, under lock):** 1) Run the check; errors → **409** `{ "errors": [CheckItem] }`, nothing written. 2) Delete `compiled-book/` contents entirely (stale artifacts must not survive renames). 3) For each part in chain order → `part-{n}-{slug}/`; for each of its chapters in chain order → `chapter-{n}-{slug}.md` = `# {chapter title}\n\n` + its scenes' prose in chain order joined by `\n\n***\n\n`; empty chapters emit heading-only (warning). 4) Emit `compile-done` + `git-status` (output lands uncommitted; the badge lights; committing is the author's deliberate act — compile never auto-commits). **Response** CompileReport.

---

## 15. Resources

Files the author keeps beside the manuscript — research, references, worldbuilding notes. Handled by `ResourceService`. No id, no index: `resources/` is scanned fresh on every list (doc 03 §resources/ — no index), so the filename is the key everywhere below.

### GET /api/books/{b}/resources
**Response** `ResourceFile[]` — `{ "filename", "mimeType", "sizeBytes", "updatedAt" }`, newest first.

### POST /api/books/{b}/resources — **multipart** `file` (required)
Any file type. **422** over 25 MB. Filename collision → suffixed (`notes.md` → `notes-2.md`), never overwritten. **201** `ResourceFile` — `filename` may differ from the uploaded name.

### GET /api/books/{b}/resources/{filename}/content
Streams the file as an attachment download. **404** if absent. `{filename}` (not a path parameter) — a name containing `/` fails to match the route at all, on top of the service's own traversal guard.

### DELETE /api/books/{b}/resources/{filename}
Moves the file to `.trash/`, never unlinks — same rule as scene deletion. **204**.

### AI access
Read tools `list_resources()` / `get_resource(filename)` are ordinary, ungated read tools (§9.3 step 4) available in every conversation, scene-parented or book-parented alike. Text-ish extensions only (`.md .markdown .txt .csv .json .yml .yaml`); anything else reports as binary. Writes never happen directly — `propose_resource_create` (a propose tool) only emits a proposal; §10's `resource-create` accept branch is the sole write path.
