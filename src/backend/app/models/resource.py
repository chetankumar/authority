"""Resource schemas (doc 03 §Resources; doc 04 §Resources).

A book resource is a file the author parks alongside the manuscript: research
PDFs, reference images, worldbuilding notes. Unlike every other collection there
is **no persisted record and no id** — ``resources/`` is scanned on read and the
filename is the key. That mirrors ``BookScanner``, which discovers the whole
shelf by folder scan for the same reason: a book folder must survive being
zipped, cloned, or hand-edited (doc 01 hard rule 4). A file dropped into
``resources/`` outside the app simply appears; an index would drift.

So the model below is a response shape only — never written to disk.
"""

from __future__ import annotations

from pydantic import BaseModel


class ResourceFile(BaseModel):
    filename: str
    mimeType: str
    sizeBytes: int
    updatedAt: str
