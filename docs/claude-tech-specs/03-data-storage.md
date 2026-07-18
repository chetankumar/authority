# 03 — Data & Storage

## Principles

1. JSON only. No database engines.
2. **Atomic writes:** serialize → write `{file}.tmp` in the same directory → `flush()` + `os.fsync()` → `os.replace()` over the original (atomic on POSIX and Windows; on POSIX, additionally fsync the directory handle so the rename survives power loss). `.tmp` is gitignored. See the Data Safety section below.
3. **Single writer:** the API. The app assumes no concurrent external editing while running.
4. Git-friendly granularity: files split so typical actions produce small diffs; git history doubles as data history.
5. **Timestamps:** ISO 8601 UTC strings. **Cross-references:** always by ID, never array position.

## ID scheme

`{prefix}-{6 lowercase hex}` via `secrets.token_hex(3)`, collision-checked against the collection, regenerate on hit.

Prefixes: `bok` book · `scn` scene · `chp` chapter · `prt` part · `chr` character · `crl` character relationship · `plt` plotline · `cnv` conversation · `msg` message · `tdo` todo · `dep` dependency · `rel` soft relationship · `prp` proposal · `mdl` model config · `aij` AI-Job definition. (No run-record prefix — a run is a conversation `cnv`.)

**Sentinels:** `scn-START` and `scn-END` are reserved IDs recognized as valid relationship endpoints. They have no record in `scenes.json`, no file, cannot be edited/deleted. Rules: Start has no previous; The End has no next; nothing may be *before Start* or *after The End*. They appear in every scene dropdown (pinned top/bottom) and are implicit members of every scenes response.

## App-level data

`{appDataRoot}/app.json`:

```json
{
  "user": { "name": "Chetan", "booksHome": "/Users/chetan/Books" },
  "appearance": { "theme": "system" },
  "ai": {
    "utilityModelId": "mdl-a1b2c3",
    "commitMessageModelId": null,
    "characterParsingModelId": null,
    "sceneSummaryModelId": null,
    "chatDefaultModelId": null
  },
  "models": [
    { "id": "mdl-a1b2c3", "label": "Sonnet 4.6", "provider": "anthropic",
      "modelName": "claude-sonnet-4-6", "apiKey": "${ANTHROPIC_API_KEY}", "baseUrl": null }
  ],
  "aiJobs": [
    { "id": "aij-9x8y7z", "name": "Check Grammar",
      "prompt": "Proofread @selection_or_scene ...",
      "defaultModelId": "mdl-a1b2c3", "outputType": "edit-proposals" }
  ],
  "elevenLabsApiKey": null,
  "elevenLabsVoices": [],
  "elevenLabsVoicesSyncedAt": null
}
```

- `ai.utilityModelId` is the general-purpose fallback for sundry system tasks (chat-thread auto-titling) **and** the fallback every task-specific slot below degrades to when its own slot is unset or dangling. The four task-specific slots (`commitMessageModelId`, `characterParsingModelId`, `sceneSummaryModelId`, `chatDefaultModelId`) each resolve independently: own slot if set and known → else `utilityModelId` → else `null` (degrade, never fail). More slots may be appended the same way as new AI-assisted tasks need their own model choice. Voice suggestion for characters also uses this utility-model fallback.
- `appearance.theme` ∈ `light | dark | system` (default `system`) — the app-wide color theme (doc 06 §1.2). App-level only; never stored per book. Missing/unknown → `system`.
- `provider` ∈ `anthropic | openai | gemini | openai-compatible | ollama`. `baseUrl` required for the latter two (LM Studio: `http://localhost:1234/v1`; Ollama: `http://localhost:11434`).
- `apiKey` may be a literal or `${ENV_VAR}` reference, resolved at call time. Keys live only at app level — never inside a book folder, so they can never be committed/pushed.
- `elevenLabsApiKey` follows the same literal / `${ENV_VAR}` / empty convention. Empty or omitted resolves to env `ELEVENLABS_API_KEY` at call time. ElevenLabs is **not** a LangChain `ModelConfig` provider. `elevenLabsVoices` is a cached sync of the author's available voices (id, name, labels, previewUrl); `GET /settings/elevenlabs/voices` returns this cache without a live network call.
- `outputType` ∈ `chat | edit-proposals | metadata-proposals | audio-script`.
- **No bookshelf registry.** The shelf is a live scan of `booksHome` for subfolders containing `config/book.json`. Subfolders without it are silently ignored.

