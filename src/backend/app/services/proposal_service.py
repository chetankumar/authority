"""ProposalService — accept/reject AI proposals (doc 04 §10).

The only mutation path for AI output (aside from enrichment exact-match writes).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.atomic import atomic_write_text
from app.core.errors import ApiError, not_found, validation
from app.core.event_hub import EventHub
from app.core.ids import new_id
from app.models.character import CharacterCreate, CharacterUpdate
from app.models.enums import ProposalStatus, ProposalType
from app.models.proposal import (
    CharacterCreatePayload,
    CharacterRelationshipCreatePayload,
    Proposal,
    ProposalAcceptResult,
    ResourceCreatePayload,
    TodoCreatePayload,
)
from app.models.scene import SceneUpdate
from app.services.book_registry import BookRegistry
from app.services.resource_service import ResourceService
from app.services.scene_service import SceneService, _content_metrics, _now as scene_now
from app.services.structure_service import StructureService
from app.services.todo_service import TodoService

log = logging.getLogger("authority.proposals")

_SCENE_META_FIELDS = frozenset(
    {
        "title",
        "description",
        "location",
        "dateTime",
        "mood",
        "emotionalArc",
        "summary",
        "characters",
    }
)
_CHARACTER_META_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "age",
        "gender",
        "nationality",
        "ethnicity",
        "occupation",
        "want",
        "need",
        "flaw",
        "arc",
        "personality",
        "history",
        "notes",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProposalService:
    def __init__(
        self,
        registry: BookRegistry,
        scene_service: SceneService,
        hub: EventHub,
        structure_service: StructureService,
        todo_service: TodoService,
        resource_service: ResourceService,
    ) -> None:
        self._registry = registry
        self._scenes = scene_service
        self._hub = hub
        self._structure = structure_service
        self._todos = todo_service
        self._resources = resource_service

    def reject(self, book_id: str, proposal_id: str) -> Proposal:
        mgr = self._registry.get(book_id)
        located = mgr.find_proposal(proposal_id)
        if located is None:
            raise not_found("proposal", proposal_id)
        conv, mi, pi = located
        prop = conv.messages[mi].proposals[pi]
        if prop.status != ProposalStatus.pending:
            raise ApiError(409, "Proposal already resolved.", {"code": "already-resolved"})
        prop.status = ProposalStatus.rejected
        prop.resolvedAt = _now()
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        return prop

    async def accept(self, book_id: str, proposal_id: str) -> ProposalAcceptResult:
        mgr = self._registry.get(book_id)
        located = mgr.find_proposal(proposal_id)
        if located is None:
            raise not_found("proposal", proposal_id)
        conv, mi, pi = located
        prop = conv.messages[mi].proposals[pi]
        if prop.status != ProposalStatus.pending:
            raise ApiError(409, "Proposal already resolved.", {"code": "already-resolved"})

        result: dict = {}
        if prop.type == ProposalType.edit:
            result = await self._apply_edit(book_id, prop)
            if prop.status == ProposalStatus.not_found:
                conv.messages[mi].proposals[pi] = prop
                conv.updatedAt = _now()
                mgr.save_conversation(conv)
                return ProposalAcceptResult(proposal=prop, result=result)
        elif prop.type == ProposalType.metadata_update:
            result = await self._apply_metadata(book_id, prop)
        elif prop.type == ProposalType.todo_create:
            result = await self._apply_todo(book_id, prop, conv.id)
        elif prop.type == ProposalType.character_create:
            result = await self._apply_character(book_id, prop)
        elif prop.type == ProposalType.character_relationship_create:
            result = await self._apply_character_relationship(book_id, prop)
        elif prop.type == ProposalType.resource_create:
            result = await self._apply_resource_create(book_id, prop)
        else:
            raise validation({"type": f"Unsupported proposal type: {prop.type}"})

        prop.status = ProposalStatus.applied
        prop.resolvedAt = _now()
        conv.messages[mi].proposals[pi] = prop
        conv.updatedAt = _now()
        mgr.save_conversation(conv)
        return ProposalAcceptResult(proposal=prop, result=result)

    async def _apply_edit(self, book_id: str, prop: Proposal) -> dict:
        payload = prop.payload
        scene_id = payload.get("sceneId")
        find = payload.get("find") or ""
        replace = payload.get("replace")
        if not scene_id or replace is None:
            raise validation({"payload": "Edit proposal is incomplete."})

        mgr = self._registry.get(book_id)
        async with mgr.lock:
            records = {r.id: r for r in mgr.get_scenes()}
            rec = records.get(scene_id)
            if rec is None:
                raise not_found("scene", scene_id)
            path = mgr.scene_file_path(rec.file)
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            idx = content.find(find)
            if idx < 0:
                prop.status = ProposalStatus.not_found
                prop.resolvedAt = _now()
                return {}
            new_content = content[:idx] + replace + content[idx + len(find) :]
            atomic_write_text(path, new_content)
            word_count, content_hash = _content_metrics(new_content)
            bookkeeping = mgr.get_scene_bookkeeping(scene_id).model_copy()
            bookkeeping.wordCount = word_count
            bookkeeping.contentHash = content_hash
            bookkeeping.updatedAt = scene_now()
            mgr.save_scene_bookkeeping(scene_id, bookkeeping)
            self._hub.emit(book_id, "scene-updated", {"id": scene_id, "changed": ["content"]})
            return {"wordCount": word_count, "contentHash": content_hash}

    async def _apply_metadata(self, book_id: str, prop: Proposal) -> dict:
        payload = prop.payload
        target_type = str(payload.get("targetType") or "scene").strip().lower()
        target_id = payload.get("targetId")
        field = payload.get("field")
        new_value = payload.get("newValue")
        if not target_id or not field:
            raise validation({"payload": "Metadata proposal is incomplete."})

        if target_type in ("scene", "scn"):
            if field not in _SCENE_META_FIELDS:
                raise validation({"field": f"Cannot update scene field '{field}' via proposal."})
            body = SceneUpdate.model_construct(**{field: new_value})
            object.__setattr__(body, "__pydantic_fields_set__", {field})
            if payload.get("oldValue") is None:
                scene = self._scenes.get_scene(book_id, target_id)
                prop.payload["oldValue"] = getattr(scene, field, None)
            await self._scenes.update_scene(book_id, target_id, body)
            self._hub.emit(book_id, "scene-updated", {"id": target_id, "changed": [field]})
            return {"targetType": "scene", "targetId": target_id, "field": field, "newValue": new_value}

        if target_type in ("character", "chr"):
            if field not in _CHARACTER_META_FIELDS:
                raise validation({"field": f"Cannot update character field '{field}' via proposal."})
            mgr = self._registry.get(book_id)
            existing = next((c for c in mgr.get_characters() if c.id == target_id), None)
            if existing is None:
                raise not_found("character", target_id)
            if payload.get("oldValue") is None:
                prop.payload["oldValue"] = getattr(existing, field, None)
            body = CharacterUpdate.model_construct(**{field: new_value})
            object.__setattr__(body, "__pydantic_fields_set__", {field})
            await self._structure.update_character(book_id, target_id, body)
            return {"targetType": "character", "targetId": target_id, "field": field, "newValue": new_value}

        raise validation({"targetType": f"Unsupported metadata target: {target_type}"})

    async def _apply_todo(self, book_id: str, prop: Proposal, conversation_id: str) -> dict:
        # Link the new todo back to the conversation it was proposed in, so its
        # 💬 opens straight into the discussion that raised it (doc 04 §8).
        payload = TodoCreatePayload.model_validate(prop.payload)
        todo = await self._todos.create(
            book_id, payload.parentType, payload.parentId, payload.action, conversation_id=conversation_id
        )
        self._hub.emit(book_id, "todos-created", {"todos": [todo.model_dump(mode="json")]})
        return {"todo": todo.model_dump(mode="json")}

    async def _apply_resource_create(self, book_id: str, prop: Proposal) -> dict:
        """Write an AI-drafted file into ``resources/`` — but only from here.

        The AI has no execute tool for resources: doc 01 grants standing consent
        to bookkeeping alone, and a resource file is neither prose nor
        bookkeeping. So this accept is the only path, and ``create_text_file``
        suffixes rather than overwrites — the returned filename may differ from
        the proposed one.
        """
        payload = ResourceCreatePayload.model_validate(prop.payload)
        resource = await self._resources.create_text_file(book_id, payload.filename, payload.content)
        return {"resource": resource.model_dump(mode="json")}

    async def _apply_character(self, book_id: str, prop: Proposal) -> dict:
        payload = CharacterCreatePayload.model_validate(prop.payload)
        mgr = self._registry.get(book_id)

        existing = _find_matching_character(mgr.get_characters(), payload.name, payload.aliases)
        if existing is not None:
            chr_id = existing.id
        else:
            body = CharacterCreate(
                name=payload.name,
                aliases=payload.aliases,
                age=payload.age,
                gender=payload.gender,
                nationality=payload.nationality,
                ethnicity=payload.ethnicity,
                occupation=payload.occupation,
                want=payload.want,
                need=payload.need,
                flaw=payload.flaw,
                arc=payload.arc,
                personality=payload.personality,
                history=payload.history,
                notes=payload.notes,
            )
            character = await self._structure.create_character(book_id, body)
            chr_id = character.id

        if payload.sceneId:
            scene = next((s for s in mgr.get_scenes() if s.id == payload.sceneId), None)
            if scene is not None:
                from app.models.scene import SceneCharacterRef

                current = list(mgr.get_scene_bookkeeping(payload.sceneId).characters)
                if not any(r.characterId == chr_id for r in current):
                    new_chars = [*current, SceneCharacterRef(characterId=chr_id, involvement="")]
                    body = SceneUpdate.model_construct(characters=new_chars)
                    object.__setattr__(body, "__pydantic_fields_set__", {"characters"})
                    await self._scenes.update_scene(book_id, payload.sceneId, body)
                    self._hub.emit(book_id, "scene-updated", {"id": payload.sceneId, "changed": ["characters"]})

        return {"characterId": chr_id}

    async def _apply_character_relationship(self, book_id: str, prop: Proposal) -> dict:
        payload = CharacterRelationshipCreatePayload.model_validate(prop.payload)
        rel = await self._structure.create_character_relationship(
            book_id,
            payload.characterAId,
            payload.characterBId,
            payload.category,
            payload.aToB,
            payload.bToA,
            payload.description,
        )
        return {"characterRelationshipId": rel.id}


def _find_matching_character(characters, name: str, aliases: list[str]):
    """Case-insensitive match on name/aliases — avoids creating a duplicate
    when the AI proposes a character that (partially) already exists."""
    candidates = {name.lower(), *(a.lower() for a in aliases)}
    for c in characters:
        existing = {c.name.lower(), *(a.lower() for a in c.aliases)}
        if candidates & existing:
            return c
    return None
