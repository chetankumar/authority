# api/conversations — conversations, messages, AI-Job runs

The universal thread primitive: notes, chats, and AI-job runs are all conversations. Messages may carry proposals. AI participation is toggleable per conversation. Handled by `ConversationService` (+ `AIOrchestrator`/`ModelFactory`, `JobService`). Spec: [doc 04 §9](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/conversations` | `{ kind, parentType, parentId, aiParticipant?, title? }`. Default aiParticipant `{enabled:false, modelId:null}` (note-stacking). Creates `cnv-{hex}.json`, title from body or `"Untitled"`. 201 |
| GET | `/api/books/{b}/conversations/{id}` | Full Conversation with messages + proposals (per-file load) |
| PATCH | `/api/books/{b}/conversations/{id}` | `{ title?, status?, aiParticipant? }` — the mid-thread AI toggle + model switch. Enabling with no modelId ever set → 422 `model-required` |
| DELETE | `/api/books/{b}/conversations/{id}` | Hard delete; clears matching jobs' `conversationId`. 204 |
| POST | `/api/books/{b}/conversations/{id}/messages` | **SSE** `{ content (req), context? }`. See flow below |
| POST | `/api/books/{b}/ai-jobs/run` | `{ aiJobId, sceneId, scope, selectionText? }`. Creates ai-job conversation + queued job. 202 `{ jobId, conversationId }` |

## Message send flow (§9.3)

1. Append user Message (excerpts stored verbatim). Persist + index.
2. If title is still `"Untitled"`: utility model with a dedicated naming prompt (ask for 3–5 words; not chat framing). Store the reply as returned (trim only — no sanitizer). Emit SSE `title`. Fallback if no utility model / failure: first ~5 words of the user message.
3. Emit SSE `message` for the user turn. `aiParticipant.enabled == false` → `done` (pure note).
4. `enabled == true` → resolve ModelConfig (422 if unresolvable). Build LangChain call: system = book systemPrompt + assistant framing + CURRENT SCENE + tool schemas; history = messages (`@placeholders` resolved for the model); bind **read + propose tools**.
5. SSE: `token` events stream; tools execute server-side mid-stream. On completion persist assistant Message + final `message` event, then `done`.
6. Failure mid-stream → `error` event; user message stays; no assistant message written.
- Concurrent sends to one conversation → 409 `generation-in-progress`.

## AI-Job run (§9.4)

Creates conversation (kind `ai-job`, parent scene, title = **job definition name**, aiParticipant enabled with job default model, aiJobId + name snapshot) and a queued Job. The [worker](../../worker/CLAUDE.md) resolves placeholders, appends format instructions per outputType, posts a system-authored first message, streams the model, parses fenced JSON into proposals. Follow-ups are plain §9.3 sends.

## Persistence

One file per conversation `db/conversations/cnv-*.json`; `index.json` is derived (rewritten on any change; rebuildable by folder scan).
