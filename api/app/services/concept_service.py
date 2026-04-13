"""Concept ontology service — graph DB is the single source of truth.

All concepts, edges, and tags live in the graph database (graph_service).
There is no separate store. Concepts are created through the API the same
way any data is created — whether by a human, an agent, or a migration
script that reads from a JSON file.

On first access, if the graph DB has no concept nodes, the service
creates the initial concepts from the JSON definition files. This is
functionally identical to POSTing them through the API — the JSON files
are just a convenient way to version-control the initial concept
definitions. Once in the DB, they're living data like everything else.

Relationship types and axes define the vocabulary of edge types and
dimensional axes — reference metadata that describes what kinds of
connections and dimensions exist. These are loaded from JSON because
they're schema-level, not data-level.
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

# Reference metadata (schema-level, not data-level) — loaded from JSON.
_relationships: list[dict[str, Any]] = []
_axes: list[dict[str, Any]] = []

# Entity-concept tags (in-memory for now — could move to graph edges later).
_entity_tags: dict[str, list[str]] = {}

# Whether the initial concepts have been ensured in this process.
_ensured = False


def reset_ensure_flag() -> None:
    """Reset so initial concepts are re-checked on next access.

    Called by test fixtures that create a fresh DB per test.
    """
    global _ensured
    _ensured = False


def _ensure_initial_concepts() -> None:
    """If the graph DB has no concept nodes, create them from the JSON
    definition files. This is functionally identical to calling
    create_concept() for each one — the JSON files are just a convenient
    way to express the initial set.

    Idempotent: if concepts already exist, this is a no-op.
    """
    global _ensured
    if _ensured:
        return
    _ensured = True

    from app.services import graph_service
    from app.services.unified_db import ensure_schema
    ensure_schema()

    # Always load reference metadata (relationship types + axes)
    _load_reference_metadata()

    # Ensure ALL concepts from JSON definitions exist in the graph DB
    # with their FULL properties. If a concept already exists, update
    # its properties to include any new fields added to the JSON since
    # it was first created. If it doesn't exist, create it.
    concept_files = [
        _ONTOLOGY_DIR / "core-concepts.json",
        *sorted(_ONTOLOGY_DIR.glob("living-collective*.json")),
    ]

    total_concepts = 0
    total_edges = 0

    for concept_file in concept_files:
        if not concept_file.exists():
            continue
        try:
            data = json.loads(concept_file.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to read %s: %s", concept_file.name, exc)
            continue

        for c in data.get("concepts", []):
            first_class = {"id", "name", "description"}
            props = {k: v for k, v in c.items() if k not in first_class}
            props.setdefault("userDefined", False)

            existing = graph_service.get_node(c["id"])
            if existing:
                # Update existing node with any new/changed properties.
                # This ensures rich content fields added to the JSON after
                # the node was first created still flow into the graph DB.
                graph_service.update_node(
                    c["id"],
                    name=c.get("name", c["id"]),
                    description=c.get("description", ""),
                    properties=props,
                )
                total_concepts += 1
                continue
            try:
                graph_service.create_node(
                    id=c["id"],
                    type="concept",
                    name=c.get("name", c["id"]),
                    description=c.get("description", ""),
                    phase="gas",
                    properties=props,
                )
                total_concepts += 1
            except Exception:
                pass  # Concurrent creation — safe to ignore

        # Seed edges
        for e in data.get("edges", []):
            try:
                edge_id = f"{e['from']}-{e['type']}-{e['to']}"
                graph_service.create_edge(
                    from_id=e["from"],
                    to_id=e["to"],
                    type=e["type"],
                    strength=e.get("strength", 0.8),
                    created_by="initial-definitions",
                )
                total_edges += 1
            except Exception:
                pass

    # Seed non-concept entity types (communities, scenes, stories, practices, networks)
    # Same pattern as concepts: pass through all properties, update if exists, create if not.
    entity_types = [
        ("communities", "community"),
        ("scenes", "scene"),
        ("stories", "story"),
        ("practices", "practice"),
        ("networks", "network-org"),
    ]
    total_entities = 0
    for concept_file in concept_files:
        if not concept_file.exists():
            continue
        try:
            data = json.loads(concept_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for json_key, node_type in entity_types:
            for item in data.get(json_key, []):
                first_class = {"id", "name", "description"}
                props = {k: v for k, v in item.items() if k not in first_class}
                existing = graph_service.get_node(item["id"])
                if existing:
                    graph_service.update_node(
                        item["id"],
                        name=item.get("name", item["id"]),
                        description=item.get("description", ""),
                        properties=props,
                    )
                else:
                    try:
                        graph_service.create_node(
                            id=item["id"],
                            type=node_type,
                            name=item.get("name", item["id"]),
                            description=item.get("description", ""),
                            phase="water",
                            properties=props,
                        )
                    except Exception:
                        pass
                total_entities += 1

    log.info("Ensured %d concepts, %d edges, %d entities in graph DB", total_concepts, total_edges, total_entities)


def _load_reference_metadata() -> None:
    """Load relationship types and axes (schema-level reference data)."""
    global _relationships, _axes
    for filename, key, target in [
        ("core-relationships.json", "relationships", "_relationships"),
        ("core-axes.json", "axes", "_axes"),
    ]:
        path = _ONTOLOGY_DIR / filename
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                globals()[target] = data.get(key, [])
                log.info("Loaded %d %s from reference metadata", len(globals()[target]), key)
            except Exception as exc:
                log.warning("Failed to load %s: %s", filename, exc)


# Seed lazily on first access, not at module load — tests create fresh
# DBs after module import, so module-level seeding would seed the wrong DB.


# ---------------------------------------------------------------------------
# Read operations — all delegate to graph_service
# ---------------------------------------------------------------------------

def _gs():
    """Lazy import + lazy seed. Every read/write goes through here, so
    seeding happens on first access — not at module load (which would
    seed the wrong DB when tests create fresh per-test databases)."""
    _ensure_initial_concepts()
    from app.services import graph_service
    return graph_service


def list_concepts(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    result = _gs().list_nodes(type="concept", limit=limit, offset=offset)
    return {
        "items": result.get("items", []),
        "total": result.get("total", len(result.get("items", []))),
        "limit": limit,
        "offset": offset,
    }


def get_concept(concept_id: str) -> dict[str, Any] | None:
    return _gs().get_node(concept_id)


def search_concepts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search concepts by name, description, or keywords."""
    q = query.lower()
    # Graph service's list_nodes supports search parameter
    result = _gs().list_nodes(type="concept", search=q, limit=limit)
    items = result.get("items", [])
    # Also check keywords (graph search may not cover JSONB arrays)
    if len(items) < limit:
        all_concepts = _gs().list_nodes(type="concept", limit=1000).get("items", [])
        seen = {c["id"] for c in items}
        for c in all_concepts:
            if c["id"] in seen:
                continue
            kws = c.get("keywords", [])
            if any(q in kw.lower() for kw in kws):
                items.append(c)
                seen.add(c["id"])
            if len(items) >= limit:
                break
    return items[:limit]


