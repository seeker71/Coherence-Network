"""Concept service — loads Living Codex ontology and serves concepts + edges."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "config" / "ontology"

_concepts: list[dict[str, Any]] = []
_relationships: list[dict[str, Any]] = []
_axes: list[dict[str, Any]] = []
_concept_index: dict[str, dict[str, Any]] = {}
_edges: list[dict[str, Any]] = []  # user-created edges


def _load_ontology() -> None:
    global _concepts, _relationships, _axes, _concept_index
    for name, key, target in [
        ("core-concepts.json", "concepts", "_concepts"),
        ("core-relationships.json", "relationships", "_relationships"),
        ("core-axes.json", "axes", "_axes"),
    ]:
        path = _ONTOLOGY_DIR / name
        if path.exists():
            data = json.loads(path.read_text())
            items = data.get(key, [])
            globals()[target] = items
            if key == "concepts":
                globals()["_concept_index"] = {c["id"]: c for c in items}
            log.info("Loaded %d %s from ontology", len(items), key)


_load_ontology()


def list_concepts(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    total = len(_concepts)
    return {"items": _concepts[offset:offset + limit], "total": total, "limit": limit, "offset": offset}


def get_concept(concept_id: str) -> dict[str, Any] | None:
    return _concept_index.get(concept_id)


def search_concepts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    q = query.lower()
    return [c for c in _concepts if q in c.get("name", "").lower() or q in c.get("description", "").lower()][:limit]


def list_relationship_types() -> list[dict[str, Any]]:
    return _relationships


def list_axes() -> list[dict[str, Any]]:
    return _axes


def get_concept_edges(concept_id: str) -> list[dict[str, Any]]:
    return [e for e in _edges if e.get("from") == concept_id or e.get("to") == concept_id]


def create_edge(from_id: str, to_id: str, rel_type: str, created_by: str = "unknown") -> dict[str, Any]:
    import uuid
    from datetime import datetime, timezone
    edge = {
        "id": str(uuid.uuid4())[:12],
        "from": from_id,
        "to": to_id,
        "type": rel_type,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _edges.append(edge)
    return edge


def get_stats() -> dict[str, Any]:
    return {"concepts": len(_concepts), "relationship_types": len(_relationships), "axes": len(_axes), "user_edges": len(_edges)}
