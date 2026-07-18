"""Scene audio drama schemas (docs/audio-system.md).

Persisted at ``scenes/{id}/audio/manifest.json``. Each sequence item links its
mp3 via ``renderedFile`` (filename under ``lines/``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AudioLineStatus, AudioSequenceItemType, AudioSynthesisStatus


class VoiceSettings(BaseModel):
    stability: float = 0.5
    similarity_boost: float = 0.75


class Speaker(BaseModel):
    name: str
    role: str  # "narration" | "dialogue"
    voice_name: str = ""
    voice_id: str = ""
    direction: str = ""


class AudioSequenceItem(BaseModel):
    id: str
    type: AudioSequenceItemType
    speaker: str | None = None
    speaker_id: str | None = None
    text: str = ""
    voice_settings: VoiceSettings | None = None
    generation_status: AudioLineStatus = AudioLineStatus.new
    change_reason: str = ""
    renderedFile: str | None = None
    duration_seconds: float | None = None
    prompt_influence: float | None = None


class AudioScriptNotes(BaseModel):
    # Directing prompt often emits [{id, prose, tts}]; we also accept {id: "prose→tts"}.
    respellings: list[dict[str, Any]] | dict[str, str] = Field(default_factory=list)
    removed_ids: list[str] = Field(default_factory=list)
    # Directing prompt uses one paragraph; format instructions may use a string list.
    changelog: str | list[str] = ""
    # Allow extra narrative notes from the directing prompt without failing validation.
    model_config = {"extra": "allow"}


class AudioManifest(BaseModel):
    title: str = ""
    revision: int = 1
    speakers: dict[str, Speaker] = Field(default_factory=dict)
    notes: AudioScriptNotes = Field(default_factory=AudioScriptNotes)
    sequence: list[AudioSequenceItem] = Field(default_factory=list)
    synthesisStatus: AudioSynthesisStatus = AudioSynthesisStatus.idle
    updatedAt: str = ""
    stitchedFile: str | None = None
    lastError: str | None = None

    @staticmethod
    def _normalize(data: dict[str, Any]) -> dict[str, Any]:
        """Coerce loosely-typed JSON (numeric ids, camelCase aliases, casing)."""
        raw = dict(data)
        seq = []
        for item in raw.get("sequence") or []:
            entry = dict(item)
            if "id" in entry:
                entry["id"] = str(entry["id"])
            if "generation_status" not in entry and "generationStatus" in entry:
                entry["generation_status"] = entry.pop("generationStatus")
            # Enum fields: tolerate common casing / aliases.
            if "type" in entry and isinstance(entry["type"], str):
                entry["type"] = entry["type"].strip().lower()
            if "generation_status" in entry and isinstance(entry["generation_status"], str):
                entry["generation_status"] = entry["generation_status"].strip().lower()
            seq.append(entry)
        raw["sequence"] = seq
        speakers = {}
        for key, sp in (raw.get("speakers") or {}).items():
            speakers[str(key)] = sp
        raw["speakers"] = speakers
        notes = raw.get("notes")
        if isinstance(notes, dict):
            notes = dict(notes)
            removed = notes.get("removed_ids") or notes.get("removedIds") or []
            notes["removed_ids"] = [str(x) for x in removed]
            raw["notes"] = notes
        return raw

    @classmethod
    def from_disk(cls, data: dict[str, Any]) -> AudioManifest:
        """Load a persisted manifest — keep synthesis / renderedFile fields."""
        return cls.model_validate(cls._normalize(data))

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> AudioManifest:
        """Parse an AI/proposal payload — strip runtime fields the model may echo."""
        raw = cls._normalize(data)
        raw.pop("synthesisStatus", None)
        raw.pop("updatedAt", None)
        raw.pop("stitchedFile", None)
        raw.pop("lastError", None)
        for item in raw.get("sequence") or []:
            if isinstance(item, dict):
                item.pop("renderedFile", None)
                item.pop("duration_seconds", None)
        return cls.model_validate(raw)


class AudioLinePatch(BaseModel):
    text: str | None = None
    voice_settings: VoiceSettings | None = None


class GitignoreBody(BaseModel):
    patterns: list[str] = Field(default_factory=list)


class VoiceSuggestBody(BaseModel):
    """Optional unsaved form overrides — Suggest should use what the author sees, not only disk."""

    name: str | None = None
    age: str | None = None
    gender: str | None = None
    nationality: str | None = None
    ethnicity: str | None = None
    occupation: str | None = None
    personality: str | None = None
    history: str | None = None
    want: str | None = None
    need: str | None = None
    flaw: str | None = None
    arc: str | None = None
    notes: str | None = None


class VoiceSuggestResponse(BaseModel):
    voiceId: str | None = None
    rationale: str = ""
