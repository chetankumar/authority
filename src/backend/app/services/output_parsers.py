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
    """Parse enrichment JSON: {summary?, matched?, matchedCharacterIds?, unrecognizedNames?}."""
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

AUDIO_SCRIPT_FORMAT_INSTRUCTIONS = """
When you produce an audio-drama script, end your reply with a fenced JSON object matching this shape
(speakers may be included; voice_id/voice_name are overwritten from the Character Sheet / Narrator on Accept):
```json
{
  "title": "Scene title",
  "revision": 1,
  "speakers": {
    "narrator": { "name": "Narrator", "role": "narration", "voice_name": "", "voice_id": "", "direction": "…" },
    "chr-xxxxxx": { "name": "Name", "role": "dialogue", "voice_name": "", "voice_id": "", "direction": "…" }
  },
  "notes": {
    "removed_ids": [],
    "changelog": "one paragraph or a list of strings",
    "respellings": [{ "id": "1", "prose": "read", "tts": "red" }]
  },
  "sequence": [
    {
      "id": "1",
      "type": "dialogue",
      "speaker": "Name",
      "speaker_id": "chr-xxxxxx",
      "text": "[emotion] spoken line",
      "voice_settings": { "stability": 0.5, "similarity_boost": 0.75 },
      "generation_status": "new",
      "change_reason": ""
    }
  ]
}
```
Required: `sequence` with every item having `id`, `type` (dialogue|narration|sfx), `generation_status` (new|regenerate|unchanged).
Non-sfx items need `speaker_id`, `text`, and `voice_settings` with stability in {0.0, 0.5, 1.0}.
Preceding analysis is fine; the fenced object is what gets accepted.
""".strip()


def parse_audio_script(text: str, scene_id: str) -> tuple[str, list[Proposal]]:
    display, parsed = extract_fenced_json(text)
    if not isinstance(parsed, dict) or "sequence" not in parsed:
        return text, []
    proposal = Proposal(
        id=new_id("prp"),
        type=ProposalType.audio_script_create,
        status=ProposalStatus.pending,
        payload={"sceneId": scene_id, "manifest": parsed, "rationale": ""},
    )
    return display, [proposal]
