"""BookScanner (doc 04 §1.3, §4).

There is **no bookshelf registry** (doc 03): the shelf is a live scan of
books-home for subfolders containing ``config/book.json``. Folders without it
are silently ignored; an unparseable ``book.json`` surfaces as a broken-book
card rather than failing the whole scan. Results are cached and invalidated on
book creation or a books-home change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.errors import ApiError
from app.models.book import BookConfig, BookSummary
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.books")

_COVER_STEM = "cover"


def _books_home_unset() -> ApiError:
    return ApiError(422, "Books home isn't set.", {"code": "books-home-unset"})


def _find_cover(book_dir: Path) -> Path | None:
    assets = book_dir / "assets"
    if not assets.is_dir():
        return None
    for entry in assets.iterdir():
        if entry.is_file() and entry.stem == _COVER_STEM:
            return entry
    return None


class BookScanner:
    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings
        # Cache keyed on (booksHome, dir mtime): a folder added/removed in
        # books-home bumps its mtime, so discovered books appear next scan.
        self._cache: tuple[str, int, list[BookSummary]] | None = None

    def invalidate(self) -> None:
        self._cache = None

    def books_home(self) -> Path:
        raw = self._settings.get_user().booksHome
        if not raw:
            raise _books_home_unset()
        return Path(raw)

    def list_books(self) -> list[BookSummary]:
        home = self.books_home()
        key = str(home)
        mtime = home.stat().st_mtime_ns if home.is_dir() else 0
        if self._cache and self._cache[0] == key and self._cache[1] == mtime:
            return self._cache[2]

        summaries: list[BookSummary] = []
        if home.is_dir():
            for entry in sorted(home.iterdir()):
                summary = self._scan_one(entry)
                if summary is not None:
                    summaries.append(summary)

        self._cache = (key, mtime, summaries)
        return summaries

    def _scan_one(self, book_dir: Path) -> BookSummary | None:
        if not book_dir.is_dir():
            return None
        config_file = book_dir / "config" / "book.json"
        if not config_file.is_file():
            return None  # not a book folder — silently ignored

        has_cover = _find_cover(book_dir) is not None
        try:
            raw = json.loads(config_file.read_text(encoding="utf-8"))
            config = BookConfig.model_validate(raw)
        except Exception as exc:  # broken/hand-edited book.json → broken card
            log.error("Unparseable book.json in %s: %s", book_dir.name, exc)
            return BookSummary(
                id=book_dir.name,
                title=book_dir.name,
                folderName=book_dir.name,
                hasCover=has_cover,
                error=True,
            )

        return BookSummary(
            id=config.id,
            title=config.title,
            folderName=book_dir.name,
            hasCover=has_cover,
        )

    def find_book_dir(self, book_id: str) -> Path | None:
        home = self.books_home()
        if not home.is_dir():
            return None
        for entry in sorted(home.iterdir()):
            config_file = entry / "config" / "book.json"
            if not config_file.is_file():
                continue
            try:
                raw = json.loads(config_file.read_text(encoding="utf-8"))
                if raw.get("id") == book_id:
                    return entry
            except Exception:
                continue
        return None

    def cover_path(self, book_id: str) -> Path | None:
        book_dir = self.find_book_dir(book_id)
        if book_dir is None:
            return None
        return _find_cover(book_dir)
