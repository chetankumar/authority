"""StructureService (doc 04 §7) — CRUD for parts, chapters, and plotlines.

Seq-based ordering: each record carries a simple ``seq`` integer. Reordering
accepts a full ordered list of IDs and reassigns sequential numbers 1..n.
Deletion compacts remaining seq values so gaps never accumulate.

Plotlines: CRUD + computed sceneCount (scanned from scenes). Deletion is
blocked while any scene references the plotline.
"""

from __future__ import annotations

import secrets

from app.core.errors import ApiError, blocked, not_found, validation
from app.models.book import Chapter, Part
from app.models.plotline import Plotline, PlotlineRecord
from app.services.book_registry import BookRegistry


class StructureService:
    def __init__(self, registry: BookRegistry) -> None:
        self._registry = registry

    # ---- Parts ---------------------------------------------------------------

    async def list_parts(self, book_id: str) -> list[Part]:
        mgr = self._registry.get(book_id)
        return sorted(mgr.get_parts(), key=lambda p: p.seq)

    async def create_part(self, book_id: str, title: str, description: str = "") -> Part:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            title = title.strip()
            if not title:
                raise validation({"title": "Give the part a title."})
            parts = list(mgr.get_parts())
            part_id = _mint_id("prt", {p.id for p in parts})
            max_seq = max((p.seq for p in parts), default=0)
            part = Part(id=part_id, title=title, description=description, seq=max_seq + 1)
            parts.append(part)
            mgr.save_parts(parts)
            return part

    async def update_part(self, book_id: str, part_id: str, title: str | None = None, description: str | None = None) -> Part:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            parts = list(mgr.get_parts())
            part = _find(parts, part_id, "part")
            if title is not None:
                title = title.strip()
                if not title:
                    raise validation({"title": "Give the part a title."})
                part.title = title
            if description is not None:
                part.description = description
            mgr.save_parts(parts)
            return part

    async def reorder_parts(self, book_id: str, ids: list[str]) -> list[Part]:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            parts = list(mgr.get_parts())
            _validate_reorder_ids(ids, {p.id for p in parts}, "part")
            by_id = {p.id: p for p in parts}
            reordered = []
            for seq, pid in enumerate(ids, 1):
                p = by_id[pid]
                p.seq = seq
                reordered.append(p)
            mgr.save_parts(reordered)
            return reordered

    async def delete_part(self, book_id: str, part_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            parts = list(mgr.get_parts())
            _find(parts, part_id, "part")
            chapters_blocking = [{"id": c.id, "title": c.title} for c in mgr.get_chapters() if c.partId == part_id]
            scenes_blocking = [{"id": s.id, "title": s.title} for s in mgr.get_scenes() if s.partId == part_id]
            blockers: dict = {}
            if chapters_blocking:
                blockers["chapters"] = chapters_blocking
            if scenes_blocking:
                blockers["scenes"] = scenes_blocking
            if blockers:
                raise blocked(blockers)
            remaining = [p for p in parts if p.id != part_id]
            _compact_seq(remaining)
            mgr.save_parts(remaining)

    # ---- Chapters ------------------------------------------------------------

    async def list_chapters(self, book_id: str) -> list[Chapter]:
        mgr = self._registry.get(book_id)
        return sorted(mgr.get_chapters(), key=lambda c: c.seq)

    async def create_chapter(self, book_id: str, title: str, description: str = "", part_id: str | None = None) -> Chapter:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            title = title.strip()
            if not title:
                raise validation({"title": "Give the chapter a title."})
            if part_id:
                if not any(p.id == part_id for p in mgr.get_parts()):
                    raise validation({"partId": "Unknown part."})
            chapters = list(mgr.get_chapters())
            chp_id = _mint_id("chp", {c.id for c in chapters})
            max_seq = max((c.seq for c in chapters), default=0)
            chapter = Chapter(id=chp_id, title=title, description=description, partId=part_id, seq=max_seq + 1)
            chapters.append(chapter)
            mgr.save_chapters(chapters)
            return chapter

    async def update_chapter(
        self, book_id: str, chp_id: str, title: str | None = None, description: str | None = None, part_id: str | None = ...
    ) -> Chapter:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            chapters = list(mgr.get_chapters())
            chapter = _find(chapters, chp_id, "chapter")
            if title is not None:
                title = title.strip()
                if not title:
                    raise validation({"title": "Give the chapter a title."})
                chapter.title = title
            if description is not None:
                chapter.description = description
            if part_id is not ...:
                if part_id is not None and not any(p.id == part_id for p in mgr.get_parts()):
                    raise validation({"partId": "Unknown part."})
                chapter.partId = part_id
            mgr.save_chapters(chapters)
            return chapter

    async def reorder_chapters(self, book_id: str, ids: list[str]) -> list[Chapter]:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            chapters = list(mgr.get_chapters())
            _validate_reorder_ids(ids, {c.id for c in chapters}, "chapter")
            by_id = {c.id: c for c in chapters}
            reordered = []
            for seq, cid in enumerate(ids, 1):
                c = by_id[cid]
                c.seq = seq
                reordered.append(c)
            mgr.save_chapters(reordered)
            return reordered

    async def delete_chapter(self, book_id: str, chp_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            chapters = list(mgr.get_chapters())
            _find(chapters, chp_id, "chapter")
            scenes_blocking = [{"id": s.id, "title": s.title} for s in mgr.get_scenes() if s.chapterId == chp_id]
            if scenes_blocking:
                raise blocked({"scenes": scenes_blocking})
            remaining = [c for c in chapters if c.id != chp_id]
            _compact_seq(remaining)
            mgr.save_chapters(remaining)

    # ---- Plotlines -----------------------------------------------------------

    async def list_plotlines(self, book_id: str) -> list[Plotline]:
        mgr = self._registry.get(book_id)
        records = mgr.get_plotlines()
        scenes = mgr.get_scenes()
        counts: dict[str, int] = {}
        for s in scenes:
            if s.primaryPlotlineId:
                counts[s.primaryPlotlineId] = counts.get(s.primaryPlotlineId, 0) + 1
            for pid in s.secondaryPlotlineIds:
                counts[pid] = counts.get(pid, 0) + 1
        return [
            Plotline(**r.model_dump(), sceneCount=counts.get(r.id, 0))
            for r in records
        ]

    async def create_plotline(self, book_id: str, title: str, description: str = "") -> Plotline:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            title = title.strip()
            if not title:
                raise validation({"title": "Give the plotline a title."})
            plotlines = list(mgr.get_plotlines())
            plt_id = _mint_id("plt", {p.id for p in plotlines})
            record = PlotlineRecord(id=plt_id, title=title, description=description)
            plotlines.append(record)
            mgr.save_plotlines(plotlines)
            return Plotline(**record.model_dump(), sceneCount=0)

    async def update_plotline(self, book_id: str, plt_id: str, title: str | None = None, description: str | None = None) -> Plotline:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            plotlines = list(mgr.get_plotlines())
            record = _find(plotlines, plt_id, "plotline")
            if title is not None:
                title = title.strip()
                if not title:
                    raise validation({"title": "Give the plotline a title."})
                record.title = title
            if description is not None:
                record.description = description
            mgr.save_plotlines(plotlines)
            scenes = mgr.get_scenes()
            count = sum(
                1 for s in scenes
                if s.primaryPlotlineId == plt_id or plt_id in s.secondaryPlotlineIds
            )
            return Plotline(**record.model_dump(), sceneCount=count)

    async def delete_plotline(self, book_id: str, plt_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            plotlines = list(mgr.get_plotlines())
            _find(plotlines, plt_id, "plotline")
            scenes = mgr.get_scenes()
            scenes_blocking = [
                {"id": s.id, "title": s.title}
                for s in scenes
                if s.primaryPlotlineId == plt_id or plt_id in s.secondaryPlotlineIds
            ]
            if scenes_blocking:
                raise blocked({"scenes": scenes_blocking})
            remaining = [p for p in plotlines if p.id != plt_id]
            mgr.save_plotlines(remaining)


# ---- helpers ----------------------------------------------------------------

def _mint_id(prefix: str, existing: set[str]) -> str:
    for _ in range(20):
        candidate = f"{prefix}-{secrets.token_hex(3)}"
        if candidate not in existing:
            return candidate
    raise ApiError(500, f"Couldn't allocate a {prefix} id.")


def _find(items: list, item_id: str, kind: str):
    for item in items:
        if item.id == item_id:  # type: ignore[attr-defined]
            return item
    raise not_found(kind, item_id)


def _validate_reorder_ids(ids: list[str], existing: set[str], kind: str) -> None:
    id_set = set(ids)
    if len(id_set) != len(ids):
        raise validation({"ids": "Duplicate IDs in reorder list."})
    if id_set != existing:
        missing = existing - id_set
        extra = id_set - existing
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(sorted(missing))}")
        if extra:
            parts.append(f"unknown: {', '.join(sorted(extra))}")
        raise validation({"ids": f"Reorder list doesn't match existing {kind}s ({'; '.join(parts)})."})


def _compact_seq(items: list) -> None:
    items.sort(key=lambda x: x.seq)
    for i, item in enumerate(items, 1):
        item.seq = i
