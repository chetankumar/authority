"""BookService (doc 04 §1.3, §4).

Owns book creation: slug + id, folder scaffold, empty db seeds, optional cover,
``git init`` + initial commit. The folder is fresh by construction, so init
never touches an existing repo. Any failure mid-scaffold rolls the folder back
so a half-created book never lands on the shelf.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import shutil
from pathlib import Path

from app.core.atomic import atomic_write_json, atomic_write_text
from app.core.errors import ApiError, validation
from app.models.book import BookConfig, BookSummary
from app.services.book_scanner import BookScanner
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.books")

# db/*.json collections seeded empty on creation (doc 03).
# relationships.json / dependencies.json are NOT seeded here — those are
# superseded by per-scene scenes/{id}/relationships.json + dependencies.json
# (doc 03); a fresh book has no scenes yet, so there's nothing to seed, and
# BookDataManager's migration path only runs for books that already have the
# old flat files.
_EMPTY_ARRAY_FILES = (
    "scenes.json",
    "characters.json",
    "character_relationships.json",
    "plotlines.json",
    "todos.json",
    "parts.json",
    "chapters.json",
)

_CONTENT_TYPE_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def slugify(title: str) -> str:
    """Lowercase, ASCII-ish, hyphen-separated; safe as a folder name."""
    text = title.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    text = text[:60].strip("-")
    return text or "untitled"


def _cover_ext(filename: str | None, content_type: str | None) -> str:
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix:
            return suffix
    return _CONTENT_TYPE_EXT.get((content_type or "").lower(), ".png")


class BookService:
    def __init__(self, settings: SettingsService, scanner: BookScanner) -> None:
        self._settings = settings
        self._scanner = scanner
        self._lock = asyncio.Lock()

    async def create_book(
        self,
        title: str,
        cover_bytes: bytes | None = None,
        cover_filename: str | None = None,
        cover_content_type: str | None = None,
    ) -> BookSummary:
        title = title.strip()
        if not title:
            raise validation({"title": "Give the book a title."})

        home = self._scanner.books_home()  # 422 if unset
        try:
            home.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ApiError(403, "Books home isn't writable.", {"path": str(home)}) from exc

        async with self._lock:
            book_id, folder_name, book_dir = self._reserve_folder(home, title)
            try:
                self._scaffold(book_dir, book_id, title, cover_bytes, cover_filename, cover_content_type)
                self._git_init(book_dir)
            except ApiError:
                shutil.rmtree(book_dir, ignore_errors=True)
                raise
            except Exception as exc:  # noqa: BLE001 — clean up then surface
                shutil.rmtree(book_dir, ignore_errors=True)
                log.error("Book creation failed for %s: %s", folder_name, exc)
                raise ApiError(500, "Couldn't create the book.", {"reason": str(exc)}) from exc

            self._scanner.invalidate()
            return BookSummary(
                id=book_id,
                title=title,
                folderName=folder_name,
                hasCover=cover_bytes is not None,
            )

    def _reserve_folder(self, home: Path, title: str) -> tuple[str, str, Path]:
        slug = slugify(title)
        for _ in range(10):
            hex6 = secrets.token_hex(3)
            folder_name = f"{hex6}-{slug}"
            book_dir = home / folder_name
            if not book_dir.exists():
                return f"bok-{hex6}", folder_name, book_dir
        raise ApiError(409, "Couldn't allocate a unique book folder.", {"code": "already-exists"})

    def _scaffold(
        self,
        book_dir: Path,
        book_id: str,
        title: str,
        cover_bytes: bytes | None,
        cover_filename: str | None,
        cover_content_type: str | None,
    ) -> None:
        (book_dir / "config").mkdir(parents=True)
        (book_dir / "scenes").mkdir()
        (book_dir / "db" / "conversations").mkdir(parents=True)
        (book_dir / "assets").mkdir()
        (book_dir / "resources").mkdir()
        (book_dir / "compiled-book").mkdir()

        config = BookConfig(id=book_id, title=title)
        atomic_write_json(book_dir / "config" / "book.json", config.model_dump())

        for name in _EMPTY_ARRAY_FILES:
            atomic_write_json(book_dir / "db" / name, [])
        atomic_write_json(book_dir / "db" / "ui.json", {})
        atomic_write_json(book_dir / "db" / "conversations" / "index.json", [])

        atomic_write_text(book_dir / "scenes" / ".gitkeep", "")
        atomic_write_text(book_dir / "resources" / ".gitkeep", "")
        atomic_write_text(book_dir / "compiled-book" / ".gitkeep", "")
        atomic_write_text(book_dir / ".gitignore", "*.tmp\n*.mp3\n")

        if cover_bytes is not None:
            ext = _cover_ext(cover_filename, cover_content_type)
            (book_dir / "assets" / f"cover{ext}").write_bytes(cover_bytes)

    def _git_init(self, book_dir: Path) -> None:
        from git import Actor, Repo

        author_name = self._settings.get_user().name or "Authority"
        actor = Actor(author_name, "authority@localhost")

        repo = Repo.init(book_dir)
        try:
            repo.git.add(A=True)
            repo.index.commit("initialized", author=actor, committer=actor)
        finally:
            # Release GitPython's persistent helper processes; on Windows a held
            # handle would otherwise block the later folder rename/delete.
            repo.close()
