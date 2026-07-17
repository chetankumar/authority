"""ResourceService (doc 04 §Resources) — files the author parks beside the book.

Research PDFs, reference images, worldbuilding notes: material that surrounds the
novel without being the novel. They live in the book folder's ``resources/`` and
travel with it.

**Scanned, never indexed.** There is no ``db/resources.json`` and no id — the
filename is the key and ``resources/`` is read fresh on every list. This follows
``BookScanner``, which discovers the entire shelf by folder scan for exactly the
same reason (doc 01 hard rule 4: a book folder can be zipped, cloned, or moved).
Drop a file in by hand and it appears; an index would be a second source of truth
with nothing to reconcile it.

The module-level helpers below are pure and take a ``book_dir``, so the AI read
tools can reach resources without the tool registry having to inject this
service. Only the class touches the book lock.

AI cannot write here directly. ``propose_resource_create`` emits a proposal; the
author accepts it and ``ProposalService`` calls ``create_text_file``. That is
doc 01's "AI proposes → author confirms" row — a resource file is neither prose
(hard rule 1) nor bookkeeping (the one standing-consent carve-out).
"""

from __future__ import annotations

import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.atomic import atomic_write_bytes
from app.core.errors import not_found, validation
from app.models.resource import ResourceFile
from app.services.book_registry import BookRegistry

# Nothing else in the codebase caps an upload; an unbounded one would be read
# fully into memory by the router (as the book cover already is).
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# What the AI may read back as text. Everything else is listed but opaque to it.
_TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}

# A whole resource is pasted into the model's context; a runaway file would eat
# the window before the author's actual question got there.
MAX_TEXT_READ_CHARS = 100_000


def _now_from(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resources_dir(book_dir: Path) -> Path:
    """The book's ``resources/``, created on demand.

    Books scaffolded before this feature have no such folder, so every entry
    point mkdirs rather than assuming the scaffold ran.
    """
    path = book_dir / "resources"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_resource_path(book_dir: Path, filename: str) -> Path:
    """Resolve ``filename`` inside ``resources/`` or raise 422.

    The filename arrives from a URL path segment or from the model, so it is
    hostile input. Separators are rejected outright rather than stripped: a
    caller asking for ``../config/book.json`` has made a mistake worth
    surfacing, not one worth silently reinterpreting as ``book.json``.
    """
    name = filename.strip()
    if not name:
        raise validation({"filename": "Name the file."})
    if any(ch in name for ch in ("/", "\\", "\x00")) or name in {".", ".."}:
        raise validation({"filename": "A file name only — no folders or path steps."})
    if name.startswith("."):
        # Dotfiles are skipped by the scan, so accepting one would write a file
        # that never shows up in the list.
        raise validation({"filename": "Names starting with a dot are reserved."})

    root = resources_dir(book_dir).resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise validation({"filename": "That name escapes the resources folder."})
    return path


def is_text_resource(filename: str) -> bool:
    return Path(filename).suffix.lower() in _TEXT_EXTENSIONS


def scan_resources(book_dir: Path) -> list[ResourceFile]:
    """List ``resources/`` newest first. The only source of truth."""
    files: list[ResourceFile] = []
    for entry in resources_dir(book_dir).iterdir():
        if not entry.is_file() or entry.name.startswith("."):
            continue
        stat = entry.stat()
        files.append(
            ResourceFile(
                filename=entry.name,
                mimeType=mimetypes.guess_type(entry.name)[0] or "application/octet-stream",
                sizeBytes=stat.st_size,
                updatedAt=_now_from(stat.st_mtime),
            )
        )
    files.sort(key=lambda f: f.updatedAt, reverse=True)
    return files


def _free_name(root: Path, filename: str) -> str:
    """``notes.md`` → ``notes-2.md`` when taken. Never returns a name in use.

    Uploads and accepted proposals both land here. Overwriting silently would be
    the one way this feature could destroy the author's data, so a collision
    always yields a new file and leaves the original alone — the same instinct as
    ``move_scene_folder_to_trash``'s suffixing.
    """
    if not (root / filename).exists():
        return filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while (root / f"{stem}-{n}{suffix}").exists():
        n += 1
    return f"{stem}-{n}{suffix}"


def _describe(path: Path) -> ResourceFile:
    stat = path.stat()
    return ResourceFile(
        filename=path.name,
        mimeType=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        sizeBytes=stat.st_size,
        updatedAt=_now_from(stat.st_mtime),
    )


class ResourceService:
    def __init__(self, registry: BookRegistry) -> None:
        self._registry = registry

    # ---- reads (no lock) -----------------------------------------------------

    def list(self, book_id: str) -> list[ResourceFile]:
        return scan_resources(self._registry.get(book_id).book_dir)

    def path_for(self, book_id: str, filename: str) -> Path:
        """Validated on-disk path for serving a download. 404 when absent."""
        path = safe_resource_path(self._registry.get(book_id).book_dir, filename)
        if not path.is_file():
            raise not_found("resource", filename)
        return path

    def read_text(self, book_id: str, filename: str) -> str:
        path = self.path_for(book_id, filename)
        if not is_text_resource(filename):
            raise validation({"filename": "That file is not text."})
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_TEXT_READ_CHARS:
            return text[:MAX_TEXT_READ_CHARS] + "\n\n[truncated]"
        return text

    # ---- mutations (under the book lock) --------------------------------------

    async def upload(self, book_id: str, filename: str, data: bytes) -> ResourceFile:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            if len(data) > MAX_UPLOAD_BYTES:
                raise validation(
                    {"file": f"Files must be under {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."}
                )
            # Browsers may send a path; keep the leaf, then validate it properly.
            name = Path(filename or "").name
            safe_resource_path(mgr.book_dir, name)
            root = resources_dir(mgr.book_dir)
            path = root / _free_name(root, name)
            atomic_write_bytes(path, data)
            mgr.notify_changed()
            return _describe(path)

    async def create_text_file(self, book_id: str, filename: str, content: str) -> ResourceFile:
        """The accepted-proposal path. Same rules as an upload."""
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            safe_resource_path(mgr.book_dir, filename)
            root = resources_dir(mgr.book_dir)
            path = root / _free_name(root, filename)
            atomic_write_bytes(path, content.encode("utf-8"))
            mgr.notify_changed()
            return _describe(path)

    async def delete(self, book_id: str, filename: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            path = safe_resource_path(mgr.book_dir, filename)
            if not path.is_file():
                raise not_found("resource", filename)
            # Never unlink — the same rule scene deletion follows. The author can
            # always get the file back out of .trash/ (or out of git).
            trash = mgr.book_dir / ".trash"
            trash.mkdir(exist_ok=True)
            target = trash / path.name
            if target.exists():
                target = trash / f"{path.stem}-{int(datetime.now(timezone.utc).timestamp())}{path.suffix}"
            shutil.move(str(path), str(target))
            mgr.notify_changed()