def list_relationship_types() -> list[dict[str, Any]]:
    return _relationships


def list_axes() -> list[dict[str, Any]]:
    return _axes


def get_stats() -> dict[str, Any]:
    count_result = _gs().count_nodes("concept")
    concept_count = count_result.get("total", 0) if isinstance(count_result, dict) else 0
    return {
        "concepts": concept_count,
        "relationship_types": len(_relationships),
        "axes": len(_axes),
        "tagged_entities": len(_entity_tags),
    }


def list_concepts_by_domain(domain: str, limit: int = 50) -> dict[str, Any]:
    """List concepts filtered by domain. Scans concept nodes whose
    properties.domains array contains the requested domain."""
    d = domain.strip().lower()
    all_concepts = _gs().list_nodes(type="concept", limit=1000).get("items", [])
    matching = [c for c in all_concepts if d in [x.lower() for x in c.get("domains", [])]]
    return {
        "domain": d,
        "items": matching[:limit],
        "total": len(matching),
    }


def get_garden_view(limit: int = 500) -> dict[str, Any]:
    """Group concepts by domain for the concept garden visualization."""
    all_concepts = _gs().list_nodes(type="concept", limit=limit).get("items", [])
    domain_groups: dict[str, list[dict[str, Any]]] = {}
    for c in all_concepts:
        for domain in c.get("domains", ["core"]):
            domain_groups.setdefault(domain, []).append({
                "id": c["id"],
                "name": c.get("name", c["id"]),
                "description": c.get("description", "")[:100],
                "level": c.get("level", 0),
                "keywords": c.get("keywords", [])[:5],
            })
    return {
        "total": len(all_concepts),
        "domain_count": len(domain_groups),
        "domain_groups": domain_groups,
    }


# ---------------------------------------------------------------------------
# Write operations — all delegate to graph_service
# ---------------------------------------------------------------------------

def create_concept(data: dict[str, Any]) -> dict[str, Any]:
    concept_id = data["id"]
    # Pass through ALL provided fields as properties — no whitelist.
    # The caller decides what fields the concept has.
    first_class = {"id", "name", "description"}
    props = {k: v for k, v in data.items() if k not in first_class}
    props.setdefault("userDefined", True)
    props.setdefault("createdAt", datetime.now(timezone.utc).isoformat())

    node = _gs().create_node(
        id=concept_id,
        type="concept",
        name=data.get("name", concept_id),
        description=data.get("description", ""),
        phase="gas",
        properties=props,
    )
    return node


