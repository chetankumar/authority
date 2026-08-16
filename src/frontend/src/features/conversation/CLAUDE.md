# features/conversation — Conversation Modal (component, not a route)

The universal thread: notes, chats, AI-Job runs, and bookkeeping runs are all this one surface. 800px × 80vh. `sceneId` is optional — every scene-keyed branch is guarded on it — so this same component serves the book-level chat on the [Resources page](../resources/CLAUDE.md) with no changes beyond mounting it without a `sceneId`. Parent: [features](../CLAUDE.md). Spec: [doc 06 §10](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [conversations](../../../backend/app/api/conversations/CLAUDE.md).

## Why chats live in App, not on the editor page

The conversation window is only a view. The network request that streams the AI's reply is held by [`ConversationSessionProvider`](ConversationSessionContext.tsx) in [`App.tsx`](../../App.tsx), for as long as this book is open.

That is what lets you:

- Minimize a running chat and keep writing
- Start a second chat without killing the first
- Leave the scene (or open Tasks / Resources) and still see tokens arrive on a corner chip

Closing **one** chat (×, confirmed while it is generating) stops **that** reply only. Leaving the book, or refreshing the tab, stops all of them.

Book-wide events (git badge, Notes/Jobs list status) stay on a different connection — [`useBookEvents`](../../events/useBookEvents.ts). Reply tokens never go there.

[`ConversationHost`](ConversationHost.tsx) draws the UI that has to outlive any one page: at most one expanded modal, plus a stacked chip per other open chat. Editor, Resources, and Tasks just ask the provider to open a conversation; they do not mount the modal themselves.

## Layout

- **Header:** editable title (blur → `PATCH /conversations/{id}`) · relative timestamp · model select + **AI participant switch** · Minimize (–) · ×.
- **Body:** message list. User messages right-aligned wash; context excerpts render as bordered quote blocks labeled "From {scene title}". Assistant messages left, model label above, streaming text with blinking cursor. Only the **first** system message of a run (the resolved prompt) collapses to "Job prompt · show"; other system messages — an escalation question, an error — render plainly, since the author needs to read them.
- **Proposal cards** in assistant messages (`--attn-wash`): edit = side-by-side find (strikethrough)/replace + rationale; metadata = "Mood: ~~tense~~ → **elegiac**"; todo = "☐ {action}"; resource-create = filename + a scrollable preview of the full file content + rationale — nothing is written until Accept. [Reject] [Accept] per card; footer [Accept all ({n})] when >1 pending. Applied → `--ok-wash` ✓; rejected → faded; not-found → amber "This text is no longer in the scene." Accepting invalidates `['resources', bookId]` alongside the scene keys, since any proposal type might be a resource-create.
- **Composer:** textarea (Enter sends, Shift+Enter newline) · [Send].
- **Jump to latest:** message list never auto-follows stream/token updates. A floating ↓ (bottom-right of the list) appears when content sits below the fold; click scrolls the list container to the latest. Send scrolls once so the new turn is in view, then the viewport stays put.
- **Stream activity (ephemeral):** while the AI is generating, SSE may emit waiting heartbeats, a thinking line, and an append-only tool log (tool name + truncated args). These live only in the stream UI — they are not saved into the conversation.
- **Dock chips:** when a chat is minimized (or another chat is in front), a chip sits bottom-right with title and live status. Several chips stack. Click one to bring that chat back. Starting Chat from the editor adds a chip rather than replacing the running one.

## Controls

- **AI participant switch** → `PATCH {aiParticipant.enabled}`; on-with-no-model → model select pulses + inline 422 "Pick a model to bring the AI in".
- Model select → `PATCH {aiParticipant.modelId}` (defaults: the run's model on AI-Job/bookkeeping runs, else last-used).
- Send → `POST /messages` through the App-level provider: switch off = plain append (note path). Switch on = live stream (tokens → final message with proposal cards; `error` → inline danger row). Waiting / thinking / tool rows are ephemeral. Scrolls the list to the bottom once on send; does not keep following.
- **↓ Scroll to latest** → floating over the message list when content sits below the fold; scrolls the list container only.
- Accept/Reject/Accept-all → `POST /proposals/{id}/accept|reject`. Each resolution appends a system message to the thread (e.g. "Author accepted edit proposal …"). No auto-send after Accept — the author continues the thread manually when ready. Accepting an edit proposal first saves the open editor, but only if that editor is this conversation's scene.
- **Minimize** (–) · Esc/scrim while the AI is generating → hide the window; the reply keeps running and a chip stays in the corner.
- **× Close** while generating → confirm (“Stop listening…”) then stop that reply. Idle × / Esc / scrim → close immediately. Pending proposals survive and badge the accordion.
