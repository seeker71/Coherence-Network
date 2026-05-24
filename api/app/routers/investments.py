"""Investment endpoints — preview, portfolio, history, time pledges.

Thin HTTP wrappers over investment_service + time_pledge_service. Each
endpoint is a projection of the same underlying position state.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.investment import (
    InvestPreview,
    InvestmentHistory,
    Portfolio,
    TimePledge,
    TimePledgeCreate,
    TimePledgeFulfill,
    TimePledgeList,
)
from app.services import investment_service, time_pledge_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


@router.get(
    "/ideas/{idea_id}/invest-preview",
    response_model=InvestPreview,
    summary="ROI projection for an idea (preview-only, no recording)",
)
def get_invest_preview(idea_id: str) -> InvestPreview:
    preview = investment_service.compute_preview(idea_id)
    if preview is None:
        raise HTTPException(status_code=404, detail=f"Idea not found: {idea_id}")
    return InvestPreview(**preview)


# ---------------------------------------------------------------------------
# Portfolio + history
# ---------------------------------------------------------------------------


@router.get(
    "/contributors/{contributor_id}/investments",
    response_model=Portfolio,
    summary="List all investment positions for a contributor with summary",
)
def get_portfolio(
    contributor_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str = Query("gain_loss_desc"),
) -> Portfolio:
    data = investment_service.compute_portfolio(contributor_id)
    positions = data["positions"]

    if sort == "invested_desc":
        positions.sort(key=lambda p: p["invested_cc"], reverse=True)
    elif sort == "roi_pct_desc":
        positions.sort(key=lambda p: p["roi_pct"], reverse=True)
    elif sort == "staked_at_desc":
        positions.sort(key=lambda p: p.get("staked_at") or "", reverse=True)
    # default: gain_loss_desc — already sorted by compute_positions.

    data["positions"] = positions[offset : offset + limit]
    return Portfolio(**data)


@router.get(
    "/contributors/{contributor_id}/investment-history",
    response_model=InvestmentHistory,
    summary="CC flow timeline for a contributor's investment activity",
)
def get_investment_history(
    contributor_id: str,
    limit: int = Query(100, ge=1, le=500),
    since: str | None = Query(default=None),
    idea_id: str | None = Query(default=None),
) -> InvestmentHistory:
    data = investment_service.compute_history(
        contributor_id=contributor_id, limit=limit, since=since, idea_id=idea_id
    )
    return InvestmentHistory(**data)


# ---------------------------------------------------------------------------
# Time pledges
# ---------------------------------------------------------------------------


@router.post(
    "/contributors/{contributor_id}/pledges",
    response_model=TimePledge,
    status_code=201,
    summary="Create a time pledge with CC equivalent",
)
def create_pledge(contributor_id: str, body: TimePledgeCreate) -> TimePledge:
    try:
        pledge = time_pledge_service.create_pledge(
            contributor_id=contributor_id,
            idea_id=body.idea_id,
            hours_pledged=body.hours_pledged,
            pledge_type=body.pledge_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TimePledge(**pledge)


@router.get(
    "/contributors/{contributor_id}/pledges",
    response_model=TimePledgeList,
    summary="List a contributor's time pledges",
)
def list_pledges(
    contributor_id: str,
    status: str | None = Query(default=None),
) -> TimePledgeList:
    pledges = time_pledge_service.list_pledges(contributor_id, status=status)
    return TimePledgeList(
        contributor_id=contributor_id,
        pledges=[TimePledge(**p) for p in pledges],
    )


@router.post(
    "/contributors/{contributor_id}/pledges/{pledge_id}/fulfill",
    response_model=TimePledge,
    summary="Mark a pledge fulfilled and record the matching CC return",
)
def fulfill_pledge(
    contributor_id: str,
    pledge_id: str,
    body: TimePledgeFulfill,
) -> TimePledge:
    try:
        pledge = time_pledge_service.fulfill_pledge(
            pledge_id=pledge_id,
            contributor_id=contributor_id,
            contribution_id=body.contribution_id,
            evidence_url=body.evidence_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return TimePledge(**pledge)
