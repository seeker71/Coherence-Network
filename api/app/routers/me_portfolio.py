"""Authenticated portfolio routes — same payloads as /api/contributors/{id}/… via X-API-Key."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.models.portfolio import (
    CCHistory,
    ContributionLineageView,
    IdeaContributionDrilldown,
    IdeaContributionsList,
    PortfolioSummary,
    StakesList,
    TaskDetail,
    TasksList,
)
from app.routers.auth_keys import verify_contributor_key
from app.services import portfolio_service

router = APIRouter(prefix="/me", tags=["portfolio-me"])


def _contributor_id_from_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    if not x_api_key or not str(x_api_key).strip():
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    info = verify_contributor_key(str(x_api_key).strip())
    if not info:
        raise HTTPException(status_code=401, detail="Invalid API key")
    cid = info.get("contributor_id")
    if not cid:
        raise HTTPException(status_code=401, detail="API key has no contributor_id")
    return str(cid)


@router.get("/portfolio", response_model=PortfolioSummary, summary="My portfolio summary (API key)")
def me_portfolio(
    include_cc: bool = Query(True, description="Whether to include CC balance and percent"),
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> PortfolioSummary:
    try:
        return portfolio_service.get_portfolio_summary(contributor_id, include_cc=include_cc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cc-history", response_model=CCHistory, summary="My CC earning history (API key)")
def me_cc_history(
    window: str = Query("90d", description="Lookback window (e.g., 30d, 90d, 365d)"),
    bucket: str = Query("7d", description="Aggregation bucket (1d, 7d, 30d)"),
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> CCHistory:
    try:
        return portfolio_service.get_cc_history(contributor_id, window=window, bucket=bucket)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/idea-contributions", response_model=IdeaContributionsList, summary="My idea contributions (API key)")
def me_idea_contributions(
    sort: str = Query("cc_attributed_desc", description="Sort order"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> IdeaContributionsList:
    try:
        return portfolio_service.get_idea_contributions(
            contributor_id, sort=sort, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/idea-contributions/{idea_id}",
    response_model=IdeaContributionDrilldown,
    summary="My contributions to one idea (API key)",
)
def me_idea_contribution_detail(
    idea_id: str,
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> IdeaContributionDrilldown:
    try:
        return portfolio_service.get_idea_contribution_detail(contributor_id, idea_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/stakes", response_model=StakesList, summary="My stakes (API key)")
def me_stakes(
    sort: str = Query("roi_desc", description="Sort order"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> StakesList:
    try:
        return portfolio_service.get_stakes(contributor_id, sort=sort, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks", response_model=TasksList, summary="My tasks (API key)")
def me_tasks(
    status: str = Query("completed", description="Task status filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> TasksList:
    try:
        return portfolio_service.get_tasks(contributor_id, status=status, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}", response_model=TaskDetail, summary="My task detail (API key)")
def me_task_detail(
    task_id: str,
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> TaskDetail:
    try:
        return portfolio_service.get_task_detail(contributor_id, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/contributions/{contribution_id}/lineage",
    response_model=ContributionLineageView,
    summary="Contribution audit / lineage (API key)",
)
def me_contribution_lineage(
    contribution_id: str,
    contributor_id: str = Depends(_contributor_id_from_api_key),
) -> ContributionLineageView:
    try:
        return portfolio_service.get_contribution_lineage(contributor_id, contribution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
