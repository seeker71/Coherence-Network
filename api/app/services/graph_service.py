"""Universal graph service — CRUD for nodes and edges.

This is the single source of truth for all entities and relationships.
Entity-specific routers (ideas, specs, contributors) are thin adapters
that translate their API shape to/from this service.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError

from app.models.graph import (
    Edge, Node,
    CANONICAL_EDGE_TYPE_SET, CANONICAL_NODE_TYPE_SET, NODE_TYPE_SET,
    LIFECYCLE_DEFAULTS, SYMMETRIC_EDGE_TYPES,
)
from app.services.unified_db import session
from app.config.edge_types import CANONICAL_EDGE_TYPES

log = logging.getLogger(__name__)

_VALID_EDGE_TYPES_MSG = (
    "Valid types: inspires, depends-on, implements, contradicts, extends, analogous-to, parent-of"
)

_VALID_LIFECYCLE_STATES = frozenset({"gas", "ice", "water"})


# ── Spec 169: Semantic validation helpers ────────────────────────────


def validate_node_type(node_type: str) -> None:
    """Raise ValueError if node_type is not in the supported graph vocabulary."""
    if node_type not in NODE_TYPE_SET:
        raise ValueError(
            f"node_type '{node_type}' is not a recognized node type. "
            f"See /api/graph/node-types for valid values."
        )


def validate_edge_type(edge_type: str) -> None:
    """Raise ValueError if edge_type is not in the canonical 7-type vocabulary."""
    if edge_type not in CANONICAL_EDGE_TYPE_SET:
        raise ValueError(
            f"edge_type '{edge_type}' is not a recognized edge type. {_VALID_EDGE_TYPES_MSG}."
        )


def validate_no_self_loop(from_id: str, to_id: str) -> None:
    """Raise ValueError if from_id == to_id."""
    if from_id == to_id:
        raise ValueError(
            "Self-loop edges are not allowed: from_node_id and to_node_id must be different."
        )


def validate_lifecycle_state(state: str) -> None:
    """Raise ValueError if lifecycle state is not gas/ice/water."""
    if state not in _VALID_LIFECYCLE_STATES:
        raise ValueError(
            f"lifecycle_state '{state}' is not valid. Must be one of: gas, ice, water."
        )


def get_lifecycle_default(node_type: str) -> str:
    """Return the default lifecycle state for a given node type."""
    return LIFECYCLE_DEFAULTS.get(node_type, "gas")


# ── Node CRUD ────────────────────────────────────────────────────────


def create_node(
    *,
    id: str | None = None,
    type: str,
    name: str,
    description: str = "",
    properties: dict[str, Any] | None = None,
    phase: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Create a node. Returns the node dict.

    When strict=True, validates node_type against the canonical vocabulary (Spec 169).
    If phase is not provided, defaults based on node type (canonical types only).
    """
    if strict:
        validate_node_type(type)

    props = dict(properties or {})

    # Apply lifecycle default for canonical node types if not explicitly set
    if type in CANONICAL_NODE_TYPE_SET:
        if "lifecycle_state" not in props:
            props["lifecycle_state"] = get_lifecycle_default(type)
        else:
            validate_lifecycle_state(props["lifecycle_state"])

    # Derive phase from lifecycle_state for canonical types
    effective_phase = phase
    if effective_phase is None:
        effective_phase = props.get("lifecycle_state", "water")

    node_id = id or str(uuid.uuid4())[:12]
    with session() as s:
        node = Node(
            id=node_id,
            type=type,
            name=name,
            description=description,
            properties=props,
            phase=effective_phase,
        )
        s.add(node)
        try:
            s.commit()
            s.refresh(node)
            return node.to_dict()
        except IntegrityError:
            s.rollback()
            log.warning("Node %s already exists", node_id)
            existing = s.get(Node, node_id)
            return existing.to_dict() if existing else {"id": node_id, "error": "exists"}


def get_node(node_id: str) -> dict[str, Any] | None:
    """Get a node by ID."""
    with session() as s:
        node = s.get(Node, node_id)
        return node.to_dict() if node else None


def update_node(node_id: str, **updates: Any) -> dict[str, Any] | None:
    """Update a node. Supports updating name, description, phase, and properties."""
    with session() as s:
        node = s.get(Node, node_id)
        if not node:
            return None

        for key in ("name", "description", "phase"):
            if key in updates and updates[key] is not None:
                setattr(node, key, updates[key])

        if "properties" in updates and isinstance(updates["properties"], dict):
            # Merge properties (don't replace — merge new keys into existing)
            merged = dict(node.properties or {})
            merged.update(updates["properties"])
            node.properties = merged

        node.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(node)
        return node.to_dict()


