"""API routes for value lineage and payout attribution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.value_lineage import (
    LineageLink,
    LineageLinkCreate,
    LineageValuation,
    PayoutPreview,
    PayoutPreviewRequest,
    UsageEvent,
    UsageEventCreate,
)
from app.services import value_lineage_service

router = APIRouter()


@router.post("/value-lineage/links", response_model=LineageLink, status_code=201)
async def create_link(payload: LineageLinkCreate) -> LineageLink:
    return value_lineage_service.create_link(payload)


@router.get("/value-lineage/links/{lineage_id}", response_model=LineageLink)
async def get_link(lineage_id: str) -> LineageLink:
    link = value_lineage_service.get_link(lineage_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Lineage link not found")
    return link


@router.post(
    "/value-lineage/links/{lineage_id}/usage-events",
    response_model=UsageEvent,
    status_code=201,
)
async def add_usage_event(lineage_id: str, payload: UsageEventCreate) -> UsageEvent:
    event = value_lineage_service.add_usage_event(lineage_id, payload)
    if event is None:
        raise HTTPException(status_code=404, detail="Lineage link not found")
    return event


@router.get("/value-lineage/links/{lineage_id}/valuation", response_model=LineageValuation)
async def get_valuation(lineage_id: str) -> LineageValuation:
    report = value_lineage_service.valuation(lineage_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Lineage link not found")
    return report


@router.post("/value-lineage/links/{lineage_id}/payout-preview", response_model=PayoutPreview)
async def payout_preview(lineage_id: str, payload: PayoutPreviewRequest) -> PayoutPreview:
    report = value_lineage_service.payout_preview(lineage_id, payload.payout_pool)
    if report is None:
        raise HTTPException(status_code=404, detail="Lineage link not found")
    return report
