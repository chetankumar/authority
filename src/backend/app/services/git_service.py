"""GitService (doc 04 §13) — GitPython over the system git, one repo per book.

**Git never runs on a write path** (doc 07 §25). A scene save only fires the
payload-free ``book-changed`` signal; the git-status worker re-checks after a
debounce. The endpoints here are the exception: stage/unstage/commit/push/pull
are explicit author actions with someone watching the Git page, so they recompute
and emit ``git-status`` immediately, in-request (doc 07 §27).

``status()`` itself never emits — it is pure computation, so the request path and
the worker can both call it and decide separately whether to broadcast.

``git`` is imported lazily throughout: GitPython raises at import time when the
system ``git`` binary is missing, and that must degrade this one feature rather
than stop the app from booting.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

from app.core.errors import ApiError, not_found
from app.core.event_hub import EventHub
from app.models.git import CommitInfo, GitDiff, GitFile, GitStatus, RemoteResult, SuggestedMessage
from app.services.book_registry import BookRegistry
from app.services.context_assembler import ContextAssembler
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.git")

# Diffs are pasted into a model prompt; cap the payload (doc 04 §13). Largest
# hunks first, so the cap drops trivia rather than the substance of the change.
_DIFF_CHAR_CAP = 20_000
_SUGGEST_TIMEOUT_SECONDS = 30.0

_SUGGEST_PROMPT = (
    "Summarize these changes to a novel manuscript as a single-line git commit "
    "message. Reply with the message only — no quotes, no prefix, no trailing period.\n\n"
)

_STATUS_CODES: dict[str, str] = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "added",
    "U": "modified",
}

_git_module: ModuleType | None = None


def _git() -> ModuleType:
    """Import GitPython on first use (see the module docstring)."""
    global _git_module
    if _git_module is None:
        try:
            import git
        except Exception as exc:  # noqa: BLE001 — missing binary or broken install
            raise ApiError(
                500,
                "Git isn't available. Authority needs the system git installed.",
                {"reason": str(exc)},
            ) from exc
        _git_module = git
    return _git_module


class GitService:
    def __init__(self, registry: BookRegistry, settings: SettingsService, hub: EventHub) -> None:
        self._registry = registry
        self._settings = settings
        self._hub = hub

    # ---- reads (no lock, no emit) -------------------------------------------

    async def status(self, book_id: str) -> GitStatus:
        repo = self._open(book_id)
        try:
            return self._read_status(repo)
        finally:
            repo.close()

    async def diff(self, book_id: str, path: str) -> GitDiff:
        book_dir = self._registry.get(book_id).book_dir
        repo = self._open(book_id)
        try:
            if not repo.git.ls_files("--", path).strip():
                # Untracked: nothing in the index or HEAD to diff against, so
                # render the file as all-additions ourselves. (`--no-index`
                # against a null device isn't portable to Windows.)
                return _untracked_diff(book_dir, path)

            # Staged + unstaged against HEAD, per doc 04 §13.
            base = "HEAD" if repo.head.is_valid() else "--cached"
            text = repo.git.diff(base, "--", path)
            if _looks_binary(text):
                return GitDiff(path=path, binary=True)
            return GitDiff(path=path, diff=text)
        except _git().GitCommandError as exc:
            raise self._git_error("Couldn't read that diff.", exc) from exc
        finally:
            repo.close()

    async def log(self, book_id: str, limit: int = 20) -> list[CommitInfo]:
        repo = self._open(book_id)
        try:
            if not repo.head.is_valid():  # a repo with no commits yet
                return []
            return [_commit_info(c) for c in repo.iter_commits(max_count=limit)]
        finally:
            repo.close()

    # ---- mutations (lock + immediate emit) ----------------------------------

    async def stage(self, book_id: str, paths: list[str] | None, all_: bool | None) -> GitStatus:
        return await self._stage_op(book_id, paths, all_, unstage=False)

    async def unstage(self, book_id: str, paths: list[str] | None, all_: bool | None) -> GitStatus:
        return await self._stage_op(book_id, paths, all_, unstage=True)

    async def _stage_op(
        self, book_id: str, paths: list[str] | None, all_: bool | None, *, unstage: bool
    ) -> GitStatus:
        if not paths and not all_:
            raise ApiError(422, "Validation failed", {"fields": {"paths": "Give paths, or set all."}})

        mgr = self._registry.get(book_id)
        async with mgr.lock:
            repo = self._open(book_id)
            try:
                if unstage:
                    repo.git.reset() if all_ else repo.git.reset("--", *(paths or []))
                else:
                    repo.git.add(A=True) if all_ else repo.git.add("--", *(paths or []))
                status = self._read_status(repo)
            except _git().GitCommandError as exc:
                raise self._git_error("Couldn't update the staging area.", exc) from exc
            finally:
                repo.close()

        self._hub.emit(book_id, "git-status", status.model_dump())
        return status

    async def commit(self, book_id: str, message: str) -> CommitInfo:
        message = message.strip()
        if not message:
            raise ApiError(422, "Validation failed", {"fields": {"message": "Say what changed."}})

        mgr = self._registry.get(book_id)
        async with mgr.lock:
            repo = self._open(book_id)
            try:
                if not self._staged_paths(repo):
                    raise ApiError(422, "Nothing is staged to commit.", {"code": "nothing-staged"})

                author_name = self._settings.get_user().name or "Authority"
                actor = _git().Actor(author_name, "authority@localhost")
                info = _commit_info(repo.index.commit(message, author=actor, committer=actor))
                status = self._read_status(repo)
            except _git().GitCommandError as exc:
                raise self._git_error("Couldn't commit.", exc) from exc
            finally:
                repo.close()

        self._hub.emit(book_id, "git-status", status.model_dump())
        return info

    async def push(self, book_id: str) -> RemoteResult:
        return await self._remote_op(book_id, "push")

    async def pull(self, book_id: str) -> RemoteResult:
        return await self._remote_op(book_id, "pull")

    async def _remote_op(self, book_id: str, op: str) -> RemoteResult:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            repo = self._open(book_id)
            try:
                if not repo.remotes:
                    raise ApiError(422, "This book has no remote configured.", {"code": "no-remote"})
                summary = repo.git.push() if op == "push" else repo.git.pull()
                status = self._read_status(repo)
            except _git().GitCommandError as exc:
                # Pass git's own words through — Authority never resolves
                # conflicts, it hands off honestly (doc 04 §13).
                raise self._git_error(f"Couldn't {op}. Resolve with your git tooling.", exc) from exc
            finally:
                repo.close()

        self._hub.emit(book_id, "git-status", status.model_dump())
        return RemoteResult(ok=True, summary=(summary or "").strip() or f"{op} complete")

    # ---- suggest-message ----------------------------------------------------

    async def suggest_message(self, book_id: str) -> SuggestedMessage:
        repo = self._open(book_id)
        try:
            staged = repo.git.diff("--cached")
            if not staged.strip():
                raise ApiError(422, "Nothing is staged to describe.", {"code": "nothing-staged"})
            name_status = repo.git.diff("--cached", "--name-status")
        finally:
            repo.close()

        fallback = SuggestedMessage(message=_stats_message(name_status), fromStats=True)

        cfg = self._settings.get_utility_model()
        if cfg is None:
            return fallback

        try:
            from app.api.deps import get_ai_orchestrator

            orch = get_ai_orchestrator()
            assembler = ContextAssembler()
            messages = assembler.for_once(_SUGGEST_PROMPT + _truncate_diff(staged))
            text = await orch.invoke_once(cfg, messages, timeout=_SUGGEST_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 — the author still gets a message
            log.warning("suggest-message fell back to stats: %s", exc)
            return fallback

        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        if not lines:
            return fallback
        return SuggestedMessage(message=lines[0].strip("\"'"))

    # ---- internals ----------------------------------------------------------

    def _open(self, book_id: str) -> Any:
        """Open the book's repo. 404 if the folder lost its ``.git``."""
        book_dir: Path = self._registry.get(book_id).book_dir  # 404 if book unknown
        if not (book_dir / ".git").exists():
            raise not_found("book-git", book_id)

        try:
            return _git().Repo(book_dir)
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001 — corrupt/unreadable repo
            raise ApiError(500, "Couldn't open this book's git repository.", {"reason": str(exc)}) from exc

    def _read_status(self, repo: Any) -> GitStatus:
        # -uall expands untracked *directories* into their individual files.
        # Without it git prints one line per directory (".trash/"), so a folder
        # of five new scenes would read as "1-new" — and the count would then
        # jump the moment it was staged, because staging expands it. The badge
        # must mean the same thing before and after staging.
        raw = repo.git.status("--porcelain", "-uall")
        parsed = (_parse_porcelain_line(line) for line in raw.splitlines())
        files = [f for f in parsed if f is not None]
        ahead, behind = _ahead_behind(repo)
        return GitStatus(
            dirty=bool(files),
            files=files,
            ahead=ahead,
            behind=behind,
            hasRemote=bool(repo.remotes),
            branch=_branch_name(repo),
            summary=_summarize(files),
        )

    def _staged_paths(self, repo: Any) -> list[str]:
        return [line for line in repo.git.diff("--cached", "--name-only").splitlines() if line.strip()]

    def _git_error(self, message: str, exc: Exception) -> ApiError:
        detail = getattr(exc, "stderr", "") or str(exc)
        return ApiError(422, message, {"gitError": str(detail).strip()})


