"""Workspace Project service — CRUD for project grouping nodes and edges.

Projects are graph nodes (type="workspace-project") with "contains-idea"
edges to member ideas.  No SQL migrations — everything uses graph_service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services import graph_service

log = logging.getLogger(__name__)

NODE_TYPE = "workspace-project"
EDGE_TYPE = "contains-idea"


def create_project(
    name: str,
    description: str | None,
    workspace_id: str,
    created_by: str | None = None,
) -> dict:
    """Create a workspace-project node after validating the workspace exists."""
    ws = graph_service.get_node(workspace_id)
    if not ws or ws.get("type") != "workspace":
        raise ValueError(f"Workspace '{workspace_id}' not found")

    project_id = f"proj-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    node = graph_service.create_node(
        id=project_id,
        type=NODE_TYPE,
        name=name,
        description=description or "",
        properties={
            "workspace_id": workspace_id,
            "created_by": created_by,
            "created_at": now,
        },
    )
    return _node_to_project(node, idea_count=0)


def list_projects(workspace_id: str) -> list[dict]:
    """List all projects belonging to a workspace."""
    result = graph_service.list_nodes(type=NODE_TYPE, limit=500)
    items = result.get("items", [])
    projects = []
    for node in items:
        if node.get("workspace_id") == workspace_id:
            idea_count = _count_ideas(node["id"])
            projects.append(_node_to_project(node, idea_count=idea_count))
    return projects


def get_project(project_id: str) -> dict | None:
    """Get a project with its member ideas."""
    node = graph_service.get_node(project_id)
    if not node or node.get("type") != NODE_TYPE:
        return None
    neighbors = graph_service.get_neighbors(
        project_id, edge_type=EDGE_TYPE, direction="outgoing",
    )
    proj = _node_to_project(node, idea_count=len(neighbors))
    proj["ideas"] = neighbors
    return proj


def delete_project(project_id: str) -> bool:
    """Delete a project node and all its edges."""
    node = graph_service.get_node(project_id)
    if not node or node.get("type") != NODE_TYPE:
        return False
    return graph_service.delete_node(project_id)


def add_idea_to_project(project_id: str, idea_id: str) -> dict:
    """Add an idea to a project. Both must exist and share the same workspace."""
    proj_node = graph_service.get_node(project_id)
    if not proj_node or proj_node.get("type") != NODE_TYPE:
        raise ValueError(f"Project '{project_id}' not found")

    idea_node = graph_service.get_node(idea_id)
    if not idea_node or idea_node.get("type") != "idea":
        raise ValueError(f"Idea '{idea_id}' not found")

    # Cross-workspace check: get workspace_id from both
    proj_ws = proj_node.get("workspace_id")
    idea_ws = _get_idea_workspace_id(idea_id, idea_node)
    if proj_ws != idea_ws:
        raise ValueError(
            f"Cross-workspace rejected: project belongs to '{proj_ws}', "
            f"idea belongs to '{idea_ws}'"
        )

    edge = graph_service.create_edge(
        from_id=project_id,
        to_id=idea_id,
        type=EDGE_TYPE,
    )
    return edge


def remove_idea_from_project(project_id: str, idea_id: str) -> bool:
    """Remove an idea from a project by deleting the contains-idea edge."""
    edges = graph_service.get_edges(project_id, direction="outgoing", edge_type=EDGE_TYPE)
    for edge in edges:
        if edge.get("to_id") == idea_id:
            return graph_service.delete_edge(edge["id"])
    return False


def list_projects_for_idea(idea_id: str) -> list[dict]:
    """List all projects that contain the given idea."""
    edges = graph_service.get_edges(idea_id, direction="incoming", edge_type=EDGE_TYPE)
    projects = []
    for edge in edges:
        proj_id = edge.get("from_id")
        if proj_id:
            node = graph_service.get_node(proj_id)
            if node and node.get("type") == NODE_TYPE:
                idea_count = _count_ideas(proj_id)
                projects.append(_node_to_project(node, idea_count=idea_count))
    return projects


# ── Internal helpers ────────────────────────────────────────────────


def _count_ideas(project_id: str) -> int:
    """Count contains-idea edges outgoing from a project."""
    edges = graph_service.get_edges(project_id, direction="outgoing", edge_type=EDGE_TYPE)
    return len(edges)


def _get_idea_workspace_id(idea_id: str, idea_node: dict) -> str:
    """Resolve the workspace_id for an idea.

    Checks graph node properties first, then falls back to idea_service,
    then defaults to 'coherence-network'.
    """
    # Graph node properties may have workspace_id
    ws = idea_node.get("workspace_id")
    if ws:
        return ws

    # Fall back to idea_service which has the full Pydantic model
    try:
        from app.services import idea_service
        idea = idea_service.get_idea(idea_id)
        if idea and hasattr(idea, "workspace_id"):
            return idea.workspace_id
    except Exception:
        log.debug("Could not load idea %s via idea_service", idea_id, exc_info=True)

    return "coherence-network"


def _node_to_project(node: dict, idea_count: int = 0) -> dict:
    """Convert a graph node dict to a project response dict."""
    created_at_raw = node.get("created_at")
    if isinstance(created_at_raw, str):
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            created_at = datetime.now(timezone.utc)
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        created_at = datetime.now(timezone.utc)

    return {
        "id": node.get("id", ""),
        "name": node.get("name", ""),
        "description": node.get("description") or None,
        "workspace_id": node.get("workspace_id", ""),
        "idea_count": idea_count,
        "created_by": node.get("created_by"),
        "created_at": created_at,
    }