## Book folder

Named `{6hex}-{title-slug}/` inside books-home. Folder renames follow title renames; the hash prefix is permanent identity.

```
a3f9c2-my-great-novel/
  config/
    book.json
  scenes/
    1f2e9b-the-arrival.md        # prose only; source of truth for content
    scn-1f2e9b/                  # per-scene folder — everything but identity/hard-chain/structure
      meta.json                  # location, dateTime, mood, emotionalArc
      bookkeeping.json           # summary, characters[{characterId, involvement}], contentHash, wordCount
      dependencies.json          # this scene's outgoing depends-on edges
      relationships.json         # this scene's outgoing soft edges
      todos.json                 # this scene's own todos — see "Todos storage split" below
      audio/                     # optional scene audio drama — see "scenes/{id}/audio/" below
        manifest.json
        lines/*.mp3              # gitignored
  db/
    scenes.json  parts.json  chapters.json
    characters.json  character_relationships.json  plotlines.json  todos.json  ui.json
    conversations/
      index.json
      cnv-9f2c1a.json
  assets/
    cover.jpg                    # committed; travels with the book
  resources/                     # files the author keeps beside the book — see "Resources" below
    magic-system.md
    reference-map.png
  compiled-book/                 # build artifact; committed; wiped each compile
    part-1-beginnings/chapter-1-the-arrival.md
  .gitignore                     # *.tmp + *.mp3 (editable via Metadata → Book; mp3s are regenerable artifacts)
  .git/
```

Scene filenames: `{sceneHash}-{slug}.md`. Slug follows title renames; hash never changes. The per-scene folder is named by the **full scene id** (`scn-1f2e9b`, not the bare hex) — matches the `conversations/cnv-*.json` naming convention and stays self-describing without cross-referencing `db/scenes.json`. Empty scaffold folders carry `.gitkeep`.

**`.gitignore`:** seeded on book create with `*.tmp` and `*.mp3`. Source of truth is the file itself (not `book.json`). `GET/PUT /api/books/{b}/gitignore` exposes patterns to Metadata → Book; required patterns are re-injected on save if missing. Existing books get `*.mp3` appended via `ensure_gitignore_patterns` on open.

## config/book.json

```json
{
  "id": "bok-a3f9c2",
  "title": "My Great Novel",
  "systemPrompt": "Book-level style/genre notes prepended to every AI call for this book.",
  "storySummary": "Editable book-level summary (Metadata page).",
  "narratorVoiceId": "",
  "narratorVoiceName": "",
  "bookkeeping": { "summaryOnSave": true, "charactersOnSave": true }
}
```

`narratorVoiceId` / `narratorVoiceName` are the book-level ElevenLabs casting for scene audio narration (empty until the author assigns one on Metadata → Book).
Bookkeeping toggles default **on** for new books; unknown future keys default off.

## db/scenes.json — the master table, array of

```json
{
  "id": "scn-1f2e9b",
  "title": "The Arrival",
  "file": "scenes/1f2e9b-the-arrival.md",
  "description": "(required)",
  "previousSceneId": null, "nextSceneId": null,
  "status": "active",
  "chapterId": null, "partId": null,
  "primaryPlotlineId": null, "secondaryPlotlineIds": [],
  "createdAt": "...", "updatedAt": "..."
}
```