# ---- module helpers ---------------------------------------------------------


def _commit_info(commit: Any) -> CommitInfo:
    raw = commit.message or ""
    first_line = raw.strip().splitlines()[0] if raw.strip() else ""
    return CommitInfo(
        hash=commit.hexsha,
        message=first_line,
        timestamp=datetime.fromtimestamp(commit.committed_date, tz=timezone.utc).isoformat(),
    )


def _looks_binary(diff_text: str) -> bool:
    return "Binary files" in diff_text or "GIT binary patch" in diff_text


def _untracked_diff(book_dir: Path, path: str) -> GitDiff:
    """Render a new, never-committed file as an all-additions diff."""
    try:
        raw = (book_dir / path).read_bytes()
    except OSError:
        return GitDiff(path=path, diff="")

    if b"\0" in raw[:8000]:
        return GitDiff(path=path, binary=True)

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    header = f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n"
    return GitDiff(path=path, diff=header + "\n".join("+" + line for line in lines))


def _unquote(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        return path[1:-1]
    return path


def _parse_porcelain_line(line: str) -> GitFile | None:
    """Parse one ``git status --porcelain`` line into a GitFile.

    ``XY PATH`` — X is the index (staged) state, Y the working-tree state.
    ``staged`` means *fully* staged: the index differs from HEAD **and** nothing
    is left unstaged, so a ticked box in the UI honestly means "all of this file
    goes into the next commit". A partially-staged file (``MM``) reads as
    unstaged, because committing it would not capture what's on disk.
    """
    if len(line) < 3:
        return None

    x, y, rest = line[0], line[1], line[3:]

    if x == "?" and y == "?":
        return GitFile(path=_unquote(rest), status="untracked", staged=False)

    path = rest.split("->")[-1] if "->" in rest else rest  # renames: "old -> new"
    code = y if y != " " else x
    return GitFile(
        path=_unquote(path),
        status=_STATUS_CODES.get(code, "modified"),
        staged=x not in " ?" and y == " ",
    )


def _branch_name(repo: Any) -> str:
    """The current branch. Detached HEAD → the short sha, which is what the
    author would see in their own git; empty repo → the default branch name."""
    try:
        return repo.active_branch.name
    except TypeError:  # detached HEAD
        try:
            return repo.head.commit.hexsha[:7]
        except Exception:  # noqa: BLE001
            return "detached"
    except Exception:  # noqa: BLE001 — unborn branch (no commits yet)
        try:
            return repo.git.symbolic_ref("--short", "HEAD")
        except Exception:  # noqa: BLE001
            return ""


def _ahead_behind(repo: Any) -> tuple[int, int]:
    """Commits ahead/behind the tracking branch; (0, 0) when there isn't one.

    Note this reads the *last fetched* state of the remote — `behind` only moves
    after a fetch/pull, exactly as it would in the author's own git.
    """
    try:
        branch = repo.active_branch
        tracking = branch.tracking_branch()
        if tracking is None:
            return 0, 0
        ahead = sum(1 for _ in repo.iter_commits(f"{tracking.name}..{branch.name}"))
        behind = sum(1 for _ in repo.iter_commits(f"{branch.name}..{tracking.name}"))
        return ahead, behind
    except Exception:  # noqa: BLE001 — detached HEAD, no commits, or no upstream
        return 0, 0


def _summarize(files: list[GitFile]) -> str:
    """The badge's human roll-up (doc 04 §2.2)."""
    if not files:
        return "all-changes-synced"

    new = sum(1 for f in files if f.status in ("untracked", "added"))
    updated = sum(1 for f in files if f.status in ("modified", "renamed"))
    deleted = sum(1 for f in files if f.status == "deleted")

    segments = [
        f"{count}-{label}"
        for count, label in ((new, "new"), (updated, "updated"), (deleted, "deleted"))
        if count
    ]
    return ", ".join(segments)


def _truncate_diff(diff_text: str) -> str:
    """Cap the diff, keeping the largest per-file hunks (doc 04 §13)."""
    if len(diff_text) <= _DIFF_CHAR_CAP:
        return diff_text

    chunks = ["diff --git" + c for c in diff_text.split("diff --git") if c.strip()]
    chunks.sort(key=len, reverse=True)

    kept: list[str] = []
    budget = _DIFF_CHAR_CAP
    for chunk in chunks:
        if len(chunk) <= budget:
            kept.append(chunk)
            budget -= len(chunk)

    if not kept:  # one enormous file — a prefix beats nothing
        return diff_text[:_DIFF_CHAR_CAP]
    return "".join(kept)


def _stats_message(name_status: str) -> str:
    """Deterministic fallback when no utility model is configured (doc 04 §13)."""
    added = updated = deleted = 0
    for line in name_status.splitlines():
        code = line[:1]
        if code == "A":
            added += 1
        elif code == "D":
            deleted += 1
        elif code:
            updated += 1

    parts = [f"{n} {label}" for n, label in ((updated, "updated"), (added, "added"), (deleted, "deleted")) if n]
    if not parts:
        return "Update manuscript"

    total = added + updated + deleted
    return f"{', '.join(parts)} ({total} {'file' if total == 1 else 'files'})"
