"""BookRegistry — resolves and caches one BookDataManager per open book.

"First request naming a book triggers load" (doc 04 §4): the registry maps a
``bok-`` id to its folder via BookScanner, constructs the manager on demand, and
holds it so subsequent requests reuse the in-memory state. A missing id → 404.
"""

from __future__ import annotations

from app.core.errors import not_found
from app.services.book_data_manager import BookDataManager
from app.services.book_scanner import BookScanner


class BookRegistry:
    def __init__(self, scanner: BookScanner) -> None:
        self._scanner = scanner
        self._managers: dict[str, BookDataManager] = {}

    def get(self, book_id: str) -> BookDataManager:
        cached = self._managers.get(book_id)
        if cached is not None:
            return cached

        book_dir = self._scanner.find_book_dir(book_id)
        if book_dir is None:
            raise not_found("book", book_id)

        manager = BookDataManager(book_dir)
        self._managers[book_id] = manager
        return manager

    def forget(self, book_id: str) -> None:
        """Drop a cached manager (e.g. after a folder rename/delete)."""
        self._managers.pop(book_id, None)
