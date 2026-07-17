# api/conversations — conversations, messages, AI-Job runs

The universal — and only — run entity: notes, chats, AI-Job runs, and bookkeeping runs are all conversations. Messages may carry proposals. AI participation is toggleable per conversation. `status` carries the run lifecycle (`open`→`queued`→`running`→`waiting`/`done`/`failed`). Handled by `ConversationService` (+ `AIOrchestrator`/`ModelFactory`); AI-Job runs are prepared by `AiJobService`. Spec: [doc 04 §9](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/conversations` | Book-parented threads only (`parentType: "book"`) — the Resources page's chat list. Scene-parented threads still list from the scenes router below |
| POST | `/api/books/{b}/conversations` | `{ kind, parentType, parentId, aiParticipant?, title? }`. Default aiParticipant `{enabled:false, modelId:null}` (note-stacking). Creates `cnv-{hex}.json`, title from body or `"Untitled"`. `parentType: "book"` works today with no special-casing — the context assembler already omits CURRENT SCENE when there's no scene. 201 |
| GET | `/api/books/{b}/conversations/{id}` | Full Conversation with messages + proposals (per-file load) |
| PATCH | `/api/books/{b}/conversations/{id}` | `{ title?, status?, aiParticipant? }` — the mid-thread AI toggle + model switch. Enabling with no modelId ever set → 422 `model-required` |
| DELETE | `/api/books/{b}/conversations/{id}` | Hard delete; emits `conversation {status:"deleted"}`. 204 |
| POST | `/api/books/{b}/conversations/{id}/messages` | **SSE** `{ content (req), context? }`. See flow below |
| POST | `/api/books/{b}/ai-jobs/run` | `{ aiJobId, sceneId, scope, selectionText? }`. `AiJobService` resolves the prompt and opens an `ai-job` conversation with it inside, at `open`. **No model call** — nothing runs until the author sends. 201 `{ conversationId }` |

## Message send flow (§9.3)

1. Append user Message (excerpts stored verbatim). Persist + index.
2. If title is still `"Untitled"`: utility model with a dedicated naming prompt (ask for 3–5 words; not chat framing). Store the reply as returned (trim only — no sanitizer). Emit SSE `title`. Fallback if no utility model / failure: first ~5 words of the user message.
3. Emit SSE `message` for the user turn. `aiParticipant.enabled == false` → `done` (pure note).
4. `enabled == true` → resolve ModelConfig (422 if unresolvable). Build LangChain call: system = book systemPrompt + assistant framing + CURRENT SCENE + tool schemas; history = messages (`@placeholders` resolved for the model); bind **read + propose tools**.
5. SSE: `token` events stream; tools execute server-side mid-stream (read + propose always; **execute** tools too when the conversation is `bookkeeping`-kind, bound to its scene). On completion persist assistant Message + final `message` event, then `done`.
6. Failure mid-stream → `error` event; user message stays; no assistant message written.
- Run kinds (`ai-job`/`bookkeeping`) also transition `status`: `running` on send, then `done`, or `failed` (with the error appended as a system message so it's visible in-thread), or — a bookkeeping reply with no tool call — `waiting` (the AI asked the author something).
- `body` may be omitted: generate against the thread as it stands, no new user message. That's how the worker triggers a `queued` run whose prompt is already inside.
- Concurrent sends to one conversation → 409 `generation-in-progress`.

## AI-Job run (§9.4)

`POST /ai-jobs/run` → `AiJobService.prepare`: look up the `AIJobDefinition`, resolve its `@placeholders` against the scene, append format instructions per `outputType`, and open a conversation (kind `ai-job`, parent scene, title = **definition name**, AI enabled with the definition's default model, `aiJobId` + name snapshot) with the resolved prompt as its first (system-authored) message, at status `open`. Nothing runs. The author reviews the prompt in the modal and sends — that send is an ordinary §9.3 message that runs the model; the definition's `outputType` (looked up via `conv.aiJobId`) drives fenced-JSON→proposal parsing. Follow-ups are plain §9.3 sends.

## Persistence

One file per conversation `db/conversations/cnv-*.json`; `index.json` is derived (rewritten on any change; rebuildable by folder scan).
