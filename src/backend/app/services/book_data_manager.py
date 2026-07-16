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
from app.core.event_hub import EventHub
from app.models.book import Book, BookConfig, Chapter, Part
from app.models.character import CharacterRecord, CharacterRelationship
from app.models.conversation import Conversation, ConversationSummary
from app.models.enums import ProposalStatus
from app.models.job import Job
from app.models.plotline import PlotlineRecord
from app.models.scene import SceneRecord, SoftRelationship
from app.services.book_scanner import _find_cover

log = logging.getLogger("authority.books")


class BookDataManager:
    def __init__(self, book_dir: Path, book_id: str | None = None, hub: EventHub | None = None) -> None:
        self._dir = book_dir
        self._book_id = book_id
        self._hub = hub
        self._lock = asyncio.Lock()
        self._config: BookConfig | None = None
        self._scenes: list[SceneRecord] | None = None
        self._relationships: list[SoftRelationship] | None = None
        self._parts: list[Part] | None = None
        self._chapters: list[Chapter] | None = None
        self._plotlines: list[PlotlineRecord] | None = None
        self._characters: list[CharacterRecord] | None = None
        self._character_relationships: list[CharacterRelationship] | None = None
        self._jobs: list[Job] | None = None
        self._conversation_index: list[ConversationSummary] | None = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def book_dir(self) -> Path:
        return self._dir

    def _changed(self) -> None:
        """Signal that something in this book's folder was written.

        Payload-free and fire-and-forget: every mutating service already funnels
        its writes through this class, so this one call is the whole integration
        point for post-write reactions — no service needs its own hook. Today the
        only consumer is the git-status worker, which re-checks git after a
        debounce (doc 07 §25); git deliberately never runs on the write path.
        """
        if self._hub is not None and self._book_id is not None:
            self._hub.emit(self._book_id, "book-changed", {})

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
        self._changed()

    def save_relationships(self, relationships: list[SoftRelationship]) -> None:
        atomic_write_json(
            self._dir / "db" / "relationships.json", [r.model_dump(mode="json") for r in relationships]
        )
        self._relationships = relationships
        self._changed()

    # ---- parts / chapters / plotlines (doc 03) --------------------------------

    def get_parts(self) -> list[Part]:
        if self._parts is None:
            self._parts = self._load_collection("parts.json", Part)
        return self._parts

    def save_parts(self, parts: list[Part]) -> None:
        atomic_write_json(self._dir / "db" / "parts.json", [p.model_dump(mode="json") for p in parts])
        self._parts = parts
        self._changed()

    def get_chapters(self) -> list[Chapter]:
        if self._chapters is None:
            self._chapters = self._load_collection("chapters.json", Chapter)
        return self._chapters

    def save_chapters(self, chapters: list[Chapter]) -> None:
        atomic_write_json(self._dir / "db" / "chapters.json", [c.model_dump(mode="json") for c in chapters])
        self._chapters = chapters
        self._changed()

    def get_plotlines(self) -> list[PlotlineRecord]:
        if self._plotlines is None:
            self._plotlines = self._load_collection("plotlines.json", PlotlineRecord)
        return self._plotlines

    def save_plotlines(self, plotlines: list[PlotlineRecord]) -> None:
        atomic_write_json(self._dir / "db" / "plotlines.json", [p.model_dump(mode="json") for p in plotlines])
        self._plotlines = plotlines
        self._changed()

    def get_characters(self) -> list[CharacterRecord]:
        if self._characters is None:
            self._characters = self._load_collection("characters.json", CharacterRecord)
        return self._characters

    def save_characters(self, characters: list[CharacterRecord]) -> None:
        atomic_write_json(self._dir / "db" / "characters.json", [c.model_dump(mode="json") for c in characters])
        self._characters = characters
        self._changed()

    def get_character_relationships(self) -> list[CharacterRelationship]:
        if self._character_relationships is None:
            self._character_relationships = self._load_collection(
                "character_relationships.json", CharacterRelationship
            )
        return self._character_relationships

    def save_character_relationships(self, relationships: list[CharacterRelationship]) -> None:
        atomic_write_json(
            self._dir / "db" / "character_relationships.json",
            [r.model_dump(mode="json") for r in relationships],
        )
        self._character_relationships = relationships
        self._changed()

    def save_config(self) -> None:
        """Persist the in-memory config back to disk."""
        if self._config is not None:
            atomic_write_json(self._config_path(), self._config.model_dump(mode="json"))
            self._changed()

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
        # ui.json is tracked like everything else in the book folder, so this
        # really does dirty the repo — say so rather than letting the badge and
        # the 10s poll disagree.
        self._changed()
        return merged

    # ---- jobs (doc 03 db/jobs.json) ----------------------------------------

    def get_jobs(self) -> list[Job]:
        if self._jobs is None:
            self._jobs = self._load_collection("jobs.json", Job)
        return self._jobs

    def save_jobs(self, jobs: list[Job]) -> None:
        atomic_write_json(self._dir / "db" / "jobs.json", [j.model_dump(mode="json") for j in jobs])
        self._jobs = jobs
        self._changed()

    # ---- conversations (doc 03 db/conversations/) --------------------------

    def _conversations_dir(self) -> Path:
        path = self._dir / "db" / "conversations"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _conversation_path(self, conversation_id: str) -> Path:
        return self._conversations_dir() / f"{conversation_id}.json"

    def _index_path(self) -> Path:
        return self._conversations_dir() / "index.json"

    @staticmethod
    def _summary_from_conversation(conv: Conversation) -> ConversationSummary:
        pending = sum(
            1
            for m in conv.messages
            for p in m.proposals
            if p.status == ProposalStatus.pending
        )
        return ConversationSummary(
            id=conv.id,
            kind=conv.kind,
            title=conv.title,
            parentType=conv.parentType,
            parentId=conv.parentId,
            status=conv.status,
            updatedAt=conv.updatedAt,
            messageCount=len(conv.messages),
            pendingProposals=pending,
        )

    def get_conversation_index(self) -> list[ConversationSummary]:
        if self._conversation_index is not None:
            return self._conversation_index
        path = self._index_path()
        if not path.exists():
            self._conversation_index = self.rebuild_conversation_index()
            return self._conversation_index
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._conversation_index = [ConversationSummary.model_validate(row) for row in raw]
            return self._conversation_index
        except Exception as exc:
            log.warning("conversation index corrupt (%s); rebuilding", exc)
            self._conversation_index = self.rebuild_conversation_index()
            return self._conversation_index

    def rebuild_conversation_index(self) -> list[ConversationSummary]:
        """Scan cnv-*.json files and rewrite index.json (doc 03 derived index)."""
        summaries: list[ConversationSummary] = []
        for path in sorted(self._conversations_dir().glob("cnv-*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                conv = Conversation.model_validate(raw)
                summaries.append(self._summary_from_conversation(conv))
            except Exception as exc:
                log.warning("skipping unreadable conversation %s: %s", path.name, exc)
        summaries.sort(key=lambda s: s.updatedAt, reverse=True)
        atomic_write_json(self._index_path(), [s.model_dump(mode="json") for s in summaries])
        self._conversation_index = summaries
        return summaries

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        path = self._conversation_path(conversation_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return Conversation.model_validate(raw)
        except Exception as exc:
            self._quarantine(path, exc)
            raise

    def save_conversation(self, conv: Conversation) -> None:
        path = self._conversation_path(conv.id)
        atomic_write_json(path, conv.model_dump(mode="json"))
        # Refresh index entry.
        index = list(self.get_conversation_index())
        summary = self._summary_from_conversation(conv)
        index = [s for s in index if s.id != conv.id]
        index.append(summary)
        index.sort(key=lambda s: s.updatedAt, reverse=True)
        atomic_write_json(self._index_path(), [s.model_dump(mode="json") for s in index])
        self._conversation_index = index
        self._changed()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Remove conversation file + index entry. Returns False if missing."""
        path = self._conversation_path(conversation_id)
        if not path.exists():
            return False
        path.unlink(missing_ok=True)
        index = [s for s in self.get_conversation_index() if s.id != conversation_id]
        atomic_write_json(self._index_path(), [s.model_dump(mode="json") for s in index])
        self._conversation_index = index
        self._changed()
        return True

    def list_conversations_for_parent(
        self, parent_type: str, parent_id: str
    ) -> list[ConversationSummary]:
        return [
            s
            for s in self.get_conversation_index()
            if s.parentType.value == parent_type and s.parentId == parent_id
        ]

    def find_proposal(self, proposal_id: str) -> tuple[Conversation, int, int] | None:
        """Locate a proposal via the index → conversation files.

        Returns (conversation, message_index, proposal_index) or None.
        """
        for summary in self.get_conversation_index():
            if summary.pendingProposals == 0 and summary.messageCount == 0:
                continue
            conv = self.get_conversation(summary.id)
            if conv is None:
                continue
            for mi, msg in enumerate(conv.messages):
                for pi, prop in enumerate(msg.proposals):
                    if prop.id == proposal_id:
                        return conv, mi, pi
        # Full scan fallback (resolved proposals still findable).
        for path in self._conversations_dir().glob("cnv-*.json"):
            conv = self.get_conversation(path.stem)
            if conv is None:
                continue
            for mi, msg in enumerate(conv.messages):
                for pi, prop in enumerate(msg.proposals):
                    if prop.id == proposal_id:
                        return conv, mi, pi
        return None

    # ---- scene file helpers -------------------------------------------------

    def scene_file_path(self, rel_path: str) -> Path:
        return self._dir / rel_path

    def read_scene_content(self, rel_path: str) -> str:
        path = self._dir / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else ""
