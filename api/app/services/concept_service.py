"""Concept service — loads Living Codex ontology and serves concepts + edges."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "config" / "ontology"

_concepts: list[dict[str, Any]] = []
_relationships: list[dict[str, Any]] = []
_axes: list[dict[str, Any]] = []
_concept_index: dict[str, dict[str, Any]] = {}
_edges: list[dict[str, Any]] = []  # user-created edges
_user_concepts: list[dict[str, Any]] = []  # user-created concepts


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
        else:
            log.warning("Ontology file not found: %s", path)


_load_ontology()


def list_concepts(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    all_concepts = _concepts + _user_concepts
    total = len(all_concepts)
    return {"items": all_concepts[offset:offset + limit], "total": total, "limit": limit, "offset": offset}


def get_concept(concept_id: str) -> dict[str, Any] | None:
    # Check built-in index first
    if concept_id in _concept_index:
        return _concept_index[concept_id]
    # Check user-defined concepts
    for c in _user_concepts:
        if c["id"] == concept_id:
            return c
    return None


def search_concepts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    q = query.lower()
    all_concepts = _concepts + _user_concepts
    return [
        c for c in all_concepts
        if q in c.get("name", "").lower()
        or q in c.get("description", "").lower()
        or any(q in kw.lower() for kw in c.get("keywords", []))
    ][:limit]


def list_relationship_types() -> list[dict[str, Any]]:
    return _relationships


def list_axes() -> list[dict[str, Any]]:
    return _axes


def get_concept_edges(concept_id: str) -> list[dict[str, Any]]:
    return [e for e in _edges if e.get("from") == concept_id or e.get("to") == concept_id]


def create_edge(from_id: str, to_id: str, rel_type: str, created_by: str = "unknown") -> dict[str, Any]:
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


def create_concept(data: dict[str, Any]) -> dict[str, Any]:
    concept = {**data, "userDefined": True, "created_at": datetime.now(timezone.utc).isoformat()}
    _user_concepts.append(concept)
    return concept


def patch_concept(concept_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for i, c in enumerate(_user_concepts):
        if c["id"] == concept_id:
            _user_concepts[i] = {**c, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
            return _user_concepts[i]
    raise ValueError(f"User concept '{concept_id}' not found")


def delete_concept(concept_id: str) -> None:
    global _user_concepts
    _user_concepts = [c for c in _user_concepts if c["id"] != concept_id]


def get_related_items(concept_id: str) -> dict[str, Any]:
    """Return ideas and specs tagged with this concept (stub — extend when tagging is implemented)."""
    return {
        "concept_id": concept_id,
        "ideas": [],
        "specs": [],
        "total": 0,
    }


def get_stats() -> dict[str, Any]:
    return {
        "concepts": len(_concepts) + len(_user_concepts),
        "builtin_concepts": len(_concepts),
        "user_concepts": len(_user_concepts),
        "relationship_types": len(_relationships),
        "axes": len(_axes),
        "user_edges": len(_edges),
    }