This is deliberately the **only** thing every mutation atomically rewrites as
a whole collection — identity, hard-chain, and structure, the low-churn,
author-driven facts that ChainService, the Scene Graph, the Scene Table's
default columns, and StructureService's chapter/part/plotline checks need in
bulk. Everything that changes far more often (content saves, AI enrichment) or
is soft narrative detail lives in the scene's own folder instead (below), so
neither shares a file, a write, or a corruption blast radius with this table.

- `chapterId` XOR `partId` (both may be null; never both set) — API-enforced.
- `previousSceneId`/`nextSceneId` may hold sentinel IDs.
- `status` ∈ `active | archived`. Archiving splice-heals the chain (A→X→B ⇒ A→B) and hides the scene from graph/default table/placeholders/compilation; soft relationships kept but dormant. Unarchiving returns it **floating**. Archive/unarchive is the one thing that must stay in this table rather than move to the per-scene folder: it fires chain splice/heal (relinking 2-3 scenes' prev/next) in the same atomic write.
- `updatedAt` here reflects only *this table's* own changes. The API's assembled `Scene.updatedAt` is `max(scenes.json's updatedAt, meta.json's updatedAt, bookkeeping.json's updatedAt)` — a mood-only or summary-only edit still surfaces as the scene's latest update time without this table needing to be touched.

## scenes/{id}/meta.json — soft, author-edited narrative metadata

```json
{ "location": "", "dateTime": "", "mood": "", "emotionalArc": "", "updatedAt": "..." }
```

## scenes/{id}/bookkeeping.json — AI-owned + content-derived

```json
{ "summary": "", "characters": [{ "characterId": "chr-x", "involvement": "Finds the key." }],
  "contentHash": "sha256:...", "wordCount": 0, "updatedAt": "..." }
```

- `summary` and `characters` (each entry: `characterId` + short `involvement` of what they do in **this** scene) are system-maintained (enrichment) when the corresponding toggle is on; manually editable regardless. Enrichment's two independent calls (doc 05) each write here — never to the master table. Load migrates legacy `characterIds: string[]` → `characters` with empty involvement.
- `contentHash`/`wordCount` recomputed on every content save. Autosave now touches **only this file** — never `db/scenes.json` — so it can never contend with or block a chain splice/heal on an unrelated scene. A hash change triggers dependency-todo creation; enrichment is **not** scheduled from autosave (leave-scene / on-demand only — doc 05).

## scenes/{id}/relationships.json — this scene's outgoing soft edges

```json
[{ "id": "rel-x", "fromSceneId": "scn-a", "toSceneId": "scn-b",
   "type": "before" | "after" | "around", "createdAt": "..." }]
```

Semantics: *from is definitely-{type} to*. Rendered as thin dotted arrows ("around": no arrowhead). Owned by the *from* scene's folder — `BookDataManager.get_relationships()` still returns the flattened aggregate across every scene's file, so ChainService's placement computation, the Scene Graph, and `GET /scenes`'s `relationships` array are all unaffected by where the edge physically lives.

## db/parts.json — array of

```json
{ "id": "prt-x", "title": "Part One", "description": "", "seq": 1 }
```

Simple integer ordering. New parts are appended with `seq = max + 1`. Reordering reassigns seq 1..n from a client-provided ordered ID list. No linked-list pointers.

## db/chapters.json — array of

```json
{ "id": "chp-x", "title": "Chapter 1", "description": "", "partId": "prt-x", "seq": 1 }
```

Global seq across the whole book (not per-part). The client groups chapters by `partId` for display; chapters with `partId: null` appear as "Unassigned". Reordering works the same as parts.

## scenes/{id}/dependencies.json — this scene's outgoing depends-on edges

```json
[{ "id": "dep-x", "sceneId": "scn-10", "dependsOnSceneId": "scn-02",
   "reason": "(required)", "createdAt": "..." }]
```

Owned by the dependent scene's (`sceneId`'s) folder. `BookDataManager` keeps a
live in-memory reverse index (`get_dependents(scene_id)`) — built by one full
scan on first access, then kept current by an incremental update inside
`save_scene_dependencies` (never rescanned) — so "what depends on me" is a
memory lookup, not a folder scan, despite the edge itself living in the
*other* scene's folder.

