"""SearchService — per-book Chroma index + ask/answer (derived, not manuscript).

Chroma lives at ``{bookDir}/search-index/`` (gitignored). Re-index of a scene
always deletes that scene's vectors first. Ask retrieves matching slices, then
one-shots an answer from those slices — never whole scenes, never a conversation.
"""

from __future__ import annotations

import logging
import os
import shutil

# Chroma's PostHog client is broken on current posthog; disable before import.
os.environ["ANONYMIZED_TELEMETRY"] = "False"
logging.getLogger("chromadb.telemetry.product.posthog").disabled = True

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.atomic import atomic_write_json
from app.core.errors import ApiError, not_found, validation
from app.models.enums import SceneStatus
from app.models.search import IndexedScene, SearchAskResponse, SearchHit, SearchIndexStatus
from app.models.settings import ModelConfig
from app.services.book_registry import BookRegistry
from app.services.chain_service import compute_seq_placement
from app.services.context_assembler import ContextAssembler
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.search")

COLLECTION = "scene_chunks"
CHUNK_LINES = 100
SNIPPET_LEN = 220
QUERY_N = 20
ANSWER_CHUNKS = 8
RRF_K = 60
SUMMARIZE_TIMEOUT = 90.0
ANSWER_TIMEOUT = 60.0

_SUMMARY_PROMPT = """Write a detailed retrieval summary of this novel excerpt.
Cover who is present, where they are, what happens, objects and facts a later
search might look for. Do not transcribe dialogue. Do not invent. 120–200 words.

Scene title: {title}

Excerpt (lines {start}–{end}):
{prose}
"""

_ANSWER_PROMPT = """You answer questions about a novel from retrieved excerpts only.
Write a concise answer (one short paragraph, or a few bullets). Name the scene
title when you rely on it. If the excerpts are not enough, say so. Do not invent.

Question:
{question}

Excerpts:
{excerpts}
"""


def search_index_dir(book_dir: Path) -> Path:
    return book_dir / "search-index"


