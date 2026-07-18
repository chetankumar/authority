"""Book schemas (doc 03 §Book folder / config/book.json; doc 04 §2.2, §4).

The persisted shape is ``config/book.json``. The shelf returns lightweight
``BookSummary`` rows (a live scan of books-home). Parts/chapters are linked
lists here; the API returns them pre-ordered — but creation seeds them empty.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Bookkeeping(BaseModel):
    """Standing consents for EnrichmentService; both default on for new books."""

    summaryOnSave: bool = True
    charactersOnSave: bool = True


class Part(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    seq: int = 0


class Chapter(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    partId: str | None = None
    seq: int = 0


class BookConfig(BaseModel):
    """Persisted ``config/book.json``. Parts and chapters live in db/ files."""

    id: str
    title: str
    systemPrompt: str = ""
    storySummary: str = ""
    narratorVoiceId: str = ""
    narratorVoiceName: str = ""
    bookkeeping: Bookkeeping = Field(default_factory=Bookkeeping)


class Book(BaseModel):
    """Full book context (doc 04 §2.2). ``parts``/``chapters`` are returned
    chain-ordered; ``hasCover`` is computed from the assets folder.
    """

    id: str
    title: str
    hasCover: bool = False
    systemPrompt: str = ""
    storySummary: str = ""
    narratorVoiceId: str = ""
    narratorVoiceName: str = ""
    bookkeeping: Bookkeeping = Field(default_factory=Bookkeeping)
    parts: list[Part] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)


class BookSummary(BaseModel):
    """Shelf row (doc 04 §2.2). A broken book.json surfaces as ``error=True``."""

    id: str
    title: str
    folderName: str
    hasCover: bool = False
    error: bool = False


class BookCreate(BaseModel):
    title: str = Field(min_length=1)
