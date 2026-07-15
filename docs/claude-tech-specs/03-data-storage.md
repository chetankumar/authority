# 03 — Data & Storage

## Principles

1. JSON only. No database engines.
2. **Atomic writes:** serialize → write `{file}.tmp` in the same directory → `flush()` + `os.fsync()` → `os.replace()` over the original (atomic on POSIX and Windows; on POSIX, additionally fsync the directory handle so the rename survives power loss). `.tmp` is gitignored. See the Data Safety section below.
3. **Single writer:** the API. The app assumes no concurrent external editing while running.
4. Git-friendly granularity: files split so typical actions produce small diffs; git history doubles as data history.
5. **Timestamps:** ISO 8601 UTC strings. **Cross-references:** always by ID, never array position.

## ID scheme

`{prefix}-{6 lowercase hex}` via `secrets.token_hex(3)`, collision-checked against the collection, regenerate on hit.

Prefixes: `bok` book · `scn` scene · `chp` chapter · `prt` part · `chr` character · `plt` plotline · `cnv` conversation · `msg` message · `tdo` todo · `dep` dependency · `rel` soft relationship · `job` job · `prp` proposal · `mdl` model config · `aij` AI-Job definition.

**Sentinels:** `scn-START` and `scn-END` are reserved IDs recognized as valid relationship endpoints. They have no record in `scenes.json`, no file, cannot be edited/deleted. Rules: Start has no previous; The End has no next; nothing may be *before Start* or *after The End*. They appear in every scene dropdown (pinned top/bottom) and are implicit members of every scenes response.

## App-level data

`{appDataRoot}/app.json`:

```json
{
  "user": { "name": "Chetan", "booksHome": "/Users/chetan/Books" },
  "appearance": { "theme": "system" },
  "ai": { "utilityModelId": "mdl-a1b2c3" },
  "models": [
    { "id": "mdl-a1b2c3", "label": "Sonnet 4.6", "provider": "anthropic",
      "modelName": "claude-sonnet-4-6", "apiKey": "${ANTHROPIC_API_KEY}", "baseUrl": null }
  ],
  "aiJobs": [
    { "id": "aij-9x8y7z", "name": "Check Grammar",
      "prompt": "Proofread @selection_or_scene ...",
      "defaultModelId": "mdl-a1b2c3", "outputType": "edit-proposals" }
  ]
}
```

- `appearance.theme` ∈ `light | dark | system` (default `system`) — the app-wide color theme (doc 06 §1.2). App-level only; never stored per book. Missing/unknown → `system`.
- `provider` ∈ `anthropic | openai | gemini | openai-compatible | ollama`. `baseUrl` required for the latter two (LM Studio: `http://localhost:1234/v1`; Ollama: `http://localhost:11434`).
- `apiKey` may be a literal or `${ENV_VAR}` reference, resolved at call time. Keys live only at app level — never inside a book folder, so they can never be committed/pushed.
- `outputType` ∈ `chat | edit-proposals | metadata-proposals`.
- **No bookshelf registry.** The shelf is a live scan of `booksHome` for subfolders containing `config/book.json`. Subfolders without it are silently ignored.

## Book folder

Named `{6hex}-{title-slug}/` inside books-home. Folder renames follow title renames; the hash prefix is permanent identity.

```
a3f9c2-my-great-novel/
  config/
    book.json
  scenes/
    1f2e9b-the-arrival.md        # prose only; source of truth for content
  db/
    scenes.json  relationships.json  dependencies.json
    characters.json  plotlines.json  todos.json  jobs.json  ui.json
    conversations/
      index.json
      cnv-9f2c1a.json
  assets/
    cover.jpg                    # committed; travels with the book
  compiled-book/                 # build artifact; committed; wiped each compile
    part-1-beginnings/chapter-1-the-arrival.md
  .gitignore                     # *.tmp
  .git/
```

Scene filenames: `{sceneHash}-{slug}.md`. Slug follows title renames; hash never changes. Empty scaffold folders carry `.gitkeep`.

## config/book.json

```json
{
  "id": "bok-a3f9c2",
  "title": "My Great Novel",
  "systemPrompt": "Book-level style/genre notes prepended to every AI call for this book.",
  "storySummary": "Editable book-level summary (Metadata page).",
  "bookkeeping": { "summaryOnSave": true, "charactersOnSave": true },
  "parts":    [{ "id": "prt-x", "title": "", "description": "", "previousPartId": null, "nextPartId": null }],
  "chapters": [{ "id": "chp-x", "title": "", "description": "", "partId": null,
                 "previousChapterId": null, "nextChapterId": null }]
}
```

Bookkeeping toggles default **on** for new books; unknown future keys default off. Parts and chapters are linked lists ordered by prev/next; the API always returns them pre-ordered.

## db/scenes.json — array of

```json
{
  "id": "scn-1f2e9b",
  "title": "The Arrival",
  "file": "scenes/1f2e9b-the-arrival.md",
  "description": "(required)",
  "location": "", "dateTime": "",
  "previousSceneId": null, "nextSceneId": null,
  "chapterId": null, "partId": null,
  "mood": "", "emotionalArc": "", "summary": "",
  "characterIds": [],
  "status": "active",
  "contentHash": "sha256:...", "wordCount": 0,
  "createdAt": "...", "updatedAt": "..."
}
```

- `chapterId` XOR `partId` (both may be null; never both set) — API-enforced.
- `previousSceneId`/`nextSceneId` may hold sentinel IDs.
- `status` ∈ `active | archived`. Archiving splice-heals the chain (A→X→B ⇒ A→B) and hides the scene from graph/default table/placeholders/compilation; soft relationships kept but dormant. Unarchiving returns it **floating**.
- `summary` and `characterIds` are system-maintained (enrichment) when the corresponding toggle is on; manually editable regardless.
- `contentHash`/`wordCount` recomputed on every content save. A hash change triggers dependency-todo creation and the enrichment settle timer.

