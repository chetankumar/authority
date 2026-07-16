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
import shutil
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
from app.models.scene import Dependency, SceneBookkeeping, SceneMeta, SceneRecord, SoftRelationship
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
        self._scene_meta: dict[str, SceneMeta] | None = None
        self._scene_bookkeeping: dict[str, SceneBookkeeping] | None = None
        self._scene_relationships: dict[str, list[SoftRelationship]] | None = None
        self._scene_dependencies: dict[str, list[Dependency]] | None = None
        self._dependents_index: dict[str, list[Dependency]] | None = None
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
            self._migrate_scenes_if_needed()
            self._scenes = self._load_collection("scenes.json", SceneRecord)
        return self._scenes

    def save_scenes(self, scenes: list[SceneRecord]) -> None:
        atomic_write_json(self._dir / "db" / "scenes.json", [s.model_dump(mode="json") for s in scenes])
        self._scenes = scenes
        self._changed()

    # ---- per-scene folder (scenes/{id}/) ------------------------------------
    #
    # meta.json / bookkeeping.json / dependencies.json / relationships.json hold
    # everything that isn't identity/hard-chain/structure (which stays on the
    # master SceneRecord above). A parse failure in any one of these degrades
    # only that scene — quarantined + defaulted, never raised — unlike the
    # whole-collection quarantine used for db/*.json (doc 03 §Data safety):
    # smaller blast radius is the whole point of this split.

    def _scenes_dir(self) -> Path:
        return self._dir / "scenes"

    def _scene_folder(self, scene_id: str) -> Path:
        return self._scenes_dir() / scene_id

    def _quarantine_scene_file(self, path: Path, exc: Exception) -> None:
        target = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        try:
            path.replace(target)
            log.error(
                "%s failed to load (%s); quarantined to %s — this scene's data degrades to defaults",
                path, exc, target,
            )
        except OSError:
            log.error("%s failed to load (%s); quarantine failed", path, exc)

    def _read_scene_object(self, path: Path, model: type) -> Any:
        if not path.exists():
            return model()
        try:
            return model.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            self._quarantine_scene_file(path, exc)
            return model()

    def _read_scene_list(self, path: Path, model: type) -> list:
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [model.model_validate(row) for row in raw]
        except Exception as exc:
            self._quarantine_scene_file(path, exc)
            return []

    # -- meta ------------------------------------------------------------------

    def _ensure_meta_loaded(self) -> dict[str, SceneMeta]:
        if self._scene_meta is None:
            self._scene_meta = {
                rec.id: self._read_scene_object(self._scene_folder(rec.id) / "meta.json", SceneMeta)
                for rec in self.get_scenes()
            }
        return self._scene_meta

    def get_scene_meta(self, scene_id: str) -> SceneMeta:
        return self._ensure_meta_loaded().get(scene_id, SceneMeta())

    def get_all_meta(self) -> dict[str, SceneMeta]:
        return dict(self._ensure_meta_loaded())

    def save_scene_meta(self, scene_id: str, meta: SceneMeta) -> None:
        atomic_write_json(self._scene_folder(scene_id) / "meta.json", meta.model_dump(mode="json"))
        self._ensure_meta_loaded()[scene_id] = meta
        self._changed()

    # -- bookkeeping -------------------------------------------------------------

    def _ensure_bookkeeping_loaded(self) -> dict[str, SceneBookkeeping]:
        if self._scene_bookkeeping is None:
            self._scene_bookkeeping = {
                rec.id: self._read_scene_object(self._scene_folder(rec.id) / "bookkeeping.json", SceneBookkeeping)
                for rec in self.get_scenes()
            }
        return self._scene_bookkeeping

    def get_scene_bookkeeping(self, scene_id: str) -> SceneBookkeeping:
        return self._ensure_bookkeeping_loaded().get(scene_id, SceneBookkeeping())

    def get_all_bookkeeping(self) -> dict[str, SceneBookkeeping]:
        return dict(self._ensure_bookkeeping_loaded())

    def save_scene_bookkeeping(self, scene_id: str, bookkeeping: SceneBookkeeping) -> None:
        atomic_write_json(self._scene_folder(scene_id) / "bookkeeping.json", bookkeeping.model_dump(mode="json"))
        self._ensure_bookkeeping_loaded()[scene_id] = bookkeeping
        self._changed()

    # -- relationships (soft placement edges) -----------------------------------

    def _ensure_scene_relationships_loaded(self) -> dict[str, list[SoftRelationship]]:
        if self._scene_relationships is None:
            self._scene_relationships = {}
            for rec in self.get_scenes():
                rels = self._read_scene_list(self._scene_folder(rec.id) / "relationships.json", SoftRelationship)
                if rels:
                    self._scene_relationships[rec.id] = rels
        return self._scene_relationships

    def get_scene_relationships(self, scene_id: str) -> list[SoftRelationship]:
        return list(self._ensure_scene_relationships_loaded().get(scene_id, []))

    def save_scene_relationships(self, scene_id: str, relationships: list[SoftRelationship]) -> None:
        atomic_write_json(
            self._scene_folder(scene_id) / "relationships.json",
            [r.model_dump(mode="json") for r in relationships],
        )
        cache = self._ensure_scene_relationships_loaded()
        if relationships:
            cache[scene_id] = relationships
        else:
            cache.pop(scene_id, None)
        self._changed()

    def get_relationships(self) -> list[SoftRelationship]:
        """Flattened aggregate across every scene's relationships.json —
        signature preserved so existing callers (ScenesResponse, ChainService's
        rel_ids, PlaceholderRegistry) don't need to change."""
        return [r for rels in self._ensure_scene_relationships_loaded().values() for r in rels]

    def delete_scene_relationship(self, rel_id: str) -> bool:
        for scene_id, rels in self._ensure_scene_relationships_loaded().items():
            if any(r.id == rel_id for r in rels):
                self.save_scene_relationships(scene_id, [r for r in rels if r.id != rel_id])
                return True
        return False

    # -- dependencies (prerequisite edges) ---------------------------------------

    def _ensure_dependencies_loaded(self) -> None:
        if self._scene_dependencies is not None:
            return
        self._scene_dependencies = {}
        self._dependents_index = {}
        for rec in self.get_scenes():
            deps = self._read_scene_list(self._scene_folder(rec.id) / "dependencies.json", Dependency)
            if deps:
                self._scene_dependencies[rec.id] = deps
            for d in deps:
                self._dependents_index.setdefault(d.dependsOnSceneId, []).append(d)

    def get_scene_dependencies(self, scene_id: str) -> list[Dependency]:
        self._ensure_dependencies_loaded()
        return list((self._scene_dependencies or {}).get(scene_id, []))

    def get_dependents(self, scene_id: str) -> list[Dependency]:
        """Reverse index: dependencies owned by *other* scenes that point at
        ``scene_id``. Built by one full scan on first access, then kept live by
        the incremental update in ``save_scene_dependencies`` — never rescanned."""
        self._ensure_dependencies_loaded()
        return list((self._dependents_index or {}).get(scene_id, []))

    def save_scene_dependencies(self, scene_id: str, dependencies: list[Dependency]) -> None:
        self._ensure_dependencies_loaded()
        assert self._scene_dependencies is not None and self._dependents_index is not None
        atomic_write_json(
            self._scene_folder(scene_id) / "dependencies.json",
            [d.model_dump(mode="json") for d in dependencies],
        )
        # Incremental reverse-index update: drop this scene's old edges, add the new.
        for old in self._scene_dependencies.get(scene_id, []):
            bucket = self._dependents_index.get(old.dependsOnSceneId)
            if bucket is not None:
                self._dependents_index[old.dependsOnSceneId] = [d for d in bucket if d.id != old.id]
        if dependencies:
            self._scene_dependencies[scene_id] = dependencies
        else:
            self._scene_dependencies.pop(scene_id, None)
        for d in dependencies:
            self._dependents_index.setdefault(d.dependsOnSceneId, []).append(d)
        self._changed()

    # -- folder lifecycle ---------------------------------------------------------

    def create_scene_folder(self, scene_id: str, meta: SceneMeta, bookkeeping: SceneBookkeeping) -> None:
        """Seed a new scene's per-scene files. Called before the master row is
        committed (leaf-first ordering) — an orphaned folder with no master row
        pointing at it is harmless; nothing discovers it."""
        folder = self._scene_folder(scene_id)
        atomic_write_json(folder / "meta.json", meta.model_dump(mode="json"))
        atomic_write_json(folder / "bookkeeping.json", bookkeeping.model_dump(mode="json"))
        atomic_write_json(folder / "dependencies.json", [])
        atomic_write_json(folder / "relationships.json", [])
        if self._scene_meta is not None:
            self._scene_meta[scene_id] = meta
        if self._scene_bookkeeping is not None:
            self._scene_bookkeeping[scene_id] = bookkeeping

    def move_scene_folder_to_trash(self, scene_id: str) -> None:
        """Mirrors the existing prose .md → .trash/ behavior (doc 03) — nothing
        is silently destroyed, just moved aside with the same recoverability
        window as the prose file gets."""
        folder = self._scene_folder(scene_id)
        if not folder.exists():
            return
        trash_dir = self._dir / ".trash"
        trash_dir.mkdir(parents=True, exist_ok=True)
        target = trash_dir / scene_id
        if target.exists():
            target = trash_dir / f"{scene_id}-{int(time.time())}"
        shutil.move(str(folder), str(target))
        if self._scene_meta is not None:
            self._scene_meta.pop(scene_id, None)
        if self._scene_bookkeeping is not None:
            self._scene_bookkeeping.pop(scene_id, None)
        if self._scene_relationships is not None:
            self._scene_relationships.pop(scene_id, None)
        if self._scene_dependencies is not None:
            self._scene_dependencies.pop(scene_id, None)

    # -- migration from the old flat (pre-split) scenes.json shape -------------

    _OLD_SHAPE_KEYS = (
        "location", "dateTime", "mood", "emotionalArc",
        "summary", "characterIds", "contentHash", "wordCount",
    )

    def _migrate_scenes_if_needed(self) -> None:
        path = self._dir / "db" / "scenes.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return  # let the normal load path quarantine this properly
        if not isinstance(raw, list) or not raw:
            return
        if not any(
            isinstance(row, dict) and any(k in row for k in self._OLD_SHAPE_KEYS) for row in raw
        ):
            return  # already the trimmed shape

        log.info("migrating %s scenes.json to master + per-scene layout", self._dir.name)

        trimmed_rows: list[dict] = []
        for row in raw:
            scene_id = row["id"]
            meta = SceneMeta(
                location=row.get("location", ""),
                dateTime=row.get("dateTime", ""),
                mood=row.get("mood", ""),
                emotionalArc=row.get("emotionalArc", ""),
                updatedAt=row.get("updatedAt", ""),
            )
            bookkeeping = SceneBookkeeping(
                summary=row.get("summary", ""),
                characterIds=row.get("characterIds") or [],
                contentHash=row.get("contentHash", ""),
                wordCount=row.get("wordCount", 0),
                updatedAt=row.get("updatedAt", ""),
            )
            folder = self._scene_folder(scene_id)
            atomic_write_json(folder / "meta.json", meta.model_dump(mode="json"))
            atomic_write_json(folder / "bookkeeping.json", bookkeeping.model_dump(mode="json"))
            if not (folder / "dependencies.json").exists():
                atomic_write_json(folder / "dependencies.json", [])
            if not (folder / "relationships.json").exists():
                atomic_write_json(folder / "relationships.json", [])
            trimmed_rows.append({
                "id": scene_id,
                "title": row.get("title", ""),
                "file": row.get("file", ""),
                "description": row.get("description", ""),
                "previousSceneId": row.get("previousSceneId"),
                "nextSceneId": row.get("nextSceneId"),
                "status": row.get("status", "active"),
                "chapterId": row.get("chapterId"),
                "partId": row.get("partId"),
                "primaryPlotlineId": row.get("primaryPlotlineId"),
                "secondaryPlotlineIds": row.get("secondaryPlotlineIds") or [],
                "createdAt": row.get("createdAt") or row.get("updatedAt", ""),
                "updatedAt": row.get("updatedAt", ""),
            })

        rel_path = self._dir / "db" / "relationships.json"
        if rel_path.exists():
            try:
                rel_raw = json.loads(rel_path.read_text(encoding="utf-8"))
            except Exception:
                rel_raw = []
            by_from: dict[str, list[dict]] = {}
            for r in rel_raw:
                by_from.setdefault(r.get("fromSceneId"), []).append(r)
            for scene_id, rows in by_from.items():
                folder = self._scene_folder(scene_id)
                if folder.exists():
                    atomic_write_json(folder / "relationships.json", rows)

        dep_path = self._dir / "db" / "dependencies.json"
        if dep_path.exists():
            try:
                dep_raw = json.loads(dep_path.read_text(encoding="utf-8"))
            except Exception:
                dep_raw = []
            by_scene: dict[str, list[dict]] = {}
            for d in dep_raw:
                by_scene.setdefault(d.get("sceneId"), []).append(d)
            for scene_id, rows in by_scene.items():
                folder = self._scene_folder(scene_id)
                if folder.exists():
                    atomic_write_json(folder / "dependencies.json", rows)

        # Commit point: trimmed master, written last. A crash before this line
        # leaves db/scenes.json in the old shape, so the next load re-detects
        # and re-runs migration from scratch (idempotent — leaf files just get
        # overwritten with identical data).
        atomic_write_json(path, trimmed_rows)

        # Supersede (never delete) the old flat files, after the commit so a
        # crash before it leaves the originals intact for a retry.
        ts = int(time.time())
        if rel_path.exists():
            rel_path.replace(rel_path.with_name(f"relationships.json.pre-split-{ts}"))
        if dep_path.exists():
            dep_path.replace(dep_path.with_name(f"dependencies.json.pre-split-{ts}"))

        log.info("migration complete for %s: %d scenes", self._dir.name, len(trimmed_rows))

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
