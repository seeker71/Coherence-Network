"""Graph router — generic CRUD for nodes and edges.

This is the universal API. Entity-specific routers (/api/ideas, /api/specs)
are thin adapters that call graph_service with type filters.

Spec 169 additions:
  GET /api/graph/node-types  — canonical 10-type registry
  GET /api/graph/edge-types  — canonical 7-type registry
  GET /api/graph/proof       — aggregate proof the graph is the fractal data layer
  GET /api/graph/nodes/{id}/neighbors — extended with lifecycle_state, rel_type, direction
"""

import math
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any

from app.services import graph_service
from app.models.graph import CANONICAL_EDGE_TYPE_SET, NODE_TYPE_SET

router = APIRouter()


# ── Request models ───────────────────────────────────────────────────


class NodeCreate(BaseModel):
    id: str | None = None
    type: str
    name: str
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    phase: str = "water"


class NodeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    phase: str | None = None
    properties: dict[str, Any] | None = None
    # Type changes — only movement between presence types is allowed,
    # so a visitor can't hijack a system/agent account or rewrite
    # themselves as a concept. The service enforces the allowed set.
    type: str | None = None


class EdgeCreate(BaseModel):
    from_id: str
    to_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    strength: float = 1.0
    created_by: str = "system"


# ── Node endpoints ──────────────────────────────────────────────────


