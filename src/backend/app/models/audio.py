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
    respellings: dict[str, str] = Field(default_factory=dict)
    removed_ids: list[str] = Field(default_factory=list)
    changelog: list[str] = Field(default_factory=list)
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

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> AudioManifest:
        """Coerce loosely-typed model JSON (e.g. numeric ids) into our schema."""
        raw = dict(data)
        seq = []
        for item in raw.get("sequence") or []:
            entry = dict(item)
            if "id" in entry:
                entry["id"] = str(entry["id"])
            if "generation_status" not in entry and "generationStatus" in entry:
                entry["generation_status"] = entry.pop("generationStatus")
            seq.append(entry)
        raw["sequence"] = seq
        speakers = {}
        for key, sp in (raw.get("speakers") or {}).items():
            speakers[str(key)] = sp
        raw["speakers"] = speakers
        return cls.model_validate(raw)


class AudioLinePatch(BaseModel):
    text: str | None = None
    voice_settings: VoiceSettings | None = None


class GitignoreBody(BaseModel):
    patterns: list[str] = Field(default_factory=list)


class VoiceSuggestResponse(BaseModel):
    voiceId: str | None = None
    rationale: str = ""