def patch_concept(concept_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    # First-class node columns that update_node handles directly
    first_class = {"name", "description"}
    direct = {k: v for k, v in updates.items() if k in first_class}
    # Everything else goes into the JSONB properties column
    props = {k: v for k, v in updates.items() if k not in first_class}
    if props:
        direct["properties"] = props

    result = _gs().update_node(concept_id, **direct)
    return result or {"error": "not found"}


def delete_concept(concept_id: str) -> dict[str, Any]:
    # Only allow deleting user-defined concepts
    node = _gs().get_node(concept_id)
    if not node:
        return {"error": f"Concept '{concept_id}' not found"}
    if not node.get("userDefined", False):
        return {"error": f"Concept '{concept_id}' is a core ontology concept and cannot be deleted"}
    _gs().delete_node(concept_id)
    return {"deleted": concept_id}


def create_concept_from_plain(data: dict[str, Any]) -> dict[str, Any]:
    """Create a concept from plain-language input with auto-generated metadata."""
    import re
    name = data.get("name", "")
    description = data.get("description", "")
    text = f"{name} {description}".lower()
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "been", "have", "has"}
    keywords = list(dict.fromkeys(w for w in words if w not in stopwords))[:10]

    concept_id = data.get("id") or f"user-{uuid.uuid4().hex[:8]}"
    return create_concept({
        "id": concept_id,
        "name": name or concept_id,
        "description": description,
        "keywords": keywords,
        "domains": data.get("domains", []),
        "level": data.get("level", 3),
    })


# ---------------------------------------------------------------------------
# Edge operations — delegate to graph_service
# ---------------------------------------------------------------------------

def get_concept_edges(concept_id: str) -> list[dict[str, Any]]:
    """Get all edges connected to a concept (incoming and outgoing)."""
    neighbors = _gs().get_neighbors(concept_id, direction="both")
    edges = []
    for neighbor in neighbors:
        edges.append({
            "id": neighbor.get("edge_id", f"{concept_id}-{neighbor.get('edge_type', '?')}-{neighbor.get('id', '?')}"),
            "from": neighbor.get("from_id", concept_id) if neighbor.get("direction") == "outgoing" else neighbor.get("id", "?"),
            "to": neighbor.get("id", "?") if neighbor.get("direction") == "outgoing" else concept_id,
            "type": neighbor.get("edge_type", "related"),
            "strength": neighbor.get("strength", 1.0),
            "created_by": neighbor.get("created_by", ""),
        })
    # Fallback: if graph_service.get_neighbors doesn't return the shape we
    # need, query edges directly
    if not edges:
        try:
            from app.services.unified_db import session
            from app.models.graph import Edge
            with session() as s:
                db_edges = (
                    s.query(Edge)
                    .filter((Edge.from_id == concept_id) | (Edge.to_id == concept_id))
                    .limit(100)
                    .all()
                )
                edges = [e.to_dict() for e in db_edges]
        except Exception:
            pass
    return edges


def create_edge(from_id: str, to_id: str, rel_type: str, created_by: str = "unknown") -> dict[str, Any]:
    result = _gs().create_edge(
        from_id=from_id,
        to_id=to_id,
        type=rel_type,
        created_by=created_by,
    )
    return result


# ---------------------------------------------------------------------------
# Tagging operations (in-memory for now — could move to graph edges)
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
        "count": len(_entity_tags[key]),
    }


def get_entity_concepts(entity_type: str, entity_id: str) -> list[str]:
    return _entity_tags.get(_tag_key(entity_type, entity_id), [])


def get_related_items(concept_id: str) -> dict[str, Any]:
    """Find all entities tagged with a concept."""
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


def suggest_concept_placement(
    plain_text: str,
    domains: list[str] | None = None,
    contributor: str | None = None,
) -> dict[str, Any]:
    """Suggest where a new concept fits in the ontology."""
    import re
    words = re.findall(r"\b[a-zA-Z]{3,}\b", plain_text.lower())
    stopwords = {"the", "and", "for", "with", "that", "this", "from"}
    keywords = [w for w in words if w not in stopwords][:10]

    results = search_concepts(" ".join(keywords[:3]), limit=5)
    similar = [{"id": c["id"], "name": c.get("name"), "score": 0.5} for c in results]

    return {
        "extracted_keywords": keywords,
        "similar_concepts": similar,
        "suggested_domains": domains or [],
        "suggested_level": 3,
    }
