"""Contributor messaging service — graph-backed message nodes and edges.

Messages are graph nodes (type="message") with edges connecting sender
and recipient (or workspace for broadcast messages).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services import graph_service


def send_message(
    from_contributor_id: str,
    *,
    to_contributor_id: str | None = None,
    to_workspace_id: str | None = None,
    subject: str | None = None,
    body: str = "",
) -> dict[str, Any]:
    """Create a message node and connect it to sender and recipient.

    Exactly one of *to_contributor_id* or *to_workspace_id* must be set.
    """
    if bool(to_contributor_id) == bool(to_workspace_id):
        raise ValueError(
            "Exactly one of to_contributor_id or to_workspace_id must be set."
        )

    msg_id = f"msg-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    properties: dict[str, Any] = {
        "from_contributor_id": from_contributor_id,
        "body": body,
        "read": False,
        "created_at": now.isoformat(),
    }
    if to_contributor_id:
        properties["to_contributor_id"] = to_contributor_id
    if to_workspace_id:
        properties["to_workspace_id"] = to_workspace_id
    if subject:
        properties["subject"] = subject

    node_name = subject or body[:50]

    node = graph_service.create_node(
        id=msg_id,
        type="message",
        name=node_name,
        description=body,
        phase="water",
        properties=properties,
    )

    # Edge: sender --sent-message--> message
    graph_service.create_edge(
        from_id=from_contributor_id,
        to_id=msg_id,
        type="sent-message",
        created_by=from_contributor_id,
    )

    # Edge: message --> recipient or workspace
    if to_contributor_id:
        graph_service.create_edge(
            from_id=msg_id,
            to_id=to_contributor_id,
            type="received-message",
            created_by=from_contributor_id,
        )
    elif to_workspace_id:
        graph_service.create_edge(
            from_id=msg_id,
            to_id=to_workspace_id,
            type="workspace-message",
            created_by=from_contributor_id,
        )

    return node


def _node_to_message(node: dict[str, Any]) -> dict[str, Any]:
    """Convert a graph node dict to a message response dict.

    Node.to_dict() merges properties into the top-level dict, so all
    message fields (from_contributor_id, body, read, etc.) are top-level keys.
    """
    return {
        "id": node["id"],
        "from_contributor_id": node.get("from_contributor_id", ""),
        "to_contributor_id": node.get("to_contributor_id"),
        "to_workspace_id": node.get("to_workspace_id"),
        "subject": node.get("subject"),
        "body": node.get("body", ""),
        "read": node.get("read", False),
        "created_at": node.get("created_at", ""),
    }


def get_inbox(
    contributor_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> dict[str, Any]:
    """Get messages received by a contributor.

    Returns dict with contributor_id, messages, total, and unread_count.
    """
    # Get all incoming 'received-message' edges targeting this contributor
    edges = graph_service.get_edges(
        contributor_id, direction="incoming", edge_type="received-message"
    )

    # Load message nodes
    messages: list[dict[str, Any]] = []
    for edge in edges:
        msg_node_id = edge["from_id"]
        node = graph_service.get_node(msg_node_id)
        if node and node.get("type") == "message":
            messages.append(_node_to_message(node))

    # Count unread before filtering
    unread_count = sum(1 for m in messages if not m["read"])

    if unread_only:
        messages = [m for m in messages if not m["read"]]

    # Sort by created_at desc (newest first)
    messages.sort(key=lambda m: m.get("created_at", ""), reverse=True)

    total = len(messages)
    paginated = messages[offset : offset + limit]

    return {
        "contributor_id": contributor_id,
        "messages": paginated,
        "total": total,
        "unread_count": unread_count,
    }


def get_workspace_messages(
    workspace_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Get messages sent to a workspace."""
    edges = graph_service.get_edges(
        workspace_id, direction="incoming", edge_type="workspace-message"
    )

    messages: list[dict[str, Any]] = []
    for edge in edges:
        msg_node_id = edge["from_id"]
        node = graph_service.get_node(msg_node_id)
        if node and node.get("type") == "message":
            messages.append(_node_to_message(node))

    messages.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return messages[offset : offset + limit]


def get_thread(
    contributor_a: str,
    contributor_b: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get conversation thread between two contributors.

    Returns messages where from=a,to=b OR from=b,to=a, sorted by
    created_at ascending (oldest first for thread view).
    """
    seen_ids: set[str] = set()
    thread_messages: list[dict[str, Any]] = []

    # Messages sent by A (outgoing sent-message edges from A)
    edges_a = graph_service.get_edges(
        contributor_a, direction="outgoing", edge_type="sent-message"
    )
    for edge in edges_a:
        msg_id = edge["to_id"]
        if msg_id in seen_ids:
            continue
        node = graph_service.get_node(msg_id)
        if not node or node.get("type") != "message":
            continue
        if node.get("to_contributor_id") == contributor_b:
            seen_ids.add(msg_id)
            thread_messages.append(_node_to_message(node))

    # Messages sent by B (outgoing sent-message edges from B)
    edges_b = graph_service.get_edges(
        contributor_b, direction="outgoing", edge_type="sent-message"
    )
    for edge in edges_b:
        msg_id = edge["to_id"]
        if msg_id in seen_ids:
            continue
        node = graph_service.get_node(msg_id)
        if not node or node.get("type") != "message":
            continue
        if node.get("to_contributor_id") == contributor_a:
            seen_ids.add(msg_id)
            thread_messages.append(_node_to_message(node))

    # Sort ascending (oldest first) for thread view
    thread_messages.sort(key=lambda m: m.get("created_at", ""))
    return thread_messages[:limit]


def mark_read(message_id: str, contributor_id: str) -> dict[str, Any] | None:
    """Mark a message as read.

    Updates the message node properties with read=True, read_by, and read_at.
    Returns the updated node or None if not found.
    """
    node = graph_service.get_node(message_id)
    if not node or node.get("type") != "message":
        return None

    now = datetime.now(timezone.utc)
    updated = graph_service.update_node(
        message_id,
        properties={
            "read": True,
            "read_by": contributor_id,
            "read_at": now.isoformat(),
        },
    )
    return updated
