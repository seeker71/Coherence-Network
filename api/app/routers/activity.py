"""Activity feed routes — read-only workspace activity streams.

GET /workspaces/{workspace_id}/activity        — paginated event feed
GET /workspaces/{workspace_id}/activity/summary — event count rollup
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.activity import ActivityFeedResponse, ActivitySummaryResponse
from app.services import activity_service

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/activity",
    response_model=ActivityFeedResponse,
    summary="List activity events for a workspace",
)
async def list_activity(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
) -> ActivityFeedResponse:
    """List activity events for a workspace."""
    events = activity_service.list_events(
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
    )
    # Determine has_more: if we got a full page there might be more
    total_events = activity_service.list_events(
        workspace_id=workspace_id,
        limit=500,
        offset=0,
        event_type=event_type,
    )
    total = len(total_events)
    has_more = (offset + limit) < total
    return ActivityFeedResponse(
        workspace_id=workspace_id,
        events=events,
        total=total,
        has_more=has_more,
    )


@router.get(
    "/workspaces/{workspace_id}/activity/summary",
    response_model=ActivitySummaryResponse,
    summary="Get activity event counts by type for a workspace",
)
async def activity_summary(
    workspace_id: str,
    days: int = Query(7, ge=1, le=365),
) -> ActivitySummaryResponse:
    """Get activity event counts by type for a workspace."""
    counts = activity_service.event_summary(
        workspace_id=workspace_id,
        days=days,
    )
    return ActivitySummaryResponse(
        workspace_id=workspace_id,
        event_counts=counts,
        period_days=days,
    )
