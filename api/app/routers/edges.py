"""Dedicated edges router — /api/edges and /api/entities/{id}/edges.

Implements the canonical 46-type edge navigation layer from spec task_fbceb79ee5d481d5.
The /api/graph/edges and /api/graph/nodes/{id}/edges routes remain in graph.py as aliases.
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Any

from app.config.edge_types import EDGE_TYPE_FAMILIES, CANONICAL_EDGE_TYPES
from app.services import graph_service
from app.services.locale_projection import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    project,
    resolve_caller_lang,
)

router = APIRouter()
log = logging.getLogger(__name__)


_LOCALIZABLE_NODE_TYPES = {
    "contributor", "asset", "community", "network-org", "place",
    "event", "scene", "practice", "skill", "concept",
}


def _project_edge_stub(stub: dict, lang: str) -> None:
    """Project an embedded from_node/to_node stub on an edge response.

    Mirrors graph._project_node but operates on the lighter node-stub
    shape the edges endpoint returns (id + type + name + image_url + slug,
    no description). Title-only projection is the common case for chips.
    """
    node_id = stub.get("id")
    node_type = stub.get("type")
    if not node_id or node_type not in _LOCALIZABLE_NODE_TYPES:
        return
    project(stub, "node", node_id, lang, title_field="name", body_field="description")
    # If the cache had no view for this lang yet, attune-on-miss so the
    # next chip-render lands in the cached path. Best-effort.
    try:
        from app.services import translation_cache_service as _tcache
        from app.services import translator_service as _ts
        if _tcache.canonical_view("node", node_id, lang) is None and _ts.has_backend():
            anchors = _tcache.all_canonical_views("node", node_id)
            if not _tcache.find_anchor(anchors):
                _tcache.write_view(
                    entity_type="node",
                    entity_id=node_id,
                    lang=DEFAULT_LOCALE,
                    content_title=stub.get("name", "") or "",
                    content_description="",
                    content_markdown="",
                    author_type=_tcache.AUTHOR_TYPE_ORIGINAL_HUMAN,
                )
            _ts.attune_from_anchor(
                entity_type="node", entity_id=node_id, target_lang=lang,
            )
            project(stub, "node", node_id, lang, title_field="name", body_field="description")
    except Exception as e:  # pragma: no cover
        log.debug("edges._project_edge_stub attune-on-miss skipped: %s", e)


# ── Request models ────────────────────────────────────────────────────


class EdgeCreateRequest(BaseModel):
    from_id: str
    to_id: str
    type: str
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


class EdgeUpdateRequest(BaseModel):
    """Refresh an existing edge's strength and/or properties.

    Used when re-running an ingest pass with sharper signals — e.g.
    the watch-history clusterer re-applying duration-based strength
    on top of edges originally created with count-based strength.
    Properties merge into existing; strength replaces.
    """
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    properties: dict[str, Any] | None = None


# ── Type Registry ─────────────────────────────────────────────────────


@router.get("/edges/types", summary="Return all 46 canonical edge types grouped by family")
async def get_edge_types(family: str | None = None):
    """Return all 46 canonical edge types grouped by family.

    Stable and cacheable — no DB query needed.
    Returns 200 with empty families array if family filter matches nothing.
    """
    families = EDGE_TYPE_FAMILIES
    if family:
        families = [f for f in families if f["slug"] == family or f["name"] == family]

    total = sum(len(f["types"]) for f in families)
    return {
        "total": total,
        "families": families,
    }


# ── Edge CRUD ─────────────────────────────────────────────────────────


@router.get("/edges", summary="List edges with optional filters. Responses include from_node and to_node stubs")
async def list_edges(
    request: Request,
    type: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    lang: str | None = Query(None),
):
    """List edges with optional filters. Responses include from_node and to_node stubs.

    Locale-projects the embedded ``from_node``/``to_node`` name + description
    so a visitor walking edges (e.g. a contributor's contributes-to chain
    populating the body of evidence) reads work titles in their own
    language. Cache-miss triggers a best-effort libretranslate attunement
    on the underlying nodes via the same mechanism /graph/nodes/{id} uses.
    """
    result = graph_service.list_edges(
        edge_type=type, from_id=from_id, to_id=to_id, limit=limit, offset=offset
    )
    target_lang = resolve_caller_lang(request, lang)
    if target_lang and target_lang != DEFAULT_LOCALE and target_lang in SUPPORTED_LOCALES:
        items = result.get("items", []) if isinstance(result, dict) else []
        for edge in items:
            for stub_key in ("from_node", "to_node"):
                stub = edge.get(stub_key) if isinstance(edge, dict) else None
                if stub:
                    _project_edge_stub(stub, target_lang)
    return result


@router.get("/edges/{edge_id}", summary="Get a single edge by ID with node stubs")
async def get_edge(edge_id: str):
    """Get a single edge by ID with node stubs."""
    edge = graph_service.get_edge_by_id(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return edge


@router.post("/edges", status_code=201, summary="Create a typed edge between two entities")
async def create_edge(body: EdgeCreateRequest, strict: bool = False):
    """Create a typed edge between two entities.

    - Returns 409 if the (from_id, to_id, type) triplet already exists.
    - Returns 404 if either endpoint node does not exist.
    - Returns 400 with strict=true if type is not in the 46 canonical list.
    - Non-canonical types are allowed by default (canonical: false in response).
    """
    # Validate canonical type in strict mode
    is_canonical = body.type in CANONICAL_EDGE_TYPES
    if strict and not is_canonical:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown edge type '{body.type}'. Use GET /api/edges/types for valid types.",
        )

    # Validate that both endpoint nodes exist
    from_node = graph_service.get_node(body.from_id)
    if not from_node:
        raise HTTPException(status_code=404, detail=f"Node '{body.from_id}' not found")
    to_node = graph_service.get_node(body.to_id)
    if not to_node:
        raise HTTPException(status_code=404, detail=f"Node '{body.to_id}' not found")

    result = graph_service.create_edge_strict(
        from_id=body.from_id,
        to_id=body.to_id,
        type=body.type,
        properties=body.properties,
        strength=body.strength,
        created_by=body.created_by,
    )

    if result.get("error") == "edge_exists":
        raise HTTPException(
            status_code=409,
            detail=f"Edge already exists: {body.from_id} --[{body.type}]--> {body.to_id}",
        )

    result["canonical"] = is_canonical
    result["from_node"] = {"id": from_node["id"], "type": from_node["type"], "name": from_node["name"]}
    result["to_node"] = {"id": to_node["id"], "type": to_node["type"], "name": to_node["name"]}
    return result


@router.patch("/edges/{edge_id}", summary="Refresh an edge's strength and/or properties")
async def update_edge(edge_id: str, body: EdgeUpdateRequest):
    """Refresh an existing edge.

    Strength replaces (when supplied); properties merge into existing.
    Used by re-ingest passes that bring sharper signals than the
    original create — e.g. the watch-history clusterer refreshing
    inspired-by edges with duration-based strength on top of edges
    originally created with count-based strength.
    """
    updates = body.model_dump(exclude_none=True)
    result = graph_service.update_edge(edge_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return result


@router.delete("/edges/{edge_id}", summary="Delete an edge by ID")
async def delete_edge(edge_id: str):
    """Delete an edge by ID."""
    if not graph_service.delete_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}


# ── Entity-scoped edge endpoints ───────────────────────────────────────


@router.get("/entities/{entity_id}/edges", summary="List all edges for any entity regardless of node type")
async def get_entity_edges(
    entity_id: str,
    type: str | None = None,
    direction: str = Query(default="both", pattern="^(both|outgoing|incoming)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List all edges for any entity regardless of node type.

    Returns 404 if the entity does not exist.
    Enriches each edge with from_node and to_node stubs.
    """
    entity = graph_service.get_node(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return graph_service.list_edges_for_entity(
        entity_id=entity_id,
        edge_type=type,
        direction=direction,
        limit=limit,
        offset=offset,
    )


@router.get("/entities/{entity_id}/neighbors", summary="Return neighboring node objects reachable via 1 hop from entity_id")
async def get_entity_neighbors(
    entity_id: str,
    type: str | None = None,
    node_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return neighboring node objects reachable via 1 hop from entity_id.

    Returns 404 if entity does not exist.
    """
    entity = graph_service.get_node(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return graph_service.get_neighbors_enriched(
        node_id=entity_id, edge_type=type, node_type=node_type, limit=limit
    )
