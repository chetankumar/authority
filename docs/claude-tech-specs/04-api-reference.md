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
| **SceneService** | Scene CRUD orchestration; content saves (hash, word count); dependency-todo fanout; enrichment settle timers; file naming/renames |
| **StructureService** | Parts/chapters linked lists; move-before/after rewiring; blocked deletions; plotlines; characters (uniqueness) |
| **ConversationService** | Conversation lifecycle; message append; passes parent scene into ContextAssembler; streams via AIOrchestrator |
| **ProposalService** | Locates a proposal by id (via conversation index); applies/rejects; the only code path that mutates on behalf of AI output |
| **JobService + Worker** | `jobs.json` queue; resolves AI-Job placeholders then ContextAssembler → AIOrchestrator; per-book FIFO, ≤2 global |
| **EnrichmentService** | The system bookkeeping job (summary, character mapping) |
| **AIOrchestrator / ModelFactory** | `ModelConfig → LangChain BaseChatModel`; invoke_once / structured / stream + tool loop; `${ENV}` key resolution |
| **GitService** | GitPython wrapper: status/stage/unstage/diff/commit/push/pull/log; post-write status checks |
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
**`conversationKind`**: `note` · `chat` · `ai-job` · `task-discussion`.
**`proposalType`**: `edit` · `metadata-update` · `todo-create` · `character-create`. **`proposalStatus`**: `pending` · `applied` · `rejected` · `not-found`.
**`jobType`**: `user` (AI-Job run) · `system` (enrichment). **`jobStatus`**: `queued` · `running` · `done` · `failed`. **`jobScope`**: `full` · `selection` (user jobs) · `summary` · `characters` · `both` (system jobs).
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
  "characterIds": ["chr-x"], "status": "active",
  "contentHash": "sha256:...", "wordCount": 1240,
  "seq": 1, "placement": "trunk",
  "createdAt": "...", "updatedAt": "..." }
```
`seq`/`placement` are **computed** by ChainService on read, never stored. `chapterId` XOR `partId` (both nullable, never both set). `dateTime`/`location` are free-text *story* values. `summary`/`characterIds` are system-maintained when the corresponding bookkeeping toggle is on, manually editable regardless.
`primaryPlotlineId` is the scene's main plotline (nullable). `secondaryPlotlineIds` lists additional plotlines. A primary must not also appear in secondaries.

**SoftRelationship** `{ "id", "fromSceneId", "toSceneId", "type", "createdAt" }`
**Dependency** `{ "id", "sceneId", "dependsOnSceneId", "reason", "createdAt" }` — `sceneId` is the *dependent* scene; `reason` required, human text explaining the logical link.
**Character** `{ "id", "name", "aliases": [], "personality", "history", "notes", "sceneCount": 3 }` — `sceneCount` computed. Uniqueness enforced across all names **and** aliases.
**Plotline** `{ "id", "title", "description", "sceneCount": 5 }` — `sceneCount` is computed by scanning scenes (via `primaryPlotlineId` and `secondaryPlotlineIds`). Plotlines do not store scene references.
**Todo** `{ "id", "parentType", "parentId", "parentTitle", "action", "status", "origin", "sourceDependencyId", "conversationId", "createdAt", "updatedAt" }` — `parentTitle` resolved on read for grid display.

**ConversationSummary** (index rows) `{ "id", "kind", "title", "parentType", "parentId", "status", "updatedAt", "messageCount", "pendingProposals" }`

**Conversation** = ConversationSummary + `{ "aiParticipant": { "enabled": bool, "modelId": "mdl-..|null" }, "aiJobId": "aij-..|null", "createdAt", "messages": [Message] }`

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
Payload variants — `metadata-update`: `{ "targetType": "scene", "targetId", "field", "oldValue", "newValue", "rationale" }` (`field` any PATCHable scene metadata field; never prose). `todo-create`: `{ "parentType", "parentId", "action" }`. `character-create`: `{ "name", "aliases"?, "personality"?, "history"?, "notes"?, "rationale"?, "sceneId"? }` — Accept runs character uniqueness checks; may be unavailable until the Characters API lands (`422 characters-unavailable`).

**Job**
```json
{ "id": "job-x", "type": "user", "aiJobId": "aij-..", "conversationId": "cnv-..",
  "sceneId": "scn-..", "scope": "full", "modelId": "mdl-..",
  "status": "queued", "error": null, "result": { "unrecognizedNames": [] },
  "createdAt": "...", "startedAt": null, "finishedAt": null }
