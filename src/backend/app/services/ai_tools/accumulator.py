"""ProposalAccumulator — collects propose-tool outputs during one stream."""

from __future__ import annotations

from app.models.proposal import Proposal


class ProposalAccumulator:
    def __init__(self) -> None:
        self._items: list[Proposal] = []

    def add(self, proposal: Proposal) -> None:
        self._items.append(proposal)

    def all(self) -> list[Proposal]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()