**Not yet exposed via CRUD API** (create/edit/delete a dependency itself —
`POST/PATCH/DELETE /dependencies`). The model and per-scene storage exist so
the storage layer has a real shape; the delete-blocked check
(`SceneService.delete_scene`) reads it today. No status on the dependency
itself.

**Fanout-on-content-save is implemented.** When a scene's content hash
changes on save, `SceneService._fanout_dependency_todos` walks
`get_dependents(scene_id)` and creates a todo on each dependent scene (action
`"'{depended-on title}' changed — verify dependency: {reason}"`, origin
`dependency`, `sourceDependencyId` set), deduped against any todo already
open for that same `sourceDependencyId`. The todo lands in the *dependent*
scene's own `todos.json` (below) — a scene-parented todo, same as any other.

## Todos storage split

Unlike most `db/*.json` collections, todos are split by `parentType` across
two locations — the same reasoning as the meta/bookkeeping/dependencies/
relationships split above: smaller files, smaller corruption blast radius,
and a scene-parented todo naturally travels with the rest of that scene's
data (archive it, trash it, and the todo goes with it).

**`scenes/{id}/todos.json`** — this scene's own todos (every todo where
`parentType == "scene"` and `parentId == {id}`):

```json
[{ "id": "tdo-x", "parentType": "scene", "parentId": "scn-10",
   "action": "...", "status": "open" | "done" | "closed",
   "origin": "user" | "dependency" | "ai", "sourceDependencyId": null,
   "conversationId": null, "createdAt": "...", "updatedAt": "..." }]
```

