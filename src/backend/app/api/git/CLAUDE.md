# api/git

The deliberate-commit ritual: status, stage/unstage, diff, suggest-message, commit, push/pull, log. `GitService` wraps GitPython over the system git (the user's credentials/SSH config apply). Spec: [doc 04 §13](../../../../../docs/claude-tech-specs/04-api-reference.md). 404 if the book folder lost its `.git`.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/git/status` | `GitStatus { dirty, files:[GitFile], ahead, behind, hasRemote, branch, summary }`. Also serves the client's 10s safety-net poll |
| POST | `/api/books/{b}/git/stage` · `/unstage` | `{ paths?, all? }` (one required). Real `git add` / `git reset`. Returns refreshed status; emits `git-status` |
| GET | `/api/books/{b}/git/diff?path=` | `{ path, diff }` (staged+unstaged vs HEAD); binary → `{ binary:true }` |
| POST | `/api/books/{b}/git/suggest-message` | Staged diff (422 `nothing-staged`) → truncate ~20k → utility model single-line commit message; no utility model → deterministic stats fallback. `{ message }` |
| POST | `/api/books/{b}/git/commit` | `{ message (req) }`. 422 `nothing-staged`. `{ hash }`; emits `git-status` |
| POST | `/api/books/{b}/git/push` · `/pull` | 422 `no-remote`. Errors verbatim (`detail.gitError`); pull halts on conflicts ("resolve with your git tooling" — Authority never resolves conflicts). Emits `git-status` |
| GET | `/api/books/{b}/git/log?limit=20` | `[CommitInfo]` |

`summary` is the badge's human roll-up, built by `GitService.status()`: `"all-changes-synced"` when clean, else the non-zero segments of `"{n}-new, {m}-updated, {k}-deleted"`. `branch` is read-only orientation (short sha when detached) — branch management stays CLI territory (doc 07 §6).

**Read status with `--porcelain -uall`.** Plain `--porcelain` collapses an untracked *directory* into a single line, so a folder of five new scenes counts as one — and the number then jumps when staged, because staging expands it. The count must mean the same thing before and after staging.

## Emission rule (doc 07 §27)

Every **mutating** endpoint here recomputes status and emits `git-status` **immediately, in-request** — the author is on the Git page waiting, so a debounce would read as a bug. Reads (`status`, `diff`, `log`) emit nothing. *Incidental* dirtying from unrelated writes (scene autosave, structure edits) is not this router's problem: those fire `book-changed`, and the [git-status worker](../../worker/CLAUDE.md) re-checks after a 5s debounce.

## Windows discipline

Every op must `repo.close()` in a `finally` — GitPython keeps persistent helper processes alive, and a held handle blocks later folder renames/deletes on Windows (the same reason `BookService._git_init` does it).

## Scope (deliberate, doc 07)

Stage-commit-push-pull only. No branches/revert/rebase — that's CLI territory by design. Manual, deliberate commits; auto-commit on save is rejected. Compiled output is committed by the author, never auto-committed.
