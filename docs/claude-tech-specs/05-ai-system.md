# 05 — AI System

## Provider abstraction (LangChain)

One factory: `model_config → BaseChatModel`.

| provider | LangChain class | Notes |
|---|---|---|
| `anthropic` | `ChatAnthropic` | apiKey required |
| `openai` | `ChatOpenAI` | apiKey required |
| `gemini` | `ChatGoogleGenerativeAI` | apiKey optional — defaults to `GOOGLE_API_KEY` |
| `openai-compatible` | `ChatOpenAI(base_url=...)` | LM Studio etc.; baseUrl required, key optional |
| `ollama` | `ChatOllama(base_url=...)` | baseUrl required |

Key resolution at call time: a literal key is used verbatim; `${ENV_VAR}` reads that environment variable; an **empty** key falls back to the provider's default environment variable (`anthropic` → `ANTHROPIC_API_KEY`, `openai` → `OPENAI_API_KEY`, `gemini` → `GOOGLE_API_KEY`), so authors who already export the standard variable need not enter anything. A missing/unset variable surfaces as a clear error (at model-test or first use). Everything downstream (chat, jobs, streaming, tool-calling) is provider-agnostic.

**AI task models** (`app.json → ai.*`): rather than one model for every system task, each task has its own slot, so (for example) scene summarization and character parsing can run on different models:

| Slot | Used for |
|---|---|
| `utilityModelId` | The general-purpose fallback (below) **and** sundry system tasks that don't warrant their own slot — today, chat conversation title-naming |
| `commitMessageModelId` | Git commit-message suggestion |
| `sceneSummaryModelId` | Enrichment's scene-summarization pass |
| `characterParsingModelId` | Enrichment's character-matching pass, and the escalation chats it seeds when a match is ambiguous or unrecognized |
| `chatDefaultModelId` | Preselected model when the author opens a new chat from the editor (a UI default only — the author can still change it in the conversation) |

**Resolution:** each task-specific slot resolves to its own model if set and known, else falls back to `utilityModelId`, else `null` — degrade gracefully, never fail. `utilityModelId` itself has no further fallback. More slots may be appended the same way as new AI-assisted tasks need independent model choice.

Chat-title-naming: ask for a 3–5 word name when a thread is still `"Untitled"`, via a dedicated naming prompt — not the chat-assistant framing. The model's reply is stored as returned (whitespace trimmed only — **no server-side sanitizer or word clipping**). If no model resolves, falls back to the first words of the user message.

**Conversation titles (three paths):**

1. **Escalation** (any “background AI needs the author”): the **caller** supplies a short `title` on the escalation issue. EscalationService stores that title as-is (fallback `"Needs your input"`). Example: enrichment passes `who is Lencie?` for an unknown name — other future callers pass their own labels without changing EscalationService.
2. **AI-Job:** conversation title = the job definition’s name (no clock suffix).
3. **Chat / note:** utility model names the thread after the first user message while still Untitled. Truncation for display is **UI-only** (ellipsis + full title on hover).

**Book system prompt** (`book.json → systemPrompt`): prepended to every AI call for that book (chats, jobs, enrichment) — not used for the title-naming one-shot.

## Context assembly & placeholders (who calls what)

There is no separate “context service.” Two pieces do the work:

| Piece | Role |
|---|---|
| **ContextAssembler** | Translator only. Takes a saved conversation (or a one-shot prompt) and builds the LangChain message list the model sees: system framing + book `systemPrompt` + optional **CURRENT SCENE** block + each stored message as user/assistant/system. It does **not** talk to the network, open the editor URL, or invent which scene is “current.” Callers pass that in. |
| **PlaceholderRegistry** | Dictionary of known `@tokens` plus `resolve(prompt, mgr, scene_id, selection_text)`. Replaces tokens with prose/metadata from disk for that **explicit** `scene_id`. It never infers “most recently updated” or “which tab is open.” |

**Scene identity rule:** the target scene always comes from the editor URL → conversation `parentId` / job `sceneId`. If that id is not passed into `resolve` or into the assembler’s `CURRENT SCENE` block, the model only has tools and may guess wrong.

### Who calls ContextAssembler

