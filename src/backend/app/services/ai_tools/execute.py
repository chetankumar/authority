"""Execute tools — the third tool category, alongside read and propose (doc 05).

Read tools execute freely but only read. Propose tools never touch disk; they
accumulate Proposal objects for the author to accept. These *write*, directly,
with no proposal in between — and that is deliberate, not a hole in the rule.

The hard rule (doc 01) is that **prose** is sacred: no AI code path may write a
scene's ``.md``. Bookkeeping fields — the scene summary and per-scene character
involvement — are not prose. They are exactly what the author already grants
standing consent for via the Bookkeeping toggles, and enrichment has always
written them straight to ``scenes/{id}/bookkeeping.json``. The only thing that
changes here is *how the model says so*: a tool call instead of a fenced JSON
blob the server parses. Same write, same consent, better mechanism — and when
the model can't decide, it now simply doesn't call the tool and asks the author
in the thread instead.

These tools are **scene-bound**: ``scene_id`` is closed over, not a parameter,
so a bookkeeping run cannot write some other scene's fields.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.errors import ApiError
from app.models.scene import SceneCharacterRef, SceneUpdate

log = logging.getLogger("authority.ai")


def _reason(exc: ApiError) -> str:
    """Render an ApiError as something the model can act on. ``validation()``
    puts the useful text under detail.fields and leaves .error as a generic
    "Validation failed", which would tell the model nothing."""
    fields = (exc.detail or {}).get("fields") if isinstance(exc.detail, dict) else None
    if isinstance(fields, dict) and fields:
        return "; ".join(f"{k}: {v}" for k, v in fields.items())
    return exc.error


def build_execute_tools(book_id: str, scene_id: str, scene_service: Any) -> list[Any]:
    """Bookkeeping write tools for one scene. ``scene_service`` is passed in
    rather than imported to keep the dependency direction one-way (ai_tools is
    a leaf; SceneService already reaches for tools via the orchestrator)."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class SummaryArgs(BaseModel):
        summary: str = Field(description="A concise prose summary of what happens in this scene.")

    class CharacterRefArg(BaseModel):
        characterId: str = Field(description="An id from the character directory. Never invent one.")
        involvement: str = Field(
            default="",
            description="One line on what this character does or undergoes in THIS scene.",
        )

    class CharactersArgs(BaseModel):
        characters: list[CharacterRefArg] = Field(
            description="The complete cast of this scene. This REPLACES the current list."
        )

    async def set_scene_summary(summary: str) -> str:
        try:
            await scene_service.update_scene(book_id, scene_id, SceneUpdate(summary=summary))
        except ApiError as exc:
            return f"Rejected: {_reason(exc)}"
        return "Scene summary updated."

    async def set_scene_characters(characters: list) -> str:
        # LangChain coerces each item to CharacterRefArg per args_schema, but a
        # direct/JSON call can hand back plain dicts — accept either.
        def _field(item: object, name: str) -> str:
            if isinstance(item, dict):
                return str(item.get(name) or "")
            return str(getattr(item, name, "") or "")

        refs = [
            SceneCharacterRef(
                characterId=_field(c, "characterId"),
                involvement=_field(c, "involvement"),
            )
            for c in characters
        ]
        try:
            await scene_service.update_scene(book_id, scene_id, SceneUpdate(characters=refs))
        except ApiError as exc:
            # Unknown character ids come back as a 422 from update_scene's own
            # validation — hand the model the reason so it can correct itself
            # or ask, rather than silently dropping the write.
            return f"Rejected: {_reason(exc)}"
        return json.dumps({"ok": True, "count": len(refs)})

    return [
        StructuredTool.from_function(
            coroutine=set_scene_summary,
            name="set_scene_summary",
            description="Record the summary of the scene being enriched. Call once when you're confident.",
            args_schema=SummaryArgs,
        ),
        StructuredTool.from_function(
            coroutine=set_scene_characters,
            name="set_scene_characters",
            description=(
                "Record which existing characters appear in the scene being enriched, and what "
                "each does in it. Replaces the current list, so include everyone who belongs. "
                "Only use ids from the character directory; if you are unsure who someone is, "
                "do not call this — ask the author instead."
            ),
            args_schema=CharactersArgs,
        ),
    ]
