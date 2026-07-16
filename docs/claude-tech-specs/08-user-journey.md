# 08 — The Journey: End-to-End Traces

This document stitches the whole system together. It follows one author's complete journey — the same journey the spec was designed around — and traces **every action through every layer**: the control clicked (doc 06) → the HTTP call (doc 04) → the services engaged and the data they read/write (docs 02–03, 05) → how the result returns → how the action completes on screen.

Trace notation:

```
CLICK    what the author does
→ HTTP   method + path (+ body essentials)
→ SERVER router → Service.method: numbered internal steps  [files read/written]
→ REPLY  response body essentials / SSE events
→ UI     what the author sees happen
```

Files are relative to the book folder unless prefixed `app:` (app data root). "Lock" = the book's asyncio mutation lock. Every file write is the atomic pattern (tmp → fsync → `os.replace`).

---

## J1 — Launch

**CLICK** Author runs `start.sh` on ubuntu or `start.bat` on windows

```
→ SCRIPT  1. GET /api/health — no answer, so not already running
          2. conda env "authority" found (first run would: create env, pip install,
             npm install && npm run build, write .setup-complete)
          3. exec uvicorn app:app --port 8700 --workers 1
→ SERVER  startup: acquire filelock on app:.lock (second instance would exit:
          "Authority is already running") · read app:launcher.config.json ·
          SettingsService loads app:app.json into memory · logging → console + logs/api.log ·
          JobService worker task starts (idle) · static mount of frontend/dist with
          SPA index-fallback
→ SCRIPT  polls GET /api/health → 200 {"status":"ok"} → xdg-open http://localhost:8700
→ UI      browser opens; SPA boots; router lands on /
```

## J2 — Home page loads

```
→ HTTP    GET /api/settings/user            (top bar greeting)
→ SERVER  SettingsService: memory read of app.json.user
→ REPLY   { "name": null, "booksHome": null }        (first ever run)
→ HTTP    GET /api/books
→ SERVER  BookScanner: booksHome unset
→ REPLY   422 books-home-unset
→ UI      Top bar says "Welcome". Shelf shows the empty state:
          "Set your books folder to get started" → [Open settings]
```

## J3 — User Settings: name + books-home

**CLICK** Settings → User Settings. Types name "Chetan", path `~/Books`, clicks **Save**.

```
→ HTTP    PATCH /api/settings/user  { name:"Chetan", booksHome:"~/Books" }
→ SERVER  SettingsService: 1. expanduser → /Users/chetan/Books; exists? no →
          422 path-not-found
→ UI      Inline error under the field + [Create this folder]
CLICK     [Create this folder]
→ HTTP    PATCH /api/settings/user  { ..., createBooksHome:true }
→ SERVER  1. os.makedirs · writability probe (tempfile) ok
          2. persist  [app:app.json]   3. BookScanner cache invalidated
→ REPLY   { name:"Chetan", booksHome:"/Users/chetan/Books" }
→ UI      Toast "Settings saved". Top bar: "Welcome, Chetan".
```

## J4 — AI Settings: add a model

**CLICK** AI Settings → **[Add model]** → provider `anthropic`, label "Sonnet", model `claude-sonnet-4-6`, key `${ANTHROPIC_API_KEY}` → **Save**.

```
→ HTTP    POST /api/settings/models  { label, provider, modelName, apiKey }
→ SERVER  SettingsService: 1. provider rule — anthropic requires apiKey ✓ (stored
          verbatim as the ${ENV} reference; resolved only at call time by ModelFactory)
          2. id mdl-3fa2c1 · persist  [app:app.json]
→ REPLY   ModelConfig with apiKeyMasked "…KEY}"
→ UI      Row appears in the table, key masked. Author also sets it as
          Default utility model → PATCH /api/settings/ai { utilityModelId } → [app:app.json]
```

## J5 — AI-Jobs: define "Editorial Review"

**CLICK** AI-Jobs → **[Add AI-Job]**. In the prompt textarea types `You are reviewing @cur…` — the `@` opens the autocomplete.

