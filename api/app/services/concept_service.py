"""Concept service — loads Living Codex ontology and serves concepts + edges + entity tags."""

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

# Runtime mutable state (in-memory for now; persisted separately via DB layer if available)
_edges: list[dict[str, Any]] = []       # user-created concept→concept edges
_tags: list[dict[str, Any]] = []        # entity tagging records (concept→idea/news/spec/task)
_custom_concepts: list[dict[str, Any]] = []  # concepts created via POST /concepts


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


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def list_concepts(
    limit: int = 50,
    offset: int = 0,
    axis: str | None = None,
) -> dict[str, Any]:
    all_concepts = list(_concepts) + _custom_concepts
    if axis:
        all_concepts = [c for c in all_concepts if axis in c.get("axes", [])]
    total = len(all_concepts)
    return {
        "items": all_concepts[offset:offset + limit],
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
    all_concepts = list(_concepts) + _custom_concepts
    results = []
    for c in all_concepts:
        name_match = q in c.get("name", "").lower()
        desc_match = q in c.get("description", "").lower()
        kw_match = any(q in kw.lower() for kw in c.get("keywords", []))
        if name_match or desc_match or kw_match:
            results.append(c)
    return results[:limit]


def list_relationship_types() -> list[dict[str, Any]]:
    return _relationships


def list_axes() -> list[dict[str, Any]]:
    return _axes


def get_concept_edges(concept_id: str) -> dict[str, Any]:
    """Get all edges (seed hierarchy + user edges) for a concept."""
    concept = get_concept(concept_id)
    if concept is None:
        return {"seed_edges": [], "user_edges": []}

    # Build seed edges from parent/child fields in ontology
    seed_edges = []
    for parent_id in concept.get("parentConcepts", []):
        if get_concept(parent_id):
            seed_edges.append({
                "from": parent_id,
                "to": concept_id,
                "type": "parent_of",
                "source": "ontology",
            })
    for child_id in concept.get("childConcepts", []):
        if get_concept(child_id):
            seed_edges.append({
                "from": concept_id,
                "to": child_id,
                "type": "parent_of",
                "source": "ontology",
            })

    # User-created edges
    user_edges = [
        e for e in _edges
        if e.get("from") == concept_id or e.get("to") == concept_id
    ]

    return {
        "seed_edges": seed_edges,
        "user_edges": user_edges,
        "total": len(seed_edges) + len(user_edges),
    }


def get_related_entities(concept_id: str) -> dict[str, Any]:
    """Return all entities tagged with this concept, grouped by type."""
    tags = [t for t in _tags if t.get("concept_id") == concept_id]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        etype = tag["entity_type"]
        by_type.setdefault(etype, []).append(tag)
    return {
        "concept_id": concept_id,
        "tags": tags,
        "by_type": by_type,
        "total": len(tags),
    }


def get_stats() -> dict[str, Any]:
    return {
        "concepts": len(_concepts) + len(_custom_concepts),
        "seed_concepts": len(_concepts),
        "custom_concepts": len(_custom_concepts),
        "relationship_types": len(_relationships),
        "axes": len(_axes),
        "user_edges": len(_edges),
        "entity_tags": len(_tags),
    }


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_concept(data: dict[str, Any]) -> dict[str, Any]:
    """Add a new custom concept (non-seed)."""
    concept = {
        "id": data["id"],
        "name": data["name"],
        "description": data.get("description", ""),
        "typeId": data.get("typeId", "codex.ucore.custom"),
        "level": data.get("level", 1),
        "keywords": data.get("keywords", []),
        "parentConcepts": data.get("parentConcepts", []),
        "childConcepts": data.get("childConcepts", []),
        "axes": data.get("axes", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "user",
    }
    _custom_concepts.append(concept)
    log.info("Created custom concept: %s", concept["id"])
    return concept


def patch_concept(concept_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update mutable fields on a concept (works on both seed and custom)."""
    # Try custom concepts first (mutable)
    for i, c in enumerate(_custom_concepts):
        if c["id"] == concept_id:
            _custom_concepts[i] = {**c, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
            return _custom_concepts[i]

    # For seed concepts, patch in-place (they're dicts in memory)
    if concept_id in _concept_index:
        _concept_index[concept_id].update(updates)
        # Update in _concepts list too
        for i, c in enumerate(_concepts):
            if c["id"] == concept_id:
                _concepts[i] = _concept_index[concept_id]
                break
        return _concept_index[concept_id]

    return {}


def delete_concept(concept_id: str) -> bool:
    """Delete a custom concept."""
    for i, c in enumerate(_custom_concepts):
        if c["id"] == concept_id:
            _custom_concepts.pop(i)
            # Clean up related tags
            global _tags
            _tags = [t for t in _tags if t.get("concept_id") != concept_id]
            return True
    return False


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


def tag_entity(
    concept_id: str,
    entity_type: str,
    entity_id: str,
    tagged_by: str = "unknown",
) -> dict[str, Any]:
    """Tag an entity with a concept. Idempotent — duplicate tags are skipped."""
    # Check for existing tag
    existing = next(
        (t for t in _tags
         if t["concept_id"] == concept_id
         and t["entity_type"] == entity_type
         and t["entity_id"] == entity_id),
        None,
    )
    if existing:
        return existing

    tag = {
        "id": str(uuid.uuid4())[:12],
        "concept_id": concept_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "tagged_by": tagged_by,
        "tagged_at": datetime.now(timezone.utc).isoformat(),
    }
    _tags.append(tag)
    return tag


def untag_entity(concept_id: str, entity_type: str, entity_id: str) -> bool:
    """Remove a concept tag from an entity. Returns True if removed."""
    global _tags
    before = len(_tags)
    _tags = [
        t for t in _tags
        if not (
            t["concept_id"] == concept_id
            and t["entity_type"] == entity_type
            and t["entity_id"] == entity_id
        )
    ]
    return len(_tags) < before


def get_entity_concepts(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    """Get all concepts tagged on a given entity."""
    tags = [t for t in _tags if t["entity_type"] == entity_type and t["entity_id"] == entity_id]
    result = []
    for tag in tags:
        concept = get_concept(tag["concept_id"])
        if concept:
            result.append({"tag": tag, "concept": concept})
    return result
