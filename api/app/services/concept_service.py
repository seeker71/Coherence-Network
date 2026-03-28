"""Concept service — loads Living Codex ontology and serves concepts + edges.

Data:
- 184 universal concepts from config/ontology/core-concepts.json
- 46 relationship types from config/ontology/core-relationships.json
- 53 axes from config/ontology/core-axes.json

User-defined concepts and edges are stored in-memory during the session.
Tagging (associating concepts with ideas/specs) is also in-memory.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ONTOLOGY_DIR = Path(__file__).resolve().parents[3] / "config" / "ontology"

# Ontology seed data (read from JSON files at startup)
_concepts: list[dict[str, Any]] = []
_relationships: list[dict[str, Any]] = []
_axes: list[dict[str, Any]] = []
_concept_index: dict[str, dict[str, Any]] = {}
_edges: list[dict[str, Any]] = []
_user_concepts: set[str] = set()  # IDs of user-created concepts (can be deleted)
_entity_tags: dict[str, list[str]] = {}  # "idea:abc" -> [concept_id, ...]


def _load_ontology() -> None:
    global _concepts, _relationships, _axes, _concept_index
    for filename, key, target in [
        ("core-concepts.json", "concepts", "_concepts"),
        ("core-relationships.json", "relationships", "_relationships"),
        ("core-axes.json", "axes", "_axes"),
    ]:
        path = _ONTOLOGY_DIR / filename
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items = data.get(key, [])
                globals()[target] = items
                if key == "concepts":
                    globals()["_concept_index"] = {c["id"]: c for c in items}
                log.info("Loaded %d %s from ontology", len(items), key)
            except Exception as exc:
                log.warning("Failed to load %s: %s", filename, exc)
        else:
            log.warning("Ontology file not found: %s", path)


_load_ontology()


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def list_concepts(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    total = len(_concepts)
    return {
        "items": _concepts[offset:offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_concept(concept_id: str) -> dict[str, Any] | None:
    if concept_id in _concept_index:
        return _concept_index[concept_id]
    # Check custom concepts
    for c in _custom_concepts:
        if c["id"] == concept_id:
            return c
    return None


def search_concepts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    q = query.lower()
    results = []
    for c in _concepts:
        name_match = q in c.get("name", "").lower()
        desc_match = q in c.get("description", "").lower()
        kw_match = any(q in kw.lower() for kw in c.get("keywords", []))
        if name_match or desc_match or kw_match:
            results.append(c)
        if len(results) >= limit:
            break
    return results


def list_relationship_types() -> list[dict[str, Any]]:
    return _relationships


def list_axes() -> list[dict[str, Any]]:
    return _axes


def get_stats() -> dict[str, Any]:
    return {
        "concepts": len(_concepts),
        "relationship_types": len(_relationships),
        "axes": len(_axes),
        "user_edges": len(_edges),
        "user_concepts": len(_user_concepts),
        "tagged_entities": len(_entity_tags),
    }


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_concept(data: dict[str, Any]) -> dict[str, Any]:
    concept: dict[str, Any] = {
        "id": data["id"],
        "name": data.get("name", data["id"]),
        "description": data.get("description", ""),
        "typeId": data.get("type_id", "codex.ucore.user"),
        "level": data.get("level", 0),
        "keywords": data.get("keywords", []),
        "parentConcepts": data.get("parent_concepts", []),
        "childConcepts": data.get("child_concepts", []),
        "axes": data.get("axes", []),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "userDefined": True,
    }
    _concepts.append(concept)
    _concept_index[concept["id"]] = concept
    _user_concepts.add(concept["id"])
    return concept


def patch_concept(concept_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    concept = _concept_index[concept_id]
    field_map = {
        "name": "name",
        "description": "description",
        "keywords": "keywords",
        "axes": "axes",
    }
    for field, target_field in field_map.items():
        if field in updates:
            concept[target_field] = updates[field]
    concept["updatedAt"] = datetime.now(timezone.utc).isoformat()
    return concept


def delete_concept(concept_id: str) -> dict[str, Any]:
    if concept_id not in _user_concepts:
        return {"error": f"Concept '{concept_id}' is a core ontology concept and cannot be deleted"}
    concept = _concept_index.pop(concept_id, None)
    if concept:
        _concepts.remove(concept)
    _user_concepts.discard(concept_id)
    return {"deleted": concept_id}


# ---------------------------------------------------------------------------
# Edge operations
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tagging operations
# ---------------------------------------------------------------------------

def _tag_key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def tag_entity(entity_type: str, entity_id: str, concept_ids: list[str]) -> dict[str, Any]:
    key = _tag_key(entity_type, entity_id)
    existing = set(_entity_tags.get(key, []))
    existing.update(concept_ids)
    _entity_tags[key] = list(existing)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "concept_ids": _entity_tags[key],
    }


def get_entity_concepts(entity_type: str, entity_id: str) -> dict[str, Any]:
    key = _tag_key(entity_type, entity_id)
    concept_ids = _entity_tags.get(key, [])
    concepts = [get_concept(cid) for cid in concept_ids if get_concept(cid)]
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "concepts": concepts,
    }


def get_related_items(concept_id: str) -> dict[str, Any]:
    """Find all entities tagged with this concept."""
    ideas = []
    specs = []
    for key, concept_ids in _entity_tags.items():
        if concept_id in concept_ids:
            entity_type, entity_id = key.split(":", 1)
            if entity_type == "idea":
                ideas.append(entity_id)
            elif entity_type == "spec":
                specs.append(entity_id)
    return {
        "concept_id": concept_id,
        "ideas": ideas,
        "specs": specs,
        "total": len(ideas) + len(specs),
    }
