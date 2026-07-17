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
| `characterParsingModelId` | Enrichment's character-matching run — the same model that asks the author in-thread when a match is ambiguous or unrecognized |
| `chatDefaultModelId` | Preselected model when the author opens a new chat from the editor (a UI default only — the author can still change it in the conversation) |

**Resolution:** each task-specific slot resolves to its own model if set and known, else falls back to `utilityModelId`, else `null` — degrade gracefully, never fail. `utilityModelId` itself has no further fallback. More slots may be appended the same way as new AI-assisted tasks need independent model choice.

Chat-title-naming: ask for a 3–5 word name when a thread is still `"Untitled"`, via a dedicated naming prompt — not the chat-assistant framing. The model's reply is stored as returned (whitespace trimmed only — **no server-side sanitizer or word clipping**). If no model resolves, falls back to the first words of the user message.

**Conversation titles (three paths):**

1. **Bookkeeping run:** title is what the run does — `"Scene summarization"` or `"Character enrichment"` — set by EnrichmentService at creation. An escalation (the AI asking about an unclear character) is a message *in that same conversation*, not a new thread with its own title.
2. **AI-Job:** conversation title = the job definition’s name (no clock suffix).
3. **Chat / note:** utility model names the thread after the first user message while still Untitled. Truncation for display is **UI-only** (ellipsis + full title on hover).

**Book system prompt** (`book.json → systemPrompt`): prepended to every AI call for that book (chats, jobs, enrichment) — not used for the title-naming one-shot.

## Context assembly & placeholders (who calls what)

There is no separate “context service.” Two pieces do the work:

| Piece | Role |
|---|---|
| **ContextAssembler** | Translator only. Takes a saved conversation (or a one-shot prompt) and builds the LangChain message list the model sees: system framing + book `systemPrompt` + optional **CURRENT SCENE** block + each stored message as user/assistant/system. It does **not** talk to the network, open the editor URL, or invent which scene is “current.” Callers pass that in. |
| **PlaceholderRegistry** | Dictionary of known `@tokens` plus `resolve(prompt, mgr, scene_id, selection_text)`. Replaces tokens with prose/metadata from disk for that **explicit** `scene_id`. It never infers “most recently updated” or “which tab is open.” |

**Scene identity rule:** the target scene always comes from the editor URL → conversation `parentId`. If that id is not passed into `resolve` or into the assembler’s `CURRENT SCENE` block, the model only has tools and may guess wrong.

### Who calls ContextAssembler

| Caller | When |
|---|---|
| **ConversationService** | Any message send — chat, AI-Job run, or bookkeeping run (all are conversations) |
| **GitService** | One-shot commit-message prompts (no conversation thread) |

Those callers hand the message list to **AIOrchestrator**, which invokes the model (with tools when bound).

### Who calls PlaceholderRegistry.resolve

| Caller | When |
|---|---|
| **AiJobService** | Expands the AI-Job definition prompt against the scene when preparing the run; expanded text is stored as the **system**-authored first message of the conversation |
| **ContextAssembler** | When building model payloads: expands `@tokens` inside *user* messages for the model only (stored transcript still shows the literal `@current_scene`) |
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

1. Editor runs a job with `sceneId` from the URL → `POST /ai-jobs/run`.
2. **AiJobService** calls `PlaceholderRegistry.resolve(job_prompt, scene_id=that id)` (and optional selection text) and opens the conversation with the expanded text as its system-authored first message, at status `open`. **No model call yet.**
3. The author reviews the prompt in the modal and sends (composer prefilled `start`).
4. That send is an ordinary chat send: **ConversationService** → **ContextAssembler** (same `CURRENT SCENE` framing) → **AIOrchestrator** runs; the definition's `outputType` drives proposal parsing.

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
2. **AiJobService** resolves the definition's prompt against the scene and opens a conversation (kind `ai-job`, parent scene, title = definition name, model = job default) with that prompt as its system-authored first message, at status `open`. **201** `{ conversationId }`. The client opens the modal on it — the prompt is right there to review, the composer prefilled `start`. Nothing has run.
3. The author sends. That's an ordinary message send (ConversationService → ContextAssembler with book systemPrompt + CURRENT SCENE → AIOrchestrator, **with tools**, streaming into the conversation). Status goes `running` → `done`.
4. Output parsing by the definition's `outputType` (looked up via `conv.aiJobId`):
   - `chat` — reply is plain conversation.
   - `edit-proposals` — model instructed (via injected format instructions) to emit edits as structured find/replace items; parsed into `edit` proposals on the message.
   - `metadata-proposals` — same pattern for metadata-update proposals.
