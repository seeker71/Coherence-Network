"""Contributor service — thin helpers used by auth_keys and other non-router code.

Wraps graph_service so callers don't need to import routers directly.
"""

from __future__ import annotations


def get_contributor(contributor_id: str) -> dict | None:
    """Return the graph node for *contributor_id* (by name), or None if not found."""
    from app.services import graph_service

    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return node
    # Secondary search: scan all contributors by name/legacy_id
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if n.get("name") == contributor_id or n.get("legacy_id") == contributor_id:
            return n
    return None


def create_contributor(
    name: str,
    contributor_type: str = "HUMAN",
    email: str | None = None,
) -> dict:
    """Create a contributor graph node.  Returns the node dict.

    Safe to call when the contributor may already exist — callers should catch
    exceptions if strict uniqueness enforcement is not desired.
    """
    from app.services import graph_service

    node_id = f"contributor:{name}"
    effective_email = email or f"{name}@coherence.network"
    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=name,
        description=f"{contributor_type} contributor",
        phase="water",
        properties={
            "contributor_type": contributor_type,
            "email": effective_email,
        },
    )
    return graph_service.get_node(node_id) or {"id": node_id, "name": name}
