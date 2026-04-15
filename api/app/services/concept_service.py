"""Concept ontology service — graph DB is the single source of truth.

All concepts, edges, tags, relationship types, and axes live in the
graph database. There is no separate store. The DB is populated and
enriched via:
- API endpoints (PATCH /api/graph/nodes/{id})
- sync_kb_to_db.py (reads KB markdown → PATCHes via API)
- seed_schema_to_db.py (one-time: loads relationship types + axes)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# Entity-concept tags (in-memory for now — could move to graph edges later).
_entity_tags: dict[str, list[str]] = {}

# Whether the DB schema has been ensured.
_ready = False


def reset_ensure_flag() -> None:
    """Reset so schema is re-checked on next access.

    Called by test fixtures that create a fresh DB per test.
    """
    global _ready
    _ready = False


def _ensure_ready() -> None:
    """Ensure DB schema exists.

    No seeding — the DB is the source of truth. All data is
    created/updated via API endpoints or sync scripts.
    """
    global _ready
    if _ready:
        return
    _ready = True

    from app.services.unified_db import ensure_schema
    ensure_schema()


# ---------------------------------------------------------------------------
# Read operations — all delegate to graph_service
# ---------------------------------------------------------------------------

def _gs():
    """Lazy import + ensure ready. Every read/write goes through here."""
    _ensure_ready()
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
    """List all relationship types from DB."""
    result = _gs().list_nodes(type="relationship_type", limit=200)
    return result.get("items", [])


def list_axes() -> list[dict[str, Any]]:
    """List all ontology axes from DB."""
    result = _gs().list_nodes(type="axis", limit=200)
    return result.get("items", [])


def get_stats() -> dict[str, Any]:
    count_result = _gs().count_nodes("concept")
    concept_count = count_result.get("total", 0) if isinstance(count_result, dict) else 0
    rel_result = _gs().count_nodes("relationship_type")
    rel_count = rel_result.get("total", 0) if isinstance(rel_result, dict) else 0
    axis_result = _gs().count_nodes("axis")
    axis_count = axis_result.get("total", 0) if isinstance(axis_result, dict) else 0
    return {
        "concepts": concept_count,
        "relationship_types": rel_count,
        "axes": axis_count,
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
    """Group concepts by domain for the concept garden visualization.

    Returns the shape the web client expects:
      cards: list of concept objects
      domain_groups: {domain: [concept_id, ...]}
      total, shown, hint
    """
    all_concepts = _gs().list_nodes(type="concept", limit=limit).get("items", [])
    cards = []
    domain_groups: dict[str, list[str]] = {}
    for c in all_concepts:
        cards.append({
            "id": c["id"],
            "name": c.get("name", c["id"]),
            "description": (c.get("description") or "")[:200],
            "level": c.get("level", 0),
            "domains": c.get("domains", ["core"]),
            "keywords": c.get("keywords", [])[:8],
            "userDefined": c.get("userDefined", False),
            "contributor": c.get("contributor"),
        })
        for domain in c.get("domains", ["core"]):
            domain_groups.setdefault(domain, []).append(c["id"])
    return {
        "cards": cards,
        "total": len(all_concepts),
        "shown": len(cards),
        "domain_groups": domain_groups,
        "hint": f"{len(all_concepts)} concepts across {len(domain_groups)} domains",
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


def validate_story_format(story_content: str) -> list[dict[str, str]]:
    """Validate story content format and return warnings.

    Checks for common formatting issues that break the renderer:
    - ASCII arrows (-> instead of →)
    - Cross-refs with descriptions (→ lc-xxx — description)
    - Cross-refs with markdown links (→ [Name](file.md))
    - Non-existent cross-ref IDs
    - Inline visuals not isolated by blank lines
    """
    import re

    warnings: list[dict[str, str]] = []
    lines = story_content.split("\n")

    # Collect known concept IDs
    known_ids: set[str] = set()
    try:
        all_concepts = _gs().list_nodes(type="concept", limit=1000).get("items", [])
        known_ids = {c["id"] for c in all_concepts}
    except Exception:
        pass

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # ASCII arrow
        if stripped.startswith("-> "):
            warnings.append({
                "line": str(i),
                "issue": "ascii_arrow",
                "message": "Use → (Unicode arrow) instead of ->",
            })

        # Cross-ref with markdown link
        if stripped.startswith("\u2192 ") and "[" in stripped and "](" in stripped:
            warnings.append({
                "line": str(i),
                "issue": "annotated_crossref",
                "message": "Cross-refs should be plain IDs: → lc-xxx, lc-yyy (no markdown links)",
            })

        # Cross-ref with description after em-dash
        if stripped.startswith("\u2192 ") and " \u2014 " in stripped:
            refs = stripped[2:].split(",")
            for ref in refs:
                if " \u2014 " in ref:
                    warnings.append({
                        "line": str(i),
                        "issue": "crossref_description",
                        "message": "Cross-refs should not have descriptions: remove text after —",
                    })
                    break

        # Cross-ref with non-existent ID
        if stripped.startswith("\u2192 ") and known_ids:
            refs = stripped[2:].split(",")
            for ref in refs:
                cid = ref.strip().split(" ")[0].strip()
                if cid and cid not in known_ids:
                    warnings.append({
                        "line": str(i),
                        "issue": "unknown_crossref",
                        "message": f"Cross-ref '{cid}' does not match any known concept",
                    })

        # Inline visual not isolated
        if re.match(r"^!\[.*\]\(visuals:", stripped):
            if i > 1 and lines[i - 2].strip() and not lines[i - 2].strip().startswith("#"):
                warnings.append({
                    "line": str(i),
                    "issue": "visual_not_isolated",
                    "message": "Inline visuals should have a blank line before them",
                })

    return warnings


def update_story(
    concept_id: str,
    story_content: str | None = None,
    visuals: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Update a concept's living story and optionally its visuals.

    If visuals are not provided but story_content contains inline
    ``![caption](visuals:prompt)`` entries, they are auto-extracted.

    Returns the updated concept dict plus a ``warnings`` list of
    any format issues found in the story content.
    """
    import re

    props: dict[str, Any] = {}
    warnings: list[dict[str, str]] = []

    if story_content is not None:
        warnings = validate_story_format(story_content)
        props["story_content"] = story_content
        # Auto-extract visuals from inline markdown if not explicitly given
        if visuals is None:
            extracted = []
            for m in re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", story_content):
                extracted.append({"caption": m.group(1).strip(), "prompt": m.group(2).strip()})
            if extracted:
                props["visuals"] = extracted
        else:
            props["visuals"] = visuals
    elif visuals is not None:
        props["visuals"] = visuals

    if not props:
        return get_concept(concept_id) or {"error": "no updates"}

    result = patch_concept(concept_id, props)
    if warnings:
        result["warnings"] = warnings
    return result