5. Author continues the conversation freely; accepts/rejects proposals whenever. Status rides the book SSE channel (`conversation` events) and shows in the AI Jobs accordion pane.

## Enrichment (bookkeeping)

Maintains `scene.summary` and `scene.characters` (each `{ characterId, involvement }`). A bookkeeping run is a **conversation** (kind `bookkeeping`); the model does the work by calling **execute tools**, and asks the author in-thread when it can't.

**Trigger — leave-scene + on-demand:** content saves never schedule enrichment. When the author **leaves** the scene editor (and prose changed this visit), the client calls `POST /scenes/{id}/enrich/auto`; EnrichmentService opens a bookkeeping conversation for each half the book's toggles enable (`summaryOnSave`, `charactersOnSave`) and that has a resolvable model (both off / no models → nothing). On-demand: `POST /scenes/{id}/enrich` (Scene Modal ↻ AI-redo) ignores toggles.

**Two independent conversations, not one call:** summary and characters are separate runs against separately-configured models (`ai.sceneSummaryModelId` / `ai.characterParsingModelId`), so scope `both` opens **two** conversations ("Scene summarization", "Character enrichment"). Each is created at status `queued`; the [conversation worker](#worker) drains them.

Each run's prompt carries the scene prose. The character prompt also carries the cast directory (names/aliases) **and the scene's current `characters` rows** (ids + involvement), so a redo preserves/refines author-edited involvement rather than rebuilding from prose alone.

- **Clear cases:** the model calls `set_scene_summary` or `set_scene_characters` — execute tools that write through `SceneService.update_scene` (validating character ids, preserving `contentHash`/`wordCount`, emitting `scene-updated`). The run ends `done`.
- **Unclear cases:** unmatched names, ambiguous matches, or "is this too minor?" → the prompt tells the model **not** to call the tool but to ask the author, in plain language, in that same conversation. A run that calls no tool ends `waiting` (the "needs you" state). The author answers in-thread; the model responds and can then call the tool. There is no separate escalation service and no `propose_character_create` step in this path — the model asks, the author tells it, it records. (Adding a genuinely new character is still the author's job on the Character Sheet.)

**Toggle semantics:** toggle ON = AI owns the field and may overwrite on leave-scene for *clear* updates. Want a hand-written summary? Flip it off. No freeze flags.

## AI tool-calling surface

Bound via LangChain tool-calling on every assistant invocation.

**Read tools — execute freely (read-only):** `get_scene(id)` (prose + metadata), `list_scenes()` (titles, seq, placement), `get_scene_summaries()`, `get_character_sheet(id|all)`, `search_text(query)` (across active scene files), `get_plotlines()`, `get_story_summary()`, `get_todos(sceneId?)`. Bound on every run.

**Propose tools — never mutate; emit proposal objects into the message:** `propose_edit(sceneId, find, replace, rationale)`, `propose_metadata_update(targetType, targetId, field, newValue)`, `propose_todo(parentType, parentId, action)`, `propose_character_create(name, aliases?, …, sceneId?)` — fill in whatever the prose/conversation makes clear, not just the name — `propose_character_relationship(characterAId, characterBId, category, aToB, bToA, description?, rationale?)`. Bound on every run. On accept, character-create dedupes case-insensitively against existing names/aliases and, if `sceneId` was passed, tags the character onto that scene. The only endpoints acting on these are `POST /proposals/{id}/accept|reject` — author-triggered.

**Execute tools — write bookkeeping directly:** `set_scene_summary(summary)`, `set_scene_characters([{characterId, involvement}])`. Bound **only** on bookkeeping conversations, and bound to that conversation's scene. They write through `SceneService.update_scene`, not the manager. This is not a hole in the prose hard rule: prose (`.md`) is still untouchable; summary and character involvement are bookkeeping the author already consents to via the toggles — the execute tool is just a cleaner mechanism than parsing JSON out of a reply.

## Streaming & events

- **Message streaming:** `POST /conversations/{id}/messages` responds as an SSE stream: `token` events, then `message` (final persisted message incl. proposals).
- **Book channel:** `GET /books/{id}/events` — `conversation`, `scene-updated`, `todos-created`, `git-status`, `compile-done`. One connection per open book; drives badges, accordion statuses, live metadata patches.

## Worker

`ConversationWorker` — single asyncio task; per-book FIFO, concurrency 1 per book (≤2 global). Drains conversations at status `queued` (automatic bookkeeping runs; explicit AI-Job runs never queue — they run when the author sends). Runs each via `ConversationService.send_message` with no body. Terminal status `failed` (error appended as a visible system message) or `waiting` (AI asked a question); no automatic retry.