```
→ HTTP    GET /api/settings/placeholders          (fetched once, cached)
→ REPLY   [{name:"@current_scene", description:"Full prose…"}, …]
→ UI      Menu filters as she types; Enter inserts @current_scene. She adds
          @previous_scenes_summary and @character_sheet the same way, picks
          output type "Edit proposals — returns applyable find-and-replace edits",
          default model Sonnet → [Save job]
→ HTTP    POST /api/settings/ai-jobs  { name, prompt, defaultModelId, outputType:"edit-proposals" }
→ SERVER  SettingsService: PlaceholderRegistry scans tokens (@[a-z0-9_]+) — all known ✓ ·
          id aij-77d0be · persist  [app:app.json]
→ REPLY   AIJobDefinition
→ UI      Row in the jobs table. (A typo like @charcter_sheet would have returned
          422 {unknownPlaceholders} → inline warning + [Save anyway] → force:true.)
```

## J6 — Add a book

**CLICK** Home → **[+ Add book]** → title "My Great Novel", drops a cover image → **[Create book]**.

```
→ HTTP    POST /api/books   (multipart: title, cover)
→ SERVER  BookService: 1. validate title/booksHome/writability
          2. id bok-a3f9c2 · slug my-great-novel · mkdir a3f9c2-my-great-novel/
          3. scaffold  [config/book.json (bookkeeping both true, empty parts/chapters),
             scenes/.gitkeep, db/{scenes,relationships,dependencies,characters,
             plotlines,todos,jobs,ui}.json seeded empty, db/conversations/index.json,
             assets/cover.jpg (stored as-is), compiled-book/.gitkeep, .gitignore "*.tmp"]
          4. GitService: git init · add -A · commit "initialized"
          5. BookScanner cache add
→ REPLY   201 BookSummary
→ UI      Toast "Book created"; router navigates into /book/bok-a3f9c2
```

## J7 — Entering the book

```
→ HTTP    GET /api/books/bok-a3f9c2
→ SERVER  first request naming this book → BookDataManager.load():
          reads every db/*.json + config/book.json into memory (per-file corrupt
          quarantine + Pydantic load-validation per doc 03 Data Safety) ·
          ChainService pre-orders parts/chapters (both empty)
→ REPLY   Book { title, bookkeeping, parts:[], chapters:[] }   (client caches: ['book', id])
→ HTTP    GET /api/books/{id}/events        (SSE — stays open for the session)
→ SERVER  EventHub registers the subscriber
→ HTTP    GET /api/books/{id}/scenes
→ REPLY   { scenes:[], relationships:[], sentinels:[scn-START, scn-END] }
→ UI      Left nav switches to book context; Graph view renders just the two
          sentinel pills and the empty-state "No scenes yet." [Add scene]
```

## J8 — First scene

**CLICK** **[＋ Add scene]** → Scene Modal (create). Title "The Arrival", description filled, Previous = *Start* → **[Save scene]**.

```
→ HTTP    POST /api/books/{b}/scenes  { title, description, previousSceneId:"scn-START" }
→ SERVER  SceneService (lock): 1. validate (title/desc non-empty; chapter-xor-part n/a;
          sentinel rules ok)  2. id scn-1f2e9b · create empty file
          [scenes/1f2e9b-the-arrival.md] · hash/wordCount of empty
          3. ChainService.splice: Start currently has no next → Start→scn-1f2e9b
          4. persist [db/scenes.json] · GitService dirty-check → EventHub git-status
→ REPLY   201 { scene (seq:1, placement:"trunk"), affectedScenes:[] }
→ UI      Node fades in under (Start), solid arrow connecting. Top-bar badge
          lights: "2 pending changes · Commit now?" (scenes.json + the new .md)
```

## J9 — Second scene, softly placed

**CLICK** [＋ Add scene] → "The Cellar", description, no hard links; Soft placement row: *definitely after* → "The Arrival" → Save.