def regenerate_visuals(concept_id: str, concept: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """Regenerate Pollinations images for a concept.

    Downloads gallery visuals (from ``visuals`` property) and story visuals
    (from inline ``![caption](visuals:prompt)`` in ``story_content``).
    Uses deterministic seeds so images are reproducible.
    """
    import re
    import urllib.parse
    from pathlib import Path

    # Constants — must match scripts/kb_common.py and web/lib/vision-utils.ts
    SEED_STRIDE = 17
    STORY_SEED_STRIDE = 13

    def _concept_seed(cid: str) -> int:
        return sum(ord(c) for c in cid)

    def _pollinations_url(prompt: str, seed: int, width: int = 1024, height: int = 576) -> str:
        encoded = urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"

    # Find output directory — works from API root or repo root
    candidates = [
        Path(__file__).resolve().parents[3] / "web" / "public" / "visuals" / "generated",
        Path.cwd() / "web" / "public" / "visuals" / "generated",
        Path.cwd().parent / "web" / "public" / "visuals" / "generated",
    ]
    output_dir = next((d for d in candidates if d.exists()), candidates[0])
    output_dir.mkdir(parents=True, exist_ok=True)

    base_seed = _concept_seed(concept_id)
    results: list[dict[str, str]] = []

    try:
        import httpx as _httpx
    except ImportError:
        return {"error": "httpx not installed — cannot download images", "results": []}

    def _download(url: str, dest: Path) -> bool:
        try:
            resp = _httpx.get(url, timeout=120, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest.write_bytes(resp.content)
                return True
        except Exception:
            pass
        return False

    # Gallery visuals
    gallery_visuals = concept.get("visuals", [])
    for i, v in enumerate(gallery_visuals):
        prompt = v.get("prompt", "")
        if not prompt:
            continue
        seed = base_seed + i * SEED_STRIDE
        filename = f"{concept_id}-{i}.jpg"
        dest = output_dir / filename
        if dest.exists() and not force:
            results.append({"file": filename, "status": "exists"})
            continue
        url = _pollinations_url(prompt, seed)
        if _download(url, dest):
            results.append({"file": filename, "status": "downloaded"})
        else:
            results.append({"file": filename, "status": "failed"})

    # Story visuals
    story_content = concept.get("story_content", "")
    if story_content:
        for i, m in enumerate(re.finditer(r"!\[([^\]]*)\]\(visuals:([^)]+)\)", story_content)):
            prompt = m.group(2).strip()
            if not prompt:
                continue
            seed = base_seed + i * STORY_SEED_STRIDE
            filename = f"{concept_id}-story-{i}.jpg"
            dest = output_dir / filename
            if dest.exists() and not force:
                results.append({"file": filename, "status": "exists"})
                continue
            url = _pollinations_url(prompt, seed)
            if _download(url, dest):
                results.append({"file": filename, "status": "downloaded"})
            else:
                results.append({"file": filename, "status": "failed"})

    downloaded = sum(1 for r in results if r["status"] == "downloaded")
    existing = sum(1 for r in results if r["status"] == "exists")
    failed = sum(1 for r in results if r["status"] == "failed")

    return {
        "concept_id": concept_id,
        "total": len(results),
        "downloaded": downloaded,
        "existing": existing,
        "failed": failed,
        "results": results,
    }


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
        # graph_service.get_neighbors uses "via_edge_type" and "via_direction"
        edge_type = neighbor.get("via_edge_type") or neighbor.get("edge_type", "related")
        direction = neighbor.get("via_direction") or neighbor.get("direction")
        is_outgoing = direction == "outgoing"
        edges.append({
            "id": neighbor.get("edge_id", f"{concept_id}-{edge_type}-{neighbor.get('id', '?')}"),
            "from": concept_id if is_outgoing else neighbor.get("id", "?"),
            "to": neighbor.get("id", "?") if is_outgoing else concept_id,
            "type": edge_type,
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
