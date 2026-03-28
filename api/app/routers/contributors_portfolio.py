"""Contributor Portfolio API routes (spec 174)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.portfolio import (
    CCHistory,
    IdeaContributionDrilldown,
    IdeaContributionsList,
    PortfolioSummary,
    StakeDetail,
    StakesList,
    TasksList,
)
from app.services import portfolio_service

router = APIRouter()


@router.get(
    "/contributors/{contributor_id}/portfolio",
    response_model=PortfolioSummary,
    summary="Get contributor portfolio summary",
)
def get_portfolio_summary(
    contributor_id: str,
    include_cc: bool = Query(True, description="Whether to include CC balance and percent"),
) -> PortfolioSummary:
    """Retrieve an aggregated portfolio summary for a specific contributor."""
    try:
        return portfolio_service.get_portfolio_summary(contributor_id, include_cc=include_cc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/cc-history",
    response_model=CCHistory,
    summary="Get contributor CC earning history",
)
def get_cc_history(
    contributor_id: str,
    window: str = Query("90d", description="Lookback window (e.g., 30d, 90d, 365d)"),
    bucket: str = Query("7d", description="Aggregation bucket (1d, 7d, 30d)"),
) -> CCHistory:
    """Retrieve the CC earning history series for a specific contributor."""
    try:
        return portfolio_service.get_cc_history(contributor_id, window=window, bucket=bucket)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/idea-contributions",
    response_model=IdeaContributionsList,
    summary="List ideas the contributor has worked on",
)
def get_idea_contributions(
    contributor_id: str,
    sort: str = Query("cc_attributed_desc", description="Sort order"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> IdeaContributionsList:
    """List all ideas this contributor has contributed to, with health and CC totals."""
    try:
        return portfolio_service.get_idea_contributions(
            contributor_id, sort=sort, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/idea-contributions/{idea_id}",
    response_model=IdeaContributionDrilldown,
    summary="Get detail of contributions to a specific idea",
)
def get_idea_contribution_detail(
    contributor_id: str,
    idea_id: str,
) -> IdeaContributionDrilldown:
    """Retrieve detailed list of contributions and value lineage for one idea."""
    try:
        return portfolio_service.get_idea_contribution_detail(contributor_id, idea_id)
    except (ValueError, PermissionError) as exc:
        status_code = 404 if isinstance(exc, ValueError) else 403
        raise HTTPException(status_code=status_code, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/stakes",
    response_model=StakesList,
    summary="List ideas the contributor has staked on",
)
def get_stakes(
    contributor_id: str,
    sort: str = Query("roi_desc", description="Sort order"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> StakesList:
    """List all ideas this contributor has active stakes in, with valuation and ROI."""
    try:
        return portfolio_service.get_stakes(contributor_id, sort=sort, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/stakes/{stake_id}",
    response_model=StakeDetail,
    summary="Get detail of a single stake position",
)
def get_stake_detail(
    contributor_id: str,
    stake_id: str,
) -> StakeDetail:
    """Retrieve full detail for a single stake: ROI, idea activity since staking, and value lineage."""
    try:
        return portfolio_service.get_stake_detail(contributor_id, stake_id)
    except (ValueError, PermissionError) as exc:
        status_code = 404 if isinstance(exc, ValueError) else 403
        raise HTTPException(status_code=status_code, detail=str(exc))


@router.get(
    "/contributors/{contributor_id}/tasks",
    response_model=TasksList,
    summary="List tasks the contributor has completed",
)
def get_tasks(
    contributor_id: str,
    status: str = Query("completed", description="Task status filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TasksList:
    """List tasks assigned to or completed by this contributor."""
    try:
        return portfolio_service.get_tasks(contributor_id, status=status, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
