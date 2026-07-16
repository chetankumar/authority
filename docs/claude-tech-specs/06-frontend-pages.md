# 06 — Frontend Specification

Complete UI contract: design system and style rules (§1), frontend architecture (§2), then every page and modal — purpose, object placement, and a behavior table for every control: what it does, which API it calls, and **why it exists**. Endpoint details live in doc 04; this doc references them by path.

---

## 1. Design system & style rules

### 1.1 Design philosophy

Authority is a place to write a novel. Three consequences, applied everywhere:

1. **The prose is the hero.** The editor page is the design's center of gravity; every other page exists to get out of its way. Chrome recedes: management surfaces are quiet, utilitarian, low-contrast; the writing surface is generous and typographically serious.
2. **Calm by default, loud only when the author must act.** Exactly one attention color (amber) and it means one thing: *something awaits your decision* — pending git changes, pending proposals, dependency todos. Nothing else competes for attention.
3. **Copy is design material.** Buttons say exactly what happens, in sentence case, active voice ("Commit staged files", not "Submit"). An action keeps its name through the flow (button "Compile book" → success toast "Book compiled"). Errors state what went wrong and how to fix it; they never apologize and are never vague. Empty states are invitations to act, not dead ends.

### 1.2 Color tokens & theming (CSS variables; Tailwind maps to these — components never use raw hex)

Ink-and-paper study palette. Deliberately **not** the warm-cream/terracotta or dark-acid looks; a cool, quiet room. **Every color and elevation ships as a semantic token with a light and a dark value; components reference only tokens, never a raw hex or rgb.** That single discipline is what makes theming work everywhere at once — Tailwind classes, the D3 graph SVG (`fill="var(--accent)"`), the editor sheet, and the AG Grid theme all resolve the same variables.

**Theming mechanism.** Light values live on `:root`; dark values on `:root[data-theme="dark"]`. A controller sets `data-theme` on `<html>` from the resolved theme; flipping the attribute recolors the entire app in one move. There are **no per-component light/dark stylesheets, and none may be added** — a component that needs to differ between themes gets a *new token*, not a second rule.

**Theme choice** is `light | dark | system` (`system` follows the OS via `prefers-color-scheme`), **default `system`**. It is an **app-level** preference — all books, the bookshelf, and Settings share it — stored in `app.json` (doc 03 `appearance.theme`; endpoints doc 04 §3). Never per book: a theme is a viewing preference, not part of the portable manuscript.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#FAFAF8` | `#14171A` | App background |
| `--surface` | `#FFFFFF` | `#1D2125` | Cards, modals, panels, editor sheet (elevation reads by lightness in dark) |
| `--ink` | `#1F2328` | `#E6E8EB` | Primary text |
| `--ink-soft` | `#5C6470` | `#A2A9B4` | Secondary text, labels, icons |
| `--ink-faint` | `#9AA1AB` | `#6C7480` | Placeholders, disabled, timestamps |
| `--line` | `#E4E4DF` | `#2C3237` | Borders, dividers, hairlines (carry elevation in dark) |
| `--accent` | `#2F5A78` | `#5E9BC2` | Primary buttons, links, active nav, focus rings, trunk edges |
| `--accent-wash` | `#EBF1F5` | `#1F2E38` | Selected rows, active-nav background, hover fills |
| `--on-accent` | `#FFFFFF` | `#0E1417` | Text/icons on `--accent` **and** `--danger` fills (dark flips to dark ink on the lighter fills) |
| `--attn` | `#B7791F` | `#E0A94A` | Amber: everything pending an author decision (git badge, proposals, dependency todos, warnings) |
| `--attn-wash` | `#FBF3E4` | `#2C2513` | Amber backgrounds |
| `--ok` | `#2F7D4F` | `#4FB07C` | Applied proposals, done states, success |
| `--ok-wash` | `#EAF4EE` | `#16281E` | Success backgrounds |
| `--danger` | `#A3382C` | `#D9695C` | Destructive actions, errors, blocked-deletion dialogs |
| `--danger-wash` | `#F9ECEA` | `#2E1A17` | Danger backgrounds |
| `--edge-soft` | `#5C6470` | `#8A929E` | Soft-relationship dotted edges in the graph — deliberately stronger than `--ink-faint` so the dashes read (hard/trunk edges use `--accent`) |
| `--scrim` | `rgb(31 35 40 / 0.4)` | `rgb(0 0 0 / 0.6)` | Modal/overlay backdrop |
| `--shadow-overlay` | `0 8px 24px rgb(0 0 0 / 0.10)` | `0 10px 28px rgb(0 0 0 / 0.55)` | The one reserved overlay shadow (§1.4) |

The specific dark hex values are the design's starting point and tunable in `tokens.css`; the token *names and contract* are fixed.

### 1.3 Typography

