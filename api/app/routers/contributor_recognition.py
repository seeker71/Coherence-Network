from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.contributor_growth import ContributorGrowthSnapshot
from app.models.contributor_recognition import ContributorRecognitionSnapshot
from app.models.error import ErrorDetail
from app.services import contributor_growth_service, contributor_recognition_service

router = APIRouter()


@router.get(
    "/contributors/{contributor_id}/recognition",
    response_model=ContributorRecognitionSnapshot,
    summary="Get contributor recognition snapshot",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_recognition(contributor_id: UUID, request: Request) -> ContributorRecognitionSnapshot:
    snapshot = contributor_recognition_service.get_contributor_recognition_snapshot(
        contributor_id,
        store=getattr(request.app.state, "graph_store", None),
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return snapshot


@router.get(
    "/contributors/{contributor_id}/growth",
    response_model=ContributorGrowthSnapshot,
    summary="Get contributor growth snapshot (streaks, levels, timeline, milestones)",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_growth(contributor_id: str) -> ContributorGrowthSnapshot:
    """Return the full growth picture for a contributor:
    level, streaks, 26-week timeline, type breakdown, and earned milestones.
    Works with any contributor_id string — UUID or provider-scoped identity.
    """
    snapshot = contributor_growth_service.get_contributor_growth(contributor_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No contributions found for this contributor")
    return snapshot


@router.get(
    "/contributions/feed",
    summary="Community feed of recent contributions",
)
def get_community_feed(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Return the most recent contributions across all contributors for the community feed.
    Sorted by recorded_at descending. Includes display_name for each contributor.
    """
    return contributor_growth_service.get_community_feed(limit=limit, offset=offset)