```
→ HTTP    POST /scenes { title, description, softRelations:[{type:"after", sceneId:"scn-1f2e9b"}] }
→ SERVER  SceneService: create scn-8c31d7 + file · no splice · creates
          rel-4e9a02 {from:scn-8c31d7, to:scn-1f2e9b, type:"after"}
          [db/scenes.json, db/relationships.json]
→ REPLY   { scene (placement:"floating", seq: after trunk numbering) }
→ UI      Satellite node appears right of "The Arrival", slightly below its level,
          thin dotted arrow The Arrival ⇢ The Cellar. Hover on the edge:
          "definitely after The Arrival".
```

## J10 — Structure: a part and a chapter

**CLICK** Metadata → Parts → [＋ Add part] "Part One" → Chapters tab → [＋ Add chapter] "Chapter 1", Part = Part One.

```
→ HTTP    POST /parts { title:"Part One" }
→ SERVER  StructureService (lock): append to part chain (first: prev/next null) ·
          persist [config/book.json]
→ HTTP    POST /chapters { title:"Chapter 1", partId:"prt-…" }
→ SERVER  same pattern  [config/book.json]
→ UI      Chapter row appears grouped under "Part One". Readiness strip (auto
          GET /compile/check on page load) shows errors like "The Arrival: no
          chapter", "The Cellar: floating" — the standing to-finish list.
```

## J11 — Into the editor, writing, autosave

**CLICK** Graph → double-click "The Arrival".

```
→ HTTP    GET /scenes/scn-1f2e9b
→ SERVER  memory metadata + reads the .md file
→ REPLY   { …scene, content:"" }
→ UI      Left nav collapses to the rail; empty Literata sheet, cursor ready.
```

Author writes. Two seconds after a pause:

```
→ HTTP    PUT /scenes/scn-1f2e9b/content { content:"…full markdown…" }
→ SERVER  SceneService (lock): 1. atomic write [scenes/1f2e9b-the-arrival.md]
          2. wordCount 412 · new sha256 ≠ old →
             a. dependency fanout: no Dependency rows point here yet → none
             b. EnrichmentService: (re)set 60s settle timer for scn-1f2e9b
          3. persist [db/scenes.json] · git-status SSE (badge count updates)
→ REPLY   { wordCount:412, contentHash:"sha256:…", todosCreated:[] }
→ UI      Bottom bar: "412 words · Saved 2:41pm". This repeats invisibly with
          every pause; each save resets the settle timer.
```

## J12 — Enrichment fires (the system working alone)

Author stops typing for 60s (or navigates away → immediate settle).

```
→ SERVER  settle timer fires → EnrichmentService reads book.json.bookkeeping
          {summaryOnSave:true, charactersOnSave:true} → JobService enqueues
          Job job-c2d4e6 {type:"system", scope:"both", sceneId, modelId: utility}
          [db/jobs.json] · EventHub: job {status:"queued"}
→ WORKER  picks it up → job "running" (SSE) →
          reads scene prose [scenes/….md] + character directory (memory; empty so far)
          → AIOrchestrator + utility model → summary text; character matching finds
          the name "Marlow" but no directory entry exists → never silently creates
→ SERVER  (lock) scene.summary = generated text · characterIds for exact matches only ·
          persist [db/scenes.json, db/jobs.json] ·
          unmatched/ambiguous → EscalationService opens a chat on the scene seeded
          with the question · SSE: scene-updated · job {status:"done", result}
→ UI      Right pane → Notes/AI Jobs: escalation chat appears. Author answers;
          AI may propose_character_create → Accept → character sheet (+ optional tag).
          Clear bookkeeping writes need no confirm — the toggles are standing consent.
```

**CLICK** in the escalation chat → author decides → proposal Accept (when Characters API exists) → later enrichment matches him → `scene-updated {changed:["characterIds"]}`.

## J13 — Stuck: chat from a selection

Author selects a paragraph, **CLICK** [Chat] in the tool panel.

