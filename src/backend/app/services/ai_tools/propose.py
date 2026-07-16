"""Propose tools — never mutate; emit Proposal objects (doc 05)."""

from __future__ import annotations

from typing import Any

from app.core.ids import new_id
from app.models.enums import ParentType, ProposalStatus, ProposalType
from app.models.proposal import Proposal
from app.services.ai_tools.accumulator import ProposalAccumulator


def build_propose_tools(accumulator: ProposalAccumulator) -> list[Any]:
    """Return LangChain StructuredTools that append to ``accumulator``."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class EditArgs(BaseModel):
        sceneId: str
        find: str = Field(description="Exact current text in the scene")
        replace: str = Field(description="Replacement text")
        rationale: str = Field(default="", description="Why this edit")

    class MetaArgs(BaseModel):
        targetType: str = Field(
            default="scene",
            description="What to update: 'scene' or 'character'",
        )
        targetId: str = Field(description="Scene id (scn-…) or character id (chr-…)")
        field: str = Field(
            description=(
                "Metadata field name (never prose). For scene: title, description, "
                "location, dateTime, mood, emotionalArc, summary. For character: name, "
                "aliases, age, gender, nationality, ethnicity, occupation, want, need, "
                "flaw, arc, personality, history, notes."
            )
        )
        newValue: Any = None
        rationale: str = ""

    class TodoArgs(BaseModel):
        parentType: str = Field(description="scene | chapter | part | book")
        parentId: str
        action: str

    class CharacterArgs(BaseModel):
        name: str
        aliases: list[str] = Field(default_factory=list)
        age: str = Field(default="", description="Free text, e.g. '34' or 'mid-30s'")
        gender: str = ""
        nationality: str = ""
        ethnicity: str = ""
        occupation: str = Field(default="", description="Job or role in the story world")
        want: str = Field(default="", description="External, plot-visible goal")
        need: str = Field(default="", description="Internal psychological need, often in tension with want")
        flaw: str = Field(default="", description="The trait that drives conflict")
        arc: str = Field(default="", description="How the character changes over the story")
        personality: str = ""
        history: str = ""
        notes: str = ""
        rationale: str = ""
        sceneId: str | None = Field(default=None, description="Optional scene to tag after create")

    class CharacterRelationshipArgs(BaseModel):
        characterAId: str
        characterBId: str
        category: str = Field(
            description="family | romantic | friendship | rivalry | professional | mentorship | other"
        )
        aToB: str = Field(description="How characterA relates to characterB, e.g. 'mother of'")
        bToA: str = Field(description="How characterB relates to characterA, e.g. 'daughter of'")
        description: str = Field(default="", description="Nuance/dynamic of the relationship")
        rationale: str = ""

    def propose_edit(sceneId: str, find: str, replace: str, rationale: str = "") -> str:
        accumulator.add(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.edit,
                status=ProposalStatus.pending,
                payload={"sceneId": sceneId, "find": find, "replace": replace, "rationale": rationale},
            )
        )
        return "Edit proposal recorded for author review."

    def propose_metadata_update(
        targetType: str,
        targetId: str,
        field: str,
        newValue: Any = None,
        rationale: str = "",
    ) -> str:
        accumulator.add(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.metadata_update,
                status=ProposalStatus.pending,
                payload={
                    "targetType": targetType,
                    "targetId": targetId,
                    "field": field,
                    "oldValue": None,  # filled on accept from current state
                    "newValue": newValue,
                    "rationale": rationale,
                },
            )
        )
        return "Metadata proposal recorded for author review."

    def propose_todo(parentType: str, parentId: str, action: str) -> str:
        try:
            pt = ParentType(parentType)
        except ValueError:
            return f"Unknown parentType: {parentType}"
        accumulator.add(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.todo_create,
                status=ProposalStatus.pending,
                payload={"parentType": pt.value, "parentId": parentId, "action": action},
            )
        )
        return "Todo proposal recorded for author review."

    def propose_character_create(
        name: str,
        aliases: list[str] | None = None,
        age: str = "",
        gender: str = "",
        nationality: str = "",
        ethnicity: str = "",
        occupation: str = "",
        want: str = "",
        need: str = "",
        flaw: str = "",
        arc: str = "",
        personality: str = "",
        history: str = "",
        notes: str = "",
        rationale: str = "",
        sceneId: str | None = None,
    ) -> str:
        accumulator.add(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.character_create,
                status=ProposalStatus.pending,
                payload={
                    "name": name,
                    "aliases": aliases or [],
                    "age": age,
                    "gender": gender,
                    "nationality": nationality,
                    "ethnicity": ethnicity,
                    "occupation": occupation,
                    "want": want,
                    "need": need,
                    "flaw": flaw,
                    "arc": arc,
                    "personality": personality,
                    "history": history,
                    "notes": notes,
                    "rationale": rationale,
                    "sceneId": sceneId,
                },
            )
        )
        return "Character-create proposal recorded for author review."

    def propose_character_relationship(
        characterAId: str,
        characterBId: str,
        category: str,
        aToB: str,
        bToA: str,
        description: str = "",
        rationale: str = "",
    ) -> str:
        accumulator.add(
            Proposal(
                id=new_id("prp"),
                type=ProposalType.character_relationship_create,
                status=ProposalStatus.pending,
                payload={
                    "characterAId": characterAId,
                    "characterBId": characterBId,
                    "category": category,
                    "aToB": aToB,
                    "bToA": bToA,
                    "description": description,
                    "rationale": rationale,
                },
            )
        )
        return "Character-relationship proposal recorded for author review."

    return [
        StructuredTool.from_function(
            func=propose_edit,
            name="propose_edit",
            description="Propose a find/replace edit to scene prose. Does not apply it.",
            args_schema=EditArgs,
        ),
        StructuredTool.from_function(
            func=propose_metadata_update,
            name="propose_metadata_update",
            description=(
                "Propose updating a metadata field on a scene or character. "
                "Use targetType 'character' for cast-sheet fields like occupation. "
                "Does not apply it — author must accept."
            ),
            args_schema=MetaArgs,
        ),
        StructuredTool.from_function(
            func=propose_todo,
            name="propose_todo",
            description="Propose creating a todo/task. Does not create it.",
            args_schema=TodoArgs,
        ),
        StructuredTool.from_function(
            func=propose_character_create,
            name="propose_character_create",
            description=(
                "Propose adding a character to the sheet. Author must accept. "
                "Use when a name is new or ambiguous — never invent silently. "
                "Fill in any fields the prose or conversation makes clear "
                "(demographics, occupation, want/need/flaw/arc, personality, "
                "history) — not just the name."
            ),
            args_schema=CharacterArgs,
        ),
        StructuredTool.from_function(
            func=propose_character_relationship,
            name="propose_character_relationship",
            description=(
                "Propose a relationship between two existing characters. Author "
                "must accept. Relationships are directional: describe how "
                "characterA relates to characterB (aToB) and the reverse (bToA) "
                "separately, since most relationships aren't symmetric "
                "(e.g. 'mother of' / 'daughter of')."
            ),
            args_schema=CharacterRelationshipArgs,
        ),
    ]
