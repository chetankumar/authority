# 07 — Decisions & Deferred

## Decisions made during planning (confirmed by the author)

1. Browser app; Python API (FastAPI) + Node-built SPA served by Python; single port (default 8700); localhost, single user, no auth.
2. Launcher: conda preferred / venv fallback; first-run install+build; health poll; auto-open browser; detect-already-running; Ctrl+C teardown; logs console + file; both .sh and .bat; separate dev.sh.
3. JSON-only persistence, atomic writes, API as single writer.
4. Books-home convention: shelf = live folder scan; no registry file; no folder-browser APIs. Book folders named `{hash}-{slug}`, rename follows title.
5. Git per book: init on create; pre-existing repos left untouched; GitPython over system git; manual deliberate commits with top-bar nudge; **auto-commit on save: rejected**. Compiled output committed.
6. Scene identity: 6-hex hash prefixes everywhere; scene files `{hash}-{slug}.md`.
7. Hard chain with **splice** insertion and **splice-heal** on removal/archive; soft relationships in a separate table; virtual **Start/The End** sentinel nodes, connectable, formal completeness anchors.
8. Graph: vertical trunk top-center flowing down; soft satellites left/right; orphans bottom; deterministic computed layout; zoom/pan only, no node dragging, nothing persisted.
9. Table: AG Grid Community (free/MIT); computed Seq; column state persisted per book in db/ui.json.
10. Editor: TipTap; autosave (2s debounce + blur + nav); Ctrl+S; Prev/Next buttons with scroll-to-top; Next-without-next opens prefilled create modal.
11. Prose hard rule + write-permission model as in doc 01. Metadata updates by AI require explicit confirmation (proposals) — except the two bookkeeping toggles (standing consent) and dependency-generated todos (mechanical).
12. Bookkeeping toggles (book-level, in book.json): update summary on save; update character references on save; extensible panel; on-demand AI-redo ignores toggles; toggle-ON means AI always wins (no freeze flags).
13. Enrichment: settle-then-run (60s), coalescing, utility model. Clear matches update summary/`characterIds` under bookkeeping toggles. Unclear cases (unmatched names, ambiguity, minor-character judgment) escalate to a chat; character sheet creates only via author-accepted `character-create` proposals — never silent auto-create.
14. Conversations universal; AI participant toggleable mid-thread; per-message model attribution; selection context as snapshot excerpt; first-words default naming (no AI auto-titling).
15. Edit application: exact-match find/replace; `not-found` when stale; apply one-by-one or accept-all (client loop, no batch atomicity).
16. Deletion of containers (parts/chapters) **blocked** while referenced (409 report); author manually nulls assignments first. Chain healing automatic.
17. Compilation is a **gate**: errors block / warnings inform; all active scenes chaptered and on a single Start→End chain; contiguity required; report deep-links every violation; wipe-and-regenerate; `***` scene breaks; never auto-commits.
18. Relationships editing lives in the Scene Modal's Basics tab — no separate popup.
19. Markers deferred; selection-as-context is the v1 substitute.
20. Placeholder registry server-owned; @-autocomplete; save-time validation. `@previous_scenes_summary` = full prior chain, summaries only.
21. **Theming (added post-v1-draft):** `light / dark / system`, default `system`; **app-level** preference in `app.json` (`appearance.theme`), never per book (a theme is a viewing preference, not part of the portable manuscript). Delivered purely through semantic CSS-variable tokens — light on `:root`, dark on `:root[data-theme="dark"]`; components reference tokens only, **no raw hex and no per-component light/dark stylesheets** (a theme difference gets a new token, not a second rule). Top-bar sun/moon toggle. Supersedes the earlier "dark theme out of v1 scope" note in doc 06 §1.2.
22. **Parts/chapters use seq-based ordering** (not linked lists). Each part and chapter has a simple `seq` integer. Reordering is done via a dedicated reorder endpoint that accepts the full ordered list of IDs and reassigns seq 1..n. Drag-and-drop in the Metadata page. Stored in `db/parts.json` and `db/chapters.json`, not in `config/book.json`.
23. **Plotline-scene relationship owned by Scene.** Scenes carry `primaryPlotlineId` (single FK, nullable) and `secondaryPlotlineIds` (array). Plotlines on disk are just `{ id, title, description }` — no scene references. `sceneCount` is computed by scanning scenes. Plotline assignment lives in the Scene Modal Basics tab.
24. **EventHub is generic core infrastructure, not part of the AI layer.** The build-phase list (doc 02) groups the SSE hub under phase 7 "AI layer" because AI streaming was the first consumer, but nothing about per-book pub/sub depends on LangChain, jobs, or conversations. It lives in `core/`, is built by whichever phase first needs to push (in practice: Git, phase 8), and later consumers just call the same `emit`. **Corrects the misreading that the git badge was blocked on the AI layer.**
25. **Git status is computed by a debounced background worker, never inline on the write path.** Doc 02's earlier wording ("after every disk write... git status is re-checked") is superseded. A write only fires the payload-free internal `book-changed` signal; a dedicated `GitStatusWorker` asyncio task (its own standing task, *not* a separate OS process — a single-process local app gains nothing from IPC) consumes it and runs the real `git status`. Rationale: shelling out to git on every autosave adds latency to the one path that must never stutter — typing.
26. **The debounce is a pure 5s debounce, not a throttle.** Each `book-changed` cancels and restarts the timer, so a continuous autosave streak defers the check until the author actually pauses. Accepted tradeoff: during a long unbroken writing session the badge may stay stale — which is precisely when the author least wants a commit nudge. The 10s poll (below) bounds the staleness anyway.
27. **Explicit git actions bypass the debounce.** Stage/unstage/commit/push/pull recompute status and emit `git-status` immediately, in-request. The author is on the Git page watching; a 5s lag on "did my commit land?" would be a bug, not calm design.
28. **The client polls `GET /git/status` every 10s as a safety net.** Belt and braces alongside SSE: the poll and the event write identical server truth into the same cache key, so they cannot conflict — the poll is purely redundant until something (a dropped signal, a flaky reconnect, a bug in the worker) makes it the thing that saves the badge from lying. A stale amber badge is worse than no badge. The interval pauses while the tab is hidden (TanStack's default) and TanStack's refetch-on-focus covers the return, so the badge is correct by the time anyone can see it — polling a tab nobody is looking at buys nothing. **Verified behavior**, not an assumption: measured ~10.1s spacing while visible, zero polls while hidden.

## Defaults chosen by the spec (author may veto at review)

These closed remaining open threads with reasonable defaults; each is a one-line change if vetoed.

1. **Todo statuses:** `open / done / closed` — no in-progress state.
2. **Character deletion:** blocked (409) while referenced by scenes — consistent with parts/chapters strictness.
3. **Plotline deletion:** blocked while any scene references it (via `primaryPlotlineId` or `secondaryPlotlineIds`).
4. **Soft-relation contradiction at compile time** (chain order violates a "definitely before/after") = **error**; satisfied/redundant soft relations = warning inviting cleanup.
5. **Empty chapter at compile** = warning, emitted as heading-only file (not a block).
6. **Bookkeeping toggles default ON** for new books.
7. **Standing readiness indicator** on the Metadata page (same check API as compile).
8. **Archive surfacing:** Basics tab button + table row action.
9. **Reverse-dependency read-only list** shown in the Dependencies tab.
10. **Chat model default:** last model used; job runs use the job's default.
11. **API keys:** plaintext in app-level app.json with `${ENV_VAR}` alternative; never inside book folders.
12. **Row click in table** opens the editor (Edit-metadata is the smaller affordance).
13. Log file truncated per launch (no rotation history).
14. Settle window 60s (constant; can become a setting later).

## Deferred (explicitly out of v1)

1. Inline positional text markers (todo/edit/comment anchored in prose).
2. Event list in the metadata manager.
3. Export beyond markdown (docx/epub/pdf).
4. Concurrent external editing of scene files while the app runs.
5. Auth / multi-user / remote hosting.
6. Git beyond stage-commit-push-pull (branches, revert, rebase — CLI territory).
7. AI auto-titling of conversations; AI dependency-impact analysis; plotline auto-detection (natural future bookkeeping toggles).
8. Book-level utility-model override (app-level only in v1).

## Glossary

**Trunk** — the hard chain connected to Start. **Unanchored** — a hard chain not yet connected to Start. **Floating** — a scene with only soft relationships. **Orphan** — a scene with no relationships. **Archived** — set aside, out of the book, nothing deleted. **Settle** — the quiet period after saves before enrichment runs. **Proposal** — an AI-suggested change awaiting author accept/reject. **Sentinels** — the virtual Start/The End nodes. **Utility model** — the configured model for system tasks. **Enrichment** — the system job maintaining summary + character refs.
