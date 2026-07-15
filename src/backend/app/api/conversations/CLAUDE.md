# api/conversations — conversations, messages, AI-Job runs

The universal thread primitive: notes, chats, and AI-job runs are all conversations. Messages may carry proposals. AI participation is toggleable per conversation. Handled by `ConversationService` (+ `AIService`/`ModelFactory`, `JobService`). Spec: [doc 04 §9](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/conversations` | `{ kind, parentType, parentId, aiParticipant? }`. Default aiParticipant `{enabled:false, modelId:null}` (note-stacking). Creates `cnv-{hex}.json`, title "Untitled". 201 |
| GET | `/api/books/{b}/conversations/{id}` | Full Conversation with messages + proposals (per-file load) |
| PATCH | `/api/books/{b}/conversations/{id}` | `{ title?, status?, aiParticipant? }` — the mid-thread AI toggle + model switch. Enabling with no modelId ever set → 422 `model-required` |
| POST | `/api/books/{b}/conversations/{id}/messages` | **SSE** `{ content (req), context? }`. See flow below |
| POST | `/api/books/{b}/ai-jobs/run` | `{ aiJobId, sceneId, scope, selectionText? }`. Creates ai-job conversation + queued job. 202 `{ jobId, conversationId }` |

## Message send flow (§9.3)

1. Append user Message (excerpts stored verbatim; first user message sets title = first ~6 words). Persist + index.
2. `aiParticipant.enabled == false` → 200 JSON `{ message }` (pure note). Done.
3. `enabled == true` → resolve ModelConfig (422 if unresolvable). Build LangChain call: system = book systemPrompt + assistant framing + tool schemas; history = messages (context excerpts as quoted blocks); bind **read + propose tools**.
4. SSE: `token` events stream; tools execute server-side mid-stream (read tools answer from BookDataManager; propose tools accumulate Proposal objects). On completion persist assistant Message + final `message` event, then `done`.
5. Failure mid-stream → `error` event; user message stays; no assistant message written.
- Concurrent sends to one conversation → 409 `generation-in-progress`.

## AI-Job run (§9.4)

Creates conversation (kind `ai-job`, parent scene, title "{job.name} — HH:MM", aiParticipant enabled with job default model, aiJobId + name snapshot) and a queued Job. The [worker](../../worker/CLAUDE.md) resolves placeholders, appends format instructions per outputType, posts a system-authored first message, streams the model, parses fenced JSON into proposals. Follow-ups are plain §9.3 sends.

## Persistence

One file per conversation `db/conversations/cnv-*.json`; `index.json` is derived (rewritten on any change; rebuildable by folder scan).