| Role | Face | Rules |
|---|---|---|
| **Prose (editor + rendered markdown in chats/notes)** | **Literata** (bundled webfont; fallback Georgia, serif) | 1.05rem/1.75; editor measure capped at **68ch**; paragraphs spaced, not indented |
| **UI** | **Inter** (fallback system-ui) | 0.875rem base; labels 0.75rem, `--ink-soft`, +0.02em tracking; sentence case everywhere — no all-caps except 2-letter badges |
| **Data/mono** (hashes, diffs, ids, word counts) | ui-monospace stack | 0.8125rem |

Type scale: 12 / 13 / 14 (base) / 16 / 20 / 24 / 30px. Page titles 20/semibold; modal titles 16/semibold. The editor is the only place type gets big; UI stays small and quiet.

### 1.4 Space, shape, elevation, motion

- **Spacing:** 4px scale. Page gutters 24px; card padding 16px; control height 32px (inputs, buttons); dense grids 28px rows.
- **Radii:** 6px controls, 10px cards/modals, 999px pills (sentinels, status chips).
- **Elevation:** borders over shadows. Flat surfaces + `--line` hairlines; one soft shadow level reserved for overlays (modals, popovers, tooltips) via the `--shadow-overlay` token (§1.2). In dark mode elevation leans on `--line` and surface lightness; the token weakens the shadow accordingly.
- **Motion:** 150ms ease-out for hover/fade; 200ms for modal/popover enter (fade + 4px rise); accordion height 200ms. Graph zoom/pan is direct (no easing lag). `prefers-reduced-motion` disables all non-essential transitions. Nothing bounces, nothing pulses except the single streaming-cursor blink in chat.

### 1.5 Component conventions (used by every page below)

- **Buttons:** *Primary* (accent fill, white text — one per view maximum); *Secondary* (surface, `--line` border); *Ghost* (text-only, for toolbars); *Danger* (danger fill — only inside confirm dialogs, never bare on a page). Icon-buttons get tooltips (600ms delay).
- **Modals:** centered, 560px (forms) / 720px (Scene Modal) / 800px (Conversation); scrim via `--scrim` (§1.2); Esc closes unless streaming or unsaved fields (then confirm). Title left, × right, actions bottom-right (primary rightmost).
- **Popovers** (Bookkeeping, column chooser): anchored, 280px, close on outside-click/Esc.
- **Toasts:** bottom-right, 4s, one line, past-tense confirmation ("Scene archived", "Committed 9f2c1a"). Errors persist until dismissed.
- **Badges:** count pills; amber = pending decision, `--ink-faint` = neutral count.
- **Empty states:** icon + one sentence + one action button. E.g. graph: "No scenes yet." / [Add scene].
- **Blocked-deletion dialog** (shared component for parts/chapters/plotlines/characters, driven by any 409 `blockedBy`): danger-tinted title "Can't delete {name} yet", body lists each referencing item as a **link that navigates to the fix location**, single button "Close". Exists because the strict-deletion rule (doc 07 §16) demands the author do the unassigning — the dialog is the map.
- **Confirm dialogs:** only for destructive/irreversible acts (delete, remove cover). Never for archiving (reversible) or proposals (they *are* the confirmation).
- **Focus:** 2px `--accent` ring on all interactive elements; full keyboard reachability; modals trap focus.

---

## 2. Frontend architecture

```
frontend/src/
  api/            # typed client: one function per endpoint (doc 04); SSE helpers
  queries/        # TanStack Query hooks + key factory
  events/         # useBookEvents(bookId): one EventSource per open book → cache patches
  components/     # shared: Modal, Popover, Toast, Badge, BlockedDeletionDialog, SearchableSelect, ...
  features/       # per-page folders: bookshelf/, settings/, graph/, table/, editor/,
                  # conversation/, sceneModal/, characters/, metadata/, tasks/, git/
  styles/         # tokens.css (the §1.2 variables), tailwind config mapping
  App.tsx, router.tsx
```

- **Query keys:** `['book', id]`, `['scenes', bookId]`, `['todos', bookId]`, `['conversations', bookId, sceneId]`, `['jobs', bookId, sceneId]`, `['git', bookId]`, `['compileCheck', bookId]`, `['settings', section]`.
- **SSE integration:** `useBookEvents` subscribes to `GET /books/{id}/events` and translates events → cache updates: `scene-updated` patches `['scenes']`; `job` patches `['jobs']` + streaming modal state; `todos-created` invalidates `['todos']`; `git-status` patches `['git']` (drives the top-bar badge); `compile-done` invalidates `['compileCheck']`. On reconnect: refetch active queries.
- **Editor autosave:** local dirty buffer → debounce 2s → `PUT content`; never blocks typing; failures show a persistent "Not saved — retrying" state, retry with backoff.
- **Routing:** as listed below per page; unknown ids → friendly 404 panel with "Back to bookshelf".

---

## 3. Global shell