```
→ HTTP    POST /conversations { kind:"chat", parentType:"scene", parentId:scn-1f2e9b }
→ SERVER  ConversationService: creates cnv-9f2c1a (aiParticipant {enabled:false}) ·
          [db/conversations/cnv-9f2c1a.json, index.json updated]
→ UI      Conversation Modal opens; the selection is queued as context for the
          first message. Author flips the AI participant switch ON, picks Sonnet:
→ HTTP    PATCH /conversations/cnv-9f2c1a { aiParticipant:{enabled:true, modelId:"mdl-3fa2c1"} }
→ UI      Types "Does this paragraph contradict the cellar scene?" → Send
→ HTTP    POST /conversations/cnv-9f2c1a/messages
          { content, context:[{sceneId, excerpt:"…the selected text…"}] }   (SSE response)
→ SERVER  1. append user Message (title becomes "Does this paragraph contradict…")
             [cnv file + index]
          2. enabled → build LangChain call: system = book systemPrompt + framing +
             tool schemas; history = messages (excerpt as quoted block); bind tools
          3. stream: token events →; mid-stream the model calls read tool
             get_scene(scn-8c31d7) — served from memory, prose from disk; it may call
             propose tools, which only accumulate Proposal objects
          4. persist assistant Message {modelId, content, proposals} → final
             "message" event → "done"
→ UI      Tokens render live under the model's label. Author reads the answer,
          flips the AI switch OFF, and types two follow-up notes to herself —
          each a plain POST /messages that just appends (no model call).
          She closes the modal: nothing to save — every message already persisted.
          Right pane → Notes now lists the conversation by name and time.
```

## J14 — Running the Editorial Review job

**CLICK** Tool panel → **AI-Jobs ▾** → "Editorial Review" (no selection active → scope full).

```
→ HTTP    POST /ai-jobs/run { aiJobId:"aij-77d0be", sceneId:"scn-1f2e9b", scope:"full" }
→ SERVER  1. ConversationService: cnv-b8d1f0 {kind:"ai-job", title:"Editorial Review — 14:52",
             aiParticipant:{enabled:true, modelId: job default}, aiJobId + name snapshot}
          2. JobService: Job job-e91a2b {type:"user", status:"queued"}  [jobs.json]
→ REPLY   202 { jobId, conversationId }
→ UI      Conversation Modal opens on the empty thread; AI Jobs pane shows
          "Editorial Review · queued".
→ WORKER  status "running" (SSE) →
          1. PlaceholderRegistry resolves the prompt: @current_scene ← the .md prose;
             @previous_scenes_summary ← ChainService walks prev-chain to Start,
             emits "Title — summary" lines (summaries only); @character_sheet ←
             db/characters.json entries
          2. outputType edit-proposals → format instructions appended (reply must
             end with a fenced JSON array of {find, replace, rationale})
          3. resolved prompt posted as a system-authored first message (collapsed
             in the UI to "Job prompt · show")
          4. model streamed into the conversation (same J13 mechanics, live in the
             open modal)
          5. fenced JSON parsed → three edit Proposals attached to the assistant
             message (block stripped from displayed content); parse failure would
             degrade to chat + result.warning
          6. job "done" (SSE)  [cnv file, jobs.json]
→ UI      The reply's prose commentary, then three amber proposal cards:
          strikethrough find / replacement / rationale, each [Reject] [Accept],
          footer [Accept all (3)].
```

## J15 — Accepting an edit (the only AI path into prose)

**CLICK** [Accept] on card one.

```
→ HTTP    POST /proposals/prp-11aa22/accept
→ SERVER  ProposalService (lock): locate via index → cnv-b8d1f0 → pending ✓ ·
          type edit → read [scenes/1f2e9b-the-arrival.md] · find first exact
          occurrence of payload.find — present → replace once → save through the
          STANDARD content path: atomic write, hash recompute, dependency fanout,
          settle-timer reset (an applied edit is a content change like any other) ·
          proposal status "applied" + resolvedAt  [.md, db/scenes.json, cnv file]
          · SSE scene-updated, git-status
→ REPLY   { proposal, result:{ wordCount, contentHash } }
→ UI      Card turns green ✓. The editor (same scene open) reconciles content.
          Card two: author had meanwhile rewritten that sentence — accept returns
          status "not-found" → amber note "This text is no longer in the scene."
          Nothing changed on disk. Card three: [Reject] → POST …/reject → card fades.
```

