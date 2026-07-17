# features/git — `/book/{id}/git`

The deliberate-commit ritual: review, stage, describe, save. Two columns — left 60%: changes + commit box + history; right 40%: diff panel ("Select a file to see its changes"). Parent: [features](../CLAUDE.md). Spec: [doc 06 §14](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [git](../../../backend/app/api/git/CLAUDE.md).

## Controls

- **Branch line** beside the page title: `⎇ {branch}` + "in sync with origin" / "2 to push · 1 to pull" / "no remote". Read-only orientation, never guessing which branch a commit lands on.
- **Changes list** rows: ☑ + path (mono) + status letter + **Discard** → `POST /git/stage|unstage {paths}`; row click → `GET /git/diff?path=` into the right panel; Discard → confirm → `POST /git/discard {paths}` (staged + unstaged thrown away; untracked deleted). **[Stage all]** → `stage {all:true}`. **[Discard all]** → confirm → `discard {all:true}`.
- **Diff panel:** read-only unified diff, mono, additions `--ok`, deletions `--danger`; binary → "Binary file".
- **Commit message textarea** + **✨ Suggest message** → `POST /git/suggest-message` (spinner; no utility model → stats fallback with faint note "Written from file stats").
- **[Commit staged files]** — enabled iff ≥1 staged ∧ message non-empty; `POST /git/commit` → toast "Committed {shorthash}" → badge clears **immediately** (the endpoint emits `git-status` in-request; no debounce on explicit actions).
- **History strip** → `GET /git/log` (shorthash · message · relative time; read-only).
- **[Push ↑2] / [Pull ↓0]** — only when `hasRemote`; `POST /git/push|pull`; errors verbatim in a danger panel + "Resolve with your git tooling".

## Scope

Backup and history without pretending to be a full git client — stage/commit/push/pull/discard only (doc 07). Branches/revert/rebase stay CLI. The top-bar amber badge (global shell) nudges here when the repo is dirty.

## The badge

Renders `GitStatus.summary` + " · Commit now?" (e.g. "7-new, 1-updated, 3-deleted · Commit now?"), amber, only when dirty. Two update paths, deliberately redundant (doc 07 §25–28):

- **Ambient** — the author is just writing. Writes fire a server-side `book-changed` signal; a debounced worker re-checks git 5s after typing stops and pushes `git-status` over SSE. Git never runs on the autosave request itself.
- **Explicit** — stage/commit/discard/push/pull emit `git-status` in-request; the badge reacts at once.
- **Net** — `useGitStatus` polls every 10s regardless, so a lost event can't leave the badge stale. A silently-wrong amber badge is worse than no badge.