```

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
**Logic:** SettingsService collects references — AI-Job `defaultModelId`s and `ai.utilityModelId`. Any → **409** `{ "blockedBy": { "aiJobs": [{id,name}], "utilityModel": true } }`. Else remove. (Conversations referencing it historically are unaffected; a later message-send with a deleted model → 422 at send time.)

### POST /api/settings/models/{id}/test
**Logic:** SettingsService loads the stored config and asks ModelFactory to build the LangChain chat model, resolving a `${ENV_VAR}` key at call time; it then sends a single `"hello model"` chat completion (guarded by a ~30s timeout). **Response** 200 `ModelTestResult`: `ok:true` with a short reply excerpt + `latencyMs`, or `ok:false` with a human-readable `error` (unset env var, auth failure, unreachable base URL, timeout). **404** unknown id. This is the only settings endpoint that performs network I/O and it never mutates `app.json`; failures are results, not error responses (still 200), so the client renders them inline. No connectivity test happens on model create/patch — this endpoint is the explicit, on-demand check.

### GET /api/settings/ai
**Response** `{ "utilityModelId": "mdl-..|null" }` — the model EnrichmentService and git suggest-message use.

### PATCH /api/settings/ai
**Request** `{ "utilityModelId": "mdl-..|null" }`. 422 if id unknown.

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
**Logic (SceneService, under lock):** 1) 422: empty title/description; both chapterId+partId set (`chapter-xor-part`); unknown FKs; prev/next sentinel violations (nothing precedes Start / follows The End). 2) Generate id; create empty `scenes/{hash}-{slug}.md`; contentHash of empty content, wordCount 0. 3) **Splice** (ChainService): if `previousSceneId=A` and A→B exists → rewire A→New→B (B's previous updated); mirror for nextSceneId; if both given they must be currently adjacent (422 `not-adjacent`) — splice between them. 4) Create SoftRelationship rows (dedup exact duplicates silently). 5) Persist scenes.json + relationships.json; emit `scene-updated`. **Response 201** `{ "scene": Scene, "affectedScenes": [Scene] }` — affected = neighbors whose links changed; client patches the graph without refetch.

### GET /api/books/{b}/scenes/{id}
**Response** `{ ...Scene, "content": "full markdown prose" }` — the only scene read that includes prose (editor load). Reads the .md file directly.

### PATCH /api/books/{b}/scenes/{id}
**Request (all optional):** `title` (slug-renames the .md file; `file` field updated) · `description` · `location` · `dateTime` · `mood` · `emotionalArc` · `summary` (manual edit) · `characterIds` (full replacement array; unknown ids 422) · `chapterId` / `partId` (XOR enforced on the merged result; setting one clears the other implicitly? **No** — client sends the clear explicitly as `null`; server 422s if both end up set) · `previousSceneId` / `nextSceneId` (ChainService: detach-heal old links, splice new) · `status` (`archived`: splice-heal chain, soft relations kept dormant; `active`: return floating — old slot not reclaimed).
**Logic:** under lock; sentinel/FK validation as in create; persist; emit `scene-updated` with the changed-field list. **Response** `{ "scene": Scene, "affectedScenes": [Scene] }`. Metadata PATCH never touches prose or contentHash.

### PUT /api/books/{b}/scenes/{id}/content
**Request** `{ "content": "full markdown" }` — full-document replacement (autosave semantics; no patching).
**Logic (SceneService, under lock):** 1) Atomic write of the .md (tmp + fsync + replace). 2) Recompute wordCount (whitespace tokenization) + sha256 contentHash. 3) **If hash changed:** (a) dependency fanout — for every Dependency where `dependsOnSceneId == this`, create a Todo on the dependent scene: action `"'{this.title}' changed — verify dependency: {reason}"`, origin `dependency`, `sourceDependencyId` set; **dedup:** skip if an *open* todo for the same dependency already exists (typing sessions must not stack duplicates); emit `todos-created` if any. (b) EnrichmentService: (re)set this scene's settle timer (doc 05). 4) Persist scenes.json. **Response** `{ "wordCount": 1240, "contentHash": "sha256:..", "todosCreated": [Todo] }`.

### POST /api/books/{b}/scenes/{id}/enrich
**Request** `{ "scope": "summary" | "characters" | "both" }` — the on-demand AI-redo; **ignores** bookkeeping toggles (an explicit request is its own consent).
**Logic:** 422 `no-utility-model` if unset. JobService enqueues a system Job (scope as given, modelId = utility); replaces any queued (not running) enrichment for this scene. **Response 202** `{ "jobId": "job-.." }`; results arrive as `job` + `scene-updated` SSE events.

### GET /api/books/{b}/scenes/{id}/conversations
**Response** `[ConversationSummary]` for `parentType=scene, parentId=id`, from the derived index (no conversation files opened). Newest first.

### GET /api/books/{b}/scenes/{id}/todos
**Response** `[Todo]` for this scene, open first then by createdAt desc.

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
**Request** `{ "sceneId": "the dependent scene", "dependsOnSceneId": "the required scene", "reason": "required non-empty" }`. **Logic:** 422 on self-dependency, unknown/archived/sentinel scenes, empty reason, duplicate pair (same sceneId+dependsOnSceneId). Creating fires **no** todo — todos fire on later content change of the depended-on scene. **Response 201** Dependency.

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

### GET /api/books/{b}/characters → `[Character]` with sceneCounts.
### POST — `{ "name": required, "aliases"?: [], "personality"?, "history"?, "notes"? }`. **Uniqueness:** the new name and every alias must not collide (case-insensitive) with any existing character's name or aliases → 422 `{ "conflict": { "value": "Marlow", "existingCharacter": {id,name} } }`. The enrichment matcher must never face ambiguity.
### PATCH /{id} — same fields; same uniqueness on the merged result.
### DELETE /{id} — **409** listing scenes whose characterIds reference it; remove from those scenes first.

---

## 8. Todos

### GET /api/books/{b}/todos → `[Todo]` (all in book, parentTitle resolved). Filtering/sorting is client-side (AG Grid).
### POST — `{ "parentType", "parentId", "action": required }` → origin `user`, status `open`. 422 unknown parent. **201** Todo.
### PATCH /{id} — `{ "status"?: todoStatus, "action"?: string }`.
### DELETE /{id} — hard delete (kept for mistakes; normal lifecycle is `closed`). **204**.

---

## 9. Conversations, Messages, AI-Job runs

### POST /api/books/{b}/conversations
**Request**
```json
{ "kind": conversationKind, "parentType": parentType, "parentId": "..",
  "aiParticipant"?: { "enabled": bool, "modelId": "mdl-..|null" },
  "title"?: "optional initial title" }