## J16 — A dependency, and the day it pays off

In "The Cellar"'s Scene Modal → Dependencies tab: depends on **The Arrival**, reason "Marlow must find the key here first" → **[Add dependency]**.

```
→ HTTP    POST /dependencies { sceneId:"scn-8c31d7", dependsOnSceneId:"scn-1f2e9b", reason }
→ SERVER  validate (non-self, both active, reason non-empty, no duplicate pair) ·
          dep-5f0c33  [db/dependencies.json]   — no todo fires now
```

Weeks later the author rewrites The Arrival (Marlow no longer finds the key). Autosave:

```
→ SERVER  PUT content → hash changed → dependency fanout: dep-5f0c33 points here →
          no open todo for it exists yet → create Todo on scn-8c31d7:
          "'The Arrival' changed — verify dependency: Marlow must find the key here
          first" {origin:"dependency", sourceDependencyId}  [db/todos.json]
          · SSE todos-created
→ UI      If The Cellar's editor is open: To-dos badge ticks up, amber ⛓ row.
          Tasks page shows it book-wide. The author reads it → the change matters →
          fixes The Cellar; or it doesn't → row menu Close (status "closed").
          Repeated saves during the session do NOT stack duplicates (open-todo dedup).
```

## J16.5 — The badge keeps itself honest (the system working alone)

Nobody clicks anything. The author is writing; the git badge updates itself. Three
**independent** mechanisms produce that: the write (A), the debounced worker (B),
and the poll (C). They never call each other.

**(A) The write — git does not run here.**

```
       Author writes; pauses 2s (editor autosave, as J11)
→ HTTP  PUT /scenes/scn-1f2e9b/content { content:"…" }
→ SERVER SceneService (lock): 1. atomic write [scenes/1f2e9b-the-arrival.md]
          2. wordCount + sha256 recompute
          3. BookDataManager.save_scenes(...) → atomic write [db/scenes.json]
          4. lock released
          5. BookDataManager emits book-changed {} — payload-free, fire-and-forget
             · EventHub places it on (a) the global queue the git-status worker
               reads and (b) each open tab's per-book queue (tabs ignore it —
               nothing in the UI renders from book-changed)
→ REPLY   { wordCount:412, contentHash:"sha256:…" }
→ UI      "412 words · Saved 2:41pm". No git status has run. Badge unchanged.
```

**(B) The worker — reacting, ~5s later.**

```
→ WORKER  GitStatusWorker (one standing asyncio task, subscribed to the hub's
          global channel) receives book-changed:
          1. cancels any pending debounce timer for this bookId
          2. starts a fresh 5s timer
             (another book-changed inside those 5s → back to step 1; a long
              autosave streak keeps deferring the check until typing stops)
          3. 5s of quiet → timer fires → GitService.status(bok-a3f9c2)
          4. GitPython runs the real `git status` on the working tree
          5. summary built from the file counts → "3-updated"
          6. emit git-status { dirty:true, files:[…], summary:"3-updated", … }
→ SSE     each open tab's /events connection receives it
→ UI      useBookEvents → queryClient.setQueryData(['git', bookId], status) →
          top bar fades in, amber: "3-updated · Commit now?"
```

**(C) The poll — the net, running regardless.**

```
→ HTTP    every 10s while a book is open, useGitStatus refetches GET /git/status
→ SERVER  the same GitService.status(), synchronously in-request
→ UI      written into the same ['git', bookId] cache entry
```

