# features/git — `/book/{id}/git`

The deliberate-commit ritual: review, stage, describe, save. Two columns — left 60%: changes + commit box + history; right 40%: diff panel ("Select a file to see its changes"). Parent: [features](../CLAUDE.md). Spec: [doc 06 §14](../../../../../docs/claude-tech-specs/06-frontend-pages.md), backend [git](../../../backend/app/api/git/CLAUDE.md).

## Controls

- **Changes list** rows: ☑ + path (mono) + status letter → `POST /git/stage|unstage {paths}`; row click → `GET /git/diff?path=` into the right panel. **[Stage all]** → `stage {all:true}`.
- **Diff panel:** read-only unified diff, mono, additions `--ok`, deletions `--danger`; binary → "Binary file".
- **Commit message textarea** + **✨ Suggest message** → `POST /git/suggest-message` (spinner; no utility model → stats fallback with faint note "Written from file stats").
- **[Commit staged files]** — enabled iff ≥1 staged ∧ message non-empty; `POST /git/commit` → toast "Committed {shorthash}" → badge clears via SSE.
- **History strip** → `GET /git/log` (shorthash · message · relative time; read-only).
- **[Push ↑2] / [Pull ↓0]** — only when `hasRemote`; `POST /git/push|pull`; errors verbatim in a danger panel + "Resolve with your git tooling".

## Scope

Backup and history without pretending to be a full git client — stage/commit/push/pull only (doc 07). The top-bar amber badge (global shell) nudges here when the repo is dirty.