def catalog_path(book_dir: Path) -> Path:
    return search_index_dir(book_dir) / "catalog.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def chunk_lines(text: str, size: int = CHUNK_LINES) -> list[tuple[int, int, str]]:
    """Return (1-based lineStart, lineEnd, chunk text) for non-empty groups."""
    lines = text.splitlines()
    if not lines:
        return []
    out: list[tuple[int, int, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        piece = lines[i : i + size]
        start = i + 1
        end = i + len(piece)
        body = "\n".join(piece).strip()
        if body:
            out.append((start, end, "\n".join(piece)))
        i += size
    return out


def _snippet(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= SNIPPET_LEN:
        return compact
    return compact[: SNIPPET_LEN - 1] + "…"


def _rrf_merge(ranked_id_lists: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_id_lists:
        for rank, key in enumerate(ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
    return scores


class SearchService:
    def __init__(
        self,
        registry: BookRegistry,
        settings: SettingsService,
        orchestrator: Any,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._orch = orchestrator
        self._assembler = ContextAssembler()
        self._clients: dict[str, Any] = {}

    def _dir(self, book_id: str) -> Path:
        return search_index_dir(self._registry.get(book_id).book_dir)

    def _client(self, book_id: str) -> Any:
        existing = self._clients.get(book_id)
        if existing is not None:
            return existing
        import chromadb

        path = self._dir(book_id)
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(path))
        self._clients[book_id] = client
        return client

    def _collection(self, book_id: str) -> Any:
        return self._client(book_id).get_or_create_collection(name=COLLECTION)

    def drop_client(self, book_id: str) -> None:
        self._clients.pop(book_id, None)

    def _read_catalog(self, book_id: str) -> dict[str, Any]:
        path = catalog_path(self._registry.get(book_id).book_dir)
        if not path.is_file():
            return {"scenes": {}}
        try:
            import json

            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("scenes"), dict):
                return raw
        except Exception:
            log.warning("unreadable search catalog for %s", book_id)
        return {"scenes": {}}

    def _write_catalog(self, book_id: str, catalog: dict[str, Any]) -> None:
        mgr = self._registry.get(book_id)
        dest = search_index_dir(mgr.book_dir)
        dest.mkdir(parents=True, exist_ok=True)
        atomic_write_json(catalog_path(mgr.book_dir), catalog)

    def index_status(self, book_id: str, run: dict[str, Any] | None = None) -> SearchIndexStatus:
        self._registry.get(book_id)
        catalog = self._read_catalog(book_id)
        scenes = [
            IndexedScene(
                id=sid,
                contentHash=str(row.get("contentHash") or ""),
                chunkCount=int(row.get("chunkCount") or 0),
                indexedAt=str(row.get("indexedAt") or ""),
            )
            for sid, row in catalog.get("scenes", {}).items()
            if isinstance(row, dict)
        ]
        scenes.sort(key=lambda s: s.id)
        status = SearchIndexStatus(
            status="idle",
            indexedSceneCount=len(scenes),
            scenes=scenes,
        )
        if run:
            status.status = str(run.get("status") or "idle")
            status.sceneId = run.get("sceneId")
            status.done = int(run.get("done") or 0)
            status.total = int(run.get("total") or 0)
            status.error = run.get("error")
        return status

    def require_summary_model(self) -> ModelConfig:
        cfg = self._settings.get_scene_summary_model()
        if cfg is None:
            raise ApiError(
                422,
                "No model configured for indexing or answering search.",
                {"code": "no-utility-model"},
            )
        return cfg

    def require_scene(self, book_id: str, scene_id: str) -> None:
        mgr = self._registry.get(book_id)
        if not any(r.id == scene_id for r in mgr.get_scenes()):
            raise not_found("scene", scene_id)

    def list_indexable_scene_ids(self, book_id: str) -> list[str]:
        mgr = self._registry.get(book_id)
        return [r.id for r in mgr.get_scenes() if r.status == SceneStatus.active]

    async def index_scene(self, book_id: str, scene_id: str) -> None:
        """Wipe this scene's vectors, then rebuild from current prose."""
        mgr = self._registry.get(book_id)
        records = mgr.get_scenes()
        record = next((r for r in records if r.id == scene_id), None)
        if record is None:
            raise not_found("scene", scene_id)

        model = self.require_summary_model()
        bookkeeping = mgr.get_scene_bookkeeping(scene_id)
        content = mgr.read_scene_content(record.file)
        chunks = chunk_lines(content)
        seq_map = compute_seq_placement(records, set())
        seq, _ = seq_map.get(scene_id, (None, None))

        async with mgr.lock:
            col = self._collection(book_id)
            try:
                col.delete(where={"sceneId": scene_id})
            except Exception:
                log.debug("no prior vectors for %s", scene_id)

            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict[str, Any]] = []

            for idx, (line_start, line_end, prose) in enumerate(chunks):
                summary = await self._summarize_chunk(model, record.title, line_start, line_end, prose)
                meta_base: dict[str, Any] = {
                    "sceneId": scene_id,
                    "title": record.title,
                    "seq": int(seq) if seq is not None else -1,
                    "chunkIndex": idx,
                    "lineStart": line_start,
                    "lineEnd": line_end,
                    "contentHash": bookkeeping.contentHash or "",
                }
                ids.append(f"{scene_id}:{idx}:summary")
                documents.append(summary)
                metadatas.append({**meta_base, "kind": "summary"})
                ids.append(f"{scene_id}:{idx}:prose")
                documents.append(prose)
                metadatas.append({**meta_base, "kind": "prose"})

            if ids:
                col.upsert(ids=ids, documents=documents, metadatas=metadatas)

            catalog = self._read_catalog(book_id)
            scenes = dict(catalog.get("scenes") or {})
            scenes[scene_id] = {
                "contentHash": bookkeeping.contentHash or "",
                "chunkCount": len(chunks),
                "indexedAt": _now(),
            }
            catalog["scenes"] = scenes
            self._write_catalog(book_id, catalog)

    async def delete_index(self, book_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            self.drop_client(book_id)
            path = search_index_dir(mgr.book_dir)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

    async def ask(self, book_id: str, question: str) -> SearchAskResponse:
        q = question.strip()
        if not q:
            raise validation({"question": "Ask a question."})

        mgr = self._registry.get(book_id)
        catalog = self._read_catalog(book_id)
        indexed_count = len(catalog.get("scenes") or {})
        if indexed_count == 0:
            return SearchAskResponse(
                answer="Nothing is indexed yet. Index a scene from the editor, or rebuild from Metadata → Book.",
                hits=[],
                indexedSceneCount=0,
            )

        hashes = {
            r.id: mgr.get_scene_bookkeeping(r.id).contentHash or ""
            for r in mgr.get_scenes()
        }

        col = self._collection(book_id)
        semantic_keys, by_key = self._semantic_hits(col, q)
        keyword_keys, kw_docs = self._keyword_hits(col, q)
        for key, rec in kw_docs.items():
            by_key.setdefault(key, rec)

        scores = _rrf_merge([semantic_keys, keyword_keys])
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

        hits: list[SearchHit] = []
        seen_chunks: set[str] = set()
        for key, score in ranked:
            rec = by_key.get(key)
            if rec is None:
                continue
            chunk_key = f"{rec['sceneId']}:{rec['chunkIndex']}"
            if chunk_key in seen_chunks:
                continue
            seen_chunks.add(chunk_key)
            scene_id = rec["sceneId"]
            stored_hash = rec.get("contentHash") or ""
            current = hashes.get(scene_id, stored_hash)
            seq_raw = rec.get("seq", -1)
            seq = None if seq_raw in (-1, None) else int(seq_raw)
            hits.append(
                SearchHit(
                    sceneId=scene_id,
                    title=str(rec.get("title") or ""),
                    seq=seq,
                    chunkIndex=int(rec.get("chunkIndex") or 0),
                    kind=str(rec.get("kind") or "summary"),
                    snippet=_snippet(str(rec.get("document") or "")),
                    score=round(float(score), 6),
                    stale=bool(stored_hash and current and stored_hash != current),
                )
            )

        if not hits:
            return SearchAskResponse(
                answer="No matching passages in the index. Try different wording, or re-index scenes.",
                hits=[],
                indexedSceneCount=indexed_count,
            )

        answer = await self._answer(q, hits, by_key)
        return SearchAskResponse(answer=answer, hits=hits[:20], indexedSceneCount=indexed_count)

    def _semantic_hits(self, col: Any, q: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
        by_key: dict[str, dict[str, Any]] = {}
        try:
            result = col.query(query_texts=[q], n_results=QUERY_N, include=["documents", "metadatas"])
        except Exception:
            log.exception("chroma semantic query failed")
            return [], {}
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        order: list[str] = []
        for i, doc_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            key = f"{meta.get('sceneId')}:{meta.get('chunkIndex')}"
            rec = {
                "sceneId": meta.get("sceneId") or "",
                "title": meta.get("title") or "",
                "seq": meta.get("seq", -1),
                "chunkIndex": meta.get("chunkIndex") or 0,
                "kind": meta.get("kind") or "",
                "contentHash": meta.get("contentHash") or "",
                "document": docs[i] if i < len(docs) else "",
            }
            if key not in by_key:
                by_key[key] = rec
                order.append(key)
        return order, by_key

    def _keyword_hits(self, col: Any, q: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
        if len(q) < 2:
            return [], {}
        by_key: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        try:
            result = col.get(
                where_document={"$contains": q},
                limit=QUERY_N,
                include=["documents", "metadatas"],
            )
        except Exception:
            log.debug("chroma keyword query failed", exc_info=True)
            return [], {}
        ids = result.get("ids") or []
        docs = result.get("documents") or []
        metas = result.get("metadatas") or []
        for i, _doc_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            key = f"{meta.get('sceneId')}:{meta.get('chunkIndex')}"
            rec = {
                "sceneId": meta.get("sceneId") or "",
                "title": meta.get("title") or "",
                "seq": meta.get("seq", -1),
                "chunkIndex": meta.get("chunkIndex") or 0,
                "kind": meta.get("kind") or "",
                "contentHash": meta.get("contentHash") or "",
                "document": docs[i] if i < len(docs) else "",
            }
            if key not in by_key:
                by_key[key] = rec
                order.append(key)
        return order, by_key

    async def _summarize_chunk(
        self, model: ModelConfig, title: str, start: int, end: int, prose: str
    ) -> str:
        prompt = _SUMMARY_PROMPT.format(title=title, start=start, end=end, prose=prose[:12000])
        messages = self._assembler.for_once(prompt)
        try:
            text = await self._orch.invoke_once(model, messages, timeout=SUMMARIZE_TIMEOUT)
        except Exception:
            log.exception("chunk summary failed; storing a truncated excerpt instead")
            return _snippet(prose) or "(empty excerpt)"
        text = (text or "").strip()
        return text or _snippet(prose)

    async def _answer(
        self, question: str, hits: list[SearchHit], by_key: dict[str, dict[str, Any]]
    ) -> str:
        try:
            model = self.require_summary_model()
        except ApiError:
            return "No model is configured to write an answer. Matching scenes are listed below."

        blocks: list[str] = []
        for hit in hits[:ANSWER_CHUNKS]:
            rec = by_key.get(f"{hit.sceneId}:{hit.chunkIndex}") or {}
            prose = rec.get("document") or hit.snippet
            blocks.append(f"### {hit.title} (chunk {hit.chunkIndex + 1}, {hit.kind})\n{prose}")
        prompt = _ANSWER_PROMPT.format(question=question, excerpts="\n\n".join(blocks))
        messages = self._assembler.for_once(prompt)
        try:
            text = await self._orch.invoke_once(model, messages, timeout=ANSWER_TIMEOUT)
        except Exception as exc:
            log.warning("search answer failed: %s", exc)
            return "Couldn't write an answer. Matching scenes are listed below."
        return (text or "").strip() or "Couldn't write an answer. Matching scenes are listed below."
