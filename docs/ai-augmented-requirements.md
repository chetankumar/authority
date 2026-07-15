# Book Studio — Requirements Document

**Version:** 1.0 (Draft for review)
**Status:** Consolidated from initial requirements + planning decisions
**Purpose:** This is the authoritative statement of *what* the application must do. Technical specifications (database design, API design, frontend design) derive from this document and will be produced separately.

---

## 1. Vision

A local, browser-based, AI-assisted novel-writing studio. At its heart is a simple, zen-like markdown editor that lets the author focus on the writing. Around the editor sits a management layer that organizes the book: scenes, structure, metadata, notes, tasks, and AI assistance.

**Guiding principles:**

- The author writes the book. The AI does everything *except* write the book.
- The AI never changes anything without explicit author approval. Every AI-suggested change is a proposal the author accepts or rejects (Claude Code style).
- Scenes are markdown files on disk. The author's prose is always plain, portable, and readable outside the app.
- Each book is a self-contained, portable folder and a git repository.
- Local only. Single user. No cloud, no accounts, no external services other than AI provider APIs.

---

## 2. Architecture Constraints

1. **Browser application.** The UI runs in a standard web browser (this also allows browser extensions such as Grammarly to work in the editor).
2. **Two separate projects:**
   - **API server** — Python. Owns all filesystem access, all data, git operations, AI provider calls, and the background job system. Libraries are allowed.
   - **Frontend** — Node.js based, kept simple. Talks only to the API. Never touches the filesystem directly.
3. **Deployment:** localhost only. No authentication in v1.
4. **Storage:** JSON files only. No database engines, no SQLite, no Redis, no external services. All writes must be atomic (write temp file, rename over original). The API server is the single writer.
5. **Asynchronous AI jobs:** the client submits a job; the API executes it in the background; the client is updated when the job completes (and receives streaming updates where applicable).

---

## 3. Data Layout & Identity

1. **App root** (configurable location) holds app-level data: settings, AI provider configurations, API keys, model list, reusable AI-Job definitions, and the bookshelf registry (list of books and their folder paths).
2. **Book folder** (any path on disk, chosen at book creation) holds everything about one book: book metadata, scene markdown files, the book's JSON database files, cover art, and compiled output. Book data is never stored at the app level — each book is independently portable.
3. **Scene files** live in a `scenes/` folder inside the book. Filename format: `{hash}-{slug}.md`.
4. **IDs:** every entity receives an auto-generated ID containing a 6-character hash (e.g., `scn-a3f9c2`). Scene filenames use the scene's hash so multiple scenes may share similar titles without conflict. The hash is permanent; the slug may change if the title changes.
5. **Separation of truth:** the markdown file is the single source of truth for scene prose; the JSON database is the single source of truth for all metadata and structure.

---

## 4. Novel Structure

### 4.1 Scene

The unit of the novel. Properties:

- Title *(required)* and Description *(required)*
- Location (in story), Date/Time (in story)
- Mood, Emotional Arc, Summary
- Characters appearing in the scene
- Previous Scene / Next Scene — **hard relationships**, optional. A scene may be "floating" (no fixed position) indefinitely.
- Chapter or Part assignment — optional, and **mutually exclusive**: a scene belongs to a chapter *or* directly to a part, never both (a chapter already belongs to a part).
- A content hash, maintained automatically, used for dependency change detection.

### 4.2 Soft relationships

In addition to the hard previous/next chain, a scene may be loosely positioned relative to other scenes:

- **Definitely before** another scene
- **Definitely after** another scene
- **Somewhere around** another scene

These are stored separately from the hard chain and rendered differently in the graph view (thin dotted lines vs. solid lines).

### 4.3 Chapter

Structural element containing one or more scenes. Has a title, an optional previous/next chapter, and belongs to a part. Chapters are compiled from scenes — see §9.

### 4.4 Part

Structural container. Has a title and optional previous/next part. Contains chapters, and may directly contain scenes and notes.

### 4.5 Dependencies

A scene may depend on events in another scene (e.g., a character does Y in Scene 10, which requires that he did X in Scene 2). A dependency records: the dependent scene, the scene depended upon, and the reason.

