# features/editor — `/book/{id}/scene/{sid}` (Scene Editor)

The room where the book gets written — the design's center of gravity. Everything else in this layout exists to be ignorable. Parent: [features](../CLAUDE.md). Spec: [doc 06 §9](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Layout

Auto-collapsed left nav (icon rail) · center writing column · right pane (320px, toggleable). The sheet: `--surface` on `--paper`, Literata, **68ch** measure, generous top margin. Load: `GET /scenes/{id}` (metadata + content).

## Tool panel

- **AI-Jobs ▾** — menu from `GET /settings/ai-jobs`; pick → `POST /ai-jobs/run` with sceneId + scope (`selection` if a selection is active, else `full`) → Conversation Modal opens streaming.
- **Metadata** → Scene Modal. **Bookkeeping** → popover of leave-scene toggles → `PATCH /books/{id} {bookkeeping}` (footer "Applies to this whole book"). Manual ↻ AI-redo is on the Scene Modal Characters/Summary tabs. **Chat** → `POST /conversations {kind:"chat", parent:scene}` → Conversation Modal (active selection rides the first message as context). **◫** pane toggle (persisted in ui.json).

## Writing surface

TipTap + tiptap-markdown, contenteditable (Grammarly-compatible). Inline editable title → `PATCH {title}` (slug-renames the file). Autosave: 2s debounce + blur + route-leave → `PUT content`; Ctrl/Cmd+S immediate. On leave (if prose changed this visit) → `POST …/enrich/auto`. Save indicator: "Saving…" → "Saved · 2:41pm"; failure → persistent amber "Not saved — retrying". Live local word count.

## Prev / Next

Save current, then navigate + scroll to top; **Next with no neighbor** → Scene Modal (create) with Previous prefilled → navigate into the new scene on save; Prev with no neighbor → disabled ("This is the first scene").

## Right pane accordion

- **Notes** (`GET /scenes/{id}/conversations`, kinds note/chat) → Conversation Modal.
- **To-dos** (`GET`/`POST /scenes/{id}/todos`, persisted in this scene's own `scenes/{id}/todos.json` — doc 03 §Todos storage split, not the book-level [Tasks page](../tasks/CLAUDE.md)'s file): inline "Add a task for this scene…" field above the list; checkbox = done, 🗑 = delete (confirm), ✕ = closed (`PATCH`); dependency rows ⛓ + amber; 💬 opens the linked conversation, creating a `task-discussion` one on first use.
- **AI Jobs** (`GET /jobs?scene=`): name · status chip (live via SSE) · unrecognized-names note → its conversation.
- Amber count badges on headers = open/pending items.
