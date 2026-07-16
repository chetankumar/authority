"""BookDataManager (doc 04 §1.3) — one per open book.

The book's in-memory owner: loads ``config/book.json`` (and, in later phases,
``db/*.json``) into memory, owns the book's **asyncio mutation lock**, and is
the single write-through point for the book folder. This first increment loads
the config and serves the read-only book context; scene/db collections land
with the Scenes phase.

Load-time safety (doc 03 §Data safety): a config that fails to parse is never
overwritten — it is quarantined to ``book.json.corrupt-{ts}`` and the load
raises a clear error rather than silently resetting the book.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.core.atomic import atomic_write_json
from app.core.errors import ApiError
from app.models.book import Book, BookConfig, Chapter, Part
from app.models.plotline import PlotlineRecord
from app.models.scene import SceneRecord, SoftRelationship
from app.services.book_scanner import _find_cover

log = logging.getLogger("authority.books")


class BookDataManager:
    def __init__(self, book_dir: Path) -> None:
        self._dir = book_dir
        self._lock = asyncio.Lock()
        self._config: BookConfig | None = None
        self._scenes: list[SceneRecord] | None = None
        self._relationships: list[SoftRelationship] | None = None
        self._parts: list[Part] | None = None
        self._chapters: list[Chapter] | None = None
        self._plotlines: list[PlotlineRecord] | None = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def book_dir(self) -> Path:
        return self._dir

    def _config_path(self) -> Path:
        return self._dir / "config" / "book.json"

    def _load(self) -> BookConfig:
        if self._config is not None:
            return self._config

        path = self._config_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            config = BookConfig.model_validate(raw)
        except Exception as exc:  # never overwrite; quarantine + surface
            quarantine = path.with_name(f"book.json.corrupt-{int(time.time())}")
            try:
                path.replace(quarantine)
                log.error("book.json in %s failed to load (%s); quarantined to %s", self._dir.name, exc, quarantine)
            except OSError:
                log.error("book.json in %s failed to load (%s); quarantine failed", self._dir.name, exc)
            raise ApiError(422, "This book's config couldn't be read.", {"code": "book-unreadable"}) from exc

        self._config = config
        return config

    def get_book(self) -> Book:
        config = self._load()
        parts = sorted(self.get_parts(), key=lambda p: p.seq)
        chapters = sorted(self.get_chapters(), key=lambda c: c.seq)
        return Book(
            id=config.id,
            title=config.title,
            hasCover=_find_cover(self._dir) is not None,
            systemPrompt=config.systemPrompt,
            storySummary=config.storySummary,
            bookkeeping=config.bookkeeping,
            parts=parts,
            chapters=chapters,
        )

    @property
    def config(self) -> BookConfig:
        return self._load()

    # ---- db collections (doc 03) --------------------------------------------

    def _quarantine(self, path: Path, exc: Exception) -> None:
        """Never overwrite a file that failed to parse; move it aside and surface
        (doc 03 §Data safety, layer 4)."""
        target = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        try:
            path.replace(target)
            log.error("%s in %s failed to load (%s); quarantined to %s", path.name, self._dir.name, exc, target)
        except OSError:
            log.error("%s in %s failed to load (%s); quarantine failed", path.name, self._dir.name, exc)
        raise ApiError(422, "This book's data couldn't be read.", {"code": "data-unreadable", "file": path.name})

    def _load_collection(self, name: str, model: type) -> list:
        path = self._dir / "db" / name
        try:
            raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            return [model.model_validate(row) for row in raw]
        except Exception as exc:  # quarantine + surface
            self._quarantine(path, exc)
            raise  # unreachable; _quarantine always raises

    def get_scenes(self) -> list[SceneRecord]:
        if self._scenes is None:
            self._scenes = self._load_collection("scenes.json", SceneRecord)
        return self._scenes

    def get_relationships(self) -> list[SoftRelationship]:
        if self._relationships is None:
            self._relationships = self._load_collection("relationships.json", SoftRelationship)
        return self._relationships

    def save_scenes(self, scenes: list[SceneRecord]) -> None:
        atomic_write_json(self._dir / "db" / "scenes.json", [s.model_dump(mode="json") for s in scenes])
        self._scenes = scenes

    def save_relationships(self, relationships: list[SoftRelationship]) -> None:
        atomic_write_json(
            self._dir / "db" / "relationships.json", [r.model_dump(mode="json") for r in relationships]
        )
        self._relationships = relationships

    # ---- parts / chapters / plotlines (doc 03) --------------------------------

    def get_parts(self) -> list[Part]:
        if self._parts is None:
            self._parts = self._load_collection("parts.json", Part)
        return self._parts

    def save_parts(self, parts: list[Part]) -> None:
        atomic_write_json(self._dir / "db" / "parts.json", [p.model_dump(mode="json") for p in parts])
        self._parts = parts

    def get_chapters(self) -> list[Chapter]:
        if self._chapters is None:
            self._chapters = self._load_collection("chapters.json", Chapter)
        return self._chapters

    def save_chapters(self, chapters: list[Chapter]) -> None:
        atomic_write_json(self._dir / "db" / "chapters.json", [c.model_dump(mode="json") for c in chapters])
        self._chapters = chapters

    def get_plotlines(self) -> list[PlotlineRecord]:
        if self._plotlines is None:
            self._plotlines = self._load_collection("plotlines.json", PlotlineRecord)
        return self._plotlines

    def save_plotlines(self, plotlines: list[PlotlineRecord]) -> None:
        atomic_write_json(self._dir / "db" / "plotlines.json", [p.model_dump(mode="json") for p in plotlines])
        self._plotlines = plotlines

    def save_config(self) -> None:
        """Persist the in-memory config back to disk."""
        if self._config is not None:
            atomic_write_json(self._config_path(), self._config.model_dump(mode="json"))

    # ---- ui.json (client-owned shape, doc 04 §4) ----------------------------

    def get_ui(self) -> dict[str, Any]:
        path = self._dir / "db" / "ui.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}

    def merge_ui(self, patch: dict[str, Any]) -> dict[str, Any]:
        merged = {**self.get_ui(), **patch}
        atomic_write_json(self._dir / "db" / "ui.json", merged)
        return merged

    # ---- scene file helpers -------------------------------------------------

    def scene_file_path(self, rel_path: str) -> Path:
        return self._dir / rel_path

    def read_scene_content(self, rel_path: str) -> str:
        path = self._dir / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else ""
