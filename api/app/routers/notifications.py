"""Notifications — quiet witnesses of response.

Reads existing reaction/voice tables to compute what has been said to
this viewer since they last checked. No push infra; the client polls
when it comes into foreground.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from app.services import notification_service
from app.services.localized_errors import caller_lang

router = APIRouter()


@router.get(
    "/notifications",
    summary="Quiet list of who spoke back to you since your last check",
    description=(
        "Events since the ISO timestamp in `since`. Pass `contributor_id` "
        "if you have one (matches replies + voice-reactions); pass "
        "`author_name` to also catch @mentions. Either alone works."
    ),
)
async def list_notifications(
    request: Request,
    contributor_id: str | None = Query(None),
    author_name: str | None = Query(None),
    since: str | None = Query(None, description="ISO 8601 timestamp; newer events are returned"),
    limit: int = Query(50, ge=1, le=200),
    lang: str | None = Query(None, description="Override caller locale for event bodies"),
) -> dict:
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None
    locale = caller_lang(request, lang)
    events = notification_service.unseen_for(
        contributor_id=contributor_id,
        author_name=author_name,
        since=since_dt,
        limit=limit,
        locale=locale,
    )
    return {
        "events": events,
        "count": len(events),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "locale": locale,
    }
