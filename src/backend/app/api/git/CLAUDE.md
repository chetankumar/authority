# api/git

The deliberate-commit ritual: status, stage/unstage, diff, suggest-message, commit, push/pull, log. `GitService` wraps GitPython over the system git (the user's credentials/SSH config apply). Spec: [doc 04 §13](../../../../../docs/claude-tech-specs/04-api-reference.md). 404 if the book folder lost its `.git`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/git/status` | `GitStatus { dirty, files:[GitFile], ahead, behind, hasRemote }` |
| POST | `/api/books/{b}/git/stage` · `/unstage` | `{ paths?, all? }` (one required). Real `git add` / `git reset`. Returns refreshed status |
| GET | `/api/books/{b}/git/diff?path=` | `{ path, diff }` (staged+unstaged vs HEAD); binary → `{ binary:true }` |
| POST | `/api/books/{b}/git/suggest-message` | Staged diff (422 `nothing-staged`) → truncate ~20k → utility model single-line commit message; no utility model → deterministic stats fallback. `{ message }` |
| POST | `/api/books/{b}/git/commit` | `{ message (req) }`. 422 `nothing-staged`. `{ hash }`; emits `git-status` |
| POST | `/api/books/{b}/git/push` · `/pull` | 422 `no-remote`. Errors verbatim (`detail.gitError`); pull halts on conflicts ("resolve with your git tooling" — Authority never resolves conflicts). Emits `git-status` |
| GET | `/api/books/{b}/git/log?limit=20` | `[CommitInfo]` |

## Scope (deliberate, doc 07)

Stage-commit-push-pull only. No branches/revert/rebase — that's CLI territory by design. Manual, deliberate commits; auto-commit on save is rejected. Compiled output is committed by the author, never auto-committed.