```
Default aiParticipant: `{enabled:false, modelId:null}` (note-stacking). **Logic:** ConversationService creates `cnv-{hex}.json` with empty messages; title is the optional `title` or `"Untitled"`. Index updated. **201** Conversation. *(AI-Job runs don't call this — see §9.4. Escalations pass a caller-supplied short title — see EscalationService.)*

### GET /api/books/{b}/conversations/{id}
**Response** full Conversation with messages + proposals (per-file load on demand).

### PATCH /api/books/{b}/conversations/{id}
**Request** `{ "title"?, "status"?: "open"|"archived", "aiParticipant"?: { "enabled"?, "modelId"? } }` — the mid-thread AI toggle and model switch live here. Enabling with no modelId and none previously set → 422 `model-required`.

### DELETE /api/books/{b}/conversations/{id}
Hard delete for mistakes. Removes `cnv-*.json` and the index entry; any jobs pointing at this conversation get `conversationId` cleared. **204**. Rejected **409** `generation-in-progress` if a stream is active.

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
4. **enabled == true:** resolve ModelConfig (422 `model-missing`/`model-deleted` if unresolvable). Build the LangChain call: system = book systemPrompt + Authority's assistant framing + CURRENT SCENE + tool schemas; history = conversation messages mapped to roles (context excerpts injected as quoted blocks inside user turns; `@placeholders` in user text resolved for the model); bind read + propose tools (doc 05).
5. Respond as **SSE**: `token` events (`{ "text": ".." }`) as the model streams; tool calls execute server-side mid-stream (read tools answer from BookDataManager; propose tools accumulate Proposal objects); on completion, persist the assistant Message (content, modelId, proposals) and send a final `message` event carrying it, then `done`.
6. Model/tool failure mid-stream → `error` event `{ "error": ".." }`; user message stays persisted; no assistant message written.
Concurrent sends to one conversation are rejected 409 `generation-in-progress`.

### 9.4 POST /api/books/{b}/ai-jobs/run
**Request**
```json
{ "aiJobId": "aij-..", "sceneId": "scn-..",
  "scope": "full" | "selection", "selectionText"?: "required when scope=selection" }