Lazy-loaded and cached per scene like `dependencies.json`/`relationships.json`
(`BookDataManager._ensure_scene_todos_loaded`). Reading *all* scene todos at
once (the Tasks page's "also show scene todos" toggle) is **not** backed by a
maintained reverse index the way `get_dependents` is — `get_all_scene_todos()`
just walks every scene and reads its file fresh on each call. That aggregate
is only ever read from a rare, human-paced request (opening the Tasks page),
not a hot path like autosave, so a plain scan is simpler than a second
data structure that could drift, at negligible cost even for a few hundred
scenes.

**`db/todos.json`** — every other todo, i.e. `parentType` ∈ `chapter | part |
book`:

```json
{ "id": "tdo-x", "parentType": "chapter" | "part" | "book", "parentId": "...",
  "action": "...", "status": "open" | "done" | "closed",
  "origin": "user" | "dependency" | "ai", "sourceDependencyId": null,
  "conversationId": null, "createdAt": "...", "updatedAt": "..." }
```

A todo's id resolves to whichever tier it lives in without the caller needing
to know which (`BookDataManager.find_todo`) — the same flat-id-across-storage
pattern `DELETE /relationships/{id}` already uses. `conversationId` is
set-once: it links the todo to the conversation it was discussed or proposed
in (💬 in the UI); there's no way to clear it back to null.

**Open todos no longer block scene deletion** (a deviation from the
delete-blockers this doc's earlier drafts implied) — an archived scene with
open todos can still be hard-deleted; its `todos.json` moves to `.trash/`
with the rest of the folder, same as its dependencies/relationships.

## db/characters.json

```json
{ "id": "chr-x", "name": "(required, unique across names+aliases)",
  "aliases": [],
  "age": "", "gender": "", "nationality": "", "ethnicity": "", "occupation": "",
  "want": "", "need": "", "flaw": "", "arc": "",
  "personality": "", "history": "", "notes": "",
  "voiceId": "", "voiceName": "",
  "createdAt": "...", "updatedAt": "..." }
```

The character collection is the master name list. Aliases feed the enrichment matcher. `voiceId` / `voiceName` are the persistent ElevenLabs voice assignment for scene audio (Character Sheet); empty until assigned.

Fields beyond name/aliases are grouped by intent: **identity** (age, gender,
nationality, ethnicity, occupation — free text throughout; `age` is a string
because fiction rarely wants a strict int, e.g. `"mid-30s"`) and **craft**
(want = the external, plot-visible goal; need = the internal psychological
truth, often in tension with want; flaw = what drives conflict; arc = how the
character changes). `sceneCount` is **computed** on read (scanned from every
scene's `scenes/{id}/bookkeeping.json` → `characters[].characterId`), never stored — same
pattern as `Plotline.sceneCount` (which scans the master table's
`primaryPlotlineId`/`secondaryPlotlineIds` instead, since those stayed there).

## db/character_relationships.json

```json
{ "id": "crl-x", "characterAId": "chr-x", "characterBId": "chr-y",
  "category": "family" | "romantic" | "friendship" | "rivalry" | "professional" | "mentorship" | "other",
  "aToB": "mother of", "bToA": "daughter of",
  "description": "Free text — the dynamic, tension, or history.",
  "createdAt": "...", "updatedAt": "..." }
```

Character relationships are their own collection, not a field on the
character — most relationships aren't symmetric (mother/daughter,
mentor/student, unrequited love), so `aToB` and `bToA` are independent labels
rather than one shared string. `category` is a small controlled vocabulary
for future filtering/visualization; the labels and `description` carry the
actual nuance. One record per unordered `(characterAId, characterBId)` pair —
duplicates rejected at creation. No status/lifecycle field: relationships are
current-state descriptions the author edits directly as the story evolves.

## db/plotlines.json

```json
{ "id": "plt-x", "title": "", "description": "" }
```

Plotlines do not store scene references. The relationship is owned by scenes via `primaryPlotlineId` and `secondaryPlotlineIds`. The API computes `sceneCount` by scanning scenes on read.

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

## resources/ — no index

Files the author keeps beside the manuscript: research PDFs, reference images, worldbuilding notes. There is **no `db/resources.json` and no id** — `resources/` is scanned fresh on every list request, and the filename is the key. This follows the bookshelf itself: `BookScanner` discovers every book by folder scan for the same reason (doc 01 hard rule 4, portability) — a book folder must survive being zipped, cloned, or hand-edited outside the app. An index would be a second source of truth with nothing to reconcile it against; a file dropped into `resources/` by hand simply appears on the next scan.

Any file type is accepted, up to 25 MB. A name collision on upload or on an accepted `resource-create` proposal never overwrites — the incoming file is suffixed (`notes.md` → `notes-2.md`) instead. Deletion moves the file to `.trash/`, matching scene deletion — never a physical unlink.

The AI can read resources (`list_resources`, `get_resource` — ordinary, ungated read tools; text-ish extensions only, capped at ~100k characters) but cannot write one directly. `propose_resource_create` emits a proposal; only an accepted proposal calls the write path, per doc 01's write-permission table.

## scenes/{id}/audio/ — script + regenerable mp3s

Scene audio drama artifacts (see [`docs/audio-system.md`](../audio-system.md)):

```
scenes/{id}/audio/
  manifest.json              # tracked in git — script, speakers, synthesisStatus, per-line renderedFile
  lines/
    001-narrator-{itemId}.mp3
    002-chr-xxxx-{itemId}.mp3
  scene_stitched.mp3         # optional batch stitch; Play scene does not require it
```

- **`manifest.json`** is the single source of truth for the script and links. Each sequence item's **`renderedFile`** attribute points at a filename under `lines/`.
- **Mp3s are gitignored** (`*.mp3` in the book `.gitignore`). After clone, the author re-runs generate for missing files. Manifest stays committed so casting and line text travel with the book.
- Accepting an `audio-script-create` proposal **merges** into the manifest (unchanged lines keep prior text + `renderedFile`). Synthesis is a separate author action and writes binaries via `atomic_write_bytes`. Deletion moves the whole `audio/` folder to `.trash/`.

## No jobs.json

There is no job file. A *run* — an AI-Job the author triggers, or an automatic bookkeeping pass — is a **conversation** (`db/conversations/`), distinguished by `kind` (`ai-job` / `bookkeeping`) and carrying its lifecycle in `status` (`open · queued · running · waiting · done · failed`, see [doc 04 §2.1](04-api-reference.md)). A `Conversation` already holds everything a job record used to: the scene (`parentId`), the model (`aiParticipant.modelId`), the definition (`aiJobId`), and timestamps. The [conversation worker](05-ai-system.md) drives automatic runs by draining conversations at `status: queued`. Books created before this change carry a legacy `db/jobs.json`; it is deleted on first load (nothing to migrate — the conversation it shadowed already exists).

## db/ui.json

Per-book UI preferences, portable with the book: AG Grid column state (visibility, order, widths), right-pane visibility, and future keys. Written debounced.

## Data safety & concurrency

Protection is achieved through patterns (stdlib) plus exactly one library. Five layers:

1. **Torn-write protection** — the hardened atomic-write helper above (`tempfile` in same dir, `fsync`, `os.replace`, POSIX dir fsync). ~15 lines, stdlib only; the `atomicwrites` package is deprecated and must not be used.
2. **In-process races** — the server runs exactly **one** Uvicorn worker (`workers=1`, pinned in the launcher; multiple workers would mean multiple writers). Within the async event loop, every mutation acquires the target book's `asyncio.Lock` (app.json has its own) around its read-modify-write-persist cycle. Reads take no lock; mutations replace collections rather than tweaking them in place, so readers never observe half-mutated state.
3. **Double-instance protection** — at startup the API takes an exclusive lock on `{appDataRoot}/.lock` via the **`filelock`** library (the single added dependency; pure Python, cross-platform). A second instance fails fast with "Authority is already running" instead of silently double-writing.
4. **Corrupt-load recovery** — a JSON file that fails to parse at load is never overwritten: it is copied to `{file}.corrupt-{timestamp}`, a loud error names it, and the book loads degraded. Derived files (`conversations/index.json`) are rebuilt automatically from a folder scan. Git is the ultimate restore mechanism: every commit is a known-good snapshot (`git checkout -- db/scenes.json`).

   Per-scene files (`scenes/{id}/meta.json`, `bookkeeping.json`, `dependencies.json`, `relationships.json`) follow the same quarantine-and-never-overwrite rule, but scoped: a corrupt file degrades **only that scene** to defaults (blank mood/summary, no tagged characters) rather than the load-time `ApiError` that a corrupt `db/*.json` collection raises. This is a deliberate improvement from splitting `scenes.json` — the whole point of the split was shrinking the blast radius of a bad file, and this is where that pays off. The master `db/scenes.json` itself keeps the stricter raise-and-degrade-the-whole-book behavior, same as every other `db/*.json` collection.
5. **Load-time schema validation** — on-disk documents are validated against the same Pydantic models used at the API boundary when a book loads; violations are reported per-file (treated as layer-4 corruption), catching hand-edited or drifted data before it compounds.

## Migration: old flat scenes.json → master + per-scene

Books created before this split have every scene field on one row in
`db/scenes.json` plus flat `db/relationships.json`/`db/dependencies.json`.
`BookDataManager` detects this transparently the first time a book is opened
— no manual step: if any row carries a field that no longer belongs on the
trimmed master (`location`, `dateTime`, `mood`, `emotionalArc`, `summary`,
`characterIds`, `contentHash`, `wordCount`), it splits every row into master +
`meta.json` + `bookkeeping.json`, groups the old flat relationships/
dependencies files by owning scene into each scene's folder, then commits the
trimmed `db/scenes.json` **last** — the actual commit point. A crash before
that write leaves the old shape in place, so the next load simply retries the
whole migration (rewriting already-written per-scene files is a harmless
no-op). The superseded flat files are renamed (never deleted) to
`relationships.json.pre-split-{ts}` / `dependencies.json.pre-split-{ts}`.
