"""Hardened atomic write (doc 03 §2).

serialize → temp file in the same directory → flush + fsync → os.replace over
the original (atomic on POSIX and Windows). On POSIX the directory handle is
fsynced too, so the rename survives power loss. The deprecated ``atomicwrites``
package is deliberately not used.

``atomic_write_bytes`` is the primitive; text and JSON encode down to it, so the
fsync/replace sequence exists in exactly one place. Binary matters for uploaded
book resources, which are arbitrary files rather than serialized documents.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    # POSIX: fsync the directory so the rename itself is durable. os.O_DIRECTORY
    # does not exist on Windows, where directory fsync is neither needed nor allowed.
    if hasattr(os, "O_DIRECTORY"):
        dir_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
