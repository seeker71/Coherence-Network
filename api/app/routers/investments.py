"""Investment UX: ROI preview, portfolio, flow graph, time commitments."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import investment_service
from app.services import contributor_identity_service

router = APIRouter()


def _resolve_contributor(contributor_id: str | None, provider: str | None, provider_id: str | None) -> str:
    if contributor_id:
        return contributor_id
    if provider and provider_id:
        found = contributor_identity_service.find_contributor_by_identity(provider, provider_id)
        if found:
            return found
        cid = f"{provider}:{provider_id}"
        contributor_identity_service.link_identity(
            contributor_id=cid,
            provider=provider,
            provider_id=provider_id,
            display_name=provider_id,
            verified=False,
        )
        return cid
    raise HTTPException(status_code=422, detail="Provide contributor_id OR provider+provider_id")


@router.get("/investments/preview", summary="Projected ROI for a CC stake on an idea")
async def get_investment_preview(
    idea_id: str = Query(..., min_length=1),
    amount_cc: float = Query(..., gt=0),
) -> dict:
    try:
        return investment_service.preview_investment(idea_id, amount_cc)
    except ValueError as exc:
        if str(exc) == "idea_not_found":
            raise HTTPException(status_code=404, detail="Idea not found") from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/investments/portfolio", summary="Staked positions and estimated values")
async def get_investment_portfolio(
    contributor_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
) -> dict:
    cid = _resolve_contributor(contributor_id, provider, provider_id)
    return investment_service.build_portfolio(cid)


@router.get("/investments/flow", summary="CC flow graph + timeline for a contributor")
async def get_investment_flow(
    contributor_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    provider_id: str | None = Query(default=None),
) -> dict:
    cid = _resolve_contributor(contributor_id, provider, provider_id)
    return investment_service.build_investment_flow(cid)


class TimeCommitmentBody(BaseModel):
    contributor_id: str | None = None
    provider: str | None = None
    provider_id: str | None = None
    hours: float = Field(gt=0, le=10_000)
    commitment: Literal["review", "implement"]


@router.post("/investments/time/{idea_id}", summary="Record hours committed to review or implement")
async def post_time_commitment(idea_id: str, body: TimeCommitmentBody) -> dict:
    cid = _resolve_contributor(body.contributor_id, body.provider, body.provider_id)
    try:
        return investment_service.record_time_commitment(
            idea_id=idea_id,
            contributor_id=cid,
            hours=body.hours,
            commitment=body.commitment,
        )
    except ValueError as exc:
        err = str(exc)
        if err == "idea_not_found":
            raise HTTPException(status_code=404, detail="Idea not found") from exc
        raise HTTPException(status_code=422, detail=err) from exc
