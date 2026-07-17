# features/conversation — Conversation Modal (component, not a route)

The universal thread: notes, chats, AI-Job runs, and bookkeeping runs are all this one surface. 800px × 80vh. `sceneId` is optional — every scene-keyed branch is guarded on it — so this same component serves the book-level chat on the [Resources page](../resources/CLAUDE.md) with no changes beyond mounting it without a `sceneId`. Parent: [features](../CLAUDE.md). Spec: [doc 06 §10](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [conversations](../../../backend/app/api/conversations/CLAUDE.md).

## Layout

- **Header:** editable title (blur → `PATCH /conversations/{id}`) · relative timestamp · model select + **AI participant switch** · ×.
- **Body:** message list. User messages right-aligned wash; context excerpts render as bordered quote blocks labeled "From {scene title}". Assistant messages left, model label above, streaming text with blinking cursor. Only the **first** system message of a run (the resolved prompt) collapses to "Job prompt · show"; other system messages — an escalation question, an error — render plainly, since the author needs to read them.
- **Proposal cards** in assistant messages (`--attn-wash`): edit = side-by-side find (strikethrough)/replace + rationale; metadata = "Mood: ~~tense~~ → **elegiac**"; todo = "☐ {action}"; resource-create = filename + a scrollable preview of the full file content + rationale — nothing is written until Accept. [Reject] [Accept] per card; footer [Accept all ({n})] when >1 pending. Applied → `--ok-wash` ✓; rejected → faded; not-found → amber "This text is no longer in the scene." Accepting invalidates `['resources', bookId]` alongside the scene keys, since any proposal type might be a resource-create.
- **Composer:** textarea (Enter sends, Shift+Enter newline) · [Send].

## Controls

- **AI participant switch** → `PATCH {aiParticipant.enabled}`; on-with-no-model → model select pulses + inline 422 "Pick a model to bring the AI in".
- Model select → `PATCH {aiParticipant.modelId}` (defaults: the run's model on AI-Job/bookkeeping runs, else last-used).
- Send → `POST /messages`: switch off = plain append (note path); switch on = SSE stream (tokens live → final `message` with proposal cards; `error` → inline danger row).
- Accept/Reject/Accept-all → `POST /proposals/{id}/accept|reject` (Accept-all loops sequentially, halting on not-found).
- Close/click-out just closes — every message persists on send; pending proposals survive and badge the accordion.