**Behavior:** when the content of a scene changes (detected via content hash on save), the system automatically creates a **task/todo on every scene that depends on it**, referencing the dependency reason. The author reviews the task: if the change affects the dependent scene, they fix it; otherwise they simply close the task. Dependencies themselves carry no status.

### 4.6 Plotlines

A plotline has a title and description, and is linked to the scenes that carry it.

---

## 5. Conversations — the universal primitive

Every note, comment, question, AI chat, and AI job is a **conversation**: a titled thread of messages attached to a parent (scene, chapter, part, or the book itself).

1. A conversation has a kind (note, chat, AI job, task discussion), a status (open/archived), and a message history.
2. **Toggleable AI participation.** A conversation can have AI as a participant or not, switchable at any time via a button. With AI removed, the author stacks notes/messages to themself. The author may add a model as participant to pull AI in, converse, then remove it and continue solo — all in the same thread. The model can be chosen per conversation, and each assistant message records which model produced it.
3. **Selection as context.** While writing, the author can select a line/paragraph and click chat: a conversation opens (or continues) with the selected text attached to the message as context. The excerpt is a snapshot captured at send time (inline positional markers are out of scope for v1 — see §12).
4. **Proposals.** AI messages may carry proposals — concrete suggested actions (text edits, metadata updates, summary updates, todo creation). Every proposal is pending until the author explicitly accepts or rejects it. Nothing is applied automatically.

---

## 6. Todos / Tasks

1. A todo has: parent (scene, chapter, part, or book), action text, and status (**open / done / closed** — *open question: is an "in-progress" state wanted?*).
2. Todos are created by: the author directly, the dependency system (§4.5), or an accepted AI proposal.
3. A todo may link to a conversation for extended discussion.

---

## 7. Metadata Manager

1. **Character sheets** — name, aliases, personality, history, notes. The character collection doubles as the master name list / "who's who" directory.
2. **Plotlines** — as in §4.6.
3. **Story summary and scene summaries.**
4. **Event list** — deferred to a later version (§12).

---

## 8. AI System

### 8.1 Providers & models

1. Support **any provider**: Anthropic, OpenAI, and any OpenAI-compatible endpoint — which includes local models via Ollama and LM Studio.
2. A Settings page manages providers, API keys, base URLs, and the list of available models. This configuration lives in the app-level root data, never inside a book folder (keys can never be committed/pushed with a book). API keys are stored in the app-level JSON; environment-variable references are supported as an alternative to plaintext keys.

### 8.2 AI-Jobs (reusable)

1. The author can define named, reusable AI-Jobs (e.g., "Check Grammar", "Editorial Review", "Custom Analysis") consisting of: name, custom prompt, default model, scope (full text or selection), and output type (chat reply, edit proposals, or metadata proposals).
2. AI-Jobs appear as a dropdown in the scene editor's top menu. Selecting one starts a job against the current scene (full text or current selection).
3. **Every AI-Job run is a conversation** — it opens as a chat using the job's default model, is tracked with a lifecycle (queued / running / done / failed), and remains accessible in the right-side panel afterward.

### 8.3 Built-in tool categories

The system must support, via AI-Jobs, at minimum:

1. Spell check & grammar — full text or selection
2. Custom edit job — instruction in, list of edits out; author applies edits one by one or apply-all
3. Editorial review — full text or selection
4. Custom analysis — full text or selection

### 8.4 Edit application

Edits are **exact-match find and replace** proposals: (find text, replacement text, rationale). If the exact text can no longer be located (author kept writing), that edit reports "could not locate" and is skipped rather than misapplied.

### 8.5 AI capabilities & boundaries

1. The AI has **read access** to book data via internal tools: scene content and summaries, character sheets, scene lists, text search across scenes, metadata.
2. The AI can propose writes: update scene metadata (e.g., characters appearing, summary), create todos, propose edits. **All writes are proposals requiring explicit author approval.**
3. The AI **never edits scene prose directly** and never writes to any file directly. The author is the only writer of the book.
4. A **book-level system prompt** (genre, style rules, voice notes) is prepended to every AI job for that book.

---

## 9. Chapter Compilation

