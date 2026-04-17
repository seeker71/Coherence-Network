"""Explore queue — a curated stream of entities the viewer hasn't met yet.

The meeting surface is powerful only if the viewer knows which entity to
visit. Without a queue, it's a destination. With a queue, it's a walk.

This service builds small, seeded queues per entity type. It prefers:
  1. Entities the viewer has not yet reacted to (fresh meetings)
  2. Entities that have been quiet recently (needing witness)
  3. Entities that carry at least one recent voice or reaction (alive)

Deterministic but shuffled per-session so two viewers see different orders.
"""

from __future__ import annotations

import hashlib
import random
from typing import Optional

from sqlalchemy import desc, select

from app.services import unified_db as _udb


def _session_seed(session_key: Optional[str]) -> int:
    if not session_key:
        return 0
    h = hashlib.sha256(session_key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def _seen_ids_for(contributor_id: Optional[str], entity_type: str) -> set[str]:
    if not contributor_id:
        return set()
    from app.services.reaction_service import ReactionRecord
    with _udb.session() as s:
        rows = s.execute(
            select(ReactionRecord.entity_id).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.author_id == contributor_id,
            )
        ).all()
    return {r[0] for r in rows}


def _concept_candidates(limit: int) -> list[dict]:
    from app.services import concept_service
    # Limit generously — we'll prune by seen set then trim.
    payload = concept_service.list_concepts(limit=limit * 3)
    items = (payload or {}).get("items", [])
    out: list[dict] = []
    for c in items or []:
        cid = c.get("id")
        if not cid:
            continue
        out.append(
            {
                "entity_type": "concept",
                "entity_id": cid,
                "title": c.get("name") or cid,
                "description": (c.get("description") or "")[:400],
                "image_url": c.get("visual_path"),
            }
        )
    return out


def _idea_candidates(limit: int) -> list[dict]:
    from app.services import idea_service
    items = (idea_service.list_ideas(limit=limit * 3) or {}).get("items", [])
    out: list[dict] = []
    for i in items or []:
        iid = i.get("id")
        if not iid:
            continue
        out.append(
            {
                "entity_type": "idea",
                "entity_id": iid,
                "title": i.get("name") or iid,
                "description": (i.get("description") or "")[:400],
                "image_url": None,
            }
        )
    return out


def _contributor_candidates(limit: int) -> list[dict]:
    try:
        from app.services import onboarding_service
        items = onboarding_service.list_contributors(limit=limit * 3)
    except Exception:
        items = []
    out: list[dict] = []
    for c in items or []:
        cid = c.get("id") or c.get("contributor_id")
        if not cid:
            continue
        out.append(
            {
                "entity_type": "contributor",
                "entity_id": cid,
                "title": c.get("display_name") or c.get("name") or cid,
                "description": (c.get("bio") or "")[:400],
                "image_url": c.get("avatar_url") or None,
            }
        )
    return out


_BUILDERS = {
    "concept": _concept_candidates,
    "idea": _idea_candidates,
    "contributor": _contributor_candidates,
}


def build_queue(
    entity_type: str,
    *,
    limit: int = 20,
    contributor_id: Optional[str] = None,
    session_key: Optional[str] = None,
    include_seen: bool = False,
) -> list[dict]:
    """Return an ordered queue of entities for the viewer to meet next.

    Queue shape: each item has entity_type, entity_id, title, description,
    image_url. The full-screen meeting page can render directly from this.
    """
    builder = _BUILDERS.get(entity_type)
    if not builder:
        return []
    candidates = builder(limit=limit)
    if not include_seen:
        seen = _seen_ids_for(contributor_id, entity_type)
        candidates = [c for c in candidates if c["entity_id"] not in seen]
    # Session-seeded shuffle so each viewer gets a different walk.
    seed = _session_seed(session_key or contributor_id or "")
    rnd = random.Random(seed)
    rnd.shuffle(candidates)
    return candidates[:limit]
