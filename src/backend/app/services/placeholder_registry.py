"""PlaceholderRegistry (doc 05).

Server-defined placeholder vocabulary. Single source of truth for the frontend
`@` autocomplete and for AI-Job prompt save-time validation. Token grammar:
``@[a-z0-9_]+``.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.settings import Placeholder

TOKEN_RE = re.compile(r"@[a-z0-9_]+")

# Order is display order in the autocomplete.
_REGISTRY: list[Placeholder] = [
    Placeholder(name="@current_scene", description="Full prose of the target scene"),
    Placeholder(name="@selection", description="The selected text (empty if none)"),
    Placeholder(name="@selection_or_scene", description="Selection if present, else full scene"),
    Placeholder(
        name="@scene_metadata",
        description="Title, description, location, dateTime, mood, arc, summary of the target scene",
    ),
    Placeholder(name="@scene_characters", description="Character sheets of characters tagged in the scene"),
    Placeholder(name="@character_sheet", description="All character sheets in the book"),
    Placeholder(
        name="@previous_scenes_summary",
        description="Hard prev-chain back to Start, in story order as 'Title — summary' lines",
    ),
    Placeholder(name="@all_scene_summaries", description="Every active scene's title + summary in seq order"),
    Placeholder(name="@story_summary", description="The book's story summary"),
    Placeholder(name="@plotlines", description="Plotline titles + descriptions, this scene's links flagged"),
]

_NAMES = {p.name for p in _REGISTRY}


class PlaceholderRegistry:
    @staticmethod
    def all() -> list[Placeholder]:
        return list(_REGISTRY)

    @staticmethod
    def unknown_tokens(prompt: str) -> list[str]:
        """Return distinct tokens in the prompt that are not registered, in order."""
        seen: list[str] = []
        for match in TOKEN_RE.findall(prompt):
            if match not in _NAMES and match not in seen:
                seen.append(match)
        return seen

    @staticmethod
    def resolve(
        prompt: str,
        *,
        mgr: Any,
        scene_id: str,
        selection_text: str | None = None,
    ) -> str:
        """Replace ``@tokens`` with book/scene context at run time."""
        from app.models.enums import SceneStatus
        from app.models.scene import START_ID, SceneBookkeeping, SceneMeta
        from app.services import chain_service as chain

        records = {r.id: r for r in mgr.get_scenes()}
        scene = records.get(scene_id)
        prose = mgr.read_scene_content(scene.file) if scene else ""
        selection = selection_text or ""
        all_meta = mgr.get_all_meta()
        all_bookkeeping = mgr.get_all_bookkeeping()

        def scene_meta(s: Any) -> str:
            if s is None:
                return ""
            meta = all_meta.get(s.id, SceneMeta())
            bookkeeping = all_bookkeeping.get(s.id, SceneBookkeeping())
            return "\n".join(
                [
                    f"Title: {s.title}",
                    f"Description: {s.description}",
                    f"Location: {meta.location}",
                    f"Date/Time: {meta.dateTime}",
                    f"Mood: {meta.mood}",
                    f"Emotional arc: {meta.emotionalArc}",
                    f"Summary: {bookkeeping.summary or '(no summary)'}",
                ]
            )

        def previous_summaries() -> str:
            if scene is None:
                return ""
            # Walk prev chain toward Start, then reverse for story order.
            chain_back: list[Any] = []
            cur = scene.previousSceneId
            seen: set[str] = set()
            while cur and cur != START_ID and cur in records and cur not in seen:
                seen.add(cur)
                rec = records[cur]
                if rec.status == SceneStatus.active:
                    chain_back.append(rec)
                cur = rec.previousSceneId
            chain_back.reverse()
            lines = [
                f"{r.title} — {all_bookkeeping.get(r.id, SceneBookkeeping()).summary or '(no summary)'}"
                for r in chain_back
            ]
            return "\n".join(lines) if lines else "(none)"

        def all_summaries() -> str:
            rels = mgr.get_relationships()
            rel_ids = {r.fromSceneId for r in rels} | {r.toSceneId for r in rels}
            computed = chain.compute_seq_placement(list(mgr.get_scenes()), rel_ids)
            active = [r for r in mgr.get_scenes() if r.status == SceneStatus.active]
            active.sort(key=lambda r: (computed.get(r.id, (10**9, None))[0] or 10**9, r.id))
            return "\n".join(
                f"{r.title} — {all_bookkeeping.get(r.id, SceneBookkeeping()).summary or '(no summary)'}"
                for r in active
            )

        def format_character(c: Any) -> str:
            aliases = ", ".join(getattr(c, "aliases", []) or [])
            lines = [c.name + (f" (aka {aliases})" if aliases else "")]
            facts = [
                f"{label}: {value}"
                for label, value in (
                    ("Age", c.age),
                    ("Gender", c.gender),
                    ("Nationality", c.nationality),
                    ("Ethnicity", c.ethnicity),
                    ("Occupation", c.occupation),
                )
                if value
            ]
            if facts:
                lines.append("  " + " · ".join(facts))
            craft = [
                f"{label}: {value}"
                for label, value in (
                    ("Want", c.want),
                    ("Need", c.need),
                    ("Flaw", c.flaw),
                    ("Arc", c.arc),
                )
                if value
            ]
            if craft:
                lines.append("  " + " · ".join(craft))
            for label, value in (("Personality", c.personality), ("History", c.history), ("Notes", c.notes)):
                if value:
                    lines.append(f"  {label}: {value}")
            return "\n".join(lines)

        def character_sheet_all() -> str:
            getter = getattr(mgr, "get_characters", None)
            if getter is None:
                return "(character sheet not loaded)"
            chars = getter()
            if not chars:
                return "(no characters)"
            by_id = {c.id: c for c in chars}
            parts = [format_character(c) for c in chars]

            rel_getter = getattr(mgr, "get_character_relationships", None)
            rels = rel_getter() if rel_getter else []
            rel_lines = []
            for r in rels:
                a, b = by_id.get(r.characterAId), by_id.get(r.characterBId)
                if a and b:
                    line = f"{a.name} is {r.aToB} {b.name}; {b.name} is {r.bToA} {a.name}."
                    if r.description:
                        line += f" {r.description}"
                    rel_lines.append(line)
            if rel_lines:
                parts.append("Relationships:\n" + "\n".join(rel_lines))

            return "\n\n".join(parts)

        def scene_characters() -> str:
            if scene is None:
                return "(none tagged)"
            refs = all_bookkeeping.get(scene.id, SceneBookkeeping()).characters
            if not refs:
                return "(none tagged)"
            getter = getattr(mgr, "get_characters", None)
            if getter is None:
                return "(character sheet not loaded)"
            by_id = {c.id: c for c in getter()}
            entries = []
            for ref in refs:
                c = by_id.get(ref.characterId)
                if c is None:
                    continue
                block = format_character(c)
                if ref.involvement.strip():
                    block = f"{block}\nIn this scene: {ref.involvement.strip()}"
                entries.append(block)
            return "\n\n".join(entries) if entries else "(none tagged)"

        def plotlines() -> str:
            pls = mgr.get_plotlines()
            if not pls:
                return "(none)"
            lines = []
            for p in pls:
                flag = ""
                if scene and (
                    scene.primaryPlotlineId == p.id or p.id in (scene.secondaryPlotlineIds or [])
                ):
                    flag = " [this scene]"
                lines.append(f"{p.title}: {p.description or ''}{flag}".rstrip())
            return "\n".join(lines)

        replacements = {
            "@current_scene": prose,
            "@selection": selection,
            "@selection_or_scene": selection if selection else prose,
            "@scene_metadata": scene_meta(scene),
            "@scene_characters": scene_characters(),
            "@character_sheet": character_sheet_all(),
            "@previous_scenes_summary": previous_summaries(),
            "@all_scene_summaries": all_summaries(),
            "@story_summary": mgr.config.storySummary or "(no story summary)",
            "@plotlines": plotlines(),
        }

        def repl(match: re.Match[str]) -> str:
            token = match.group(0)
            return replacements.get(token, token)

        return TOKEN_RE.sub(repl, prompt)