1. The author manually assigns scenes to chapters.
2. Scene order within a chapter is determined by the hard previous/next chain.
3. Compilation generates markdown files into a `compiled-book/` folder inside the book, organized as part subfolders containing chapter files (e.g., `compiled-book/part-1/chapter-1.md`).
4. Compiled output is a regenerable artifact — never edited directly — and **is committed to git**.
5. Markdown is the only output format. No docx/epub/pdf export.

---

## 10. Git Integration

1. Every book folder is a git repository (initialized at book creation).
2. A git management UI provides: status view, stage/unstage individual files, commit with message, push/pull to a configured remote.
3. Everything in the book folder is tracked, including compiled output. Temporary files are gitignored.

---

## 11. User Interface

### 11.1 Home page — Bookshelf

1. Grid of books: title + cover art (if uploaded).
2. "Add new title": prompts for title and folder path; creates the book folder, data files, and git repository.
3. Clicking a book opens the Book Home.

### 11.2 Book Home

Left navigation with two primary views:

1. **Graph View** — scenes as nodes (D3.js), zoom/pan. Hard prev/next links drawn as solid lines; soft before/after/around links as thin dotted lines. Nodes show the title; hover reveals the full description. Clicking a scene opens the editor.
2. **Outline (Table) View** — scenes as rows in hard-sequence order, with title, description, and additional columns the author can add/remove from the scene property list. A button reveals all floating scenes (not yet firmly sequenced). Clicking a scene opens the editor.
3. In both views the author can **add a new scene**: title and description required; sequence placement optional (hard position, or just "definitely after / definitely before" if unknown); chapter/part optional; mood and emotional arc enterable at creation.

### 11.3 Scene Editor

The heart of the application — must be excellent.

1. **Center:** a beautiful, zen-like rich markdown editor. Distraction-free writing focus. Browser-extension friendly (Grammarly must work).
2. **Top panel** (above the editor toolbar):
   - **Relationships** — popup showing this scene's hard (previous/next) and soft (definitely after/before/around) relationships; author edits them here (relationship type → dropdown of scenes).
   - **Metadata** — popup for part/chapter assignment (both optional, mutually exclusive), characters, date/time, location, summary, mood, arc, emotional trajectory.
   - **Dependencies** — popup listing scenes this scene depends on and why; author can add dependencies manually.
   - **AI-Jobs dropdown** — the author's saved AI-Jobs (§8.2), runnable against full text or current selection.
3. **Right panel** — collapsed accordion:
   - **Notes/Comments** — conversations of kind note/chat attached to this scene.
   - **Tasks/Todos** — this scene's todos (including dependency-generated ones).
   - **Agent Jobs** — AI job conversations with live status.
4. **Chat from selection:** select text → click chat → conversation opens with the selection attached as context (§5.3).

### 11.4 Settings page

Providers, API keys, models, AI-Job definitions (§8), app preferences.

### 11.5 Metadata pages

Character directory (who's who), character sheet editor, plotline management, story summary.

### 11.6 Git page/panel

Per-book git management (§10).

---

## 12. Explicitly Out of Scope for v1

1. **Inline text markers** (todo/edit/comment markers anchored to positions in text). Deferred — positional anchoring is hard; selection-as-context (§5.3) covers the primary need for now.
2. **Event list** in the metadata manager.
3. Export formats other than markdown.
4. Concurrent external editing of scene files (the app assumes it is the sole writer while running).
5. Authentication / multi-user.
6. Cloud sync (git remotes cover backup).

---

## 13. Open Questions (to resolve at review)

1. Todo lifecycle: is `open / done / closed`/ `in-progress`
2. Auto-commit on save: include the toggle in v1?
3. Plaintext API keys in app-level JSON (with env-var alternative): confirmed acceptable?

---

## 14. Delivery Plan

Specifications will be produced and reviewed step by step, in this order:

1. **Database specification** — JSON file layouts, schemas, ID scheme, write semantics. *(next)*
2. **API specification** — every endpoint with request/response shapes, job worker, streaming, proposal lifecycle, git operations, AI tool surface.
3. **Frontend specification** — pages, components, editor behavior, state management.

Each is reviewed by the author before proceeding. The final combined tech spec is handed to Claude Code for implementation.