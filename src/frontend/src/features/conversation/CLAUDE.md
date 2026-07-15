# features/conversation — Conversation Modal (component, not a route)

The universal thread: note-stacking, chat, and AI-job runs are all this one surface. 800px × 80vh. Parent: [features](../CLAUDE.md). Spec: [doc 06 §10](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [conversations](../../../backend/app/api/conversations/CLAUDE.md).

## Layout

- **Header:** editable title (blur → `PATCH /conversations/{id}`) · relative timestamp · model select + **AI participant switch** · ×.
- **Body:** message list. User messages right-aligned wash; context excerpts render as bordered quote blocks labeled "From {scene title}". Assistant messages left, model label above, streaming text with blinking cursor. System messages (job prompts) collapsed to "Job prompt · show".
- **Proposal cards** in assistant messages (`--attn-wash`): edit = side-by-side find (strikethrough)/replace + rationale; metadata = "Mood: ~~tense~~ → **elegiac**"; todo = "☐ {action}". [Reject] [Accept] per card; footer [Accept all ({n})] when >1 pending. Applied → `--ok-wash` ✓; rejected → faded; not-found → amber "This text is no longer in the scene."
- **Composer:** textarea (Enter sends, Shift+Enter newline) · [Send].

## Controls

- **AI participant switch** → `PATCH {aiParticipant.enabled}`; on-with-no-model → model select pulses + inline 422 "Pick a model to bring the AI in".
- Model select → `PATCH {aiParticipant.modelId}` (defaults: job's model on runs, else last-used).
- Send → `POST /messages`: switch off = plain append (note path); switch on = SSE stream (tokens live → final `message` with proposal cards; `error` → inline danger row).
- Accept/Reject/Accept-all → `POST /proposals/{id}/accept|reject` (Accept-all loops sequentially, halting on not-found).
- Close/click-out just closes — every message persists on send; pending proposals survive and badge the accordion.
