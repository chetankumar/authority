"""ToolRegistry — bind read + propose (+ execute) tools for a book (doc 05)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.ai_tools.accumulator import ProposalAccumulator
from app.services.ai_tools.execute import build_execute_tools
from app.services.ai_tools.propose import build_propose_tools
from app.services.ai_tools.read import build_read_tools
from app.services.book_registry import BookRegistry


class ToolRegistry:
    def __init__(
        self,
        registry: BookRegistry,
        scene_service_getter: Callable[[], Any] | None = None,
    ) -> None:
        self._registry = registry
        # A getter, not the service: the construction graph runs
        # scene_service → enrichment → conversation → tool_registry, so taking
        # SceneService directly here would close the loop. Resolved lazily at
        # bind() time, long after everything is built.
        self._scene_service_getter = scene_service_getter

    def bind(
        self,
        book_id: str,
        accumulator: ProposalAccumulator | None = None,
        *,
        bookkeeping_scene_id: str | None = None,
    ) -> tuple[list[Any], ProposalAccumulator]:
        """Return (tools, accumulator). Accumulators collect propose-tool outputs.

        ``bookkeeping_scene_id`` opts into the execute tools, bound to that one
        scene. Only bookkeeping conversations pass it — a chat or an AI-Job run
        gets read + propose only, so the only path that writes metadata without
        an author's click stays the one the Bookkeeping toggles consent to.
        """
        acc = accumulator or ProposalAccumulator()
        tools = [
            *build_read_tools(book_id, self._registry),
            *build_propose_tools(acc),
        ]
        if bookkeeping_scene_id and self._scene_service_getter is not None:
            tools.extend(
                build_execute_tools(book_id, bookkeeping_scene_id, self._scene_service_getter())
            )
        return tools, acc
