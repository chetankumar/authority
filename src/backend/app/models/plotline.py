"""Plotline schemas (doc 03 §db/plotlines.json; doc 04 §2.2, §7).

Plotlines do not store scene references. The relationship is owned by scenes
via ``primaryPlotlineId`` and ``secondaryPlotlineIds``. ``sceneCount`` is
computed by scanning scenes on read.
"""

from __future__ import annotations

from pydantic import BaseModel


class PlotlineRecord(BaseModel):
    """Persisted row in ``db/plotlines.json``."""

    id: str
    title: str
    description: str = ""


class Plotline(PlotlineRecord):
    """API response: record + computed sceneCount."""

    sceneCount: int = 0
