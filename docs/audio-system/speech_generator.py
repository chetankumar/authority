"""
Generate scene audio from speech_ref.json via ElevenLabs.

Pipeline:
  1. TTS each dialogue/narration line (eleven_v3 + per-line voice_settings)
  2. Sound Effects API for type=sfx nodes
  3. Stitch lines + gaps into scene_stitched.mp3

Usage:
  python speech_generator.py
  python speech_generator.py --skip-existing-lines
  python speech_generator.py --stitch-only --gap-ms 500
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from pydub import AudioSegment

ROOT = Path(__file__).resolve().parent
SCENE_PATH = ROOT / "speech_ref.json"
LINES_DIR = ROOT / "output" / "lines"
OUTPUT_MP3 = ROOT / "output" / "scene_stitched.mp3"

MODEL_ID = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"

DEFAULT_GAP_MS = 500
SPEAKER_CHANGE_GAP_MS = 650
SFX_GAP_MS = 400

# Sheet onomatopoeia -> descriptive Sound Effects prompts
SFX_PROMPTS: dict[str, tuple[str, float]] = {
    "WZZIP!": (
        "Sharp magical whoosh zip teleport, quick sci-fi swoosh",
        0.6,
    ),
    "BOOM!": (
        "Massive cinematic explosion fireball impact, deep braam boom",
        2.0,
    ),
}


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def line_filename(item: dict) -> str:
    sid = int(item["id"])
    speaker = slug(item.get("speaker") or "sfx")
    return f"{sid:03d}-{speaker}.mp3"


def load_scene(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def sfx_prompt_for(text: str) -> tuple[str, float]:
    key = (text or "").strip().upper()
    for sheet_key, value in SFX_PROMPTS.items():
        if key == sheet_key.upper():
            return value
    return ((text or "sound effect").strip(), 1.0)


def voice_settings_for(item: dict) -> VoiceSettings:
    vs = item.get("voice_settings") or {}
    return VoiceSettings(
        stability=float(vs.get("stability", 0.5)),
        similarity_boost=float(vs.get("similarity_boost", 0.75)),
    )


def gap_for_transition(prev: dict | None, curr: dict, default_gap_ms: int) -> int:
    if prev is None:
        return 0
    if curr.get("type") == "sfx" or prev.get("type") == "sfx":
        return max(default_gap_ms, SFX_GAP_MS)
    if prev.get("speaker_id") != curr.get("speaker_id"):
        return max(default_gap_ms, SPEAKER_CHANGE_GAP_MS)
    return default_gap_ms


def generate_lines(
    client: ElevenLabs,
    scene: dict,
    skip_existing: bool,
) -> list[Path]:
    LINES_DIR.mkdir(parents=True, exist_ok=True)
    speakers = scene["speakers"]
    written: list[Path] = []
    total = len(scene["sequence"])

    for i, item in enumerate(scene["sequence"], 1):
        out_path = LINES_DIR / line_filename(item)
        written.append(out_path)

        if skip_existing and out_path.exists():
            print(f"[skip] {i}/{total} {out_path.name}")
            continue

        if item.get("type") == "sfx":
            prompt, duration = sfx_prompt_for(item.get("text") or "")
            print(f"[sfx ] {i}/{total} {out_path.name} ({duration}s)...")
            audio = client.text_to_sound_effects.convert(
                text=prompt,
                duration_seconds=duration,
                prompt_influence=0.5,
            )
            out_path.write_bytes(b"".join(audio))
            print(f"  saved {out_path.name}")
            continue

        speaker_id = str(item["speaker_id"])
        meta = speakers[speaker_id]
        voice_id = meta["voice_id"]
        text = item["text"]
        settings = voice_settings_for(item)
        print(
            f"[tts ] {i}/{total} {out_path.name} "
            f"({meta.get('voice_name', voice_id)}, "
            f"stability={settings.stability})..."
        )
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=MODEL_ID,
            output_format=OUTPUT_FORMAT,
            voice_settings=settings,
        )
        out_path.write_bytes(b"".join(audio))
        print(f"  saved {out_path.name}")

    return written


def stitch_to_mp3(
    scene: dict,
    line_paths: list[Path],
    out_mp3: Path,
    default_gap_ms: int,
) -> None:
    sequence = scene["sequence"]
    combined = AudioSegment.silent(duration=0)
    prev = None
    for item, path in zip(sequence, line_paths):
        if not path.exists():
            print(f"[warn] missing {path}, skipping in stitch")
            continue
        gap_ms = gap_for_transition(prev, item, default_gap_ms)
        if gap_ms:
            combined += AudioSegment.silent(duration=gap_ms)
        combined += AudioSegment.from_mp3(str(path))
        prev = item

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(out_mp3), format="mp3", bitrate="192k")
    print(f"[mp3 ] wrote {out_mp3} ({len(combined) / 1000:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate scene audio from speech_ref.json (ElevenLabs TTS + SFX)"
    )
    parser.add_argument("--scene", type=Path, default=SCENE_PATH)
    parser.add_argument("--gap-ms", type=int, default=DEFAULT_GAP_MS)
    parser.add_argument("--no-stitch", action="store_true")
    parser.add_argument("--skip-existing-lines", action="store_true")
    parser.add_argument("--stitch-only", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    scene = load_scene(args.scene)

    if args.stitch_only:
        paths = [LINES_DIR / line_filename(item) for item in scene["sequence"]]
        stitch_to_mp3(scene, paths, OUTPUT_MP3, args.gap_ms)
        return

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY is not set. Add it to your environment or a .env file.")
        sys.exit(1)

    client = ElevenLabs(api_key=api_key)
    line_paths = generate_lines(
        client,
        scene,
        skip_existing=args.skip_existing_lines,
    )

    if not args.no_stitch:
        stitch_to_mp3(scene, line_paths, OUTPUT_MP3, args.gap_ms)

    print("Done.")


if __name__ == "__main__":
    main()
