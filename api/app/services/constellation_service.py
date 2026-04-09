"""Constellation service — builds network graph data optimized for visualization.

Returns nodes (ideas, contributors, concepts) and edges (resonances, contributions,
memberships) positioned for a force-directed or constellation layout.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

from app.services import graph_service
from app.services import concept_service

log = logging.getLogger(__name__)

# Color palette by node type
_TYPE_COLORS = {
    "idea": "#3b82f6",       # blue
    "contributor": "#22c55e", # green
    "concept": "#f59e0b",    # amber
}


def _hash_angle(node_id: str) -> float:
    """Deterministic angle [0, 2*pi) from node ID hash."""
    digest = hashlib.sha256(node_id.encode()).hexdigest()
    return (int(digest[:8], 16) / 0xFFFFFFFF) * 2 * math.pi


def _node_brightness(node: dict[str, Any], node_type: str, edge_counts: dict[str, int]) -> float:
    """Compute brightness [0.0, 1.0] based on node type."""
    if node_type == "idea":
        pv = float(node.get("potential_value") or 1.0)
        av = float(node.get("actual_value") or 0.0)
        return min(1.0, av / pv) if pv > 0 else 0.0
    elif node_type == "contributor":
        # Use edge count as proxy for contribution activity
        count = edge_counts.get(node.get("id", ""), 0)
        return min(1.0, count / 10.0) if count > 0 else 0.1
    elif node_type == "concept":
        count = edge_counts.get(node.get("id", ""), 0)
        return min(1.0, count / 5.0) if count > 0 else 0.1
    return 0.1


def _node_size(node: dict[str, Any], node_type: str, edge_counts: dict[str, int]) -> float:
    """Compute relative size [0.1, 1.0]."""
    if node_type == "idea":
        pv = float(node.get("potential_value") or 1.0)
        return min(1.0, max(0.1, pv / 100.0))
    count = edge_counts.get(node.get("id", ""), 0)
    return min(1.0, max(0.1, count / 10.0))


def build_constellation(
    workspace_id: str = "coherence-network",
    max_nodes: int = 100,
) -> dict[str, Any]:
    """Build constellation graph data for visualization.

    1. Fetch top ideas by potential_value
    2. Fetch active contributors
    3. Fetch key concepts from ontology
    4. Compute brightness, size, color, and position for each node
    5. Fetch edges between the collected nodes
    6. Return nodes, edges, stats
    """
    idea_limit = max(1, max_nodes // 2)
    contributor_limit = max(1, max_nodes // 4)
    concept_limit = max(1, max_nodes // 4)

    # -- Fetch ideas --
    idea_result = graph_service.list_nodes(type="idea", limit=idea_limit)
    idea_nodes = idea_result.get("items", [])

    # -- Fetch contributors --
    contributor_result = graph_service.list_nodes(type="contributor", limit=contributor_limit)
    contributor_nodes = contributor_result.get("items", [])

    # -- Fetch concepts from ontology --
    concept_result = concept_service.list_concepts(limit=concept_limit, offset=0)
    concept_items = concept_result.get("items", [])

    # Collect all node IDs for edge lookup
    all_node_ids: set[str] = set()
    for n in idea_nodes:
        all_node_ids.add(n.get("id", ""))
    for n in contributor_nodes:
        all_node_ids.add(n.get("id", ""))
    for c in concept_items:
        all_node_ids.add(c.get("id", ""))
    all_node_ids.discard("")

    # -- Fetch edges --
    edge_result = graph_service.list_edges(limit=500)
    all_edges = edge_result.get("items", [])

    # Filter edges to only those connecting our nodes
    relevant_edges = []
    for e in all_edges:
        from_id = e.get("from_id", "")
        to_id = e.get("to_id", "")
        if from_id in all_node_ids and to_id in all_node_ids:
            relevant_edges.append(e)

    # Compute edge counts per node
    edge_counts: dict[str, int] = {}
    for e in all_edges:
        from_id = e.get("from_id", "")
        to_id = e.get("to_id", "")
        if from_id in all_node_ids:
            edge_counts[from_id] = edge_counts.get(from_id, 0) + 1
        if to_id in all_node_ids:
            edge_counts[to_id] = edge_counts.get(to_id, 0) + 1

    # -- Build output nodes --
    max_edge_count = max(edge_counts.values()) if edge_counts else 1
    output_nodes: list[dict[str, Any]] = []

    def _position(node_id: str) -> tuple[float, float]:
        """Hash-based angle, connection-count-based radius (more connected = more central)."""
        angle = _hash_angle(node_id)
        count = edge_counts.get(node_id, 0)
        # More connected nodes are closer to center; radius inversely proportional to connections
        radius = 1.0 - (count / (max_edge_count + 1)) * 0.8 if max_edge_count > 0 else 0.5
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        return round(x, 4), round(y, 4)

    for n in idea_nodes:
        nid = n.get("id", "")
        x, y = _position(nid)
        output_nodes.append({
            "id": nid,
            "type": "idea",
            "name": n.get("name", ""),
            "brightness": round(_node_brightness(n, "idea", edge_counts), 4),
            "size": round(_node_size(n, "idea", edge_counts), 4),
            "color": _TYPE_COLORS["idea"],
            "x": x,
            "y": y,
        })

    for n in contributor_nodes:
        nid = n.get("id", "")
        x, y = _position(nid)
        output_nodes.append({
            "id": nid,
            "type": "contributor",
            "name": n.get("name", ""),
            "brightness": round(_node_brightness(n, "contributor", edge_counts), 4),
            "size": round(_node_size(n, "contributor", edge_counts), 4),
            "color": _TYPE_COLORS["contributor"],
            "x": x,
            "y": y,
        })

    for c in concept_items:
        cid = c.get("id", "")
        x, y = _position(cid)
        output_nodes.append({
            "id": cid,
            "type": "concept",
            "name": c.get("name", c.get("label", "")),
            "brightness": round(_node_brightness(c, "concept", edge_counts), 4),
            "size": round(_node_size(c, "concept", edge_counts), 4),
            "color": _TYPE_COLORS["concept"],
            "x": x,
            "y": y,
        })

    # -- Build output edges --
    output_edges = [
        {
            "from": e.get("from_id", ""),
            "to": e.get("to_id", ""),
            "type": e.get("type", ""),
            "strength": float(e.get("strength", 1.0)),
        }
        for e in relevant_edges
    ]

    # -- Cluster estimation: simple connected-component count --
    # Use union-find for quick cluster count
    parent: dict[str, str] = {n["id"]: n["id"] for n in output_nodes}

    def _find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], x)
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for e in relevant_edges:
        fid = e.get("from_id", "")
        tid = e.get("to_id", "")
        if fid in parent and tid in parent:
            _union(fid, tid)

    clusters = len({_find(nid) for nid in parent}) if parent else 0

    return {
        "nodes": output_nodes,
        "edges": output_edges,
        "stats": {
            "total_nodes": len(output_nodes),
            "total_edges": len(output_edges),
            "clusters": clusters,
        },
    }