## db/relationships.json — soft edges only

```json
{ "id": "rel-x", "fromSceneId": "scn-a", "toSceneId": "scn-b",
  "type": "before" | "after" | "around", "createdAt": "..." }
```

Semantics: *from is definitely-{type} to*. Rendered as thin dotted arrows ("around": no arrowhead).

## db/dependencies.json

```json
{ "id": "dep-x", "sceneId": "scn-10", "dependsOnSceneId": "scn-02",
  "reason": "(required)", "createdAt": "..." }
```

Behavior: when `dependsOnSceneId`'s content hash changes on save, auto-create a todo on each dependent scene: action = `"'{depended-on title}' changed — verify dependency: {reason}"`, origin `dependency`, `sourceDependencyId` set. No status on the dependency itself.

## db/todos.json

```json
{ "id": "tdo-x", "parentType": "scene" | "chapter" | "part" | "book", "parentId": "...",
  "action": "...", "status": "open" | "done" | "closed",
  "origin": "user" | "dependency" | "ai", "sourceDependencyId": null,
  "conversationId": null, "createdAt": "...", "updatedAt": "..." }
```

## db/characters.json

```json
{ "id": "chr-x", "name": "(required, unique across names+aliases)",
  "aliases": [], "personality": "", "history": "", "notes": "" }
```

The character collection is the master name list. Aliases feed the enrichment matcher.

## db/plotlines.json

```json
{ "id": "plt-x", "title": "", "description": "", "sceneIds": [] }
```

## db/conversations/cnv-*.json (one file per conversation)

```json
{
  "id": "cnv-9f2c1a",
  "kind": "note" | "chat" | "ai-job" | "task-discussion",
  "title": "(default: first ~6 words of first user message; renameable)",
  "parentType": "scene" | "chapter" | "part" | "book", "parentId": "scn-...",
  "aiParticipant": { "enabled": true, "modelId": "mdl-..." },
  "aiJobId": null,
  "status": "open" | "archived",
  "createdAt": "...", "updatedAt": "...",
  "messages": [
    {
      "id": "msg-x", "author": "user" | "assistant" | "system",
      "modelId": "mdl-... (assistant messages: which model spoke)",
      "content": "markdown",
      "context": [ { "sceneId": "scn-...", "excerpt": "snapshot of selected text at send time" } ],
      "proposals": [
        { "id": "prp-x",
          "type": "edit" | "metadata-update" | "todo-create",
          "payload": { "...see below..." },
          "status": "pending" | "applied" | "rejected" | "not-found",
          "resolvedAt": null }
      ],
      "createdAt": "..."
    }
  ]
}
```

Proposal payloads:
- `edit`: `{ "sceneId", "find": "exact text", "replace": "new text", "rationale" }`
- `metadata-update`: `{ "targetType": "scene", "targetId", "field", "oldValue", "newValue" }`
- `todo-create`: `{ "parentType", "parentId", "action" }`

`aiParticipant` is toggleable at any time (the stack-notes-to-myself feature). Selection context is a snapshot, never a live anchor.

## db/conversations/index.json (derived)

```json
[{ "id", "kind", "title", "parentType", "parentId", "status",
   "updatedAt", "messageCount", "pendingProposals": 2 }]
```

Rewritten on any conversation change; rebuildable by scanning the folder.

## db/jobs.json

```json
{ "id": "job-x", "type": "user" | "system",
  "aiJobId": null, "conversationId": null, "sceneId": null,
  "scope": "full" | "selection" | "summary" | "characters" | "both",
  "modelId": "mdl-...",
  "status": "queued" | "running" | "done" | "failed", "error": null,
  "result": { "unrecognizedNames": [] },
  "createdAt": "...", "startedAt": null, "finishedAt": null }
```

User jobs = AI-Job runs (scope full/selection, linked conversation). System jobs = enrichment (scope summary/characters/both, utility model).

## db/ui.json

Per-book UI preferences, portable with the book: AG Grid column state (visibility, order, widths), right-pane visibility, and future keys. Written debounced.

## Data safety & concurrency

Protection is achieved through patterns (stdlib) plus exactly one library. Five layers:

1. **Torn-write protection** — the hardened atomic-write helper above (`tempfile` in same dir, `fsync`, `os.replace`, POSIX dir fsync). ~15 lines, stdlib only; the `atomicwrites` package is deprecated and must not be used.
2. **In-process races** — the server runs exactly **one** Uvicorn worker (`workers=1`, pinned in the launcher; multiple workers would mean multiple writers). Within the async event loop, every mutation acquires the target book's `asyncio.Lock` (app.json has its own) around its read-modify-write-persist cycle. Reads take no lock; mutations replace collections rather than tweaking them in place, so readers never observe half-mutated state.
3. **Double-instance protection** — at startup the API takes an exclusive lock on `{appDataRoot}/.lock` via the **`filelock`** library (the single added dependency; pure Python, cross-platform). A second instance fails fast with "Authority is already running" instead of silently double-writing.
4. **Corrupt-load recovery** — a JSON file that fails to parse at load is never overwritten: it is copied to `{file}.corrupt-{timestamp}`, a loud error names it, and the book loads degraded. Derived files (`conversations/index.json`) are rebuilt automatically from a folder scan. Git is the ultimate restore mechanism: every commit is a known-good snapshot (`git checkout -- db/scenes.json`).
5. **Load-time schema validation** — on-disk documents are validated against the same Pydantic models used at the API boundary when a book loads; violations are reported per-file (treated as layer-4 corruption), catching hand-edited or drifted data before it compounds.