@router.get("/graph/nodes", summary="List nodes with optional type, phase, and search filters")
async def list_nodes(
    type: str | None = None,
    phase: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List nodes with optional type, phase, and search filters."""
    return graph_service.list_nodes(
        type=type, phase=phase, search=search, limit=limit, offset=offset,
    )


@router.post("/graph/nodes", summary="Create a new node. Reject unknown graph node types while preserving canonical semantics")
async def create_node(body: NodeCreate):
    """Create a new node. Reject unknown graph node types while preserving canonical semantics."""
    if body.type not in NODE_TYPE_SET:
        raise HTTPException(
            status_code=422,
            detail=(
                f"node_type '{body.type}' is not a recognized node type. "
                "See /api/graph/node-types for valid values."
            ),
        )
    # Validate lifecycle_state if provided
    lc = body.properties.get("lifecycle_state")
    if lc is not None and lc not in ("gas", "ice", "water"):
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state '{lc}' is not valid. Must be one of: gas, ice, water.",
        )
    try:
        return graph_service.create_node(
            id=body.id, type=body.type, name=body.name,
            description=body.description, properties=body.properties,
            phase=body.phase if body.phase != "water" else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/graph/nodes/count", summary="Count nodes, optionally filtered by type")
async def count_nodes(type: str | None = None):
    """Count nodes, optionally filtered by type."""
    return graph_service.count_nodes(type=type)


@router.get("/graph/stats", summary="Get graph-wide statistics")
async def graph_stats():
    """Get graph-wide statistics."""
    return graph_service.get_stats()


@router.get("/graph/nodes/{node_id}", summary="Get a single node")
async def get_node(node_id: str):
    """Get a single node."""
    node = graph_service.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return node


@router.patch("/graph/nodes/{node_id}", summary="Update a node")
async def update_node(node_id: str, body: NodeUpdate):
    """Update a node.

    When a presence-type node's name or description changes, the
    resonance service automatically re-runs so the concept edges
    stay aligned with the current text. The graph keeps itself
    attuned without anyone having to trigger a manual refresh.
    """
    updates = body.model_dump(exclude_none=True)
    result = graph_service.update_node(node_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    # Re-attune resonance only when the textual signal actually
    # changed. Properties-only PATCHes (flag updates, phase moves,
    # metadata tweaks) don't shift the node's keyword spectrum, so
    # the existing edges remain accurate and the attune call would
    # just be overhead — particularly in test flows where dozens of
    # PATCHes per second are common. Name + description changes do
    # shift the spectrum; those trigger.
    _PRESENCE_TYPES = {
        "contributor", "community", "network-org", "asset", "event",
        "scene", "practice", "skill",
    }
    text_changed = "name" in updates or "description" in updates
    if text_changed and result.get("type") in _PRESENCE_TYPES:
        try:
            from app.services import resonance_service
            resonance_service.attune(node_id)
        except Exception:  # noqa: BLE001 — re-attune failure doesn't block the update
            import logging
            logging.getLogger(__name__).debug(
                "re-attune on update non-fatal error", exc_info=True,
            )

    return result


@router.delete("/graph/nodes/{node_id}", summary="Delete a node and all its edges")
async def delete_node(node_id: str):
    """Delete a node and all its edges."""
    if not graph_service.delete_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"deleted": node_id}


# ── Edge endpoints ──────────────────────────────────────────────────


@router.get("/graph/nodes/{node_id}/edges", summary="Get edges for a node")
async def get_edges(
    node_id: str,
    direction: str = Query(default="both", pattern="^(both|outgoing|incoming)$"),
    type: str | None = None,
):
    """Get edges for a node."""
    return graph_service.get_edges(node_id, direction=direction, edge_type=type)


@router.post("/graph/edges", summary="Create an edge between two nodes. Validates edge_type and prevents self-loops (Spec 169)")
async def create_edge(body: EdgeCreate):
    """Create an edge between two nodes. Validates edge_type and prevents self-loops (Spec 169)."""
    # Canonical edge type validation
    if body.type not in CANONICAL_EDGE_TYPE_SET:
        raise HTTPException(
            status_code=422,
            detail=(
                f"edge_type '{body.type}' is not a recognized edge type. "
                "Valid types: inspires, depends-on, implements, contradicts, extends, "
                "analogous-to, parent-of."
            ),
        )
    # Self-loop prevention
    if body.from_id == body.to_id:
        raise HTTPException(
            status_code=422,
            detail="Self-loop edges are not allowed: from_node_id and to_node_id must be different.",
        )
    try:
        return graph_service.create_edge(
            from_id=body.from_id, to_id=body.to_id, type=body.type,
            properties=body.properties, strength=body.strength,
            created_by=body.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/graph/edges/{edge_id}", summary="Delete an edge")
async def delete_edge(edge_id: str):
    """Delete an edge."""
    if not graph_service.delete_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Edge '{edge_id}' not found")
    return {"deleted": edge_id}


# ── Graph query endpoints ───────────────────────────────────────────


@router.get("/graph/nodes/{node_id}/neighbors", summary="Get neighboring nodes (1–2 hops)")
async def get_neighbors(
    node_id: str,
    edge_type: str | None = None,
    rel_type: str | None = None,
    node_type: str | None = None,
    lifecycle_state: str | None = None,
    direction: str = Query(default="both", pattern="^(both|outgoing|incoming)$"),
    depth: int = Query(default=1, ge=1, le=2),
):
    """Get neighboring nodes (1–2 hops).

    Spec 169 extensions:
    - lifecycle_state: filter neighbors by gas/ice/water
    - rel_type: alias for edge_type (canonical name)
    - direction: outgoing/incoming/both
    - depth: 1 or 2
    """
    if lifecycle_state is not None and lifecycle_state not in ("gas", "ice", "water"):
        raise HTTPException(
            status_code=422,
            detail=f"lifecycle_state '{lifecycle_state}' is not valid. Must be one of: gas, ice, water.",
        )
    effective_edge_type = rel_type or edge_type
    return graph_service.get_neighbors(
        node_id,
        edge_type=effective_edge_type,
        node_type=node_type,
        direction=direction,
        lifecycle_state=lifecycle_state,
    )


@router.get("/graph/nodes/{node_id}/subgraph", summary="Get a subgraph centered on a node")
async def get_subgraph(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=5),
    edge_types: str | None = None,
):
    """Get a subgraph centered on a node."""
    types = edge_types.split(",") if edge_types else None
    return graph_service.get_subgraph(node_id, depth=depth, edge_types=types)


@router.get("/graph/path", summary="Find shortest path between two nodes")
async def find_path(
    from_id: str = Query(...),
    to_id: str = Query(...),
    max_depth: int = Query(default=5, ge=1, le=10),
):
    """Find shortest path between two nodes."""
    path = graph_service.get_path(from_id, to_id, max_depth=max_depth)
    if path is None:
        return {"path": None, "message": f"No path found within {max_depth} hops"}
    return {"path": path, "length": len(path)}


# ── Spec 169: Registry + Proof endpoints ────────────────────────────


@router.get("/graph/node-types", summary="Return the canonical 10-type node registry (Spec 169)")
async def get_node_types():
    """Return the canonical 10-type node registry (Spec 169).

    Lists all valid node_type values, their descriptions, default lifecycle states,
    and payload schemas.
    """
    return graph_service.get_node_type_registry()


@router.get("/graph/edge-types", summary="Return the canonical 7-type edge registry (Spec 169)")
async def get_edge_types():
    """Return the canonical 7-type edge registry (Spec 169).

    Lists all valid edge_type values, their semantics, symmetry, and examples.
    """
    return graph_service.get_edge_type_registry()


@router.get("/graph/proof", summary="Return aggregate proof that the graph is the fractal data layer (Spec 169)")
async def get_graph_proof():
    """Return aggregate proof that the graph is the fractal data layer (Spec 169).

    Returns node/edge counts by type, lifecycle distribution, graph density,
    coverage metrics, and last-edge timestamp. Returns 200 even on empty graph.
    """
    return graph_service.get_proof()


# ── Frequency profile endpoints (universal — any entity) ─────────────


@router.get("/profile/{entity_id}", summary="Get the frequency profile for any entity")
async def get_entity_profile(
    entity_id: str,
    version: str = Query("v2", description="Algorithm version: 'v2' (default, dynamic multi-view) or 'v1' (legacy)"),
):
    """Returns the multi-dimensional frequency profile for any graph entity.

    Works for ideas, specs, assets, concepts, contributors, providers — anything
    in the graph. v2 (default) is a multi-view profile with structural
    (personalized PageRank), categorical (IDF-weighted), and semantic (content
    signal) sub-vectors, fused via inverse-variance weighting for resonance
    matching. v1 is the legacy flat vector, kept callable so profiles signed
    under v1 remain verifiable.

    No auth required — profiles are transparent and verifiable.
    """
    if version == "v1":
        from app.services import frequency_profile_service
        profile = frequency_profile_service.get_profile(entity_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found or has no profile")
        return {
            "version": "v1",
            "entity_id": entity_id,
            "dimensions": len(profile),
            "magnitude": round(frequency_profile_service.magnitude(profile), 4),
            "hash": frequency_profile_service.profile_hash(entity_id),
            "top": [{"dimension": d, "strength": round(s, 4)}
                    for d, s in frequency_profile_service.top_dimensions(profile, n=15)],
            "profile": {k: round(v, 4) for k, v in sorted(profile.items(), key=lambda x: -x[1])},
        }

    from app.services import frequency_profile_v2
    views = frequency_profile_v2.get_profile_v2(entity_id)
    total_dims = sum(len(v) for v in views.values())
    if total_dims == 0:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found or has no profile")
    return {
        "version": "v2",
        "entity_id": entity_id,
        "dimensions": total_dims,
        "magnitude": round(frequency_profile_v2.magnitude_v2(views), 4),
        "hash": frequency_profile_v2.profile_hash_v2(entity_id),
        "top": frequency_profile_v2.top_dimensions_v2(views, n=15),
        "views": {
            name: {
                "dimensions": len(view),
                "magnitude": round(math.sqrt(sum(v * v for v in view.values())), 4) if view else 0.0,
            }
            for name, view in views.items()
        },
    }


@router.get("/profile/{entity_id}/verify", summary="Verify a profile hash")
async def verify_entity_profile(entity_id: str, expected_hash: str = Query(..., alias="hash")):
    """Recompute a profile from graph data and verify it matches the expected hash.

    Version is inferred from the hash prefix: ``v2:...`` routes to v2,
    anything else (bare hex, or explicit ``v1:``) routes to v1. This lets
    signed-v1 profiles stay verifiable after v2 becomes the default.

    No auth required. This is the public verification endpoint for profiles.
    """
    if expected_hash.startswith("v2:"):
        from app.services import frequency_profile_v2
        frequency_profile_v2.invalidate(entity_id)
        actual_hash = frequency_profile_v2.profile_hash_v2(entity_id)
        return {
            "version": "v2",
            "entity_id": entity_id,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "valid": expected_hash == actual_hash,
        }

    from app.services import frequency_profile_service
    frequency_profile_service.invalidate(entity_id)
    actual_hash = frequency_profile_service.profile_hash(entity_id)
    # Strip optional "v1:" prefix from expected for comparison tolerance
    expected_bare = expected_hash[3:] if expected_hash.startswith("v1:") else expected_hash
    return {
        "version": "v1",
        "entity_id": entity_id,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "valid": expected_bare == actual_hash,
    }


@router.post("/resonance", summary="Compute resonance between any two entities")
async def compute_resonance(body: dict):
    """Cosine similarity between two entities' frequency profiles.

    Pass ``{a, b, version?}``. Default version is v2 (multi-view fusion).
    v1 kept callable via ``version: "v1"`` for legacy compatibility.
    Works across entity types: idea-to-concept, contributor-to-asset,
    spec-to-spec, anything.
    """
    a_id = body.get("a", "")
    b_id = body.get("b", "")
    version = body.get("version", "v2")
    if version == "v1":
        from app.services import frequency_profile_service
        score = frequency_profile_service.resonance(a_id, b_id)
    else:
        from app.services import frequency_profile_v2
        score = frequency_profile_v2.resonance_v2(a_id, b_id)
    return {"version": version, "a": a_id, "b": b_id, "resonance": round(score, 4)}


@router.post("/profile/{entity_id}/sign", summary="Cryptographically sign an entity's frequency profile")
async def sign_entity_profile(entity_id: str):
    """Ed25519 sign the current frequency profile of any entity.

    Returns: profile hash, signature, public key, timestamp.
    Anyone can verify: recompute the profile hash, check the signature
    against the public key. Proves "this entity had this profile at this time."
    """
    from app.services import frequency_profile_service
    profile = frequency_profile_service.get_profile(entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return frequency_profile_service.sign_profile(entity_id)


@router.get("/profile/{entity_id}/resonant", summary="Find entities that resonate with this one")
async def find_resonant(
    entity_id: str,
    top: int = Query(10, ge=1, le=50),
    version: str = Query("v2", description="Algorithm version: 'v2' (default) or 'v1' (legacy)"),
):
    """Find the most resonant entities to a given entity.

    Searches the living-collective concept space by default. v2 fuses
    structural + categorical + semantic views; v1 uses the flat legacy vector.
    """
    if version == "v1":
        from app.services import frequency_profile_service
        return frequency_profile_service.find_resonant(entity_id, top_n=top)
    from app.services import frequency_profile_v2
    return frequency_profile_v2.find_resonant_v2(entity_id, top_n=top)


# ── Contributor identity endpoints ────────────────────────────────────


@router.post("/contributors/generate-keypair", summary="Generate a new Ed25519 keypair for a contributor")
async def generate_contributor_keypair():
    """Generate a new Ed25519 keypair.

    Returns both public and private keys. The private key is shown ONCE —
    the contributor must save it. The public key can be registered.
    """
    from app.services import contributor_keys_service
    return contributor_keys_service.generate_keypair()


@router.post("/contributors/{contributor_id}/register-key", summary="Register a public key for a contributor")
async def register_contributor_key(contributor_id: str, body: dict):
    """Store a contributor's public key on their graph node.

    Required before the contributor can sign contributions or earn CC.
    """
    from app.services import contributor_keys_service
    pub_key = body.get("public_key_hex", "")
    if not pub_key:
        raise HTTPException(status_code=400, detail="public_key_hex required")
    return contributor_keys_service.register_public_key(contributor_id, pub_key)


@router.get("/contributors/{contributor_id}/public-key", summary="Get a contributor's public key")
async def get_contributor_public_key(contributor_id: str):
    """Fetch the public key for verification of a contributor's signatures."""
    from app.services import contributor_keys_service
    pub_key = contributor_keys_service.get_public_key(contributor_id)
    if not pub_key:
        raise HTTPException(status_code=404, detail=f"No public key for '{contributor_id}'")
    return {"contributor_id": contributor_id, "public_key_hex": pub_key}


@router.post("/contributors/{contributor_id}/verify-signature", summary="Verify a contributor's signature")
async def verify_contributor_signature(contributor_id: str, body: dict):
    """Verify that a message was signed by the claimed contributor.

    Pass {message, signature_hex}. No auth required — anyone can verify.
    """
    from app.services import contributor_keys_service
    message = body.get("message", "")
    sig = body.get("signature_hex", "")
    valid = contributor_keys_service.verify_signature(contributor_id, message, sig)
    return {"contributor_id": contributor_id, "valid": valid}


# ── DIF Feedback endpoints ───────────────────────────────────────────

@router.get("/dif/feedback/stats", summary="Get DIF feedback statistics — true/false positive rates, accuracy")
async def dif_feedback_stats():
    """Get DIF feedback statistics — true/false positive rates, accuracy."""
    from app.services import dif_feedback_service
    return dif_feedback_service.get_stats()


@router.get("/dif/feedback/recent", summary="Get recent DIF feedback entries")
async def dif_feedback_recent(limit: int = Query(default=20, ge=1, le=100)):
    """Get recent DIF feedback entries."""
    from app.services import dif_feedback_service
    return dif_feedback_service.get_recent(limit=limit)


@router.post("/dif/feedback", summary="Record a DIF verification result for accuracy tracking")
async def record_dif_feedback(body: dict):
    """Record a DIF verification result for accuracy tracking."""
    from app.services import dif_feedback_service
    return dif_feedback_service.record_verification(
        task_id=body.get("task_id", ""),
        task_type=body.get("task_type", ""),
        file_path=body.get("file_path", ""),
        language=body.get("language", ""),
        dif_result=body.get("dif_result", {}),
        agent_action=body.get("agent_action", "pending"),
        idea_id=body.get("idea_id", ""),
        provider=body.get("provider", ""),
    )
