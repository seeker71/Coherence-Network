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

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from app.models.graph import Edge, Node
from app.services.unified_db import session

log = logging.getLogger(__name__)


# ── Node CRUD ────────────────────────────────────────────────────────


def create_node(
    *,
    id: str | None = None,
    type: str,
    name: str,
    description: str = "",
    properties: dict[str, Any] | None = None,
    phase: str = "water",
) -> dict[str, Any]:
    """Create a node. Returns the node dict."""
    node_id = id or str(uuid.uuid4())[:12]
    with session() as s:
        node = Node(
            id=node_id,
            type=type,
            name=name,
            description=description,
            properties=properties or {},
            phase=phase,
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
) -> dict[str, Any]:
    """Create an edge between two nodes."""
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


def list_edges(
    *,
    edge_type: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated listing of edges (global browse)."""
    with session() as s:
        q = s.query(Edge)
        if edge_type:
            q = q.filter(Edge.type == edge_type)
        if from_id:
            q = q.filter(Edge.from_id == from_id)
        if to_id:
            q = q.filter(Edge.to_id == to_id)
        total = q.count()
        rows = q.order_by(Edge.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "items": [e.to_dict() for e in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def get_edges_for_entity_nav(
    entity_id: str,
    direction: str = "both",
    edge_type: str | None = None,
) -> list[dict[str, Any]]:
    """Edges for an entity with peer node summary for navigation UIs."""
    raw = get_edges(entity_id, direction=direction, edge_type=edge_type)
    if not raw:
        return []
    peer_ids: set[str] = set()
    for e in raw:
        peer_ids.add(e["to_id"] if e["from_id"] == entity_id else e["from_id"])
    with session() as s:
        rows = s.query(Node).filter(Node.id.in_(peer_ids)).all()
        by_id = {n.id: n for n in rows}
    out: list[dict[str, Any]] = []
    for e in raw:
        peer_id = e["to_id"] if e["from_id"] == entity_id else e["from_id"]
        node = by_id.get(peer_id)
        peer_summary: dict[str, Any] = (
            {"id": peer_id, "type": node.type, "name": node.name, "phase": node.phase}
            if node
            else {"id": peer_id}
        )
        edir = "outgoing" if e["from_id"] == entity_id else "incoming"
        row = dict(e)
        row["peer_id"] = peer_id
        row["edge_direction"] = edir
        row["peer"] = peer_summary
        out.append(row)
    return out


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
) -> list[dict[str, Any]]:
    """Get neighboring nodes (1 hop by default).

    Optionally filter by edge type and/or neighbor node type.
    """
    with session() as s:
        # Get connected node IDs
        edge_q = s.query(Edge).filter(
            or_(Edge.from_id == node_id, Edge.to_id == node_id)
        )
        if edge_type:
            edge_q = edge_q.filter(Edge.type == edge_type)

        neighbor_ids = set()
        for edge in edge_q.all():
            other = edge.to_id if edge.from_id == node_id else edge.from_id
            neighbor_ids.add(other)

        if not neighbor_ids:
            return []

        # Get the actual nodes
        node_q = s.query(Node).filter(Node.id.in_(neighbor_ids))
        if node_type:
            node_q = node_q.filter(Node.type == node_type)

        return [n.to_dict() for n in node_q.all()]


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