```
┌──────────────────────────────────────────────────────────────┐
│ ◆ Authority › {Book title}        [⚠ 7 pending · Commit?]  Welcome, Chetan │  top bar, 48px
├───────────┬──────────────────────────────────────────────────┤
│ left nav  │                                                  │
│ 208px /   │                 page content                     │
│ 56px rail │                                                  │
└───────────┴──────────────────────────────────────────────────┘
```

| Control | Placement | Behavior | Why it exists |
|---|---|---|---|
| Logo + "Authority" | Top bar, left | Click → `/` (bookshelf) | Universal escape hatch; breadcrumb root |
| Book title breadcrumb | Right of logo, inside a book | Click → `/book/{id}` (graph) | Orients the author; one-click back to the book's home view |
| **Git badge** | Top bar, center-right; only when dirty | Shows `GitStatus.summary` + " · Commit now?" in `--attn` (e.g. "7-new, 1-updated, 3-deleted · Commit now?"); click → `/book/{id}/git`. Fed by `git-status` SSE, **plus** a 10s `refetchInterval` on `GET git/status` as a safety net so a dropped event can't leave the badge lying; initial state from the same query. Clean → renders nothing | The nudge that makes deliberate commits happen without auto-commit; amber = decision awaits. It updates itself ~5s after the author stops typing (debounced worker) and instantly after an explicit commit — a badge that's silently stale is worse than no badge, hence the poll |
| "Welcome, {name}" | Top bar, right | Static; from `GET /settings/user`; "Welcome" if unset | Confirms whose studio this is; motivates User Settings on first run |
| **Theme toggle** | Top bar, right (before the greeting) | Sun/moon control cycling `light → dark → system`; writes the choice via `PATCH /settings/appearance` (doc 04 §3) and sets `data-theme` on `<html>` immediately; `system` tracks `prefers-color-scheme` live. Icon reflects the resolved theme | One instant, always-visible switch; theme is app-wide, so it lives in the global chrome rather than a settings page |
| Left nav (outside book) | Home · Settings ▸ (User / AI / AI-Jobs, expands inline) | Route links; active item `--accent-wash` + accent text | |
| Left nav (inside book) | Scene Graph · Scene Table · Character Sheet · Metadata · Tasks · Git — icons + labels | Route links | Fixed order = muscle memory; Graph first because it's the book's home |
| Nav collapse chevron | Nav bottom | Toggles 208px ↔ 56px icon rail (tooltips on rail). Auto-rails on the editor page | Zen: reclaim width for prose; still one click from anywhere |
| Disconnected banner | Below top bar, full-width, danger wash | Appears when `/health` polling fails: "Backend not responding — check the terminal window." Auto-clears on recovery | The backend is a local process the author can kill by accident; name the fix, don't mystify |

---

## 4. Bookshelf — `/`

**Purpose:** choose or create a book. **Layout:** responsive card grid (200px covers, 3:4 ratio), gutter 24px; cards = cover (or gray placeholder rectangle with centered title) + title below + kebab on hover.

| Control | Placement | Behavior | Why it exists |
|---|---|---|---|
| Book card (cover/title) | Grid | Click → `/book/{id}` | The shelf metaphor: the book is the object, opening it is the primary act |
| Card kebab → "Edit book" | Card top-right, hover-reveal | Opens Edit Book modal | Rename/cover are rare acts; hidden until sought so the shelf stays clean |
| **+ Add book** card | Last grid position, dashed border | Opens Add Book modal | Creation lives where the result will appear |
| Broken-book card | Grid (scan returned `error` flag) | Non-clickable, danger tint, "Couldn't read this book's config" | Corruption is surfaced, never hidden; the folder is named so the author can inspect/restore via git |
| Empty states | Grid area | booksHome unset → "Set your books folder to get started" + [Open settings]; set but empty → "Your shelf is empty" + [Add book] | Every dead end points at its exit |

**Add Book modal** (560px): Title* input · cover drop-zone (preview, "Remove") · [Cancel] [Create book]. Create → `POST /books` (multipart) → toast "Book created" → navigate into it. booksHome errors render inline with a settings link.
**Edit Book modal:** same fields prefilled + hint under title: "Renaming also renames the book's folder." → `PATCH /books/{id}`.

---

## 5. Settings — `/settings/*`

**Layout:** all three pages share a 640px centered column; forms are label-over-field; Save is the single primary button, disabled until dirty.

### 5.1 User Settings
| Control | Behavior | Why |
|---|---|---|
| Author name input | `PATCH /settings/user {name}` on Save | Feeds the greeting; the app should know its author |
| Books Home path input + hint "Folder that will contain all your books" | Save → `PATCH {booksHome}`; 422 path-missing → inline error with [Create this folder] button (re-sends with `createBooksHome:true`); 403 → "Not writable — pick another location" | The one path the author must ever type; the create-offer removes the mkdir round-trip |

### 5.2 AI Settings
Models table (AG Grid not needed — plain table): Label · Provider · Model name · Key (masked) · Base URL · row actions.

