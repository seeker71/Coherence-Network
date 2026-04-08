"""Membership service — team edges between contributors and workspaces.

Memberships are stored as graph edges of type "member-of" from a contributor
node to a workspace node. Role, status, and timestamps live in edge properties.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services import graph_service

log = logging.getLogger(__name__)

EDGE_TYPE = "member-of"


def _resolve_contributor_node_id(contributor_id: str) -> str | None:
    """Find the contributor node, trying both prefixed and bare IDs."""
    prefixed = f"contributor:{contributor_id}"
    node = graph_service.get_node(prefixed)
    if node and node.get("type") == "contributor":
        return prefixed
    node = graph_service.get_node(contributor_id)
    if node and node.get("type") == "contributor":
        return contributor_id
    return None


def _validate_workspace(workspace_id: str) -> dict[str, Any]:
    """Return the workspace node dict or raise ValueError."""
    node = graph_service.get_node(workspace_id)
    if not node or node.get("type") != "workspace":
        raise ValueError(f"Workspace '{workspace_id}' not found")
    return node


def add_member(
    workspace_id: str,
    contributor_id: str,
    role: str = "member",
    status: str = "active",
) -> dict[str, Any]:
    """Add a contributor as a member of a workspace."""
    _validate_workspace(workspace_id)

    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        raise ValueError(f"Contributor '{contributor_id}' not found")

    now = datetime.now(timezone.utc).isoformat()
    props: dict[str, Any] = {"role": role, "status": status}
    if status == "active":
        props["joined_at"] = now

    edge = graph_service.create_edge(
        from_id=contributor_node_id,
        to_id=workspace_id,
        type=EDGE_TYPE,
        properties=props,
    )

    contributor_node = graph_service.get_node(contributor_node_id)
    return {
        "contributor_id": contributor_id,
        "contributor_name": (contributor_node or {}).get("name", ""),
        "role": role,
        "status": status,
        "joined_at": props.get("joined_at"),
    }


def invite_member(
    workspace_id: str,
    contributor_id: str,
    role: str = "member",
    invited_by: str | None = None,
) -> dict[str, Any]:
    """Invite a contributor to a workspace (status=pending)."""
    _validate_workspace(workspace_id)

    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        raise ValueError(f"Contributor '{contributor_id}' not found")

    now = datetime.now(timezone.utc).isoformat()
    props: dict[str, Any] = {
        "role": role,
        "status": "pending",
        "invited_at": now,
    }
    if invited_by:
        props["invited_by"] = invited_by

    edge = graph_service.create_edge(
        from_id=contributor_node_id,
        to_id=workspace_id,
        type=EDGE_TYPE,
        properties=props,
    )

    return {
        "invite_id": edge.get("id", ""),
        "contributor_id": contributor_id,
        "workspace_id": workspace_id,
        "role": role,
        "status": "pending",
    }


def accept_invite(workspace_id: str, contributor_id: str) -> dict[str, Any]:
    """Accept a pending invite — set status=active and joined_at=now."""
    _validate_workspace(workspace_id)

    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        raise ValueError(f"Contributor '{contributor_id}' not found")

    edges = graph_service.get_edges(
        contributor_node_id, direction="outgoing", edge_type=EDGE_TYPE,
    )

    pending_edge = None
    for e in edges:
        if e.get("to_id") == workspace_id:
            props = e.get("properties", {})
            if props.get("status") == "pending":
                pending_edge = e
                break

    if not pending_edge:
        raise ValueError("No pending invite found")

    now = datetime.now(timezone.utc).isoformat()
    updated = graph_service.update_edge(
        pending_edge["id"],
        properties={"status": "active", "joined_at": now},
    )

    contributor_node = graph_service.get_node(contributor_node_id)
    role = (updated or pending_edge).get("properties", {}).get("role", "member")
    return {
        "contributor_id": contributor_id,
        "contributor_name": (contributor_node or {}).get("name", ""),
        "role": role,
        "status": "active",
        "joined_at": now,
    }


def remove_member(workspace_id: str, contributor_id: str) -> bool:
    """Remove a contributor from a workspace."""
    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        return False

    edges = graph_service.get_edges(
        contributor_node_id, direction="outgoing", edge_type=EDGE_TYPE,
    )

    for e in edges:
        if e.get("to_id") == workspace_id:
            return graph_service.delete_edge(e["id"])

    return False


def list_members(workspace_id: str) -> list[dict[str, Any]]:
    """List all members of a workspace."""
    edges = graph_service.get_edges(
        workspace_id, direction="incoming", edge_type=EDGE_TYPE,
    )

    # Batch-load contributor nodes for names
    members = []
    for e in edges:
        contributor_node_id = e.get("from_id", "")
        contributor_node = graph_service.get_node(contributor_node_id)
        props = e.get("properties", {})
        # Derive the contributor_id (strip "contributor:" prefix if present)
        cid = contributor_node_id
        if cid.startswith("contributor:"):
            cid = cid[len("contributor:"):]
        members.append({
            "contributor_id": cid,
            "contributor_name": (contributor_node or {}).get("name", ""),
            "role": props.get("role", "member"),
            "status": props.get("status", "active"),
            "joined_at": props.get("joined_at"),
        })

    return members


def list_workspaces_for_contributor(contributor_id: str) -> list[dict[str, Any]]:
    """List all workspaces a contributor belongs to."""
    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        return []

    edges = graph_service.get_edges(
        contributor_node_id, direction="outgoing", edge_type=EDGE_TYPE,
    )

    workspaces = []
    for e in edges:
        ws_id = e.get("to_id", "")
        ws_node = graph_service.get_node(ws_id)
        props = e.get("properties", {})
        workspaces.append({
            "workspace_id": ws_id,
            "workspace_name": (ws_node or {}).get("name", ""),
            "role": props.get("role", "member"),
            "joined_at": props.get("joined_at"),
        })

    return workspaces


def get_member_role(workspace_id: str, contributor_id: str) -> str | None:
    """Return the role of a contributor in a workspace, or None if not a member."""
    contributor_node_id = _resolve_contributor_node_id(contributor_id)
    if not contributor_node_id:
        return None

    edges = graph_service.get_edges(
        contributor_node_id, direction="outgoing", edge_type=EDGE_TYPE,
    )

    for e in edges:
        if e.get("to_id") == workspace_id:
            return e.get("properties", {}).get("role")

    return None


def ensure_owner_membership(workspace_id: str, owner_contributor_id: str) -> dict[str, Any]:
    """Ensure the workspace creator is registered as owner. Idempotent."""
    return add_member(workspace_id, owner_contributor_id, role="owner", status="active")
