"""Workspace CRUD service.

Workspaces are stored in the graph as nodes with type='workspace'. The default
workspace 'coherence-network' is auto-ensured at service initialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models.workspace import (
    DEFAULT_WORKSPACE_ID,
    Workspace,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceVisibility,
)
from app.services import graph_service
from app.services.workspace_resolver import (
    COHERENCE_NETWORK_PILLARS,
    get_resolver,
)


NODE_TYPE = "workspace"


def _node_to_workspace(node: dict) -> Workspace:
    props = node
    created_at_raw = node.get("created_at")
    updated_at_raw = node.get("updated_at")
    created_at = _parse_dt(created_at_raw)
    updated_at = _parse_dt(updated_at_raw)
    visibility_raw = props.get("visibility") or WorkspaceVisibility.PUBLIC.value
    try:
        visibility = WorkspaceVisibility(visibility_raw)
    except ValueError:
        visibility = WorkspaceVisibility.PUBLIC
    pillars = props.get("pillars") or []
    if isinstance(pillars, str):
        pillars = [p.strip() for p in pillars.split(",") if p.strip()]
    return Workspace(
        id=node.get("id", ""),
        name=node.get("name", ""),
        description=node.get("description", "") or "",
        pillars=list(pillars),
        owner_contributor_id=props.get("owner_contributor_id"),
        visibility=visibility,
        bundle_path=props.get("bundle_path"),
        created_at=created_at,
        updated_at=updated_at,
    )


def _parse_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def ensure_default_workspace() -> Workspace:
    """Create the default 'coherence-network' workspace if it does not exist."""
    existing = get_workspace(DEFAULT_WORKSPACE_ID)
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    resolver = get_resolver()
    pillars = resolver.get_pillars(DEFAULT_WORKSPACE_ID) or list(COHERENCE_NETWORK_PILLARS)
    node = graph_service.create_node(
        id=DEFAULT_WORKSPACE_ID,
        type=NODE_TYPE,
        name="Coherence Network",
        description="Default workspace for the Coherence Network platform's own ideas and specs.",
        phase="ice",
        properties={
            "pillars": list(pillars),
            "visibility": WorkspaceVisibility.PUBLIC.value,
            "bundle_path": None,  # repo root
            "created_at": now,
            "updated_at": now,
        },
    )
    return _node_to_workspace(node)


def list_workspaces() -> list[Workspace]:
    result = graph_service.list_nodes(type=NODE_TYPE, limit=500, offset=0)
    items = result.get("items", [])
    return [_node_to_workspace(n) for n in items]


def get_workspace(workspace_id: str) -> Optional[Workspace]:
    node = graph_service.get_node(workspace_id)
    if not node or node.get("type") != NODE_TYPE:
        return None
    return _node_to_workspace(node)


def create_workspace(data: WorkspaceCreate) -> Workspace | None:
    if get_workspace(data.id) is not None:
        return None  # already exists
    now = datetime.now(timezone.utc).isoformat()
    node = graph_service.create_node(
        id=data.id,
        type=NODE_TYPE,
        name=data.name,
        description=data.description,
        phase="ice",
        properties={
            "pillars": list(data.pillars),
            "owner_contributor_id": data.owner_contributor_id,
            "visibility": data.visibility.value,
            "bundle_path": f"workspaces/{data.id}",
            "created_at": now,
            "updated_at": now,
        },
    )
    return _node_to_workspace(node) if node and "error" not in node else None


def update_workspace(workspace_id: str, data: WorkspaceUpdate) -> Workspace | None:
    existing_node = graph_service.get_node(workspace_id)
    if not existing_node or existing_node.get("type") != NODE_TYPE:
        return None
    now = datetime.now(timezone.utc).isoformat()
    node_updates: dict = {}
    prop_updates: dict = {"updated_at": now}
    if data.name is not None:
        node_updates["name"] = data.name
    if data.description is not None:
        node_updates["description"] = data.description
    if data.pillars is not None:
        prop_updates["pillars"] = list(data.pillars)
    if data.visibility is not None:
        prop_updates["visibility"] = data.visibility.value
    # graph_service.update_node merges properties (not replaces), so pass only the delta.
    node_updates["properties"] = prop_updates
    updated = graph_service.update_node(workspace_id, **node_updates)
    return _node_to_workspace(updated) if updated else None


def get_pillars_for_workspace(workspace_id: str) -> list[str]:
    """Return the pillars taxonomy for a workspace. Falls back to resolver."""
    ws = get_workspace(workspace_id)
    if ws and ws.pillars:
        return list(ws.pillars)
    # Resolver fallback (reads pillars.yaml from workspace bundle)
    return get_resolver().get_pillars(workspace_id)
