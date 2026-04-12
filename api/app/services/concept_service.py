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

    # Load domain-specific ontology extensions (e.g. living-collective.json).
    # Each extension file has the same structure as core-concepts.json and
    # its concepts are merged into the main index alongside the core 184.
    for ext_path in sorted(_ONTOLOGY_DIR.glob("living-collective*.json")):
        try:
            ext_data = json.loads(ext_path.read_text(encoding="utf-8"))
            ext_concepts = ext_data.get("concepts", [])
            if ext_concepts:
                _concepts.extend(ext_concepts)
                for c in ext_concepts:
                    _concept_index[c["id"]] = c
                log.info("Loaded %d domain concepts from %s", len(ext_concepts), ext_path.name)
        except Exception as exc:
            log.warning("Failed to load domain ontology %s: %s", ext_path.name, exc)


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
    return _concept_index.get(concept_id)


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


# ---------------------------------------------------------------------------
# Accessible ontology: plain-language contribution helpers
# ---------------------------------------------------------------------------

import re


def _slugify(text: str) -> str:
    """Convert plain text to a safe concept ID slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")[:48]
    return f"user.{slug}"


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from plain text (stopword-free)."""
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may", "might",
        "can", "that", "this", "it", "its", "they", "their", "we", "our", "you",
        "your", "i", "my", "he", "she", "his", "her", "which", "who", "what",
        "when", "where", "how", "not", "no", "so", "as", "if", "then",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        if w not in stopwords and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords[:12]


def _score_similarity(concept: dict[str, Any], keywords: list[str]) -> float:
    """Score how well a concept matches a set of keywords (0.0–1.0)."""
    if not keywords:
        return 0.0
    target_text = " ".join([
        concept.get("name", ""),
        concept.get("description", ""),
        " ".join(concept.get("keywords", [])),
    ]).lower()
    hits = sum(1 for kw in keywords if kw in target_text)
    return round(hits / len(keywords), 3)


def suggest_concept_placement(
    plain_text: str,
    domains: list[str] | None = None,
    contributor: str = "anonymous",
) -> dict[str, Any]:
    """
    Accept plain-language input and return a placement suggestion.

    Non-technical contributors share an idea; the system:
    - auto-generates a concept ID and keywords
    - finds the top related existing concepts by keyword overlap
    - suggests relationship types based on language cues
    - returns a ready-to-submit concept body that can be accepted as-is

    Technical peers see the full graph; everyone else sees gardens, cards,
    and conversations.
    """
    name = plain_text.strip()
    concept_id = _slugify(name)

    # If ID already exists, append a short uuid fragment
    if concept_id in _concept_index:
        concept_id = f"{concept_id}-{str(uuid.uuid4())[:6]}"

    keywords = _extract_keywords(name)
    domains_clean = [d.strip().lower() for d in (domains or [])]

    # Find related concepts by keyword overlap
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in _concepts:
        score = _score_similarity(c, keywords)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    related = [
        {
            "id": c["id"],
            "name": c.get("name", c["id"]),
            "score": score,
            "relationship_hint": "is_related_to",
        }
        for score, c in scored[:5]
    ]

    # Suggest relationship types based on language cues
    suggested_relationships: list[str] = ["is_related_to"]
    if any(kw in keywords for kw in ["part", "component", "aspect", "element"]):
        suggested_relationships.append("is_part_of")
    if any(kw in keywords for kw in ["type", "kind", "form", "variant"]):
        suggested_relationships.append("is_a")
    if any(kw in keywords for kw in ["leads", "causes", "enables", "produces"]):
        suggested_relationships.append("leads_to")

    ready_to_submit = {
        "id": concept_id,
        "name": name,
        "description": f"Contributed by {contributor}: {name}",
        "type_id": "codex.ucore.user",
        "level": 3,
        "keywords": keywords,
        "domains": domains_clean,
        "parent_concepts": [r["id"] for r in related[:1]],
        "child_concepts": [],
        "axes": [],
        "contributor": contributor,
    }

    return {
        "suggested_id": concept_id,
        "name": name,
        "keywords": keywords,
        "domains": domains_clean,
        "related_concepts": related,
        "suggested_relationships": suggested_relationships,
        "ready_to_submit": ready_to_submit,
        "message": (
            f"Found {len(related)} related concept(s). "
            "You can submit as-is or refine the name and description before saving."
        ),
    }


def create_concept_from_plain(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a concept from a plain-language submission (output of suggest_concept_placement).
    Adds domain tagging and auto-creates relationship edges to related concepts.
    """
    concept_id = data["id"]
    if concept_id in _concept_index:
        concept_id = f"{concept_id}-{str(uuid.uuid4())[:6]}"
        data = {**data, "id": concept_id}

    domains = data.get("domains", [])
    contributor = data.get("contributor", "anonymous")

    concept: dict[str, Any] = {
        "id": concept_id,
        "name": data.get("name", concept_id),
        "description": data.get("description", ""),
        "typeId": data.get("type_id", "codex.ucore.user"),
        "level": data.get("level", 3),
        "keywords": data.get("keywords", []),
        "parentConcepts": data.get("parent_concepts", []),
        "childConcepts": data.get("child_concepts", []),
        "axes": data.get("axes", []),
        "domains": domains,
        "contributor": contributor,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "userDefined": True,
        "accessibleContribution": True,
    }
    _concepts.append(concept)
    _concept_index[concept_id] = concept
    _user_concepts.add(concept_id)

    edges_created: list[dict[str, Any]] = []
    for parent_id in concept.get("parentConcepts", []):
        if parent_id in _concept_index:
            edge = create_edge(
                from_id=concept_id,
                to_id=parent_id,
                rel_type="is_related_to",
                created_by=contributor,
            )
            edges_created.append(edge)

    return {
        "concept": concept,
        "edges_created": edges_created,
        "message": f"Concept '{concept['name']}' added to the ontology with {len(edges_created)} relationship(s).",
    }


def list_concepts_by_domain(domain: str, limit: int = 50) -> dict[str, Any]:
    """Return concepts tagged with a specific domain."""
    d = domain.lower().strip()
    matching = [c for c in _concepts if d in [x.lower() for x in c.get("domains", [])]]
    return {
        "domain": domain,
        "items": matching[:limit],
        "total": len(matching),
    }


def get_garden_view(limit: int = 100) -> dict[str, Any]:
    """
    Return a simplified 'garden' view of concepts for non-technical contributors.
    Groups concepts by domain and level, filters to accessible fields only.
    """
    cards: list[dict[str, Any]] = []
    domain_groups: dict[str, list[str]] = {}

    for c in _concepts[:limit]:
        card = {
            "id": c["id"],
            "name": c.get("name", c["id"]),
            "description": c.get("description", ""),
            "level": c.get("level", 0),
            "domains": c.get("domains", []),
            "keywords": c.get("keywords", [])[:5],
            "userDefined": c.get("userDefined", False),
            "contributor": c.get("contributor"),
        }
        cards.append(card)
        for domain in c.get("domains", []):
            domain_groups.setdefault(domain, [])
            domain_groups[domain].append(c["id"])

    return {
        "cards": cards,
        "total": len(_concepts),
        "shown": len(cards),
        "domain_groups": domain_groups,
        "hint": "Share an idea in plain language — the system finds where it fits.",
    }
