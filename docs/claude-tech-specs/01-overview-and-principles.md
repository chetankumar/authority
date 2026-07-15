# 01 — Overview & Principles

## Vision

A zen writing environment wrapped in a book-management system. The author writes scenes in a beautiful markdown editor; around it, Authority tracks structure (parts, chapters, scene sequence), metadata (characters, plotlines, summaries), tasks, notes-as-conversations, and AI assistance. The AI does everything *except* write the book.

## Application name

**Authority.** Top bar shows logo + name; greets the author by configured name ("Welcome, Chetan").

## Hard rules

1. **Prose is sacred.** No AI code path may write to a scene `.md` file. The only mutation paths for prose are: (a) the author typing in the editor (autosave), (b) the author clicking Apply on an edit proposal — an author action executed by the system.
2. **Author approval gates AI writes** except where the author has granted standing consent via the Bookkeeping toggles (see write-permission model).
3. **Single writer.** Only the Python API touches disk. The frontend never does.
4. **Portability.** A book folder can be zipped, cloned, or moved; dropped into any books-home it appears on the shelf fully functional.

## The write-permission model (authoritative)

| What | Who writes | Gate |
|---|---|---|
| Scene prose (`scenes/*.md`) | Author only | AI may only propose exact-match find/replace edits; author applies each or all. HARD RULE. |
| Scene summary + scene↔character refs, after save | System (enrichment job) | Bookkeeping toggles (book-level). Toggle ON = standing consent, no per-run confirmation. AI-redo buttons in the Scene Modal invoke the same job on demand, toggle state irrelevant. |
| All other AI-initiated metadata writes (mood, arc, location, dateTime, summary-via-chat, character links via chat, relationships, plotline links) | AI proposes → author confirms | Per-change proposal cards in the conversation (Accept / Reject / Accept all). |
| Todos created by AI | AI proposes → author confirms | Same proposal gate. |
| Todos created by the dependency system | System, automatic | No gate — a mechanical consequence of a content change; the todo is itself only a prompt to the author. |
| Everything the author does directly in the UI | Author | No gate. |

## Core domain concepts

- **Scene** — the unit of the novel. A markdown file (prose) + a metadata record. Required at creation: title, description. Status: `active` or `archived` (archived = out of the book: excluded from graph default view, compilation, completeness, and placeholder context walks; file/conversations/todos preserved).
- **Hard chain** — `previousSceneId`/`nextSceneId` links. Two virtual sentinel scenes exist in every book: **Start** (`scn-START`) and **The End** (`scn-END`). A complete book is a single unbroken chain Start → … → The End covering all active scenes.
- **Soft relationships** — *definitely before / definitely after / around* another scene. Planning scaffolding; rendered as dotted arrows; checked against the chain at compile time.
- **Chapter / Part** — structural containers. Chapter belongs to a part; both are ordered linked lists. A scene belongs to a chapter XOR directly to a part (mutually exclusive); for compilation, chapter assignment is mandatory.
- **Dependency** — "Scene 10 depends on Scene 2 because {reason}". When the depended-on scene's content hash changes, a todo is auto-created on each dependent scene.
- **Conversation** — the universal primitive for notes, chats, and AI jobs. A titled message thread attached to a scene/chapter/part/book. AI participation is toggleable per conversation at any time; each assistant message records which model produced it. Messages may carry **proposals**.
- **AI-Job** — a reusable, author-defined prompt template (with `@placeholders`), default model, and output type. Running one creates a conversation + a background job.
- **Enrichment** — the system job that maintains scene summary and scene↔character mapping (settle-then-run after saves; on-demand via AI-redo).
- **Compilation** — a gated build: completeness check (errors block, warnings inform), then `compiled-book/` is wiped and regenerated as part folders containing chapter markdown files.

## Tech stack (locked)

**Backend:** Python 3.11+, FastAPI + Uvicorn (single worker, pinned), GitPython (requires git installed on the machine), LangChain (`langchain-core`, `langchain-anthropic`, `langchain-openai`, `langchain-ollama`), `python-multipart`, `filelock` (single-instance lock). Serves the built SPA statically. No ORM, no database engine — a per-book in-memory data manager over JSON files (doc 03, Data Safety).

**Frontend:** React + TypeScript + Vite, TipTap (`@tiptap/react` + `tiptap-markdown`) for the editor, D3 for the scene graph, **AG Grid Community** (MIT, free — no license key) for tables, TanStack Query for server state, Tailwind CSS.

**Persistence:** JSON files only. Atomic writes. In-memory per-book data manager, write-through.

**Streaming/live updates:** Server-Sent Events (SSE) — one book-level event channel + per-message AI streaming.

**Version control:** real git repo per book via GitPython (uses the system git and its credentials).
