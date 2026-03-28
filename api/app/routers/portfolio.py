"""Portfolio router — contributor personal view endpoints (ux-my-portfolio)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.portfolio import (
    CCHistory,
    IdeaContributionDrilldown,
    IdeaContributionsList,
    PortfolioSummary,
    StakesList,
    TasksList,
)
from app.services import portfolio_service

router = APIRouter()


def _not_found(contributor_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Contributor not found: {contributor_id}")


@router.get(
    "/contributors/{contributor_id}/portfolio",
    response_model=PortfolioSummary,
    summary="Get contributor portfolio summary",
    tags=["portfolio"],
)
def get_portfolio_summary(contributor_id: str, include_cc: bool = Query(True)) -> PortfolioSummary:
    """Return contributor portfolio summary: identities, CC balance, idea/stake/task counts."""
    try:
        return portfolio_service.get_portfolio_summary(contributor_id, include_cc=include_cc)
    except ValueError as exc:
        raise _not_found(contributor_id) from exc


@router.get(
    "/contributors/{contributor_id}/cc-history",
    response_model=CCHistory,
    summary="Get contributor CC earning history",
    tags=["portfolio"],
)
def get_cc_history(
    contributor_id: str,
    window: str = Query("90d", description="Time window, e.g. 30d, 90d, 365d"),
    bucket: str = Query("7d", description="Bucket size: 1d, 7d, or 30d"),
) -> CCHistory:
    """Return time-series of CC earned bucketed over the requested window."""
    try:
        return portfolio_service.get_cc_history(contributor_id, window=window, bucket=bucket)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise _not_found(contributor_id) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get(
    "/contributors/{contributor_id}/idea-contributions",
    response_model=IdeaContributionsList,
    summary="List ideas a contributor contributed to",
    tags=["portfolio"],
)
def get_idea_contributions(
    contributor_id: str,
    sort: str = Query("cc_attributed_desc", description="Sort: cc_attributed_desc | recent"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> IdeaContributionsList:
    """List ideas with status, contribution types, CC attributed, and health signal."""
    try:
        return portfolio_service.get_idea_contributions(
            contributor_id, sort=sort, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise _not_found(contributor_id) from exc


@router.get(
    "/contributors/{contributor_id}/idea-contributions/{idea_id}",
    response_model=IdeaContributionDrilldown,
    summary="Drill into a contributor's contributions to a specific idea",
    tags=["portfolio"],
)
def get_idea_contribution_detail(contributor_id: str, idea_id: str) -> IdeaContributionDrilldown:
    """Return per-contribution detail for a contributor on a specific idea, plus value lineage."""
    try:
        return portfolio_service.get_idea_contribution_detail(contributor_id, idea_id)
    except ValueError as exc:
        raise _not_found(contributor_id) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/contributors/{contributor_id}/stakes",
    response_model=StakesList,
    summary="List ideas a contributor staked on",
    tags=["portfolio"],
)
def get_stakes(
    contributor_id: str,
    sort: str = Query("roi_desc", description="Sort: roi_desc"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> StakesList:
    """Return stakes with ROI since staking date and idea health signal."""
    try:
        return portfolio_service.get_stakes(contributor_id, sort=sort, limit=limit, offset=offset)
    except ValueError as exc:
        raise _not_found(contributor_id) from exc


@router.get(
    "/contributors/{contributor_id}/tasks",
    response_model=TasksList,
    summary="List tasks completed by a contributor",
    tags=["portfolio"],
)
def get_tasks(
    contributor_id: str,
    status: str = Query("completed", description="Filter by task status"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> TasksList:
    """Return tasks with provider used, outcome, CC earned, and completion date."""
    try:
        return portfolio_service.get_tasks(contributor_id, status=status, limit=limit, offset=offset)
    except ValueError as exc:
        raise _not_found(contributor_id) from exc
