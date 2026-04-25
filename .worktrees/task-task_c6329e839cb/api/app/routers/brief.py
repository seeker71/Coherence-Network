"""Brief router — daily engagement brief endpoints.

Routes:
  GET  /api/brief/daily              Generate daily brief
  POST /api/brief/feedback           Record user action on brief item
  GET  /api/brief/engagement-metrics Aggregate effectiveness metrics
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, field_validator

from app.services import brief_service

router = APIRouter(prefix="/api/brief", tags=["brief"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class BriefFeedbackRequest(BaseModel):
    brief_id: str
    section: str
    item_id: str
    action: str

    @field_validator("section")
    @classmethod
    def validate_section(cls, v: str) -> str:
        if v not in brief_service.VALID_SECTIONS:
            raise ValueError(f"Invalid section: {v!r}. Must be one of {sorted(brief_service.VALID_SECTIONS)}")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in brief_service.VALID_ACTIONS:
            raise ValueError(f"Invalid action: {v!r}. Must be one of {sorted(brief_service.VALID_ACTIONS)}")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/daily", summary="Generate and return a daily brief")
async def get_daily_brief(
    response: Response,
    contributor_id: Optional[str] = Query(default=None),
    limit_per_section: int = Query(default=3, ge=1, le=10),
    as_of: Optional[str] = Query(default=None),
) -> dict:
    """Generate and return a daily brief."""
    try:
        brief = brief_service.generate_brief(
            contributor_id=contributor_id,
            limit_per_section=limit_per_section,
            as_of=as_of,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.headers["X-Brief-ID"] = brief["brief_id"]
    return brief


@router.post("/feedback", status_code=201, summary="Record that a brief card led to an action")
async def post_feedback(body: BriefFeedbackRequest) -> dict:
    """Record that a brief card led to an action."""
    try:
        feedback = brief_service.record_feedback(
            brief_id=body.brief_id,
            section=body.section,
            item_id=body.item_id,
            action=body.action,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return feedback


@router.get("/engagement-metrics", summary="Return aggregate engagement metrics")
async def get_engagement_metrics(
    window_days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Return aggregate engagement metrics."""
    return brief_service.get_engagement_metrics(window_days=window_days)
