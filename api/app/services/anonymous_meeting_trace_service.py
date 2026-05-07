"""Anonymous meeting traces."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from app.models.graph import Node
from app.services import unified_db as _udb


_ANONYMOUS_MEETING_TRACE = "anonymous_meeting_trace"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_source(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def _normalize_surface(value: str) -> str:
    surface = str(value or "").strip()[:300]
    return surface or "/"


def _normalize_duration(value: int | float | None) -> int:
    try:
        duration = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(duration, 24 * 60 * 60 * 1000))


def _merge_surface_duration(surfaces: list[dict], surface: str, duration_ms: int) -> list[dict]:
    normalized: list[dict] = []
    seen = False
    for raw in surfaces:
        if not isinstance(raw, dict):
            continue
        existing_surface = _normalize_surface(str(raw.get("surface") or ""))
        existing_duration = _normalize_duration(raw.get("duration_ms"))
        if existing_surface == surface:
            existing_duration = max(existing_duration, duration_ms)
            seen = True
        normalized.append({"surface": existing_surface, "duration_ms": existing_duration})
    if not seen:
        normalized.append({"surface": surface, "duration_ms": duration_ms})
    return normalized


def _is_anonymous_trace(node: Node) -> bool:
    props = dict(node.properties or {})
    return node.type == "event" and bool(props.get(_ANONYMOUS_MEETING_TRACE))


def _anonymous_trace_node_id(source_point_id: str, session_id: str) -> str:
    return f"anonymous-meeting:{source_point_id.split(':', 1)[-1]}:{session_id.split(':', 1)[-1]}"


def _trace_item(node: Node) -> dict:
    props = dict(node.properties or {})
    surfaces = [
        {
            "surface": _normalize_surface(str(item.get("surface") or "")),
            "duration_ms": _normalize_duration(item.get("duration_ms")),
        }
        for item in props.get("surfaces", [])
        if isinstance(item, dict)
    ]
    duration_ms = sum(item["duration_ms"] for item in surfaces)
    return {
        "id": node.id,
        "source_point_id": props.get("source_point_id"),
        "session_id": props.get("session_id"),
        "first_seen_at": props.get("first_seen_at"),
        "last_seen_at": props.get("last_seen_at"),
        "duration_ms": duration_ms,
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "folded_into_contributor_id": props.get("folded_into_contributor_id"),
        "raw_keys_stored": "visitor_key" in props or "session_key" in props,
    }


def _summary_for_anonymous_traces(nodes: list[Node], source_point_id: str | None = None) -> dict:
    items = [_trace_item(node) for node in nodes]
    surfaces: list[str] = []
    folded_into = None
    first_seen = None
    last_seen = None
    total_duration_ms = 0
    source_points = set()
    for item in items:
        source = item.get("source_point_id")
        if source:
            source_points.add(source)
        folded_into = item.get("folded_into_contributor_id") or folded_into
        if item.get("first_seen_at") and (first_seen is None or str(item["first_seen_at"]) < str(first_seen)):
            first_seen = item["first_seen_at"]
        if item.get("last_seen_at") and (last_seen is None or str(item["last_seen_at"]) > str(last_seen)):
            last_seen = item["last_seen_at"]
        total_duration_ms += int(item["duration_ms"])
        for surface in item["surfaces"]:
            name = surface["surface"]
            if name not in surfaces:
                surfaces.append(name)
    return {
        "source_point_id": source_point_id,
        "source_point_count": len(source_points),
        "meeting_count": len(items),
        "first_seen_at": first_seen,
        "last_seen_at": last_seen,
        "total_duration_ms": total_duration_ms,
        "surfaces_met": surfaces,
        "folded_into_contributor_id": folded_into,
        "continuity_note": "source_point_id is a same-browser continuity hint, not identity proof",
    }


def _anonymous_trace_nodes(s, source_point_id: str | None = None) -> list[Node]:
    nodes = s.query(Node).filter(Node.type == "event").order_by(Node.updated_at.desc()).all()
    traces = [node for node in nodes if _is_anonymous_trace(node)]
    if source_point_id:
        traces = [
            node
            for node in traces
            if dict(node.properties or {}).get("source_point_id") == source_point_id
        ]
    return traces


def _fold_anonymous_traces(s, *, source_point_id: str, contributor_id: str) -> None:
    if not contributor_id:
        return
    for node in _anonymous_trace_nodes(s, source_point_id=source_point_id):
        props = dict(node.properties or {})
        props["folded_into_contributor_id"] = contributor_id
        node.properties = props
        node.updated_at = datetime.now(timezone.utc)
        s.add(node)


def record_anonymous_meeting_trace(body: dict) -> dict:
    """Persist a privacy-light meeting trace for one browser/session."""
    visitor_key = str(body.get("visitor_key") or "").strip()
    session_key = str(body.get("session_key") or "").strip()
    if not visitor_key:
        raise ValueError("visitor_key is required")
    if not session_key:
        raise ValueError("session_key is required")

    source_point_id = _hash_source("anon", visitor_key)
    session_id = _hash_source("session", session_key)
    node_id = _anonymous_trace_node_id(source_point_id, session_id)
    surface = _normalize_surface(str(body.get("surface") or "/"))
    duration_ms = _normalize_duration(body.get("duration_ms"))
    now = _iso_now()
    contributor_id = str(body.get("contributor_id") or "").strip() or None

    with _udb.session() as s:
        existing = s.get(Node, node_id)
        props = dict(existing.properties or {}) if existing else {}
        first_seen_at = props.get("first_seen_at") or body.get("started_at") or now
        last_seen_at = body.get("ended_at") or now
        surfaces = _merge_surface_duration(
            props.get("surfaces") if isinstance(props.get("surfaces"), list) else [],
            surface,
            duration_ms,
        )
        merged_props = {
            _ANONYMOUS_MEETING_TRACE: True,
            "source_point_id": source_point_id,
            "session_id": session_id,
            "first_seen_at": str(first_seen_at),
            "last_seen_at": str(last_seen_at),
            "surfaces": surfaces,
            "folded_into_contributor_id": contributor_id or props.get("folded_into_contributor_id"),
        }
        if existing is None:
            existing = Node(
                id=node_id,
                type="event",
                name=f"Anonymous meeting {source_point_id}",
                description="Anonymous public meeting trace",
                properties=merged_props,
                phase="water",
            )
            s.add(existing)
        else:
            existing.properties = merged_props
            existing.updated_at = datetime.now(timezone.utc)

        if contributor_id:
            _fold_anonymous_traces(s, source_point_id=source_point_id, contributor_id=contributor_id)

        s.commit()
        s.refresh(existing)
        nodes = _anonymous_trace_nodes(s, source_point_id=source_point_id)
        return {
            "source_point_id": source_point_id,
            "session": _trace_item(existing),
            "summary": _summary_for_anonymous_traces(nodes, source_point_id=source_point_id),
        }


def list_anonymous_meeting_traces(
    *,
    source_point_id: str | None = None,
    limit: int = 50,
) -> dict:
    with _udb.session() as s:
        nodes = _anonymous_trace_nodes(s, source_point_id=source_point_id)
        limited = nodes[:limit]
        return {
            "items": [_trace_item(node) for node in limited],
            "summary": _summary_for_anonymous_traces(nodes, source_point_id=source_point_id),
            "limit": limit,
        }
