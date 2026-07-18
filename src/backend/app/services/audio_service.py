"""AudioService — scene audio drama (docs/audio-system.md).

Owns ``scenes/{id}/audio/``: the JSON manifest plus regenerable line mp3s.
Shape mirrors ``resource_service.py`` (path guards, trash, atomic writes).
ElevenLabs is called only here — never from a subprocess or the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.atomic import atomic_write_bytes, atomic_write_json, atomic_write_text
from app.core.errors import ApiError, not_found, validation
from app.core.secrets import KeyResolutionError, resolve_secret
from app.models.audio import AudioLinePatch, AudioManifest, AudioSequenceItem, Speaker, VoiceSettings
from app.models.enums import AudioLineStatus, AudioSequenceItemType, AudioSynthesisStatus
from app.models.scene import SceneBookkeeping
from app.services.book_registry import BookRegistry
from app.services.settings_service import SettingsService

log = logging.getLogger("authority.audio")

MODEL_ID = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

DEFAULT_GAP_MS = 500
SPEAKER_CHANGE_GAP_MS = 650
SFX_GAP_MS = 400

REQUIRED_GITIGNORE = ("*.tmp", "*.mp3")

SFX_PROMPTS: dict[str, tuple[str, float]] = {
    "WZZIP!": ("Sharp magical whoosh zip teleport, quick sci-fi swoosh", 0.6),
    "BOOM!": ("Massive cinematic explosion fireball impact, deep braam boom", 2.0),
}

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def audio_dir(book_dir: Path, scene_id: str) -> Path:
    path = book_dir / "scenes" / scene_id / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_lines_dir(book_dir: Path, scene_id: str) -> Path:
    path = audio_dir(book_dir, scene_id) / "lines"
    path.mkdir(parents=True, exist_ok=True)
    return path


def manifest_path(book_dir: Path, scene_id: str) -> Path:
    return audio_dir(book_dir, scene_id) / "manifest.json"


def safe_audio_filename(filename: str) -> str:
    name = filename.strip()
    if not name:
        raise validation({"filename": "Name the file."})
    if any(ch in name for ch in ("/", "\\", "\x00")) or name in {".", ".."}:
        raise validation({"filename": "A file name only — no folders or path steps."})
    if name.startswith("."):
        raise validation({"filename": "Names starting with a dot are reserved."})
    return name


def read_manifest_if_exists(book_dir: Path, scene_id: str) -> AudioManifest | None:
    path = book_dir / "scenes" / scene_id / "audio" / "manifest.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AudioManifest.from_raw(raw)
    except Exception as exc:
        log.warning("corrupt audio manifest for %s: %s", scene_id, exc)
        return None


def parse_gitignore_patterns(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def ensure_gitignore_patterns(book_dir: Path, required: tuple[str, ...] = REQUIRED_GITIGNORE) -> list[str]:
    """Append missing required patterns; return the full pattern list."""
    path = book_dir / ".gitignore"
    existing = parse_gitignore_patterns(path.read_text(encoding="utf-8")) if path.is_file() else []
    seen = set(existing)
    changed = False
    for pat in required:
        if pat not in seen:
            existing.append(pat)
            seen.add(pat)
            changed = True
    if changed or not path.is_file():
        atomic_write_text(path, "\n".join(existing) + ("\n" if existing else ""))
    return existing


def write_gitignore_patterns(book_dir: Path, patterns: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for p in patterns:
        t = p.strip()
        if not t or t.startswith("#") or t in seen:
            continue
        normalized.append(t)
        seen.add(t)
    for req in REQUIRED_GITIGNORE:
        if req not in seen:
            normalized.append(req)
            seen.add(req)
    atomic_write_text(book_dir / ".gitignore", "\n".join(normalized) + ("\n" if normalized else ""))
    return normalized


def gap_for_transition(prev: AudioSequenceItem | None, curr: AudioSequenceItem) -> int:
    if prev is None:
        return 0
    if curr.type == AudioSequenceItemType.sfx or prev.type == AudioSequenceItemType.sfx:
        return max(DEFAULT_GAP_MS, SFX_GAP_MS)
    if prev.speaker_id != curr.speaker_id:
        return max(DEFAULT_GAP_MS, SPEAKER_CHANGE_GAP_MS)
    return DEFAULT_GAP_MS


def _line_filename(position: int, item: AudioSequenceItem) -> str:
    speaker = _SAFE_ID_RE.sub("_", item.speaker_id or "sfx").strip("_") or "sfx"
    item_id = _SAFE_ID_RE.sub("_", item.id).strip("_") or "line"
    return f"{position:03d}-{speaker}-{item_id}.mp3"


def _sfx_prompt_for(text: str) -> tuple[str, float]:
    key = (text or "").strip().upper()
    for sheet_key, value in SFX_PROMPTS.items():
        if key == sheet_key.upper():
            return value
    return ((text or "sound effect").strip(), 1.0)


class AudioService:
    def __init__(self, registry: BookRegistry, settings: SettingsService) -> None:
        self._registry = registry
        self._settings = settings

    def _client(self):
        try:
            key = resolve_secret(self._settings.get_raw_elevenlabs_key(), default_env="ELEVENLABS_API_KEY")
        except KeyResolutionError as exc:
            raise ApiError(422, str(exc), {"code": "no-key"}) from exc
        if not key:
            raise ApiError(422, "ElevenLabs API key not configured.", {"code": "no-key"})
        from elevenlabs.client import ElevenLabs

        return ElevenLabs(api_key=key)

    def get_manifest(self, book_id: str, scene_id: str) -> AudioManifest:
        mgr = self._registry.get(book_id)
        ensure_gitignore_patterns(mgr.book_dir)
        manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
        if manifest is None:
            raise not_found("audio", scene_id)
        return manifest

    def get_gitignore(self, book_id: str) -> list[str]:
        mgr = self._registry.get(book_id)
        return ensure_gitignore_patterns(mgr.book_dir)

    async def put_gitignore(self, book_id: str, patterns: list[str]) -> list[str]:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            result = write_gitignore_patterns(mgr.book_dir, patterns)
            mgr.notify_changed()
        return result

    async def save_manifest(
        self,
        book_id: str,
        scene_id: str,
        incoming: AudioManifest,
        *,
        merge: bool = True,
    ) -> AudioManifest:
        """Persist a manifest. When ``merge`` is True (proposal Accept), apply
        UPDATE MODE preservation and assemble authoritative speakers."""
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            ensure_gitignore_patterns(mgr.book_dir)
            existing = read_manifest_if_exists(mgr.book_dir, scene_id) if merge else None
            manifest = self._assemble_and_merge(mgr, scene_id, incoming, existing)
            manifest.updatedAt = _now()
            if merge:
                manifest.synthesisStatus = AudioSynthesisStatus.idle
                manifest.lastError = None
            path = manifest_path(mgr.book_dir, scene_id)
            atomic_write_json(path, manifest.model_dump(mode="json"))
            mgr.notify_changed()
            return manifest

    def _assemble_and_merge(
        self,
        mgr,
        scene_id: str,
        incoming: AudioManifest,
        existing: AudioManifest | None,
    ) -> AudioManifest:
        bookkeeping = mgr.get_scene_bookkeeping(scene_id)
        characters = {c.id: c for c in mgr.get_characters()}
        book = mgr.config

        speakers: dict[str, Speaker] = {}
        for ref in bookkeeping.characters:
            c = characters.get(ref.characterId)
            if c is None:
                continue
            model_sp = incoming.speakers.get(c.id)
            speakers[c.id] = Speaker(
                name=c.name,
                role="dialogue",
                voice_name=c.voiceName,
                voice_id=c.voiceId,
                direction=(model_sp.direction if model_sp else ""),
            )
        narrator_from_model = incoming.speakers.get("narrator")
        speakers["narrator"] = Speaker(
            name="Narrator",
            role="narration",
            voice_name=book.narratorVoiceName,
            voice_id=book.narratorVoiceId,
            direction=(narrator_from_model.direction if narrator_from_model else ""),
        )

        old_by_id = {item.id: item for item in (existing.sequence if existing else [])}
        merged_seq: list[AudioSequenceItem] = []
        for item in incoming.sequence:
            status = item.generation_status
            if status == AudioLineStatus.unchanged and item.id in old_by_id:
                merged_seq.append(old_by_id[item.id].model_copy(deep=True))
                continue
            if status == AudioLineStatus.regenerate and item.id in old_by_id:
                old = old_by_id[item.id]
                new_item = item.model_copy(deep=True)
                new_item.renderedFile = old.renderedFile
                new_item.generation_status = AudioLineStatus.regenerate
                merged_seq.append(new_item)
                continue
            new_item = item.model_copy(deep=True)
            if status == AudioLineStatus.new:
                new_item.renderedFile = None
            merged_seq.append(new_item)

        # Trash orphan mp3s for removed ids
        kept_ids = {i.id for i in merged_seq}
        removed = [oid for oid in old_by_id if oid not in kept_ids]
        if removed:
            self._trash_orphan_files(mgr.book_dir, scene_id, [old_by_id[oid] for oid in removed])

        missing_voices: list[str] = []
        for item in merged_seq:
            if item.type == AudioSequenceItemType.sfx:
                continue
            sid = item.speaker_id
            if not sid or sid not in speakers:
                missing_voices.append(f"line {item.id}: unknown speaker_id {sid!r}")
                continue
            if not speakers[sid].voice_id:
                missing_voices.append(
                    f"{speakers[sid].name} has no ElevenLabs voice assigned — "
                    "set one on the Character Sheet (or Narrator on Metadata → Book) before accepting."
                )
        if missing_voices:
            # Dedupe messages
            uniq = list(dict.fromkeys(missing_voices))
            raise validation({"speakers": uniq})

        revision = incoming.revision
        if existing and revision <= existing.revision:
            revision = existing.revision + 1

        return AudioManifest(
            title=incoming.title or (existing.title if existing else ""),
            revision=revision,
            speakers=speakers,
            notes=incoming.notes,
            sequence=merged_seq,
            synthesisStatus=AudioSynthesisStatus.idle,
            updatedAt=_now(),
            stitchedFile=existing.stitchedFile if existing else None,
            lastError=None,
        )

    def _trash_orphan_files(self, book_dir: Path, scene_id: str, items: list[AudioSequenceItem]) -> None:
        trash = book_dir / ".trash"
        trash.mkdir(parents=True, exist_ok=True)
        lines = audio_lines_dir(book_dir, scene_id)
        for item in items:
            if not item.renderedFile:
                continue
            src = lines / item.renderedFile
            if not src.is_file():
                continue
            dest = trash / f"{item.renderedFile}.{int(datetime.now(timezone.utc).timestamp())}"
            try:
                shutil.move(str(src), str(dest))
            except OSError as exc:
                log.warning("failed to trash %s: %s", src, exc)

    async def update_line(
        self, book_id: str, scene_id: str, item_id: str, patch: AudioLinePatch
    ) -> AudioManifest:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
            if manifest is None:
                raise not_found("audio", scene_id)
            found = False
            for item in manifest.sequence:
                if item.id != item_id:
                    continue
                found = True
                changed = False
                if patch.text is not None and patch.text != item.text:
                    item.text = patch.text
                    changed = True
                if patch.voice_settings is not None:
                    if item.voice_settings != patch.voice_settings:
                        item.voice_settings = patch.voice_settings
                        changed = True
                if changed and item.type != AudioSequenceItemType.sfx:
                    item.generation_status = AudioLineStatus.regenerate
                break
            if not found:
                raise not_found("audio-line", item_id)
            manifest.updatedAt = _now()
            atomic_write_json(manifest_path(mgr.book_dir, scene_id), manifest.model_dump(mode="json"))
            mgr.notify_changed()
            return manifest

    async def write_manifest_status(self, book_id: str, scene_id: str, manifest: AudioManifest) -> None:
        """Internal worker write — no speaker re-validation."""
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            manifest.updatedAt = _now()
            atomic_write_json(manifest_path(mgr.book_dir, scene_id), manifest.model_dump(mode="json"))
            mgr.notify_changed()

    async def synthesize_line(self, book_id: str, scene_id: str, item: AudioSequenceItem) -> str:
        """Call ElevenLabs and write the mp3. Returns the rendered filename."""
        mgr = self._registry.get(book_id)
        manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
        if manifest is None:
            raise not_found("audio", scene_id)

        # Position for filename
        position = next((i for i, it in enumerate(manifest.sequence) if it.id == item.id), 0) + 1
        filename = _line_filename(position, item)
        out_path = audio_lines_dir(mgr.book_dir, scene_id) / filename

        client = self._client()

        def _convert() -> bytes:
            if item.type == AudioSequenceItemType.sfx:
                prompt, duration = _sfx_prompt_for(item.text)
                dur = item.duration_seconds if item.duration_seconds is not None else duration
                influence = item.prompt_influence if item.prompt_influence is not None else 0.5
                audio = client.text_to_sound_effects.convert(
                    text=prompt,
                    duration_seconds=dur,
                    prompt_influence=influence,
                )
                return b"".join(audio)

            speaker = manifest.speakers.get(item.speaker_id or "")
            if speaker is None or not speaker.voice_id:
                raise ApiError(422, f"No voice for speaker {item.speaker_id}.", {"code": "no-voice"})
            vs = item.voice_settings or VoiceSettings()
            from elevenlabs.types import VoiceSettings as ELVoiceSettings

            audio = client.text_to_speech.convert(
                text=item.text,
                voice_id=speaker.voice_id,
                model_id=MODEL_ID,
                output_format=OUTPUT_FORMAT,
                voice_settings=ELVoiceSettings(
                    stability=vs.stability,
                    similarity_boost=vs.similarity_boost,
                ),
            )
            return b"".join(audio)

        data = await asyncio.to_thread(_convert)
        async with mgr.lock:
            atomic_write_bytes(out_path, data)
            # Refresh and update item
            current = read_manifest_if_exists(mgr.book_dir, scene_id)
            if current is None:
                raise not_found("audio", scene_id)
            for it in current.sequence:
                if it.id == item.id:
                    it.renderedFile = filename
                    it.generation_status = AudioLineStatus.unchanged
                    break
            current.updatedAt = _now()
            atomic_write_json(manifest_path(mgr.book_dir, scene_id), current.model_dump(mode="json"))
            mgr.notify_changed()
        return filename

    async def stitch(self, book_id: str, scene_id: str) -> Path:
        mgr = self._registry.get(book_id)
        manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
        if manifest is None:
            raise not_found("audio", scene_id)

        def _stitch() -> bytes:
            from pydub import AudioSegment

            combined = AudioSegment.silent(duration=0)
            prev = None
            lines = audio_lines_dir(mgr.book_dir, scene_id)
            for item in manifest.sequence:
                if not item.renderedFile:
                    continue
                path = lines / item.renderedFile
                if not path.is_file():
                    continue
                gap = gap_for_transition(prev, item)
                if gap:
                    combined += AudioSegment.silent(duration=gap)
                combined += AudioSegment.from_mp3(str(path))
                prev = item
            tmp = audio_dir(mgr.book_dir, scene_id) / "_stitch_tmp.mp3"
            combined.export(str(tmp), format="mp3", bitrate="192k")
            data = tmp.read_bytes()
            tmp.unlink(missing_ok=True)
            return data

        data = await asyncio.to_thread(_stitch)
        out = audio_dir(mgr.book_dir, scene_id) / "scene_stitched.mp3"
        async with mgr.lock:
            atomic_write_bytes(out, data)
            current = read_manifest_if_exists(mgr.book_dir, scene_id)
            if current:
                current.stitchedFile = "scene_stitched.mp3"
                current.updatedAt = _now()
                atomic_write_json(manifest_path(mgr.book_dir, scene_id), current.model_dump(mode="json"))
                mgr.notify_changed()
        return out

    def path_for_line(self, book_id: str, scene_id: str, filename: str) -> Path:
        mgr = self._registry.get(book_id)
        name = safe_audio_filename(filename)
        path = (audio_lines_dir(mgr.book_dir, scene_id) / name).resolve()
        root = audio_lines_dir(mgr.book_dir, scene_id).resolve()
        if path.parent != root or not path.is_file():
            raise not_found("audio-line", name)
        return path

    def path_for_stitched(self, book_id: str, scene_id: str) -> Path:
        mgr = self._registry.get(book_id)
        manifest = read_manifest_if_exists(mgr.book_dir, scene_id)
        if manifest is None or not manifest.stitchedFile:
            raise not_found("audio-stitched", scene_id)
        path = audio_dir(mgr.book_dir, scene_id) / manifest.stitchedFile
        if not path.is_file():
            raise not_found("audio-stitched", scene_id)
        return path

    async def delete_audio(self, book_id: str, scene_id: str) -> None:
        mgr = self._registry.get(book_id)
        async with mgr.lock:
            folder = mgr.book_dir / "scenes" / scene_id / "audio"
            if not folder.exists():
                raise not_found("audio", scene_id)
            trash = mgr.book_dir / ".trash"
            trash.mkdir(parents=True, exist_ok=True)
            dest = trash / f"audio-{scene_id}-{int(datetime.now(timezone.utc).timestamp())}"
            shutil.move(str(folder), str(dest))
            mgr.notify_changed()