C knows nothing about A or B — it is pure redundancy until it isn't. If the
`book-changed` signal, the `git-status` emit, or the SSE delivery is ever lost
(a flaky reconnect, a bug in the debounce), the badge still tells the truth within
10s. The event path is the fast path; the poll is the honest one. While the tab is
hidden the interval pauses — nobody is reading the badge — and refetch-on-focus
brings it current before the author can see it.

## J17 — Git: the deliberate save

Badge reads "3-updated · Commit now?" **CLICK** it. Everything here is an
*explicit* action, so — unlike J16.5 — each one recomputes and emits `git-status`
**immediately, in-request**. The worker's 5s debounce is never involved: the
author is watching this screen.

```
→ HTTP    GET /git/status
→ REPLY   { dirty:true, files:[{path:"scenes/1f2e9b-….md", status:"modified", staged:false}, …],
            ahead:0, behind:0, hasRemote:false, summary:"3-updated" }
CLICK     [Stage all]
→ HTTP    POST /git/stage {all:true}
→ SERVER  GitService (lock): repo.git.add(A=True) → recompute status →
          emit git-status immediately
→ UI      refreshed status, boxes checked
CLICK     a filename → GET /git/diff?path=… → unified diff in the right panel
CLICK     [✨ Suggest message]
→ SERVER  GitService staged diff (422 nothing-staged if empty) → truncate to cap →
          SettingsService.get_utility_model() →
            present → "Summarize these changes to a novel manuscript as a
                       single-line commit message."
            absent  → deterministic stats fallback ("3 scenes updated")
→ REPLY   { message:"Rework Marlow's arrival; seed the missing-key thread" }
→ UI      Textarea filled (a fallback message arrives with the faint note
          "Written from file stats"); author trims a word.
CLICK     [Commit staged files]
→ SERVER  POST /git/commit → GitPython commit → recompute status
          (dirty:false, summary:"all-changes-synced") → emit git-status immediately
→ REPLY   { hash:"4b7e19a" }
→ UI      Toast "Committed 4b7e19a"; badge disappears at once — no 5s wait;
          history strip gains the line.
```

## J18 — Compilation: the gate, then the book

**CLICK** Metadata. The readiness strip (auto `GET /compile/check`) reads "⚠ 2 errors".

```
→ SERVER  CompileService: ChainService walks Start→…: The Cellar has no chapter
          (scene-no-chapter) and is floating (scene-floating). Warnings: none yet.
→ UI      Expanded report; each item links. Author: Scene Modal on The Cellar →
          Basics: Previous = The Arrival (splice: Arrival→Cellar), Chapter = Chapter 1;
          then Next = The End on The Cellar. PATCHes flow as in J8/J9; the stale
          soft relation rel-4e9a02 is now satisfied by the chain → next check
          shows warning soft-relation-redundant; she deletes it
          (DELETE /relationships/rel-4e9a02). Check → "✅ Ready to compile".
CLICK     [Compile book]
→ HTTP    POST /compile
→ SERVER  (lock) re-check ✓ → wipe compiled-book/ → part chain: Part One →
          chapter chain: Chapter 1 → its scenes in chain order → write
          [compiled-book/part-1-part-one/chapter-1-chapter-1.md]
          ("# Chapter 1", scenes joined by *** breaks) → SSE compile-done, git-status
→ REPLY   CompileReport { filesWritten:[…], sceneCount:2, chapterCount:1, warnings:[] }
→ UI      Build-report dialog; toast "Book compiled — output is uncommitted" linking
          to Git, where the J17 ritual saves the manuscript into history.
```

---

## The loop

J11 → J12 → J13/J14 → J15 → J16 → J17 is the author's daily cycle: write, let the system keep the books, consult when stuck, apply what's accepted, honor the dependencies, commit the day. J18 is the horizon it all points at.

J12 and J16.5 are the two traces with no author in them — the system keeping its own books while the prose gets written. Both follow the same discipline: the expensive work (a model call, a `git status`) is deferred behind a settle timer and never blocks the save, and the author is told only when there's something to decide.