def delete_node(node_id: str) -> bool:
    """Delete a node and all its edges."""
    with session() as s:
        node = s.get(Node, node_id)
        if not node:
            return False
        # Delete connected edges
        s.query(Edge).filter(
            or_(Edge.from_id == node_id, Edge.to_id == node_id)
        ).delete(synchronize_session=False)
        s.delete(node)
        s.commit()
        return True


def list_nodes(
    type: str | None = None,
    phase: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List nodes with optional filtering."""
    with session() as s:
        q = s.query(Node)
        if type:
            q = q.filter(Node.type == type)
        if phase:
            q = q.filter(Node.phase == phase)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                or_(
                    Node.name.ilike(pattern),
                    Node.description.ilike(pattern),
                )
            )

        total = q.count()
        items = q.order_by(Node.updated_at.desc()).offset(offset).limit(limit).all()
        return {
            "items": [n.to_dict() for n in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def count_nodes(type: str | None = None) -> dict[str, int]:
    """Count nodes by type."""
    with session() as s:
        if type:
            total = s.query(Node).filter(Node.type == type).count()
            return {"total": total, "type": type}
        # Count all, grouped by type
        rows = s.query(Node.type, func.count(Node.id)).group_by(Node.type).all()
        by_type = {row[0]: row[1] for row in rows}
        return {"total": sum(by_type.values()), "by_type": by_type}


# ── Edge CRUD ────────────────────────────────────────────────────────


def create_edge(
    *,
    from_id: str,
    to_id: str,
    type: str,
    properties: dict[str, Any] | None = None,
    strength: float = 1.0,
    created_by: str = "system",
    strict: bool = False,
) -> dict[str, Any]:
    """Create an edge between two nodes.

    When strict=True, validates edge_type against the canonical vocabulary and
    prevents self-loops (Spec 169).
    """
    if strict:
        validate_edge_type(type)
        validate_no_self_loop(from_id, to_id)

    edge_id = str(uuid.uuid4())[:12]
    with session() as s:
        edge = Edge(
            id=edge_id,
            from_id=from_id,
            to_id=to_id,
            type=type,
            properties=properties or {},
            strength=strength,
            created_by=created_by,
        )
        s.add(edge)
        try:
            s.commit()
            s.refresh(edge)
            return edge.to_dict()
        except IntegrityError:
            s.rollback()
            # Edge already exists — update strength instead
            existing = s.query(Edge).filter(
                and_(Edge.from_id == from_id, Edge.to_id == to_id, Edge.type == type)
            ).first()
            if existing:
                existing.strength = strength
                s.commit()
                s.refresh(existing)
                return existing.to_dict()
            return {"error": "edge_exists"}


def get_edges(
    node_id: str,
    direction: str = "both",
    edge_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get edges for a node.

    direction: 'outgoing', 'incoming', or 'both'
    """
    with session() as s:
        if direction == "outgoing":
            q = s.query(Edge).filter(Edge.from_id == node_id)
        elif direction == "incoming":
            q = s.query(Edge).filter(Edge.to_id == node_id)
        else:
            q = s.query(Edge).filter(
                or_(Edge.from_id == node_id, Edge.to_id == node_id)
            )

        if edge_type:
            q = q.filter(Edge.type == edge_type)

        return [e.to_dict() for e in q.order_by(Edge.created_at.desc()).all()]


def delete_edge(edge_id: str) -> bool:
    """Delete an edge."""
    with session() as s:
        edge = s.get(Edge, edge_id)
        if not edge:
            return False
        s.delete(edge)
        s.commit()
        return True


# ── Graph queries ────────────────────────────────────────────────────


def get_neighbors(
    node_id: str,
    edge_type: str | None = None,
    node_type: str | None = None,
    depth: int = 1,
    direction: str = "both",
    lifecycle_state: str | None = None,
) -> list[dict[str, Any]]:
    """Get neighboring nodes (1 hop by default).

    Optionally filter by edge type, node type, direction, and lifecycle_state.
    direction: 'outgoing', 'incoming', or 'both' (default)
    lifecycle_state: 'gas', 'ice', or 'water' (Spec 169)
    """
    if lifecycle_state is not None:
        validate_lifecycle_state(lifecycle_state)

    with session() as s:
        # Get connected node IDs via edges in the requested direction
        if direction == "outgoing":
            edge_q = s.query(Edge).filter(Edge.from_id == node_id)
        elif direction == "incoming":
            edge_q = s.query(Edge).filter(Edge.to_id == node_id)
        else:
            edge_q = s.query(Edge).filter(
                or_(Edge.from_id == node_id, Edge.to_id == node_id)
            )

        if edge_type:
            edge_q = edge_q.filter(Edge.type == edge_type)

        neighbor_ids = set()
        neighbor_edge_map: dict[str, dict] = {}
        for edge in edge_q.all():
            other = edge.to_id if edge.from_id == node_id else edge.from_id
            neighbor_ids.add(other)
            if other not in neighbor_edge_map:
                neighbor_edge_map[other] = {
                    "edge_type": edge.type,
                    "direction": "outgoing" if edge.from_id == node_id else "incoming",
                }

        if not neighbor_ids:
            return []

        # Get the actual nodes
        node_q = s.query(Node).filter(Node.id.in_(neighbor_ids))
        if node_type:
            node_q = node_q.filter(Node.type == node_type)

        neighbors = []
        for n in node_q.all():
            if lifecycle_state is not None:
                node_lifecycle = (n.properties or {}).get("lifecycle_state", n.phase)
                if node_lifecycle != lifecycle_state:
                    continue
            d = n.to_dict()
            edge_ctx = neighbor_edge_map.get(n.id, {})
            d["via_edge_type"] = edge_ctx.get("edge_type")
            d["via_direction"] = edge_ctx.get("direction")
            neighbors.append(d)

        return neighbors


def get_path(from_id: str, to_id: str, max_depth: int = 5) -> list[dict[str, Any]] | None:
    """Find shortest path between two nodes via BFS. Returns list of edges or None."""
    with session() as s:
        visited = {from_id}
        queue = [(from_id, [])]

        for _ in range(max_depth):
            next_queue = []
            for current_id, path in queue:
                edges = s.query(Edge).filter(
                    or_(Edge.from_id == current_id, Edge.to_id == current_id)
                ).all()
                for edge in edges:
                    other = edge.to_id if edge.from_id == current_id else edge.from_id
                    if other == to_id:
                        return path + [edge.to_dict()]
                    if other not in visited:
                        visited.add(other)
                        next_queue.append((other, path + [edge.to_dict()]))
            queue = next_queue
            if not queue:
                break

        return None  # No path found


def get_subgraph(
    center_id: str,
    depth: int = 1,
    edge_types: list[str] | None = None,
) -> dict[str, Any]:
    """Get a subgraph centered on a node. Returns nodes + edges within depth."""
    with session() as s:
        nodes_seen = {center_id}
        edges_collected = []
        frontier = {center_id}

        for _ in range(depth):
            if not frontier:
                break
            next_frontier = set()
            for nid in frontier:
                edge_q = s.query(Edge).filter(
                    or_(Edge.from_id == nid, Edge.to_id == nid)
                )
                if edge_types:
                    edge_q = edge_q.filter(Edge.type.in_(edge_types))
                for edge in edge_q.all():
                    edges_collected.append(edge.to_dict())
                    other = edge.to_id if edge.from_id == nid else edge.from_id
                    if other not in nodes_seen:
                        nodes_seen.add(other)
                        next_frontier.add(other)
            frontier = next_frontier

        # Fetch all nodes
        all_nodes = s.query(Node).filter(Node.id.in_(nodes_seen)).all()
        return {
            "nodes": [n.to_dict() for n in all_nodes],
            "edges": edges_collected,
            "center": center_id,
            "depth": depth,
        }


def _node_stub(node: Node | None) -> dict[str, Any] | None:
    """Return a minimal node stub for edge enrichment."""
    if not node:
        return None
    return {"id": node.id, "type": node.type, "name": node.name}


def _enrich_edge(edge: Edge, s) -> dict[str, Any]:
    """Return edge dict enriched with from_node and to_node stubs."""
    d = edge.to_dict()
    from_node = s.get(Node, edge.from_id)
    to_node = s.get(Node, edge.to_id)
    d["from_node"] = _node_stub(from_node)
    d["to_node"] = _node_stub(to_node)
    d["canonical"] = edge.type in CANONICAL_EDGE_TYPES
    return d


def create_edge_strict(
    *,
    from_id: str,
    to_id: str,
    type: str,
    properties: dict[str, Any] | None = None,
    strength: float = 1.0,
    created_by: str = "system",
) -> dict[str, Any]:
    """Create an edge. Returns {'error': 'edge_exists'} on duplicate instead of updating."""
    edge_id = str(uuid.uuid4())[:12]
    with session() as s:
        edge = Edge(
            id=edge_id,
            from_id=from_id,
            to_id=to_id,
            type=type,
            properties=properties or {},
            strength=strength,
            created_by=created_by,
        )
        s.add(edge)
        try:
            s.commit()
            s.refresh(edge)
            return edge.to_dict()
        except IntegrityError:
            s.rollback()
            return {"error": "edge_exists"}


def get_edge_by_id(edge_id: str) -> dict[str, Any] | None:
    """Get a single edge by ID, enriched with node stubs."""
    with session() as s:
        edge = s.get(Edge, edge_id)
        if not edge:
            return None
        return _enrich_edge(edge, s)


def list_edges(
    edge_type: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List edges with optional filters, enriched with node stubs."""
    with session() as s:
        q = s.query(Edge)
        if edge_type:
            q = q.filter(Edge.type == edge_type)
        if from_id:
            q = q.filter(Edge.from_id == from_id)
        if to_id:
            q = q.filter(Edge.to_id == to_id)

        total = q.count()
        edges = q.order_by(Edge.created_at.desc()).offset(offset).limit(limit).all()

        # Batch-load all referenced nodes to avoid N+1
        node_ids = set()
        for e in edges:
            node_ids.add(e.from_id)
            node_ids.add(e.to_id)
        nodes_map: dict[str, Node] = {
            n.id: n for n in s.query(Node).filter(Node.id.in_(node_ids)).all()
        }

        items = []
        for e in edges:
            d = e.to_dict()
            fn = nodes_map.get(e.from_id)
            tn = nodes_map.get(e.to_id)
            d["from_node"] = _node_stub(fn)
            d["to_node"] = _node_stub(tn)
            d["canonical"] = e.type in CANONICAL_EDGE_TYPES
            items.append(d)

        return {"items": items, "total": total, "limit": limit, "offset": offset}


def list_edges_for_entity(
    entity_id: str,
    edge_type: str | None = None,
    direction: str = "both",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List edges for a given entity with optional type and direction filters."""
    with session() as s:
        if direction == "outgoing":
            q = s.query(Edge).filter(Edge.from_id == entity_id)
        elif direction == "incoming":
            q = s.query(Edge).filter(Edge.to_id == entity_id)
        else:
            q = s.query(Edge).filter(
                or_(Edge.from_id == entity_id, Edge.to_id == entity_id)
            )

        if edge_type:
            q = q.filter(Edge.type == edge_type)

        total = q.count()
        edges = q.order_by(Edge.created_at.desc()).offset(offset).limit(limit).all()

        # Batch-load nodes
        node_ids = set()
        for e in edges:
            node_ids.add(e.from_id)
            node_ids.add(e.to_id)
        nodes_map: dict[str, Node] = {
            n.id: n for n in s.query(Node).filter(Node.id.in_(node_ids)).all()
        }

        items = []
        for e in edges:
            d = e.to_dict()
            fn = nodes_map.get(e.from_id)
            tn = nodes_map.get(e.to_id)
            d["from_node"] = _node_stub(fn)
            d["to_node"] = _node_stub(tn)
            d["canonical"] = e.type in CANONICAL_EDGE_TYPES
            items.append(d)

        return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_neighbors_enriched(
    node_id: str,
    edge_type: str | None = None,
    node_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get neighboring nodes with edge context for the API /entities/{id}/neighbors endpoint."""
    with session() as s:
        edge_q = s.query(Edge).filter(
            or_(Edge.from_id == node_id, Edge.to_id == node_id)
        )
        if edge_type:
            edge_q = edge_q.filter(Edge.type == edge_type)

        edges = edge_q.limit(limit * 2).all()  # over-fetch before node_type filter

        # Build neighbor list
        neighbor_map: dict[str, dict] = {}
        for edge in edges:
            other_id = edge.to_id if edge.from_id == node_id else edge.from_id
            direction = "outgoing" if edge.from_id == node_id else "incoming"
            if other_id not in neighbor_map:
                neighbor_map[other_id] = {
                    "node": None,
                    "via_edge": {
                        "id": edge.id,
                        "type": edge.type,
                        "direction": direction,
                        "strength": edge.strength,
                    },
                }

        if not neighbor_map:
            return {"entity_id": node_id, "neighbors": [], "total": 0}

        # Batch-load neighbor nodes
        node_q = s.query(Node).filter(Node.id.in_(list(neighbor_map.keys())))
        if node_type:
            node_q = node_q.filter(Node.type == node_type)

        nodes = node_q.limit(limit).all()
        neighbors = []
        for n in nodes:
            entry = neighbor_map.get(n.id)
            if entry:
                entry["node"] = _node_stub(n)
                neighbors.append(entry)

        return {"entity_id": node_id, "neighbors": neighbors, "total": len(neighbors)}


def get_stats() -> dict[str, Any]:
    """Get graph statistics."""
    with session() as s:
        node_counts = s.query(Node.type, func.count(Node.id)).group_by(Node.type).all()
        edge_counts = s.query(Edge.type, func.count(Edge.id)).group_by(Edge.type).all()
        return {
            "total_nodes": sum(c for _, c in node_counts),
            "total_edges": sum(c for _, c in edge_counts),
            "nodes_by_type": {t: c for t, c in node_counts},
            "edges_by_type": {t: c for t, c in sorted(edge_counts, key=lambda x: -x[1])[:20]},
        }


# ── Spec 169: Registry + Proof endpoints ────────────────────────────


def get_node_type_registry() -> dict[str, Any]:
    """Return the canonical node type registry (10 types from Spec 169)."""
    import json as _json
    import os as _os
    registry_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "config", "node_type_registry.json",
    )
    try:
        with open(registry_path) as f:
            return _json.load(f)
    except (FileNotFoundError, Exception) as e:
        log.warning("Could not load node_type_registry.json: %s", e)
        return {"node_types": []}


def get_edge_type_registry() -> dict[str, Any]:
    """Return the canonical edge type registry (7 types from Spec 169)."""
    import json as _json
    import os as _os
    registry_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "config", "edge_type_registry.json",
    )
    try:
        with open(registry_path) as f:
            return _json.load(f)
    except (FileNotFoundError, Exception) as e:
        log.warning("Could not load edge_type_registry.json: %s", e)
        return {"edge_types": []}


def get_proof() -> dict[str, Any]:
    """Return aggregate proof that the graph is functioning as the fractal data layer.

    Spec 169 §GET /api/graph/proof — must return 200 even on empty graph.
    """
    with session() as s:
        node_counts = s.query(Node.type, func.count(Node.id)).group_by(Node.type).all()
        edge_counts = s.query(Edge.type, func.count(Edge.id)).group_by(Edge.type).all()

        total_nodes = sum(c for _, c in node_counts)
        total_edges = sum(c for _, c in edge_counts)
        nodes_by_type = {t: c for t, c in node_counts}
        edges_by_type = {t: c for t, c in edge_counts}

        # Lifecycle distribution — count nodes per lifecycle_state in payload
        lifecycle_dist: dict[str, int] = {"gas": 0, "ice": 0, "water": 0}
        all_nodes = s.query(Node).all()
        for n in all_nodes:
            ls = (n.properties or {}).get("lifecycle_state", n.phase)
            if ls in lifecycle_dist:
                lifecycle_dist[ls] += 1
            else:
                lifecycle_dist[ls] = lifecycle_dist.get(ls, 0) + 1

        # Graph density: edges / (nodes * (nodes-1))
        density = 0.0
        if total_nodes > 1:
            density = total_edges / (total_nodes * (total_nodes - 1))

        # Average degree
        avg_degree = (2 * total_edges / total_nodes) if total_nodes > 0 else 0.0

        # Last edge created
        last_edge = s.query(Edge).order_by(Edge.created_at.desc()).first()
        last_edge_ts = last_edge.created_at.isoformat() if last_edge and last_edge.created_at else None

        # Coverage: ideas with spec, specs with impl, impls with tests (via edges)
        idea_count = nodes_by_type.get("idea", 0)
        spec_count = nodes_by_type.get("spec", 0)
        impl_count = nodes_by_type.get("implementation", 0)

        ideas_with_spec_edges = s.query(Edge).filter(
            Edge.type.in_(["implements", "inspires", "depends-on"])
        ).count()
        specs_with_impl_edges = s.query(Edge).filter(Edge.type == "implements").count()
        artifact_count = nodes_by_type.get("artifact", 0)

        def safe_pct(num: int, denom: int) -> float:
            return round(min(num / denom, 1.0), 3) if denom > 0 else 0.0

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_by_type": nodes_by_type,
            "edges_by_type": edges_by_type,
            "lifecycle_distribution": lifecycle_dist,
            "graph_density": round(density, 6),
            "average_degree": round(avg_degree, 3),
            "last_edge_created_at": last_edge_ts,
            "coverage_pct": {
                "ideas_with_spec": safe_pct(ideas_with_spec_edges, idea_count),
                "specs_with_impl": safe_pct(specs_with_impl_edges, spec_count),
                "impls_with_test": safe_pct(artifact_count, impl_count),
            },
        }