| Caller | When |
|---|---|
| **ConversationService** | Author sends a chat message |
| **JobService** | An AI-Job runs |
| **GitService** / **EnrichmentService** | One-shot prompts (no conversation thread) |

Those callers hand the message list to **AIOrchestrator**, which invokes the model (with tools when bound).

### Who calls PlaceholderRegistry.resolve

| Caller | When |
|---|---|
| **JobService** | Expands the AI-Job definition prompt against `job.sceneId` before the run; expanded text is stored as a **system** message on the job’s conversation |
| **ContextAssembler** | When building chat/job model payloads: expands `@tokens` inside *user* messages for the model only (stored transcript still shows the literal `@current_scene`) |
| **SettingsService** | Does **not** resolve — lists vocabulary for `@` autocomplete and rejects unknown tokens when saving an AI-Job definition |

### Chat call chain

1. Editor opens chat with `parentType: scene`, `parentId: sceneId` from the URL. That binding is stored on the conversation.
2. Author types e.g. `editorial review for @current_scene`.
3. **ConversationService** saves that text as-is (token stays in the transcript).
4. It asks **ContextAssembler** for model messages, passing the conversation’s parent scene (id + title) and the book data manager.
5. Assembler injects `CURRENT SCENE (id, title)` into the system block and resolves `@tokens` in user messages against that scene id.
6. **AIOrchestrator** runs the model (tools available).

Without step 5, `@current_scene` stays literal, the model may call `list_scenes` / `get_scene`, and pick the wrong scene by freshness or sequence.

### AI-Job call chain

1. Editor runs a job with `sceneId` from the URL.
2. **JobService** calls `PlaceholderRegistry.resolve(job_prompt, scene_id=that id)` (and optional selection text).
3. Expanded text is appended as a system message on the job’s conversation.
4. **ContextAssembler** builds the thread (same `CURRENT SCENE` framing) → **AIOrchestrator** runs.

### One-line summary

Scene identity comes from the editor URL → conversation/job parent id. Placeholders only expand when someone passes that id into `resolve`. ContextAssembler packages messages; it does not discover “current” by itself.

## Placeholder registry

Server-defined; exposed via `GET /api/settings/placeholders`; drives the `@` autocomplete in the AI-Job prompt editor and save-time validation. Initial set:

| Placeholder | Resolves to |
|---|---|
| `@current_scene` | Full prose of the target scene |
| `@selection` | The selected text (empty if none) |
| `@selection_or_scene` | Selection if present, else full scene |
| `@scene_metadata` | Title, description, location, dateTime, mood, arc, summary of the target scene |
| `@scene_characters` | Full character sheets (identity + craft fields) of characters tagged in the scene |
| `@character_sheet` | Full character sheets of everyone in the book, plus their relationships to each other |
| `@previous_scenes_summary` | Hard prev-chain walked back to Start, emitted in story order as `Title — summary` lines (summaries only, never prose; missing summary → `(no summary)`); archived and soft-only scenes excluded |
| `@all_scene_summaries` | Every active scene's title + summary in seq order |
| `@story_summary` | book.json storySummary |
| `@plotlines` | Plotline titles + descriptions, this scene's links flagged |

Unknown tokens are left literal at resolve time but flagged at AI-Job definition save.

## AI-Jobs: end-to-end run

1. Author picks a job from the editor dropdown (optionally with a selection active) → `POST /ai-jobs/run`.
2. Server creates a conversation (kind `ai-job`, parent scene, title = job name + time, model = job default) and a queued job record; client opens the conversation modal, which subscribes to the stream.
3. Worker: resolve placeholders against the job’s `sceneId` → append resolved prompt as a system message → ContextAssembler (book systemPrompt + CURRENT SCENE) → invoke model **with tools** → stream tokens into the conversation.
4. Output parsing by `outputType`:
   - `chat` — reply is plain conversation.
   - `edit-proposals` — model instructed (via injected format instructions) to emit edits as structured find/replace items; parsed into `edit` proposals on the message.
   - `metadata-proposals` — same pattern for metadata-update proposals.
5. Author continues the conversation freely; accepts/rejects proposals whenever. Job status (`queued/running/done/failed`) rides the book SSE channel and shows in the AI Jobs accordion pane.

