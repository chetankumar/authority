"""ToolRegistry — bind read + propose tools for a book (doc 05)."""

from __future__ import annotations

from typing import Any

from app.services.ai_tools.accumulator import ProposalAccumulator
from app.services.ai_tools.propose import build_propose_tools
from app.services.ai_tools.read import build_read_tools
from app.services.book_registry import BookRegistry


class ToolRegistry:
    def __init__(self, registry: BookRegistry) -> None:
        self._registry = registry

    def bind(self, book_id: str, accumulator: ProposalAccumulator | None = None) -> tuple[list[Any], ProposalAccumulator]:
        """Return (tools, accumulator). Accumulators collect propose-tool outputs."""
        acc = accumulator or ProposalAccumulator()
        tools = [
            *build_read_tools(book_id, self._registry),
            *build_propose_tools(acc),
        ]
        return tools, acc