| Control | Behavior | Why |
|---|---|---|
| [Add model] | Opens model modal | |
| Model modal: Provider select | Drives contextual fields: cloud → Key required; `openai-compatible`/`ollama` → Base URL required, highlighted, placeholder shows LM Studio/Ollama example URLs | Provider rules (doc 04 §3) are taught by the form, not the error message |
| Key input, hint "Paste a key or use ${ENV_VAR}" | `POST/PATCH /settings/models`; edit modal leaves the field blank-but-untouched (omit = keep stored key) | Secrets never round-trip to the client |
| Row **Test** ↯ | `POST /settings/models/{id}/test` → button enters a spinner; success → green "OK · {latencyMs}ms" chip + toast "{label} replied"; failure → red "Failed" chip (reason on hover) + persistent error toast naming the fix (unset env var, bad key, unreachable base URL, timeout) | A model config that *looks* right isn't trustworthy until it has actually answered; the check turns "configured" into "works" without leaving Settings — especially for local `ollama`/`openai-compatible` servers that may simply be off |
| Row edit ✎ / delete 🗑 | Delete → confirm → `DELETE`; 409 → blocked dialog listing AI-Jobs / any of the five AI-task-model references | A model in use can't silently vanish from under jobs |
| **AI task models** — five selects: Default utility model, Commit message model, Scene summarization model, Character parsing model, AI chat default model | Below the table; each independently `PATCH /settings/ai {<field>}` | Every model that acts without a conversation must be an explicit, visible choice — and different bookkeeping tasks (summarizing vs. matching characters) may warrant different models. The utility model is the shared fallback for whichever of the other four are left unset, plus sundry tasks like chat-thread titling |

### 5.3 AI-Jobs
Jobs table: Name · Default model · Output type · actions. [Add AI-Job] → modal:

| Control | Behavior | Why |
|---|---|---|
| Name input | | Appears verbatim in the editor's dropdown |
| **Prompt textarea with @-autocomplete** | Typing `@` opens an anchored menu fed by `GET /settings/placeholders` (name + description), filters as typed, Enter/Tab inserts | Placeholders are the API between author intent and scene context; autocomplete makes typos structurally unlikely and teaches the vocabulary in place |
| Output type select with per-option captions: "Chat — free reply" / "Edit proposals — returns applyable find-and-replace edits" / "Metadata proposals — returns applyable field updates" | Stored on the definition; drives server-side parsing (doc 04 §2.1) | The author must understand this choice — it decides whether a job's answer is words or actions |
| Default model select · [Save job] | `POST/PATCH /settings/ai-jobs`; 422 unknown-placeholder → inline warning listing tokens + [Save anyway] (`force:true`) | Warn-don't-block: the registry will grow; authors may pre-write prompts |

---

## 6. Scene Graph — `/book/{id}`

**Purpose:** see the story's shape; the book's home. **Layout:** full-bleed canvas; floating controls only.

```
        ( Start )                    ← sentinel pill, pinned top-center
            │  solid arrows = hard chain (--accent)
        [ Scene 1 ]
            │        ┄┄▶ [ floating scene ]   ← dotted, --ink-faint, satellites left/right
        [ Scene 2 ]
            │
        ( The End )                  ← anchors trunk bottom; floats at canvas
                                       bottom while unreached
   [orphans row along the bottom]                     [＋ Add scene]  [⤢ Fit]  [🔍±]
```

Node = 168px surface card, title only (1 line, ellipsis); hover 600ms → description tooltip. Placement per the deterministic algorithm (doc 04 §5 GET scenes; layout math is a pure frontend function of that payload — same data, same picture).

| Control | Behavior | Why it exists |
|---|---|---|
| Node **single-click** | Opens Scene Modal (edit) | Inspect/adjust a scene's *facts* without leaving the map |
| Node **double-click** | → `/book/{id}/scene/{sid}` | Enter the prose; the deliberate act gets the heavier gesture |
| Sentinel pills | Non-interactive, pill-shaped, `--ink-soft` outline | Fixed reference points; visually "not scenes" so no one tries to open them |
| Canvas drag / wheel / pinch | Pan / zoom (D3 zoom behavior; no node dragging, nothing persisted) | The author reads the map, never maintains it — layout is the data's job |
| **＋ Add scene** floating button (primary) | Scene Modal (create) → `POST /scenes` → node appears via cache patch, brief 200ms fade-in | Creation belongs on the map where placement is being imagined |
| ⤢ Fit to view | Recenters/zooms to bounding box | Recovery from deep zoom; also the "show me everything" gesture |
| Edge hover | Dotted edge tooltip: "definitely after {title}" | Dotted lines carry meaning; hover names it |

