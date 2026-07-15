"""ChainService — hard-chain algebra (doc 04 §1.3, §5).

Pure, stateless functions over the scene collection. The chain is stored as each
record's ``previousSceneId``/``nextSceneId`` (single source of truth); sentinels
``scn-START``/``scn-END`` are recordless endpoints. Operations mutate the record
copies handed in (SceneService works on copies under the book lock) and report the
neighbor ids they touched so the API can return ``affectedScenes``.

Placement/seq are recomputed on every read and never persisted.
"""

from __future__ import annotations

from app.core.errors import ApiError, validation
from app.models.enums import Placement, SceneStatus
from app.models.scene import END_ID, SENTINELS, START_ID, SceneRecord

RecordMap = dict[str, SceneRecord]


def _is_sentinel(scene_id: str | None) -> bool:
    return scene_id in SENTINELS


def validate_endpoint(records: RecordMap, scene_id: str, *, as_previous: bool, self_id: str | None = None) -> None:
    """Sentinel + FK rules for a prev/next value (doc 04 §5)."""
    if as_previous and scene_id == END_ID:
        raise validation({"previousSceneId": "Nothing can come after The End."})
    if not as_previous and scene_id == START_ID:
        raise validation({"nextSceneId": "Nothing can come before Start."})
    if _is_sentinel(scene_id):
        return
    if scene_id == self_id:
        raise validation({"sequence": "A scene can't link to itself."})
    rec = records.get(scene_id)
    if rec is None:
        raise ApiError(404, "Scene not found", {"kind": "scene", "id": scene_id})
    if rec.status == SceneStatus.archived:
        field = "previousSceneId" if as_previous else "nextSceneId"
        raise validation({field: "That scene is archived."})


def detach(records: RecordMap, scene_id: str) -> set[str]:
    """Remove a scene from the hard chain, healing A→X→B ⇒ A→B. Clears the
    scene's own links. Returns the neighbor scene ids that changed."""
    rec = records[scene_id]
    prev_id, next_id = rec.previousSceneId, rec.nextSceneId
    affected: set[str] = set()

    if prev_id and not _is_sentinel(prev_id) and prev_id in records:
        records[prev_id].nextSceneId = next_id
        affected.add(prev_id)
    if next_id and not _is_sentinel(next_id) and next_id in records:
        records[next_id].previousSceneId = prev_id
        affected.add(next_id)

    rec.previousSceneId = None
    rec.nextSceneId = None
    return affected


def place_between(records: RecordMap, scene_id: str, *, previous: str | None, next_: str | None) -> set[str]:
    """Set ``scene_id``'s placement to exactly *previous → scene → next_*.

    One atomic operation (no partial-field ambiguity): the scene is first
    detached from its current slot (healing A→X→B ⇒ A→B), then linked directly
    to the chosen neighbors, rewiring them to point back. Both sides are set
    together, so setting one never silently drops the other.

    Any scene displaced by a *non-adjacent* choice (e.g. the old occupant of the
    new next's slot) is left floating rather than force-fit — the author placed
    the scene deliberately; a bumped neighbour shows up as floating to re-place.
    ``None`` means "no hard link on that side" (Start/None previous, End/None next).
    Returns every neighbor scene id whose links changed.
    """
    affected = detach(records, scene_id)  # leave the old slot healed
    rec = records[scene_id]
    rec.previousSceneId = previous
    rec.nextSceneId = next_

    if previous and not _is_sentinel(previous) and previous in records:
        prev_rec = records[previous]
        displaced = prev_rec.nextSceneId  # what used to follow `previous`
        prev_rec.nextSceneId = scene_id
        affected.add(previous)
        if displaced and not _is_sentinel(displaced) and displaced in records and displaced not in (scene_id, next_):
            records[displaced].previousSceneId = None  # bumped → floats
            affected.add(displaced)

    if next_ and not _is_sentinel(next_) and next_ in records:
        next_rec = records[next_]
        displaced = next_rec.previousSceneId  # what used to precede `next_`
        next_rec.previousSceneId = scene_id
        affected.add(next_)
        if displaced and not _is_sentinel(displaced) and displaced in records and displaced not in (scene_id, previous):
            records[displaced].nextSceneId = None  # bumped → floats
            affected.add(displaced)

    return affected


def compute_seq_placement(records: list[SceneRecord], relationship_scene_ids: set[str]) -> dict[str, tuple[int | None, Placement]]:
    """Classify every scene (doc 04 §5).

    trunk: Start's next-chain, seq 1..n · unanchored: other hard chains, by head id ·
    floating: soft-only, after hard chains · orphan: no links · archived: seq null.
    ``relationship_scene_ids`` = ids appearing in any soft relationship.
    """
    active = {r.id: r for r in records if r.status == SceneStatus.active}
    result: dict[str, tuple[int | None, Placement]] = {}

    for r in records:
        if r.status == SceneStatus.archived:
            result[r.id] = (None, Placement.archived)

    seq = 0
    seen: set[str] = set()

    def walk(head_id: str, placement: Placement) -> None:
        nonlocal seq
        cur: str | None = head_id
        while cur and cur in active and cur not in seen:
            seen.add(cur)
            seq += 1
            result[cur] = (seq, placement)
            cur = active[cur].nextSceneId
            if cur in SENTINELS:
                break

    # 1) Trunk — the chain whose head's previous is START.
    trunk_head = next((r.id for r in records if r.status == SceneStatus.active and r.previousSceneId == START_ID), None)
    if trunk_head is not None:
        walk(trunk_head, Placement.trunk)

    # 2) Unanchored — remaining scenes with a hard link, grouped into chains by
    #    head (previous is None or points outside the active set), stable id order.
    def has_hard_link(r: SceneRecord) -> bool:
        return bool(r.previousSceneId) or bool(r.nextSceneId)

    def is_chain_head(r: SceneRecord) -> bool:
        p = r.previousSceneId
        return p is None or (p not in SENTINELS and p not in active)

    for r in sorted(active.values(), key=lambda x: x.id):
        if r.id in seen or not has_hard_link(r) or not is_chain_head(r):
            continue
        walk(r.id, Placement.unanchored)

    # Any hard-linked scene not yet seen (e.g. inside a cycle) — number stably.
    for r in sorted(active.values(), key=lambda x: x.id):
        if r.id in seen or not has_hard_link(r):
            continue
        walk(r.id, Placement.unanchored)

    # 3) Floating — no hard link but referenced by a soft relationship.
    for r in sorted(active.values(), key=lambda x: x.id):
        if r.id in seen or has_hard_link(r):
            continue
        if r.id in relationship_scene_ids:
            seen.add(r.id)
            seq += 1
            result[r.id] = (seq, Placement.floating)

    # 4) Orphan — everything else.
    for r in sorted(active.values(), key=lambda x: x.id):
        if r.id in seen:
            continue
        seq += 1
        result[r.id] = (seq, Placement.orphan)

    return result
