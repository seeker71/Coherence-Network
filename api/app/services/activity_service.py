"""Activity feed service — fire-and-forget event recording and workspace-scoped queries.

Activity events are lightweight graph nodes (type="activity") with workspace_id
stored in properties. All writes are fire-and-forget (never raise).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from app.services import graph_service

log = logging.getLogger(__name__)


def record_event(
    workspace_id: str,
    event_type: str,
    actor_contributor_id: Optional[str] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_name: Optional[str] = None,
    summary: str = "",
) -> Optional[dict[str, Any]]:
    """Record an activity event as a graph node. Fire-and-forget: never raises."""
    try:
        node_id = f"act-{uuid4().hex[:12]}"
        props: dict[str, Any] = {
            "workspace_id": workspace_id,
            "event_type": event_type,
        }
        if actor_contributor_id:
            props["actor_contributor_id"] = actor_contributor_id
        if subject_type:
            props["subject_type"] = subject_type
        if subject_id:
            props["subject_id"] = subject_id
        if subject_name:
            props["subject_name"] = subject_name

        result = graph_service.create_node(
            id=node_id,
            type="activity",
            name=summary[:100] if summary else "",
            description=summary,
            phase="water",
            properties=props,
        )
        return result
    except Exception:
        log.debug("activity_service.record_event failed", exc_info=True)
        return None


def list_events(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List activity events for a workspace, with optional event_type filter.

    Uses graph_service.list_nodes to fetch activity nodes, then post-filters
    by workspace_id (and event_type if provided).
    """
    result = graph_service.list_nodes(type="activity", limit=500)
    items = result.get("items", [])

    # Post-filter by workspace_id
    filtered = [
        item for item in items
        if item.get("workspace_id") == workspace_id
    ]

    # Optional event_type filter
    if event_type:
        filtered = [
            item for item in filtered
            if item.get("event_type") == event_type
        ]

    total = len(filtered)

    # Apply offset/limit pagination
    paginated = filtered[offset : offset + limit]

    # Convert to ActivityEvent-compatible dicts
    events = []
    for item in paginated:
        events.append({
            "id": item.get("id", ""),
            "event_type": item.get("event_type", ""),
            "workspace_id": item.get("workspace_id", workspace_id),
            "actor_contributor_id": item.get("actor_contributor_id"),
            "subject_type": item.get("subject_type"),
            "subject_id": item.get("subject_id"),
            "subject_name": item.get("subject_name"),
            "summary": item.get("description", item.get("name", "")),
            "created_at": item.get("created_at", datetime.now(timezone.utc).isoformat()),
        })

    return events


def event_summary(
    workspace_id: str,
    days: int = 7,
) -> dict[str, int]:
    """Count events by type for a workspace within the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    result = graph_service.list_nodes(type="activity", limit=500)
    items = result.get("items", [])

    counts: dict[str, int] = {}
    for item in items:
        if item.get("workspace_id") != workspace_id:
            continue
        created = item.get("created_at", "")
        if isinstance(created, str) and created < cutoff_iso:
            continue
        et = item.get("event_type", "unknown")
        counts[et] = counts.get(et, 0) + 1

    return counts
