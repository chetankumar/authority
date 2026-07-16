"""Git schemas (doc 04 §2.2, §13).

The working tree is the source of truth — nothing here is persisted. ``summary``
is the human roll-up the top-bar badge renders; it is built by ``GitService`` so
that every producer of a :class:`GitStatus` (the request path and the debounced
git-status worker alike) phrases it identically.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GitFileStatus = Literal["modified", "added", "deleted", "untracked", "renamed"]


class GitFile(BaseModel):
    path: str
    status: GitFileStatus
    staged: bool


class GitStatus(BaseModel):
    dirty: bool
    files: list[GitFile] = []
    ahead: int = 0
    behind: int = 0
    hasRemote: bool = False
    branch: str = ""
    summary: str = "all-changes-synced"


class CommitInfo(BaseModel):
    hash: str
    message: str
    timestamp: str


class GitDiff(BaseModel):
    path: str
    diff: str = ""
    binary: bool = False


class SuggestedMessage(BaseModel):
    message: str
    # True when no utility model was configured and the message came from file
    # stats instead — the UI notes the provenance rather than passing it off.
    fromStats: bool = False


class RemoteResult(BaseModel):
    ok: bool = True
    summary: str = ""


# ---- request bodies ---------------------------------------------------------


class StageRequest(BaseModel):
    paths: list[str] | None = None
    all: bool | None = None

    model_config = {"extra": "forbid"}


class CommitRequest(BaseModel):
    message: str

    model_config = {"extra": "forbid"}