## Enrichment (system bookkeeping)

Maintains `scene.summary` and `scene.characters` (each `{ characterId, involvement }`).

**Trigger — leave-scene + on-demand:** content saves never schedule enrichment. When the author **leaves** the scene editor (and prose changed this visit), the client calls `POST /scenes/{id}/enrich/auto`, which queues a `system` job scoped by the book's toggles (`summaryOnSave`, `charactersOnSave`; both off, or neither toggle's model resolves, → nothing queued). On-demand: `POST /scenes/{id}/enrich` (Scene Modal ↻ AI-redo) runs regardless of toggles. Saves while a system job is queued replace the queued job (never two per scene).

**Execution — two independent calls, not one:** scope `summary` and scope `characters` are **separate model invocations**, each against its own configured model (`ai.sceneSummaryModelId` / `ai.characterParsingModelId`, doc 03/04) — this is what makes it possible to run summarization on one model and character-matching on another. Scope `both` runs both calls (even when they happen to resolve to the same model, for uniformity); either half is skipped independently if its model doesn't resolve (own slot → utility fallback → unset). A system `Job` no longer carries a single `modelId` at enqueue time — each half resolves its model at run time, and `job.result.modelsUsed` records which model served each half (`{"sceneSummary": "mdl-..", "characterParsing": "mdl-.."}`).

Input for each call: scene prose (+ character directory of names/aliases, for the character-parsing call).

- **Clear cases:** Summary call overwrites `scene.summary`. Character call sets `characters` to matched *existing* cast members with a one-line `involvement` of what they do in this scene. Field changes emit `scene-updated` SSE.
- **Unclear cases:** unmatched names, ambiguous matches, or “is this too minor?” → **EscalationService** opens a chat on the scene with a **caller-supplied short title** (enrichment uses `who is {name}?`) and seeds the thread with the longer question, defaulting the escalation chat's AI participant to the **character-parsing model** that produced the ambiguity (not the summary model). The AI may then `propose_character_create` (or other propose tools); the author Accepts before anything is written to the sheet. Enrichment **never silently creates** character records.

**Toggle semantics:** toggle ON = AI owns the field and may overwrite on leave-scene for *clear* updates. Want a hand-written summary? Flip it off. No freeze flags.

## AI tool-calling surface

Bound via LangChain tool-calling on every assistant invocation (chats and jobs).

**Read tools — execute freely:** `get_scene(id)` (prose + metadata), `list_scenes()` (titles, seq, placement), `get_scene_summaries()`, `get_character_sheet(id|all)`, `search_text(query)` (across active scene files), `get_plotlines()`, `get_story_summary()`, `get_todos(sceneId?)`.

**Write tools — never mutate; emit proposal objects into the message:** `propose_edit(sceneId, find, replace, rationale)`, `propose_metadata_update(targetType, targetId, field, newValue)`, `propose_todo(parentType, parentId, action)`, `propose_character_create(name, aliases?, age?, gender?, nationality?, ethnicity?, occupation?, want?, need?, flaw?, arc?, personality?, history?, notes?, rationale?, sceneId?)` — the AI is expected to fill in whatever the prose or conversation makes clear, not just the name, `propose_character_relationship(characterAId, characterBId, category, aToB, bToA, description?, rationale?)` — directional on both sides since most relationships aren't symmetric.

On accept, character-create proposals dedupe case-insensitively against existing names/aliases (reusing the match instead of erroring) and, if `sceneId` was passed, tag the character onto that scene.

The only mutation endpoints acting on AI output are `POST /proposals/{id}/accept|reject` — both author-triggered. This is how the hard rule is enforced structurally, not by prompt.

## Streaming & events

- **Chat/job streaming:** `POST /conversations/{id}/messages` responds as an SSE stream: `token` events, then `message` (final persisted message incl. proposals).
- **Book channel:** `GET /books/{id}/events` — `job`, `scene-updated`, `todos-created`, `git-status`, `compile-done`. One connection per open book; drives badges, accordion statuses, live metadata patches.

## Worker

Single asyncio task; per-book FIFO, concurrency 1 per book (≤2 global). Failures → status `failed` with error string; visible in the AI Jobs pane; no automatic retry (author re-runs).
