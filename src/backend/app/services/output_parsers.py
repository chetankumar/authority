"""Output parsers for structured AI responses (doc 05)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.ids import new_id
from app.models.enums import ProposalStatus, ProposalType
from app.models.proposal import Proposal

log = logging.getLogger("authority.ai")

_FENCED_JSON = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_fenced_json(text: str) -> tuple[str, Any | None]:
    """Strip the last fenced JSON block from ``text``. Returns (display_text, parsed)."""
    matches = list(_FENCED_JSON.finditer(text))
    if not matches:
        # Try whole-text JSON array/object as last resort.
        stripped = text.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                return "", json.loads(stripped)
            except json.JSONDecodeError:
                return text, None
        return text, None

    last = matches[-1]
    display = (text[: last.start()] + text[last.end() :]).strip()
    try:
        return display, json.loads(last.group(1).strip())
    except json.JSONDecodeError as exc:
        log.warning("failed to parse fenced JSON: %s", exc)
        return text, None


def parse_edit_proposals(text: str, scene_id: str) -> tuple[str, list[Proposal]]:
    display, parsed = extract_fenced_json(text)
    if not isinstance(parsed, list):
        return text, []
    proposals: list[Proposal] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        find = item.get("find")
        replace = item.get("replace")
        if not isinstance(find, str) or not isinstance(replace, str):
            continue
        proposals.append(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.edit,
                status=ProposalStatus.pending,
                payload={
                    "sceneId": scene_id,
                    "find": find,
                    "replace": replace,
                    "rationale": str(item.get("rationale") or ""),
                },
            )
        )
    return display if proposals else text, proposals


def parse_metadata_proposals(text: str, scene_id: str) -> tuple[str, list[Proposal]]:
    display, parsed = extract_fenced_json(text)
    if not isinstance(parsed, list):
        return text, []
    proposals: list[Proposal] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        if not isinstance(field, str) or not field:
            continue
        proposals.append(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.metadata_update,
                status=ProposalStatus.pending,
                payload={
                    "targetType": "scene",
                    "targetId": scene_id,
                    "field": field,
                    "oldValue": item.get("oldValue"),
                    "newValue": item.get("newValue"),
                    "rationale": str(item.get("rationale") or ""),
                },
            )
        )
    return display if proposals else text, proposals


def parse_enrichment_result(text: str) -> dict[str, Any]:
    """Parse enrichment JSON: {summary?, characterIds?, unrecognizedNames?}."""
    _, parsed = extract_fenced_json(text)
    if isinstance(parsed, dict):
        return parsed
    # Bare summary text.
    return {"summary": text.strip()}


EDIT_FORMAT_INSTRUCTIONS = """
When you propose prose edits, end your reply with a fenced JSON array of objects:
```json
[{"find": "exact current text", "replace": "replacement", "rationale": "why"}]
```
Use exact substrings from the scene. Preceding commentary is fine.
""".strip()

METADATA_FORMAT_INSTRUCTIONS = """
When you propose metadata updates, end your reply with a fenced JSON array of objects:
```json
[{"field": "mood", "newValue": "elegiac", "rationale": "why"}]
```
Field must be a scene metadata field (never prose). Preceding commentary is fine.
""".strip()