```
**Logic:** 1) 422: unknown job/scene; scope `selection` without selectionText. 2) ConversationService creates a Conversation: kind `ai-job`, parent = the scene, title = **job definition name** (no clock suffix), aiParticipant `{enabled:true, modelId: job.defaultModelId}`, aiJobId set (+ name snapshot). 3) JobService enqueues a Job (type `user`, status `queued`, links to both). **Response 202** `{ "jobId", "conversationId" }` — the client opens the conversation modal immediately and watches.
**Worker execution:** status `running` (SSE `job`) → PlaceholderRegistry resolves the prompt template against the scene (selectionText feeds `@selection`) → outputType `edit-proposals`/`metadata-proposals` appends format instructions (§2.1) → the resolved prompt is posted as a **system-authored** first message in the conversation → model invoked with tools, streamed into the conversation (same §9.3 mechanics; clients subscribed to the modal see it live) → fenced JSON parsed into Proposals on the assistant message (parse failure → degrade to chat + `result.warning`) → status `done`/`failed` (SSE). The author then continues the conversation normally — follow-ups are plain §9.3 sends.

---

## 10. Proposals

### POST /api/books/{b}/proposals/{id}/accept
**Logic (ProposalService, under book lock):** locate the proposal via the conversation index (404 unknown; 409 `already-resolved` if not pending). By type:
- **edit:** read the target scene's .md; find the *first exact occurrence* of `payload.find` (byte-exact, no normalization). Absent → status `not-found`, nothing changes, response reports it. Present → replace **one** occurrence, save through the standard content path (**PUT semantics: hash recompute → dependency fanout → settle timer** — an applied edit is a content change like any other). This is the sole prose-mutation path besides the editor, and it is author-triggered.
- **metadata-update:** apply `payload.newValue` to `payload.field` via SceneService PATCH logic (full validation; XOR rules etc. — validation failure → 422, proposal stays pending).
- **todo-create:** create the Todo, origin `ai`.
- **character-create:** create the Character via StructureService uniqueness rules; optionally tag `sceneId` on the scene. 422 if Characters layer not loaded.
Stamp status `applied` (or `not-found`) + resolvedAt; persist conversation; emit `scene-updated`/`todos-created` as applicable.
**Response** `{ "proposal": Proposal, "result": { "wordCount"?, "contentHash"?, "todo"?: Todo } }`.

### POST /api/books/{b}/proposals/{id}/reject
Marks `rejected` + resolvedAt; touches nothing else. **Response** the Proposal. *(Accept-all = client loops accept sequentially, stopping to display any `not-found`s; deliberately no batch endpoint — no batch atomicity.)*

---

## 11. Jobs

### GET /api/books/{b}/jobs?scene={id}&status={jobStatus}&type={jobType}
**Response** `[Job]` newest first, filters optional. Powers the AI Jobs accordion (live transitions via SSE; this is the load/reload read).

---

## 12. Events — GET /api/books/{b}/events (SSE)

One connection per open book. Event types and payloads:

| event | data | emitted when |
|---|---|---|
| `job` | `{ id, type, sceneId, status, result? }` | any job status transition |
| `scene-updated` | `{ id, changed: ["summary","characterIds"] }` | any scene metadata write (author, enrichment, accepted proposal) |
| `todos-created` | `{ todos: [Todo] }` | dependency fanout or accepted todo-create |
| `git-status` | `GitStatus` (§2.2, includes `summary`) | **(a)** the git-status worker's 5s debounce fired after a `book-changed`; **(b)** immediately, in-request, after an explicit stage/unstage/commit/push/pull |
| `compile-done` | `{ report: CompileReport }` | successful compile |

Clients patch TanStack Query caches from these; on reconnect, refetch active queries (channel is stateless).

**Internal events.** `book-changed` `{}` is emitted by BookDataManager after *any* `db/*.json` or `config/book.json` write. It is a payload-free signal for server-side consumers (today: the git-status worker, via the hub's global `subscribe_all` channel) and carries no information a client can act on — clients ignore unrecognized event types, so no server-side filtering is needed on the per-book channel.

**Defense in depth.** SSE is the fast path, not the only path. Clients that render git state also poll `GET /git/status` every 10s, so a dropped `book-changed`, a lost `git-status`, or a silently broken SSE reconnect still self-corrects within ~10s. The channel being stateless is what makes this safe: the poll and the event write identical server truth into the same cache entry.

---

## 13. Git

All endpoints: GitService (GitPython over the system git; the user's credentials/SSH config apply). 404 if the book folder lost its `.git`.

**Emission rule:** every *mutating* endpoint here (stage, unstage, commit, push, pull) recomputes status and emits `git-status` **immediately, in-request** — the author is on the Git page waiting, so these never go through the git-status worker's 5s debounce. The worker exists only for *incidental* dirtying from unrelated writes (scene autosave, structure edits), where nobody is watching. Reads (`status`, `diff`, `log`) emit nothing.

### GET /api/books/{b}/git/status → GitStatus (§2.2). Page load + badge initial state; also the 10s client poll (§12).
### POST /api/books/{b}/git/stage · /unstage — **Request** `{ "paths"?: ["scenes/x.md"], "all"?: true }` (one required). Real `git add` / `git reset` on those paths. **Response** refreshed GitStatus; emits `git-status`.
### GET /api/books/{b}/git/diff?path= — **Response** `{ "path", "diff": "unified diff text (staged+unstaged vs HEAD)" }`; binary files → `{ "binary": true }`.
### POST /api/books/{b}/git/suggest-message
**Logic:** staged diff (422 `nothing-staged` if empty) → truncate to a size cap (~20k chars, largest hunks first) → utility model: *"Summarize these changes to a novel manuscript as a single-line git commit message."* No utility model → deterministic fallback from stats (`"3 scenes updated, 1 added"`). **Response** `{ "message": "..." }` — fills the textarea, author edits freely.
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