Archived scenes: not rendered (the table's Archived filter is their home).

---

## 7. Scene Table — `/book/{id}/table`

**Purpose:** the working ledger — sort, filter, scan, bulk-see. **Layout:** toolbar row above a full-height AG Grid.

Toolbar: left — segmented filter **All / Placed / Floating** + **Archived** toggle; right — [Columns ▾] popover (checkbox list of available columns) + [＋ Add scene] (primary).

Grid: default columns Seq · Title · Description · Characters · Chapter · Part · Mood; available also Location, Date/Time, Emotional Arc, Summary, Words, Updated. Seq ascending default; non-trunk rows carry a small placement chip (`unanchored ~`, `floating`, `orphan`); archived rows `--ink-faint` with strikethrough title (visible only with the toggle). Column state changes → debounced `PATCH /books/{id}/ui`; restored on load.

| Control | Behavior | Why it exists |
|---|---|---|
| Row click | → editor | The table is a launchpad; the common act is the cheap one |
| Row action "Edit metadata" ✎ | Scene Modal | Fix facts without opening prose |
| Row menu → Archive / Unarchive | `PATCH scenes/{id} {status}` → toast "Scene archived" | The compile gate demands a place-or-archive decision; this is where "set aside" lives |
| Filter segments | Client-side placement filter | "What's still unplaced?" is a planning question asked constantly — one click, not a query |
| Column chooser | AG Grid column API + ui.json persistence | Authors differ (mood-driven vs. location-driven); the ledger adapts and remembers per book |
| Seq header click | Re-sort by Seq | The "restore story order" gesture after any exploration |

---

## 8. Scene Modal (unified, tabbed) — component, not a route

**Purpose:** everything *about* a scene that isn't its prose. Opened from: graph single-click, table ✎, editor's [Metadata], and create flows (create mode shows Basics only; other tabs appear after first save). 720px, tabs across the top: **Basics · Characters · Summary · Dependencies**.

### Basics
Two-column form: left — Title*, Description* (textarea), Location, Date/Time, Mood, Emotional Arc (all free text). Right — **Sequence** fieldset (Previous / Next SearchableSelects, sentinels pinned top/bottom, hint "Inserting between scenes relinks them automatically"); **Soft placement** fieldset (rows: type select + scene select + ✕; [+ Add placement]); **Structure** fieldset (Chapter select / Part select — selecting one clears and disables the other, hint "A scene belongs to a chapter *or* directly to a part"). **Plotlines** fieldset (Primary plotline — SearchableSelect dropdown, nullable; Secondary plotlines — multi-select tag input for additional plotline assignments; hint "The main narrative thread this scene serves"). Footer: [Archive scene] (ghost, left) · [Cancel] [Save scene].

| Control | Behavior | Why |
|---|---|---|
| Save | Create: `POST /scenes`; edit: `PATCH /scenes/{id}`; soft-placement rows diff → `POST/DELETE /relationships` | One Save for the whole tab; relationship rows are data the author thinks of as part of the scene |
| Prev/Next selects | Splice semantics server-side; `affectedScenes` in the response patch the graph | Placement *is* authorship of structure; dropdowns beat drag precisely |
| Archive scene | `PATCH {status:"archived"}` + inline note "The chain will close around it; find it under the table's Archived filter" | Reversible, so no confirm; the note answers "where did it go" pre-emptively |

### Characters
Chip row of referenced characters (✕ removes) + SearchableSelect "Add character…" → both via `PATCH {characterIds}`. Top-right: **↻ AI-redo** ghost button.

| Control | Behavior | Why |
|---|---|---|
| ↻ AI-redo | `POST /scenes/{id}/enrich {scope:"characters"}` → button enters spinner state; `scene-updated` SSE patches chips live; `result.unrecognizedNames` renders as an amber inline note: "Unrecognized: Marlow — [Add to characters]" | On-demand truth-refresh regardless of the toggle; the unrecognized-note closes the loop between prose and the directory without auto-creating anyone |

### Summary
Textarea + [Save summary] (`PATCH {summary}`) · ↻ AI-redo (`enrich {scope:"summary"}`) · persistent hint line reflecting the book toggle: "Auto-update on save is **on** — manual edits may be overwritten" / "…**off** — this summary is yours." **Why the hint:** the toggle-owns-the-field rule (doc 05) must be visible at the exact moment an author is about to hand-write a summary.

### Dependencies
Top list — "This scene depends on": rows *{scene title} — {reason}* with ✎ (inline reason edit → `PATCH /dependencies/{id}`) and ✕ (`DELETE`). Add row: SearchableSelect ordered by Seq (self + sentinels excluded) + Reason* input + [Add dependency] (`POST /dependencies`; Reason required — "a dependency without a why is noise" is enforced by the disabled button + hint). Bottom list — read-only "**Depended on by**" (from `GET dependencies.dependedOnBy`), each row `--attn`-tinted. **Why the second list:** it's the warning the author reads *before* rewriting a scene others lean on — the dependency system's whole purpose, surfaced at the point of danger.

---

## 9. Scene Editor — `/book/{id}/scene/{sid}`

**Purpose:** the room where the book gets written. Everything else in this layout exists to be ignorable.

```
┌─ icon rail ─┬────────────────────────────────────────────┬─ right pane 320px ─┐
│ (auto-      │  tool panel: [AI-Jobs ▾][Metadata]         │ ▸ Notes        (3) │
│  collapsed  │              [Bookkeeping][Chat]    [◫]    │ ▸ To-dos       (2)●│
│  left nav)  ├────────────────────────────────────────────┤ ▸ AI Jobs      (1) │
│             │  TipTap toolbar: B I H₁ H₂ " • …           │                    │
│             │  ┌────────── 68ch sheet ──────────┐        │  (● = amber count  │
│             │  │  Scene Title (inline-editable) │        │   of open items)   │
│             │  │                                │        │                    │
│             │  │  prose …                       │        │                    │
│             │  └────────────────────────────────┘        │                    │
│             │  1,240 words · Saved 2:41pm  [← Prev][Next →]                   │
└─────────────┴────────────────────────────────────────────┴────────────────────┘
```

The sheet: `--surface` on `--paper`, Literata, 68ch measure, generous top margin. Load: `GET /scenes/{id}` (metadata + content).

| Control | Placement | Behavior | Why it exists |
|---|---|---|---|
| **AI-Jobs ▾** | Tool panel | Menu of saved jobs (`GET /settings/ai-jobs`). Pick → `POST /ai-jobs/run` with sceneId + scope: `selection` if the editor has an active selection (selectionText sent), else `full` → Conversation Modal opens on the new conversation, streaming | The author's own toolbox, one gesture from the prose; selection-awareness makes "fix this paragraph" and "review the scene" the same menu |
| **Metadata** | Tool panel | Opens the Scene Modal | Facts about the scene without leaving the room |
| **Bookkeeping** | Tool panel | Popover of iOS-style toggles: "Update summary on save" / "Update character references on save" → `PATCH /books/{id} {bookkeeping}`; footer note "Applies to this whole book". List component — future tasks append | Standing consent must be inspectable and revocable exactly where its effects are felt; book-level scope is stated because the button sits on a scene page |
| **Chat** | Tool panel | `POST /conversations {kind:"chat", parent: scene, aiParticipant: {enabled:true, modelId: chatDefaultModel}}` → Conversation Modal with AI on and the chat default model preselected (falls back to the utility model, then the first configured model). If a selection is active, it rides the first message as `context` and renders as a quoted block | The "I'm stuck" button; selection-as-context is the v1 answer to inline markers |
| ◫ pane toggle | Tool panel, right edge | Show/hide right pane; persisted in ui.json | Zen switch: full-width prose on demand, memory per book |
| TipTap toolbar | Above sheet | Standard marks/blocks; Ctrl/Cmd+B/I etc. | Familiar; deliberately small — novels are mostly paragraphs |
| Inline title | Top of sheet | Blur/Enter → `PATCH {title}` (slug-renames the file server-side) | The title is prose-adjacent; renaming shouldn't require a modal |
| The sheet | Center | TipTap + tiptap-markdown; contenteditable (Grammarly-compatible); autosave: 2s debounce + blur + route-leave → `PUT content`; Ctrl/Cmd+S immediate | |
| Save indicator | Bottom bar | "Saving…" → "Saved · 2:41pm"; failure → persistent amber "Not saved — retrying" | Trust: an author must never wonder whether words are on disk |
| Word count | Bottom bar, mono | Live local count; server value reconciles on save | The writer's odometer |
| **← Previous / Next →** | Bottom bar, right | Save current, then: neighbor exists → navigate + **scroll to top**; Next with no neighbor → Scene Modal (create) with Previous prefilled to this scene → on save, navigate into the new scene. Prev with no neighbor → disabled with tooltip "This is the first scene" | Drafting momentum: write, next, write. The prefilled-create turns "what comes next?" into one gesture; scroll-to-top starts each scene at its beginning |
| Right pane accordion | Right, 320px | **Notes** (`GET /scenes/{id}/conversations`, kinds note/chat): rows = title (CSS ellipsis; full title on hover) · relative time · snippet; click → Conversation Modal. **To-dos** (`GET /scenes/{id}/todos`): checkbox = done (`PATCH`), ✕ = closed; dependency-origin rows carry a ⛓ icon + amber tint; 💬 opens linked conversation. **AI Jobs** (`GET /jobs?scene=`): rows = job/conversation name (ellipsis + hover) · status chip (queued/running spinner/done/failed, live via SSE) · unrecognized-names note; click → its conversation. Amber count badges on headers = open/pending items | The scene's memory: everything ever discussed, owed, or run against this scene, adjacent to the prose but collapsed by default — present, not loud |

**Leaving with a running stream/job:** navigation allowed; jobs are server-side; the AI Jobs pane and SSE keep truth. A toast on completion ("Editorial review finished") links back to the conversation.

---

## 10. Conversation Modal — component

**Purpose:** the universal thread — note-stacking, chat, and AI-job runs are all this one surface. 800px × 80vh.

**Header:** editable title (controlled; blur → `PATCH /conversations/{id}`; full title stored — list UIs truncate with hover; auto-filled from utility-model **3–5 word** semantic title when still Untitled after first send — SSE `title`) · relative timestamp · right cluster: **model select** + **"AI participant" switch** · **Delete** · ×.
**Body:** message list. User messages right-aligned wash; context excerpts render as bordered quote blocks above the text, labeled "From {scene title}". Assistant messages left, model label in `--ink-faint` above, streaming text with a blinking cursor. System messages (job prompts) collapsed to one line — "Job prompt · show" — expandable.
**Proposal cards** inside assistant messages: bordered `--attn-wash` cards. Edit: side-by-side find (strikethrough) / replace + rationale line. Metadata: "Mood: ~~tense~~ → **elegiac**" + rationale. Todo: "☐ {action}". Buttons per card [Reject] [Accept]; message footer [Accept all ({n})] when >1 pending. Applied → `--ok-wash` + ✓; rejected → faded; not-found → amber "This text is no longer in the scene."
**Composer:** textarea (Enter sends, Shift+Enter newline) · [Send].

| Control | Behavior | Why it exists |
|---|---|---|
| **AI participant switch** | `PATCH {aiParticipant.enabled}`; on-with-no-model → the model select pulses its focus ring and the send stays enabled but returns the 422 inline: "Pick a model to bring the AI in" | The stack-notes-to-myself feature: one thread can be private scratchpad, then a consultation, then private again — the switch is that boundary, visible and instant |
| Model select | `PATCH {aiParticipant.modelId}`; defaults: job's default model on job runs, else last-used | Different questions deserve different (or local) models; per-message attribution in the transcript keeps the history honest |
| Send | `POST /messages` — switch off: plain append (the note path). Switch on: SSE stream renders tokens live; final `message` event replaces the streaming buffer with the persisted message + proposal cards; `error` event → inline danger row + composer re-enabled. First send while Untitled → utility model names the thread (dedicated prompt; full reply stored); header updates via `title` event | |
| **Delete** | Confirm → `DELETE /conversations/{id}` → close modal; Notes/AI Jobs lists refresh | Hard delete for mistakes; confirm because irreversible |
| Accept / Reject / Accept all | `POST /proposals/{id}/accept|reject`; Accept-all loops sequentially, halting to surface any not-found | The approval gate made tactile: every AI-initiated change is a card the author physically dismisses or applies; not-found is shown, never silently skipped |
| Close / click-out | Just closes — every message persisted on send; pending proposals survive and badge the accordion | No "save conversation?" anxiety; the thread is already real |

---

## 11. Character Sheet — `/book/{id}/characters`

**Purpose:** the who's-who dictionary; also the enrichment matcher's vocabulary. **Layout:** 640px column; rows = name (medium) + first line of personality (`--ink-soft`) + scene-count badge; click expands inline to the edit form, grouped **Identity** (Name*, Aliases tag-input, Age, Gender, Nationality, Ethnicity, Occupation), **Craft** (Want, Need, Flaw, Arc, Personality / History / Notes textareas), and **Relationships** (see below), with [Delete] ghost-danger left, [Save] right. [＋ Add character] primary, top-right.

| Control | Behavior | Why |
|---|---|---|
| Aliases tag-input, hint "Nicknames and titles the prose uses — 'the Widow', 'Marlow'" | `POST/PATCH /characters`; 422 uniqueness conflict → inline "Already used by {name}" | Aliases are functional: they're how enrichment recognizes characters in prose; the hint teaches that |
| Want / Need / Flaw / Arc | Free text; `PATCH /characters/{id}` | The engine of character-driven fiction — an external goal in tension with an internal need, a flaw that generates conflict, and how the character changes |
| Delete | `DELETE`; 409 → Blocked-deletion dialog listing referencing scenes **and** character-relationship rows as links | Same strict rule as structure: references are unwound by the author, never swept |
| Scene-count badge | From `sceneCount` | Instantly shows who's load-bearing and who's vestigial |

### Relationships (within the expanded row)

A list of this character's relationships to others, each rendered as "*{this character} is {aToB} {other character}*" with a category chip and description; [✎] to edit, [✕] to remove. **[+ Add relationship]** picks the other character via SearchableSelect, a category (family / romantic / friendship / rivalry / professional / mentorship / other), and two independent direction labels — how this character relates to the other, and the reverse (e.g. "mother of" / "daughter of") — since most relationships aren't symmetric. `POST/PATCH/DELETE /character-relationships`; 422 on duplicate pair or missing direction labels.

---

## 12. Metadata — `/book/{id}/metadata`

**Purpose:** the book's structural workshop. **Layout:** sub-nav tabs **Parts · Chapters · Plotlines · Book**; content 720px column. A **readiness strip** persists above all tabs: `GET /compile/check` → "✅ Ready to compile" or "⚠ 3 errors · 5 warnings" (amber, expandable to the full grouped report, every item a deep link) + [Compile book] primary.

| Control | Behavior | Why it exists |
|---|---|---|
| Readiness strip | Expand → grouped CheckItems, each subject a link (scene → Scene Modal; chapter/part → its tab) | The pre-flight checklist is a *standing* instrument, not a compile-time surprise — it's the "how finished is this book, structurally?" gauge |
| [Compile book] | `POST /compile`; 409 → auto-expands the report; success → build-report dialog (files, counts, warnings) + toast "Book compiled — output is uncommitted" (links to Git) | The gate in action; the toast hands the baton to the deliberate-commit ritual |
| **Parts tab:** ordered rows, drag-and-drop reorder, ✎, 🗑, [＋ Add part] | Drag-and-drop → `POST /parts/reorder` with new ID order; 🗑 → `DELETE`, 409 → Blocked dialog | Drag-and-drop for reorder: direct, tactile, seq-based ordering underneath |
| **Chapters tab:** rows grouped under part headings + "Unassigned" group; each row has a Part select | Same CRUD; Part select → `PATCH {partId}` | The grouping *is* the book's table of contents taking shape; "Unassigned" keeps un-homed chapters visible, not lost |
| **Plotlines tab:** rows with scene-count badges; CRUD modal (title*, description) | `DELETE` 409-blocked while scenes linked | Scene counts expose thin sideplots at a glance |
| **Book tab:** Story summary textarea · Book system prompt textarea (hint: "Prepended to every AI request for this book — genre, voice, style rules") | [Save] → `PATCH /books/{id}` | The two book-level texts that shape every AI interaction deserve a deliberate, labeled home |

---

## 13. Tasks — `/book/{id}/tasks`

**Purpose:** everything owed, in one ledger. **Layout:** toolbar (status filter segmented **Open / All** · [＋ Add task]) over full-height AG Grid: Status · Action · Parent (link chip) · Origin (icon: 👤 user / ⛓ dependency / ✦ ai) · Created · Updated.

| Control | Behavior | Why |
|---|---|---|
| Parent chip | Navigates: scene → editor; chapter/part → Metadata tab; book → Metadata Book tab | A task is only useful next to the thing it's about |
| Status controls | Checkbox → done; row-menu Close → closed; both `PATCH /todos/{id}` | Done = accomplished; closed = dismissed (the dependency-review "not applicable" verdict) — two distinct ends, both cheap |
| Row menu → Open conversation / Delete | 💬 → Conversation Modal; Delete → confirm → `DELETE` | Delete exists for mistakes only; the hint in the confirm says so |
| [＋ Add task] | Inline row: action text + parent picker (defaults book) → `POST /todos` | Book-level todos ("research Venetian glassmaking") need a home that isn't a scene |
| Origin icons | Static | Provenance at a glance — especially the ⛓ rows, which are the dependency system talking |

---

## 14. Git — `/book/{id}/git`

**Purpose:** the deliberate-commit ritual: review, stage, describe, save. **Layout:** two columns — left 60%: changes + commit box + history; right 40%: diff panel (empty state: "Select a file to see its changes").

| Control | Behavior | Why it exists |
|---|---|---|
| Changes list rows: ☑ + path (mono) + status letter | ☑/☐ → `POST /git/stage|unstage {paths}`; row click → `GET /git/diff?path=` into the right panel | Per-file staging keeps unrelated work out of a commit; the diff answers "what did I actually change?" before it's history |
| [Stage all] | `stage {all:true}` | The common case in a single-author repo |
| Diff panel | Read-only unified diff, mono, additions `--ok`, deletions `--danger`; binary → "Binary file" | Review without a terminal; deliberately not an editor — fixing happens in the editor |
| Commit message textarea | | |
| **✨ Suggest message** | `POST /git/suggest-message` → fills the textarea (spinner in-button); no commit-message model (or utility fallback) resolves → stats fallback arrives with a faint note "Written from file stats" | Lowers the cost of good history; the message is *always* editable — the author owns the record |
| [Commit staged files] | Enabled iff ≥1 staged ∧ message non-empty; `POST /git/commit` → toast "Committed {shorthash}" → badge clears via SSE | The button's precondition *is* the ritual: something chosen, something said |
| History strip | `GET /git/log` — shorthash (mono) · message · relative time; read-only | Recent memory + restore points; anything deeper is CLI territory by design |
| [Push ↑2] / [Pull ↓0] | Only when `hasRemote`; `POST /git/push|pull`; errors verbatim in a danger panel + "Resolve with your git tooling" | Backup without pretending to be a git client; honest hand-off at the edge of scope |
