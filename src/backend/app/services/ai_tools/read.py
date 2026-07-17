"""Read tools — execute freely against BookDataManager (doc 05)."""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import ApiError
from app.models.scene import SceneBookkeeping
from app.services.book_data_manager import BookDataManager
from app.services.book_registry import BookRegistry
from app.services import chain_service as chain
from app.services.resource_service import (
    MAX_TEXT_READ_CHARS,
    is_text_resource,
    safe_resource_path,
    scan_resources,
)


def build_read_tools(book_id: str, registry: BookRegistry) -> list[Any]:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    def _mgr() -> BookDataManager:
        return registry.get(book_id)

    class SceneIdArgs(BaseModel):
        id: str = Field(description="Scene id, e.g. scn-a1b2c3")

    class SearchArgs(BaseModel):
        query: str

    class TodosArgs(BaseModel):
        sceneId: str | None = None

    class ResourceNameArgs(BaseModel):
        filename: str = Field(description="Resource file name, e.g. 'magic-system.md'")

    class CharacterArgs(BaseModel):
        id: str | None = Field(default=None, description="Character id, or omit for all")

    def get_scene(id: str) -> str:
        mgr = _mgr()
        records = {r.id: r for r in mgr.get_scenes()}
        rec = records.get(id)
        if rec is None:
            return json.dumps({"error": f"Scene {id} not found"})
        content = mgr.read_scene_content(rec.file)
        # Merge master + per-scene meta/bookkeeping so the AI still sees the
        # full scene shape (mood/summary/characters etc.), unaware they now
        # live in separate files (doc 03).
        data = rec.model_dump(mode="json")
        data.update(mgr.get_scene_meta(id).model_dump(mode="json"))
        data.update(mgr.get_scene_bookkeeping(id).model_dump(mode="json"))
        data["content"] = content
        return json.dumps(data, ensure_ascii=False)

    def _placement_map(mgr: BookDataManager) -> dict[str, tuple[int | None, Any]]:
        rels = mgr.get_relationships()
        rel_ids = {r.fromSceneId for r in rels} | {r.toSceneId for r in rels}
        return chain.compute_seq_placement(list(mgr.get_scenes()), rel_ids)

    def list_scenes() -> str:
        mgr = _mgr()
        computed = _placement_map(mgr)
        rows = []
        for s in mgr.get_scenes():
            seq, placement = computed.get(s.id, (None, "orphan"))
            rows.append(
                {
                    "id": s.id,
                    "title": s.title,
                    "seq": seq,
                    "placement": placement.value if hasattr(placement, "value") else placement,
                    "status": s.status.value if hasattr(s.status, "value") else s.status,
                }
            )
        return json.dumps(rows, ensure_ascii=False)

    def get_scene_summaries() -> str:
        mgr = _mgr()
        computed = _placement_map(mgr)
        all_bookkeeping = mgr.get_all_bookkeeping()
        rows = []
        for s in mgr.get_scenes():
            if s.status.value != "active" and str(s.status) != "active":
                continue
            seq, _ = computed.get(s.id, (None, None))
            summary = all_bookkeeping.get(s.id, SceneBookkeeping()).summary
            rows.append({"id": s.id, "title": s.title, "seq": seq, "summary": summary or "(no summary)"})
        return json.dumps(rows, ensure_ascii=False)

    def get_character_sheet(id: str | None = None) -> str:
        # Characters API may not be loaded yet — degrade gracefully.
        mgr = _mgr()
        getter = getattr(mgr, "get_characters", None)
        if getter is None:
            return json.dumps({"characters": [], "note": "Character sheet not loaded yet."})
        chars = getter()
        if id:
            match = next((c for c in chars if c.id == id), None)
            if match is None:
                return json.dumps({"error": f"Character {id} not found"})
            return json.dumps(match.model_dump(mode="json"), ensure_ascii=False)
        return json.dumps([c.model_dump(mode="json") for c in chars], ensure_ascii=False)

    def search_text(query: str) -> str:
        mgr = _mgr()
        q = query.lower()
        hits: list[dict[str, str]] = []
        for rec in mgr.get_scenes():
            if rec.status.value != "active" and str(rec.status) != "active":
                continue
            content = mgr.read_scene_content(rec.file)
            if q in content.lower() or q in rec.title.lower():
                # Short excerpt around first match.
                idx = content.lower().find(q)
                if idx >= 0:
                    start = max(0, idx - 40)
                    end = min(len(content), idx + len(query) + 40)
                    excerpt = content[start:end]
                else:
                    excerpt = content[:120]
                hits.append({"sceneId": rec.id, "title": rec.title, "excerpt": excerpt})
        return json.dumps(hits[:30], ensure_ascii=False)

    def get_plotlines() -> str:
        mgr = _mgr()
        return json.dumps([p.model_dump(mode="json") for p in mgr.get_plotlines()], ensure_ascii=False)

    def get_story_summary() -> str:
        return _mgr().config.storySummary or "(no story summary)"

    def get_todos(sceneId: str | None = None) -> str:
        mgr = _mgr()
        getter = getattr(mgr, "get_todos", None)
        if getter is None:
            return json.dumps({"todos": [], "note": "Todos not loaded yet."})
        todos = getter()
        if sceneId:
            todos = [t for t in todos if t.parentId == sceneId]
        return json.dumps([t.model_dump(mode="json") for t in todos], ensure_ascii=False)

    def list_resources() -> str:
        files = scan_resources(_mgr().book_dir)
        return json.dumps(
            [{**f.model_dump(mode="json"), "readable": is_text_resource(f.filename)} for f in files],
            ensure_ascii=False,
        )

    def get_resource(filename: str) -> str:
        try:
            path = safe_resource_path(_mgr().book_dir, filename)
        except ApiError as exc:
            fields = (exc.detail or {}).get("fields", {})
            return f"Rejected: {fields.get('filename', exc.error)}"
        if not path.is_file():
            return f"No resource named {filename}. Call list_resources to see what is there."
        if not is_text_resource(filename):
            # Listed but opaque: the author can see it, the model can't read it.
            return f"{filename} is a binary file — not readable as text."
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_TEXT_READ_CHARS:
            return text[:MAX_TEXT_READ_CHARS] + "\n\n[truncated]"
        return text

    return [
        StructuredTool.from_function(
            func=get_scene, name="get_scene", description="Get scene prose + metadata by id.", args_schema=SceneIdArgs
        ),
        StructuredTool.from_function(
            func=list_scenes, name="list_scenes", description="List scenes with title, seq, placement."
        ),
        StructuredTool.from_function(
            func=get_scene_summaries, name="get_scene_summaries", description="Active scene titles + summaries."
        ),
        StructuredTool.from_function(
            func=get_character_sheet,
            name="get_character_sheet",
            description="Character sheet(s). Pass id for one, or omit for all.",
            args_schema=CharacterArgs,
        ),
        StructuredTool.from_function(
            func=search_text,
            name="search_text",
            description="Search active scene prose for a query.",
            args_schema=SearchArgs,
        ),
        StructuredTool.from_function(
            func=get_plotlines, name="get_plotlines", description="List plotlines."
        ),
        StructuredTool.from_function(
            func=get_story_summary, name="get_story_summary", description="Book story summary."
        ),
        StructuredTool.from_function(
            func=get_todos, name="get_todos", description="Todos, optionally filtered by sceneId.", args_schema=TodosArgs
        ),
        StructuredTool.from_function(
            func=list_resources,
            name="list_resources",
            description=(
                "List the book's resource files — research, notes, references the "
                "author keeps beside the manuscript. `readable` marks the ones "
                "get_resource can open."
            ),
        ),
        StructuredTool.from_function(
            func=get_resource,
            name="get_resource",
            description="Read a text or markdown resource file by name.",
            args_schema=ResourceNameArgs,
        ),
    ]
