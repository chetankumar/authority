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

**Utility model** (`app.json → ai.utilityModelId`): used for system tasks — enrichment, commit-message suggestion. If unset, those features skip gracefully with a visible notice.

**Book system prompt** (`book.json → systemPrompt`): prepended to every AI call for that book (chats, jobs, enrichment).

## Placeholder registry

Server-defined; exposed via `GET /api/settings/placeholders`; drives the `@` autocomplete in the AI-Job prompt editor and save-time validation. Initial set:

| Placeholder | Resolves to |
|---|---|
| `@current_scene` | Full prose of the target scene |
| `@selection` | The selected text (empty if none) |
| `@selection_or_scene` | Selection if present, else full scene |
| `@scene_metadata` | Title, description, location, dateTime, mood, arc, summary of the target scene |
| `@scene_characters` | Character sheets of characters tagged in the scene |
| `@character_sheet` | All character sheets in the book |
| `@previous_scenes_summary` | Hard prev-chain walked back to Start, emitted in story order as `Title — summary` lines (summaries only, never prose; missing summary → `(no summary)`); archived and soft-only scenes excluded |
| `@all_scene_summaries` | Every active scene's title + summary in seq order |
| `@story_summary` | book.json storySummary |
| `@plotlines` | Plotline titles + descriptions, this scene's links flagged |

Resolution is server-side at run time. Unknown tokens are left literal but flagged at definition save.

## AI-Jobs: end-to-end run

1. Author picks a job from the editor dropdown (optionally with a selection active) → `POST /ai-jobs/run`.
2. Server creates a conversation (kind `ai-job`, parent scene, title = job name + time, model = job default) and a queued job record; client opens the conversation modal, which subscribes to the stream.
3. Worker: resolve placeholders against the scene → prepend book systemPrompt → invoke model **with tools** → stream tokens into the conversation.
4. Output parsing by `outputType`:
   - `chat` — reply is plain conversation.
   - `edit-proposals` — model instructed (via injected format instructions) to emit edits as structured find/replace items; parsed into `edit` proposals on the message.
   - `metadata-proposals` — same pattern for metadata-update proposals.
5. Author continues the conversation freely; accepts/rejects proposals whenever. Job status (`queued/running/done/failed`) rides the book SSE channel and shows in the AI Jobs accordion pane.

## AI tool-calling surface

Bound via LangChain tool-calling on every assistant invocation (chats and jobs).

**Read tools — execute freely:** `get_scene(id)` (prose + metadata), `list_scenes()` (titles, seq, placement), `get_scene_summaries()`, `get_character_sheet(id|all)`, `search_text(query)` (across active scene files), `get_plotlines()`, `get_story_summary()`, `get_todos(sceneId?)`.

**Write tools — never mutate; emit proposal objects into the message:** `propose_edit(sceneId, find, replace, rationale)`, `propose_metadata_update(targetType, targetId, field, newValue)`, `propose_todo(parentType, parentId, action)`.

The only mutation endpoints acting on AI output are `POST /proposals/{id}/accept|reject` — both author-triggered. This is how the hard rule is enforced structurally, not by prompt.

## Enrichment (system bookkeeping)

Maintains `scene.summary` and `scene.characterIds`.

**Trigger — settle-then-run:** every content save with a changed hash (re)sets a per-scene 60s settle timer. Timer fires → queue one `system` job scoped by the book's toggles (`summaryOnSave`, `charactersOnSave`; both off → nothing queued). Saves while queued replace the queued job (never two per scene); navigation away settles immediately. On-demand: `POST /scenes/{id}/enrich` runs regardless of toggles.

**Execution:** utility model; input = scene prose + character directory (names + aliases). Summary scope: overwrite `scene.summary`. Characters scope: set `characterIds` to matched *existing* characters only — **never creates character records**; unmatched names returned in `result.unrecognizedNames`, surfaced softly in the AI Jobs pane ("Unrecognized: Marlow — add to characters?"). Field changes emit `scene-updated` SSE so open views patch live.

**Toggle semantics:** toggle ON = AI owns the field and always wins on save. Want a hand-written summary? Flip it off. No freeze flags.

## Streaming & events

- **Chat/job streaming:** `POST /conversations/{id}/messages` responds as an SSE stream: `token` events, then `message` (final persisted message incl. proposals).
- **Book channel:** `GET /books/{id}/events` — `job`, `scene-updated`, `todos-created`, `git-status`, `compile-done`. One connection per open book; drives badges, accordion statuses, live metadata patches.

## Worker

Single asyncio task; per-book FIFO, concurrency 1 per book (≤2 global). Failures → status `failed` with error string; visible in the AI Jobs pane; no automatic retry (author re-runs).
