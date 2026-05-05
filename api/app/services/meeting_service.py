"""Meeting — the combined-organism sense of viewer + content.

When a viewer lands on an entity, that is not a consumption. It is a
meeting. Two organisms (the reader and the thing being read) come into
contact, and the meeting can grow or shrink the vitality of each.

This service computes the cheap version of that meeting:

- content_vitality: how witnessed this entity has been recently (view
  count, reaction count, voice count, freshness of last touch).
- viewer_vitality: a small estimate of the viewer's current presence
  (reactions they've given, voices they've shared, whether they are a
  contributor at all).
- shared_pulse: a qualitative label describing the meeting — first
  meeting, familiar, resonant, quiet.

The numbers are intentionally small integers (0-100) so the UI can
render them as a pulse ring without math. The point is not metrics; the
point is a visible ledger of felt-ness for both sides of the encounter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Optional
import uuid

from sqlalchemy import func, select

from app.models.graph import Edge, Node
from app.services import unified_db as _udb


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, n))


def _recent_cutoff(hours: int = 72):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def sense_meeting(
    entity_type: str,
    entity_id: str,
    contributor_id: Optional[str] = None,
) -> dict:
    """Return the felt-state of a viewer meeting an entity right now.

    Shape:
      {
        content: {vitality: int, reactions: int, voices: int, first_meeting: bool},
        viewer:  {vitality: int, reactions_given: int, voices_given: int, is_contributor: bool},
        shared:  {pulse: "resonant" | "familiar" | "first_meeting" | "quiet", hint: str}
      }
    """
    from app.services.reaction_service import ReactionRecord
    from app.services.concept_voice_service import ConceptVoiceRecord

    with _udb.session() as s:
        # --- content side -------------------------------------------------
        total_reactions = s.execute(
            select(func.count(ReactionRecord.id)).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.entity_id == entity_id,
            )
        ).scalar_one()
        recent_reactions = s.execute(
            select(func.count(ReactionRecord.id)).where(
                ReactionRecord.entity_type == entity_type,
                ReactionRecord.entity_id == entity_id,
                ReactionRecord.created_at >= _recent_cutoff(),
            )
        ).scalar_one()
        total_voices = 0
        if entity_type == "concept":
            total_voices = s.execute(
                select(func.count(ConceptVoiceRecord.id)).where(
                    ConceptVoiceRecord.concept_id == entity_id,
                )
            ).scalar_one() or 0

        # --- viewer side --------------------------------------------------
        viewer_reactions = 0
        viewer_voices = 0
        is_contributor = bool(contributor_id)
        if contributor_id:
            viewer_reactions = s.execute(
                select(func.count(ReactionRecord.id)).where(
                    ReactionRecord.author_id == contributor_id,
                )
            ).scalar_one() or 0
            viewer_voices = s.execute(
                select(func.count(ConceptVoiceRecord.id)).where(
                    ConceptVoiceRecord.author_id == contributor_id,
                )
            ).scalar_one() or 0

    # Content vitality: blend of total care and recent freshness
    content_vitality = _clamp(
        20
        + min(50, int(total_reactions) * 5)
        + min(20, int(recent_reactions) * 6)
        + min(20, int(total_voices) * 7)
    )
    first_meeting_for_content = int(total_reactions) + int(total_voices) == 0

    # Viewer vitality: presence grows with their own expressions
    viewer_vitality = _clamp(
        (30 if is_contributor else 15)
        + min(40, int(viewer_reactions) * 3)
        + min(30, int(viewer_voices) * 6)
    )

    # Shared pulse: qualitative label for the UI
    if first_meeting_for_content and not is_contributor:
        pulse = "first_meeting"
        hint = "first_meeting"
    elif int(total_reactions) > 20 and viewer_reactions > 2:
        pulse = "resonant"
        hint = "resonant"
    elif viewer_reactions > 0 or viewer_voices > 0:
        pulse = "familiar"
        hint = "familiar"
    elif int(total_reactions) > 0:
        pulse = "quiet"
        hint = "quiet"
    else:
        pulse = "first_meeting"
        hint = "first_meeting"

    return {
        "content": {
            "vitality": content_vitality,
            "reactions": int(total_reactions),
            "voices": int(total_voices),
            "first_meeting": first_meeting_for_content,
        },
        "viewer": {
            "vitality": viewer_vitality,
            "reactions_given": int(viewer_reactions),
            "voices_given": int(viewer_voices),
            "is_contributor": is_contributor,
        },
        "shared": {
            "pulse": pulse,
            "hint": hint,
        },
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_happened_at(value: str | None) -> str:
    if not value:
        return _iso_now()
    text = str(value).strip()
    if not text:
        return _iso_now()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _participant_node_type(kind: str) -> str:
    return "service" if kind == "agent" else "contributor"


def _participant_id(participant: dict) -> str:
    raw_id = str(participant.get("id") or "").strip()
    if raw_id:
        return raw_id
    return f"{participant.get('kind', 'person')}:{_slug(str(participant.get('name') or 'unknown'))}"


def _concept_part_node_id(concept_id: str, concept_part_id: str) -> str:
    return f"concept-part:{concept_id}:{_slug(concept_part_id)}"


def _upsert_node(
    s,
    *,
    node_id: str,
    node_type: str,
    name: str,
    description: str = "",
    properties: dict | None = None,
    phase: str = "water",
) -> Node:
    node = s.get(Node, node_id)
    props = dict(properties or {})
    if node is None:
        node = Node(
            id=node_id,
            type=node_type,
            name=name,
            description=description,
            properties=props,
            phase=phase,
        )
        s.add(node)
        s.flush()
        return node

    node.name = name or node.name
    if description:
        node.description = description
    merged = dict(node.properties or {})
    merged.update(props)
    node.properties = merged
    node.phase = phase or node.phase
    node.updated_at = datetime.now(timezone.utc)
    s.flush()
    return node


def _append_unique(values: list, value: str) -> list:
    if value and value not in values:
        values.append(value)
    return values


def _upsert_edge(
    s,
    *,
    from_id: str,
    to_id: str,
    edge_type: str,
    properties: dict | None = None,
    strength: float = 1.0,
    created_by: str = "meeting_service",
) -> Edge:
    edge = s.query(Edge).filter(
        Edge.from_id == from_id,
        Edge.to_id == to_id,
        Edge.type == edge_type,
    ).first()
    props = dict(properties or {})
    if edge is None:
        edge = Edge(
            id=str(uuid.uuid4())[:12],
            from_id=from_id,
            to_id=to_id,
            type=edge_type,
            properties=props,
            strength=strength,
            created_by=created_by,
        )
        s.add(edge)
        s.flush()
        return edge

    merged = dict(edge.properties or {})
    meeting_id = props.get("meeting_id")
    if meeting_id:
        merged["meeting_ids"] = _append_unique(
            list(merged.get("meeting_ids") or []),
            str(meeting_id),
        )
    merged.update(props)
    edge.properties = merged
    edge.strength = max(float(edge.strength or 0.0), float(strength))
    s.flush()
    return edge


def _resolve_participant_id(resonance: dict, participants: list[dict]) -> str:
    participant_id = str(resonance.get("participant_id") or "").strip()
    if participant_id:
        return participant_id

    participant_name = str(resonance.get("participant_name") or "").strip().lower()
    if participant_name:
        matches = [
            p["id"]
            for p in participants
            if str(p.get("name") or "").strip().lower() == participant_name
        ]
        if len(matches) == 1:
            return matches[0]

    if len(participants) == 1:
        return participants[0]["id"]

    raise ValueError("concept resonance must identify a participant_id or unique participant_name")


def capture_meeting_resonance(body: dict) -> dict:
    """Persist a real meeting and its participant-to-concept-part resonance."""
    meeting_id = str(body.get("meeting_id") or f"meeting:{uuid.uuid4().hex[:12]}").strip()
    title = str(body.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")

    happened_at = _normalize_happened_at(body.get("happened_at"))
    source = str(body.get("source") or "api").strip() or "api"
    channel = str(body.get("channel") or "").strip() or None

    participants: list[dict] = []
    for raw in body.get("participants") or []:
        kind = str(raw.get("kind") or "person").strip()
        if kind not in {"person", "agent"}:
            raise ValueError("participant kind must be person or agent")
        participant = {
            "id": _participant_id(raw),
            "name": str(raw.get("name") or "").strip(),
            "kind": kind,
            "role": raw.get("role"),
        }
        if not participant["name"]:
            raise ValueError("participant name is required")
        participants.append(participant)

    participant_ids = {p["id"] for p in participants}
    normalized_resonances: list[dict] = []
    for raw in body.get("concept_resonances") or []:
        participant_id = _resolve_participant_id(raw, participants)
        if participant_id not in participant_ids:
            raise ValueError(f"unknown participant_id: {participant_id}")
        concept_id = str(raw.get("concept_id") or "").strip()
        concept_part_id = str(raw.get("concept_part_id") or "").strip()
        if not concept_id or not concept_part_id:
            raise ValueError("concept_id and concept_part_id are required")
        concept_part_node_id = _concept_part_node_id(concept_id, concept_part_id)
        normalized_resonances.append({
            "participant_id": participant_id,
            "concept_id": concept_id,
            "concept_part_id": concept_part_id,
            "concept_part_node_id": concept_part_node_id,
            "concept_part_label": raw.get("concept_part_label") or concept_part_id,
            "concept_excerpt": raw.get("concept_excerpt"),
            "resonance": str(raw.get("resonance") or "").strip(),
            "strength": float(raw.get("strength") or 0.0),
            "note": raw.get("note"),
            "meeting_id": meeting_id,
            "happened_at": happened_at,
        })
    if not normalized_resonances:
        raise ValueError("at least one concept resonance is required")

    with _udb.session() as s:
        meeting = _upsert_node(
            s,
            node_id=meeting_id,
            node_type="event",
            name=title,
            description=f"Meeting capture from {source}",
            properties={
                "meeting_capture": True,
                "title": title,
                "happened_at": happened_at,
                "channel": channel,
                "source": source,
                "participants": participants,
                "concept_resonances": normalized_resonances,
            },
        )

        for participant in participants:
            _upsert_node(
                s,
                node_id=participant["id"],
                node_type=_participant_node_type(participant["kind"]),
                name=participant["name"],
                description=f"Meeting participant ({participant['kind']})",
                properties={
                    "participant_kind": participant["kind"],
                    "role": participant.get("role"),
                },
            )
            _upsert_edge(
                s,
                from_id=participant["id"],
                to_id=meeting_id,
                edge_type="co-occurs-with",
                properties={"meeting_id": meeting_id, "happened_at": happened_at},
            )

        for resonance in normalized_resonances:
            concept = s.get(Node, resonance["concept_id"])
            if concept is None:
                _upsert_node(
                    s,
                    node_id=resonance["concept_id"],
                    node_type="concept",
                    name=resonance["concept_id"],
                    description="Referenced by a meeting resonance capture.",
                    properties={"created_from": "meeting_resonance_capture"},
                    phase="gas",
                )
            _upsert_node(
                s,
                node_id=resonance["concept_part_node_id"],
                node_type="artifact",
                name=str(resonance["concept_part_label"]),
                description=str(resonance.get("concept_excerpt") or ""),
                properties={
                    "artifact_kind": "concept_part",
                    "concept_id": resonance["concept_id"],
                    "concept_part_id": resonance["concept_part_id"],
                    "concept_part_label": resonance["concept_part_label"],
                },
            )
            _upsert_edge(
                s,
                from_id=resonance["concept_id"],
                to_id=resonance["concept_part_node_id"],
                edge_type="decomposes-into",
                properties={"concept_part_id": resonance["concept_part_id"]},
            )
            _upsert_edge(
                s,
                from_id=resonance["participant_id"],
                to_id=resonance["concept_part_node_id"],
                edge_type="resonates-with",
                properties=resonance,
                strength=resonance["strength"],
            )
            _upsert_edge(
                s,
                from_id=meeting_id,
                to_id=resonance["concept_part_node_id"],
                edge_type="referenced-by",
                properties={
                    "meeting_id": meeting_id,
                    "concept_id": resonance["concept_id"],
                    "concept_part_id": resonance["concept_part_id"],
                },
            )

        s.commit()
        return {
            "meeting": meeting.to_dict(),
            "participants": participants,
            "concept_resonances": normalized_resonances,
        }


def _node_stub(s, node_id: str, fallback_kind: str | None = None) -> dict:
    node = s.get(Node, node_id)
    if node is None:
        return {"id": node_id, "name": node_id, "kind": fallback_kind}
    props = dict(node.properties or {})
    kind = props.get("participant_kind") or fallback_kind
    stub = {"id": node.id, "name": node.name, "type": node.type}
    if kind:
        stub["kind"] = kind
    return stub


def _summary_for(items: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for item in items:
        key = (
            item["participant"]["id"],
            item["concept"]["id"],
            item["concept_part"]["id"],
        )
        existing = grouped.setdefault(key, {
            "participant_id": item["participant"]["id"],
            "participant_name": item["participant"].get("name"),
            "participant_kind": item["participant"].get("kind"),
            "concept_id": item["concept"]["id"],
            "concept_part_id": item["concept_part"]["id"],
            "concept_part_label": item["concept_part"].get("label"),
            "meeting_count": 0,
            "max_strength": 0.0,
            "latest_happened_at": item["meeting"].get("happened_at"),
        })
        existing["meeting_count"] += 1
        existing["max_strength"] = max(existing["max_strength"], item["strength"])
        if str(item["meeting"].get("happened_at") or "") > str(existing.get("latest_happened_at") or ""):
            existing["latest_happened_at"] = item["meeting"].get("happened_at")
    return sorted(grouped.values(), key=lambda row: str(row.get("latest_happened_at") or ""), reverse=True)


def list_meeting_resonance(
    *,
    concept_id: str | None = None,
    participant_id: str | None = None,
    participant_kind: str | None = None,
    meeting_id: str | None = None,
    limit: int = 50,
) -> dict:
    """Recall participant resonance with concept parts from meeting captures."""
    with _udb.session() as s:
        nodes = (
            s.query(Node)
            .filter(Node.type == "event")
            .order_by(Node.updated_at.desc())
            .all()
        )
        items: list[dict] = []
        for meeting in nodes:
            props = dict(meeting.properties or {})
            if not props.get("meeting_capture"):
                continue
            if meeting_id and meeting.id != meeting_id:
                continue
            participant_by_id = {
                p.get("id"): p
                for p in props.get("participants") or []
                if p.get("id")
            }
            for resonance in props.get("concept_resonances") or []:
                if concept_id and resonance.get("concept_id") != concept_id:
                    continue
                if participant_id and resonance.get("participant_id") != participant_id:
                    continue
                participant = participant_by_id.get(resonance.get("participant_id"), {})
                kind = participant.get("kind")
                if participant_kind and kind != participant_kind:
                    continue
                concept = _node_stub(s, resonance.get("concept_id", ""))
                part = {
                    "id": resonance.get("concept_part_id"),
                    "node_id": resonance.get("concept_part_node_id"),
                    "label": resonance.get("concept_part_label"),
                    "excerpt": resonance.get("concept_excerpt"),
                }
                items.append({
                    "participant": _node_stub(
                        s,
                        resonance.get("participant_id", ""),
                        fallback_kind=kind,
                    ),
                    "concept": concept,
                    "concept_part": part,
                    "meeting": {
                        "id": meeting.id,
                        "title": props.get("title") or meeting.name,
                        "happened_at": props.get("happened_at"),
                        "channel": props.get("channel"),
                        "source": props.get("source"),
                    },
                    "resonance": resonance.get("resonance"),
                    "strength": float(resonance.get("strength") or 0.0),
                    "note": resonance.get("note"),
                })

        items.sort(key=lambda row: str(row["meeting"].get("happened_at") or ""), reverse=True)
        total = len(items)
        limited = items[:limit]
        return {
            "items": limited,
            "summary": _summary_for(limited),
            "total": total,
            "filters": {
                "concept_id": concept_id,
                "participant_id": participant_id,
                "participant_kind": participant_kind,
                "meeting_id": meeting_id,
                "limit": limit,
            },
        }
