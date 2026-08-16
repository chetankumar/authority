# features/conversation — Conversation Modal (component, not a route)

The universal thread: notes, chats, AI-Job runs, and bookkeeping runs are all this one surface. 800px × 80vh. `sceneId` is optional — every scene-keyed branch is guarded on it — so this same component serves the book-level chat on the [Resources page](../resources/CLAUDE.md) with no changes beyond mounting it without a `sceneId`. Parent: [features](../CLAUDE.md). Spec: [doc 06 §10](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [conversations](../../../backend/app/api/conversations/CLAUDE.md).

## Book-scoped stream store

Message SSE (`POST /conversations/{id}/messages`) is **not** owned by the modal and is **not** the book EventSource (`GET /books/{id}/events`). [`ConversationSessionProvider`](ConversationSessionContext.tsx) lives in [`App.tsx`](../../App.tsx) for the open book (same lifetime as `useBookEvents`):

- Sessions list + `focusedId` (at most one expanded modal).
- Per-id stream buffer (`busy`, tokens, phase, tool log, error). `send()` is the only caller of `sendMessageStream`.
- [`ConversationHost`](ConversationHost.tsx) renders stacked dock chips and the focused modal above the route outlet, so scene/page navigation does not abort streams.
- Editor / Resources / Tasks call `open(id)` instead of holding a local `conversationId`.
- Close of one session aborts only that POST. Leaving the book remounts the provider and aborts leftovers.

The modal is a view: it reads live tokens from the store and must not abort on unmount (minimize, switch session, change scene).

## Layout

- **Header:** editable title (blur → `PATCH /conversations/{id}`) · relative timestamp · model select + **AI participant switch** · Minimize (–) · ×.
- **Body:** message list. User messages right-aligned wash; context excerpts render as bordered quote blocks labeled "From {scene title}". Assistant messages left, model label above, streaming text with blinking cursor. Only the **first** system message of a run (the resolved prompt) collapses to "Job prompt · show"; other system messages — an escalation question, an error — render plainly, since the author needs to read them.
- **Proposal cards** in assistant messages (`--attn-wash`): edit = side-by-side find (strikethrough)/replace + rationale; metadata = "Mood: ~~tense~~ → **elegiac**"; todo = "☐ {action}"; resource-create = filename + a scrollable preview of the full file content + rationale — nothing is written until Accept. [Reject] [Accept] per card; footer [Accept all ({n})] when >1 pending. Applied → `--ok-wash` ✓; rejected → faded; not-found → amber "This text is no longer in the scene." Accepting invalidates `['resources', bookId]` alongside the scene keys, since any proposal type might be a resource-create.
- **Composer:** textarea (Enter sends, Shift+Enter newline) · [Send].
- **Jump to latest:** message list never auto-follows stream/token updates. A floating ↓ (bottom-right of the list) appears when content sits below the fold; click scrolls the list container to the latest. Send scrolls once so the new turn is in view, then the viewport stays put.
- **Stream activity (ephemeral):** while the AI is generating, SSE may emit waiting heartbeats, a thinking line, and an append-only tool log (tool name + truncated args). These live only in the stream UI — they are not saved into the conversation.
- **Dock chips (minimized):** fixed bottom-right, stacked; title + live status. Click restores that session. Opening another chat adds a session and focuses it — the minimized stream keeps running.

## Controls

- **AI participant switch** → `PATCH {aiParticipant.enabled}`; on-with-no-model → model select pulses + inline 422 "Pick a model to bring the AI in".
- Model select → `PATCH {aiParticipant.modelId}` (defaults: the run's model on AI-Job/bookkeeping runs, else last-used).
- Send → `POST /messages` via the session store: switch off = plain append (note path); switch on = SSE stream (tokens live → final `message` with proposal cards; `error` → inline danger row). While generating, ephemeral SSE `status` events may show waiting heartbeats, thinking, and a live tool log — not persisted in the thread. Scrolls the list to the bottom once on send; does not keep following.
- **↓ Scroll to latest** → floating over the message list when content sits below the fold; scrolls the list container only.
- Accept/Reject/Accept-all → `POST /proposals/{id}/accept|reject`. Each resolution appends a system message to the thread (e.g. "Author accepted edit proposal …"). No auto-send after Accept — the author continues the thread manually when ready. Edit-proposal Accept flushes the open editor only when that editor is this conversation's scene.
- **Minimize** (–) · Esc/scrim while busy → hide the modal shell; the store keeps the message SSE. Dock chip shows title + status.
- **× Close** while busy → confirm (“Stop listening…”) then `close(id)` (aborts that POST only). Idle × / Esc / scrim → close immediately. Pending proposals survive and badge the accordion.
