"""SceneService (doc 04 §5, §6) — scene CRUD, content saves, soft relationships.

Orchestrates under the book's asyncio mutation lock: validates, works on record
copies, delegates chain algebra to ChainService, persists atomically via
BookDataManager. ``seq``/``placement`` are computed on read. The content path is
one of only two routes that write scene ``.md`` files (the prose hard rule).

Persistence is split three ways (doc 03): the master ``SceneRecord``
(identity/hard-chain/structure, in ``db/scenes.json``), ``SceneMeta``
(location/dateTime/mood/emotionalArc, in ``scenes/{id}/meta.json``), and
``SceneBookkeeping`` (summary/characterIds/contentHash/wordCount, in
``scenes/{id}/bookkeeping.json``). This service is the one place that routes a
flat ``SceneUpdate`` request across the three, and assembles the flat ``Scene``
response back out of them — nothing outside this file needs to know the split
exists. Only a bucket that actually changed gets written (git-diff granularity;
content saves and enrichment now touch bookkeeping.json only, never master).

Hooks left for later phases and marked inline: dependency-todo fanout (phase 6
— no dependency CRUD exists yet, only the delete-blocked check) and the
enrichment settle timer (wired to EnrichmentService).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from app.core.atomic import atomic_write_text
from app.core.errors import ApiError, validation
from app.models.enums import Placement, SceneStatus
from app.models.scene import (
    ContentSaveResult,
    RelationshipCreate,
    Scene,
    SceneBookkeeping,
    SceneCreate,
    SceneMeta,
    SceneMutationResult,
    SceneRecord,
    SceneUpdate,
    SceneWithContent,
    SoftRelationship,
    ScenesResponse,
)
from app.services import chain_service as chain
from app.services.book_registry import BookRegistry
from app.services.book_service import slugify


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _content_metrics(content: str) -> tuple[int, str]:
    word_count = len(content.split())
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return word_count, f"sha256:{digest}"


def _reject_same_neighbors(previous: str | None, next_: str | None) -> None:
    if previous and next_ and previous == next_:
        raise validation({"sequence": "Previous and Next can't be the same scene."})


class SceneService:
    def __init__(self, registry: BookRegistry, enrichment: Any | None = None) -> None:
        self._registry = registry
        self._enrichment = enrichment

    def set_enrichment(self, enrichment: Any) -> None:
        self._enrichment = enrichment

    # ---- reads (no lock) ----------------------------------------------------

    def list_scenes(self, book_id: str) -> ScenesResponse:
        mgr = self._registry.get(book_id)
        records = mgr.get_scenes()
        relationships = mgr.get_relationships()
        scenes = self._decorate(mgr, records, relationships)
        return ScenesResponse(scenes=scenes, relationships=relationships)

    def get_scene(self, book_id: str, scene_id: str) -> SceneWithContent:
        mgr = self._registry.get(book_id)
        records = mgr.get_scenes()
        record = self._find(records, scene_id)
        seq, placement = self._compute(records, mgr.get_relationships()).get(scene_id, (None, Placement.orphan))
        content = mgr.read_scene_content(record.file)
        scene = self._assemble(record, mgr.get_scene_meta(scene_id), mgr.get_scene_bookkeeping(scene_id), seq, placement)
        return SceneWithContent(**scene.model_dump(), content=content)

    # ---- mutations (under the book lock) ------------------------------------

    async def create_scene(self, book_id: str, body: SceneCreate) -> SceneMutationResult:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            if not body.title.strip():
                raise validation({"title": "Give the scene a title."})
            if not body.description.strip():
                raise validation({"description": "A one-line description is required."})
            self._validate_structure(mgr, body.chapterId, body.partId)
            self._validate_plotlines(mgr, body.primaryPlotlineId, body.secondaryPlotlineIds or None)

            working = {r.id: r.model_copy(deep=True) for r in mgr.get_scenes()}

            if body.previousSceneId is not None:
                chain.validate_endpoint(working, body.previousSceneId, as_previous=True)
            if body.nextSceneId is not None:
                chain.validate_endpoint(working, body.nextSceneId, as_previous=False)
            _reject_same_neighbors(body.previousSceneId, body.nextSceneId)

            scene_id, hex6 = self._mint_id(working)
            slug = slugify(body.title)
            rel_path = f"scenes/{hex6}-{slug}.md"
            atomic_write_text(mgr.scene_file_path(rel_path), "")
            word_count, content_hash = _content_metrics("")
            now = _now()

            record = SceneRecord(
                id=scene_id,
                title=body.title.strip(),
                file=rel_path,
                description=body.description.strip(),
                chapterId=body.chapterId,
                partId=body.partId,
                createdAt=now,
                updatedAt=now,
            )
            meta = SceneMeta(
                location=body.location, dateTime=body.dateTime,
                mood=body.mood, emotionalArc=body.emotionalArc,
                updatedAt=now,
            )
            bookkeeping = SceneBookkeeping(contentHash=content_hash, wordCount=word_count, updatedAt=now)

            # Leaf files first, master commit last (doc 03) — an orphaned
            # per-scene folder with no master row is harmless; a crash between
            # these two lines just leaves an unreferenced folder.
            mgr.create_scene_folder(scene_id, meta, bookkeeping)

            working[scene_id] = record
            affected = chain.place_between(working, scene_id, previous=body.previousSceneId, next_=body.nextSceneId)
            new_records = list(working.values())
            mgr.save_scenes(new_records)

            if body.softRelations:
                existing = mgr.get_relationships()
                new_rels: list[SoftRelationship] = []
                for soft in body.softRelations:
                    rel = self._make_relationship(
                        existing + new_rels, from_id=scene_id, to_id=soft.sceneId, rtype=soft.type, working=working
                    )
                    if rel is not None:
                        new_rels.append(rel)
                if new_rels:
                    mgr.save_scene_relationships(scene_id, new_rels)

            return self._mutation_result(mgr, new_records, mgr.get_relationships(), scene_id, affected)

    async def update_scene(self, book_id: str, scene_id: str, body: SceneUpdate) -> SceneMutationResult:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            working = {r.id: r.model_copy(deep=True) for r in mgr.get_scenes()}
            record = working.get(scene_id)
            if record is None:
                raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})

            fields = body.model_fields_set
            affected: set[str] = set()
            master_touched = False
            meta = mgr.get_scene_meta(scene_id).model_copy()
            meta_touched = False
            bookkeeping = mgr.get_scene_bookkeeping(scene_id).model_copy()
            bookkeeping_touched = False

            if "title" in fields and body.title is not None:
                if not body.title.strip():
                    raise validation({"title": "Give the scene a title."})
                self._rename_file(mgr, record, body.title.strip())
                record.title = body.title.strip()
                master_touched = True

            if "description" in fields:
                if body.description is None or not body.description.strip():
                    raise validation({"description": "A one-line description is required."})
                record.description = body.description
                master_touched = True

            for name in ("location", "dateTime", "mood", "emotionalArc"):
                if name in fields:
                    setattr(meta, name, getattr(body, name) or "")
                    meta_touched = True

            if "summary" in fields:
                bookkeeping.summary = body.summary or ""
                bookkeeping_touched = True
            if "characterIds" in fields and body.characterIds is not None:
                bookkeeping.characterIds = body.characterIds
                bookkeeping_touched = True

            if "chapterId" in fields or "partId" in fields:
                chapter_id = body.chapterId if "chapterId" in fields else record.chapterId
                part_id = body.partId if "partId" in fields else record.partId
                self._validate_structure(mgr, chapter_id, part_id)
                record.chapterId = chapter_id
                record.partId = part_id
                master_touched = True

            if "primaryPlotlineId" in fields or "secondaryPlotlineIds" in fields:
                p_id = body.primaryPlotlineId if "primaryPlotlineId" in fields else record.primaryPlotlineId
                s_ids = body.secondaryPlotlineIds if "secondaryPlotlineIds" in fields else record.secondaryPlotlineIds
                self._validate_plotlines(mgr, p_id, s_ids or None)
                if "primaryPlotlineId" in fields:
                    record.primaryPlotlineId = body.primaryPlotlineId
                if "secondaryPlotlineIds" in fields:
                    record.secondaryPlotlineIds = body.secondaryPlotlineIds
                master_touched = True

            if "status" in fields and body.status is not None:
                if body.status == SceneStatus.archived and record.status != SceneStatus.archived:
                    affected |= chain.detach(working, scene_id)
                    record.status = SceneStatus.archived
                    master_touched = True
                elif body.status == SceneStatus.active:
                    record.status = SceneStatus.active  # returns floating (old slot not reclaimed)
                    master_touched = True

            reposition = ("previousSceneId" in fields or "nextSceneId" in fields) and record.status == SceneStatus.active
            if reposition:
                # Default the unspecified side to the scene's CURRENT link, so a
                # caller that sends only one side never drops the other. The modal
                # sends both together; this is the belt-and-suspenders guarantee.
                new_prev = body.previousSceneId if "previousSceneId" in fields else record.previousSceneId
                new_next = body.nextSceneId if "nextSceneId" in fields else record.nextSceneId
                if new_prev is not None:
                    chain.validate_endpoint(working, new_prev, as_previous=True, self_id=scene_id)
                if new_next is not None:
                    chain.validate_endpoint(working, new_next, as_previous=False, self_id=scene_id)
                _reject_same_neighbors(new_prev, new_next)
                affected |= chain.place_between(working, scene_id, previous=new_prev, next_=new_next)
                master_touched = True

            now = _now()
            new_records = list(working.values())
            if master_touched or affected:
                record.updatedAt = now
                mgr.save_scenes(new_records)
            if meta_touched:
                meta.updatedAt = now
                mgr.save_scene_meta(scene_id, meta)
            if bookkeeping_touched:
                bookkeeping.updatedAt = now
                mgr.save_scene_bookkeeping(scene_id, bookkeeping)

            affected.discard(scene_id)
            return self._mutation_result(mgr, new_records, mgr.get_relationships(), scene_id, affected)

    async def save_content(self, book_id: str, scene_id: str, content: str) -> ContentSaveResult:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            record = self._find(mgr.get_scenes(), scene_id)

            atomic_write_text(mgr.scene_file_path(record.file), content)
            word_count, content_hash = _content_metrics(content)
            bookkeeping = mgr.get_scene_bookkeeping(scene_id).model_copy()
            hash_changed = content_hash != bookkeeping.contentHash
            bookkeeping.wordCount = word_count
            bookkeeping.contentHash = content_hash
            bookkeeping.updatedAt = _now()
            # Content saves now touch only bookkeeping.json — the master table
            # (db/scenes.json) is never rewritten by autosave, so it can never
            # contend with or block a chain splice/heal on an unrelated scene.
            mgr.save_scene_bookkeeping(scene_id, bookkeeping)

            todos_created: list[dict] = []
            if hash_changed:
                # Phase 6 hook — dependency-todo fanout (no dependency CRUD yet).
                if self._enrichment is not None:
                    self._enrichment.reset_settle_timer(book_id, scene_id)

            return ContentSaveResult(wordCount=word_count, contentHash=content_hash, todosCreated=todos_created)

    # ---- soft relationships (doc 04 §6) -------------------------------------

    async def create_relationship(self, book_id: str, body: RelationshipCreate) -> SoftRelationship:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            working = {r.id: r for r in mgr.get_scenes()}
            relationships = mgr.get_relationships()
            existing = self._find_duplicate(relationships, body.fromSceneId, body.toSceneId, body.type)
            if existing is not None:
                return existing  # idempotent (doc 04 §6)
            rel = self._make_relationship(
                relationships, from_id=body.fromSceneId, to_id=body.toSceneId, rtype=body.type, working=working, strict=True
            )
            assert rel is not None  # strict=True raises instead of returning None
            from_rels = list(mgr.get_scene_relationships(body.fromSceneId))
            from_rels.append(rel)
            mgr.save_scene_relationships(body.fromSceneId, from_rels)
            return rel

    async def delete_scene(self, book_id: str, scene_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            working = {r.id: r.model_copy(deep=True) for r in mgr.get_scenes()}
            record = working.get(scene_id)
            if record is None:
                raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})
            if record.status != SceneStatus.archived:
                raise ApiError(409, "Archive the scene before deleting it.", {
                    "blockedBy": {"reason": "Scene must be archived before it can be deleted."},
                })

            relationships = mgr.get_relationships()
            blocked_rels = [r for r in relationships if r.fromSceneId == scene_id or r.toSceneId == scene_id]
            if blocked_rels:
                raise ApiError(409, "Can't delete this scene yet.", {
                    "blockedBy": {"relationships": [{"id": r.id, "fromSceneId": r.fromSceneId, "toSceneId": r.toSceneId} for r in blocked_rels]},
                })

            blocked: dict = {}
            dep_hits = mgr.get_scene_dependencies(scene_id) + mgr.get_dependents(scene_id)
            if dep_hits:
                blocked["dependencies"] = [{"id": d.id, "reason": d.reason} for d in dep_hits]

            todos = self._load_json(mgr, "todos.json")
            todo_hits = [t for t in todos if t.get("parentType") == "scene" and t.get("parentId") == scene_id]
            if todo_hits:
                blocked["todos"] = [{"id": t["id"], "action": t.get("action", "")} for t in todo_hits]

            convos_index = self._load_json(mgr, "conversations/index.json")
            convo_hits = [c for c in convos_index if c.get("parentType") == "scene" and c.get("parentId") == scene_id]
            if convo_hits:
                blocked["conversations"] = [{"id": c["id"], "title": c.get("title", "")} for c in convo_hits]

            jobs = self._load_json(mgr, "jobs.json")
            job_hits = [j for j in jobs if j.get("sceneId") == scene_id and j.get("jobStatus") in ("queued", "running")]
            if job_hits:
                blocked["jobs"] = [{"id": j["id"]} for j in job_hits]

            if blocked:
                raise ApiError(409, "Can't delete this scene yet.", {"blockedBy": blocked})

            chain.detach(working, scene_id)
            del working[scene_id]
            # Master first, leaf cleanup last (doc 03) — mirrors create's
            # ordering in reverse; a crash between the two leaves an orphaned
            # folder with no master row, same harmless-orphan reasoning.
            mgr.save_scenes(list(working.values()))

            scene_path = mgr.scene_file_path(record.file)
            if scene_path.exists():
                trash_dir = mgr.book_dir / ".trash"
                trash_dir.mkdir(exist_ok=True)
                scene_path.replace(trash_dir / scene_path.name)

            mgr.move_scene_folder_to_trash(scene_id)

    async def delete_relationship(self, book_id: str, rel_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            if not mgr.delete_scene_relationship(rel_id):
                raise ApiError(404, "Relationship not found", {"kind": "relationship", "id": rel_id})

    # ---- helpers ------------------------------------------------------------

    def _assemble(
        self, record: SceneRecord, meta: SceneMeta, bookkeeping: SceneBookkeeping,
        seq: int | None, placement: Placement,
    ) -> Scene:
        updated_at = max(record.updatedAt, meta.updatedAt or "", bookkeeping.updatedAt or "")
        return Scene(
            id=record.id, title=record.title, file=record.file, description=record.description,
            location=meta.location, dateTime=meta.dateTime,
            previousSceneId=record.previousSceneId, nextSceneId=record.nextSceneId,
            chapterId=record.chapterId, partId=record.partId,
            primaryPlotlineId=record.primaryPlotlineId, secondaryPlotlineIds=record.secondaryPlotlineIds,
            mood=meta.mood, emotionalArc=meta.emotionalArc,
            summary=bookkeeping.summary, characterIds=bookkeeping.characterIds,
            status=record.status, contentHash=bookkeeping.contentHash, wordCount=bookkeeping.wordCount,
            seq=seq, placement=placement,
            createdAt=record.createdAt, updatedAt=updated_at,
        )

    def _decorate(self, mgr, records: list[SceneRecord], relationships: list[SoftRelationship]) -> list[Scene]:
        computed = self._compute(records, relationships)
        all_meta = mgr.get_all_meta()
        all_bookkeeping = mgr.get_all_bookkeeping()
        out: list[Scene] = []
        for r in records:
            seq, placement = computed.get(r.id, (None, Placement.orphan))
            out.append(self._assemble(
                r, all_meta.get(r.id, SceneMeta()), all_bookkeeping.get(r.id, SceneBookkeeping()), seq, placement
            ))
        return out

    def _compute(self, records: list[SceneRecord], relationships: list[SoftRelationship]) -> dict[str, tuple[int | None, Placement]]:
        rel_ids = {r.fromSceneId for r in relationships} | {r.toSceneId for r in relationships}
        return chain.compute_seq_placement(records, rel_ids)

    def _mutation_result(self, mgr, records: list[SceneRecord], relationships: list[SoftRelationship], scene_id: str, affected: set[str]) -> SceneMutationResult:
        decorated = {s.id: s for s in self._decorate(mgr, records, relationships)}
        return SceneMutationResult(
            scene=decorated[scene_id],
            affectedScenes=[decorated[a] for a in affected if a in decorated],
        )

    def _load_json(self, mgr, name: str) -> list[dict]:
        """Best-effort load of a db/*.json collection that may not exist yet."""
        import json
        path = mgr.book_dir / "db" / name
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except Exception:
            return []

    def _find(self, records: list[SceneRecord], scene_id: str) -> SceneRecord:
        for r in records:
            if r.id == scene_id:
                return r
        raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})

    def _mint_id(self, working: dict[str, SceneRecord]) -> tuple[str, str]:
        for _ in range(10):
            hex6 = secrets.token_hex(3)
            scene_id = f"scn-{hex6}"
            if scene_id not in working:
                return scene_id, hex6
        raise ApiError(500, "Couldn't allocate a scene id.")

    def _rename_file(self, mgr, record: SceneRecord, new_title: str) -> None:
        hex6 = record.id.removeprefix("scn-")
        new_rel = f"scenes/{hex6}-{slugify(new_title)}.md"
        if new_rel == record.file:
            return
        old_path = mgr.scene_file_path(record.file)
        new_path = mgr.scene_file_path(new_rel)
        if old_path.exists():
            old_path.replace(new_path)
        record.file = new_rel

    def _validate_structure(self, mgr, chapter_id: str | None, part_id: str | None) -> None:
        if chapter_id and part_id:
            raise validation({"structure": "A scene belongs to a chapter or a part, not both."}, code="chapter-xor-part")
        if chapter_id and not any(c.id == chapter_id for c in mgr.get_chapters()):
            raise validation({"chapterId": "Unknown chapter."})
        if part_id and not any(p.id == part_id for p in mgr.get_parts()):
            raise validation({"partId": "Unknown part."})

    def _validate_plotlines(self, mgr, primary_id: str | None, secondary_ids: list[str] | None) -> None:
        plotlines = {p.id for p in mgr.get_plotlines()}
        if primary_id and primary_id not in plotlines:
            raise validation({"primaryPlotlineId": "Unknown plotline."})
        if secondary_ids:
            for sid in secondary_ids:
                if sid not in plotlines:
                    raise validation({"secondaryPlotlineIds": f"Unknown plotline: {sid}"})
            if primary_id and primary_id in secondary_ids:
                raise validation({"primaryPlotlineId": "Primary plotline must not also appear in secondary plotlines."})

    def _find_duplicate(self, relationships: list[SoftRelationship], from_id: str, to_id: str, rtype) -> SoftRelationship | None:
        for r in relationships:
            if r.fromSceneId == from_id and r.toSceneId == to_id and r.type == rtype:
                return r
        return None

    def _make_relationship(self, relationships, *, from_id: str, to_id: str, rtype, working: dict[str, SceneRecord], strict: bool = False) -> SoftRelationship | None:
        if from_id == to_id:
            if strict:
                raise validation({"toSceneId": "A scene can't relate to itself."})
            return None
        for sid in (from_id, to_id):
            if sid not in working:
                if strict:
                    raise ApiError(404, "Scene not found", {"kind": "scene", "id": sid})
                return None
        if self._find_duplicate(relationships, from_id, to_id, rtype) is not None:
            return None  # dedup silently on create-scene
        return SoftRelationship(
            id=f"rel-{secrets.token_hex(3)}",
            fromSceneId=from_id,
            toSceneId=to_id,
            type=rtype,
            createdAt=_now(),
        )
