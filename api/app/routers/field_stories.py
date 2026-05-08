"""Field story router — source-backed narrative and frequency artifacts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import (
    field_story_service,
    field_view_attribution_adjustment_service,
    field_view_attribution_service,
)

router = APIRouter()


class FieldStoryContributionIn(BaseModel):
    contributor_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    contribution_type: str = Field(default="addition", min_length=1)
    summary: str = Field(min_length=1)
    content_markdown: str = ""


class FieldStoryViewAttributionIn(BaseModel):
    surface: str = Field(default="/field/urs", min_length=1)
    presence_id: str = Field(min_length=1)
    target_selector: str = Field(default="significant-work", min_length=1)
    target_value: str = Field(min_length=1)
    session_hash: str | None = None
    viewer_contributor_id: str | None = None
    cc_amount: float = Field(default=1.0, ge=0.0, le=1000.0)


class FieldStoryViewAttributionAdjustmentIn(BaseModel):
    event_hash: str = Field(min_length=1)
    from_recipient_id: str = Field(min_length=1)
    to_recipient_id: str = Field(min_length=1)
    amount_cc: float = Field(gt=0.0, le=1000.0)
    reason_code: str = Field(default="living-redistribution", min_length=1)
    attested_by: str = Field(min_length=1)
    attestation_type: str = Field(default="steward-attestation", min_length=1)
    note: str = ""


@router.get("/field-stories", summary="List published field stories")
async def list_field_stories() -> dict:
    return {"items": field_story_service.list_field_stories()}


@router.get("/field-stories/{slug}", summary="Get a published field story")
async def get_field_story(slug: str) -> dict:
    try:
        return field_story_service.get_field_story(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/field-stories/{slug}/artifacts/{artifact_id}",
    summary="Get a single field story artifact",
)
async def get_field_story_artifact(slug: str, artifact_id: str) -> dict:
    try:
        return field_story_service.get_field_story_artifact(slug, artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {exc}") from exc


@router.get(
    "/field-stories/{slug}/spectrum",
    summary="Get field story frequency spectrum summaries",
)
async def get_field_story_spectrum(slug: str) -> dict:
    try:
        return field_story_service.get_field_story_spectrum(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/field-stories/{slug}/trace/{selector}/{value:path}",
    summary="Get a compact month, author, or work influence trace",
)
async def get_field_story_trace_slice(slug: str, selector: str, value: str) -> dict:
    try:
        return field_story_service.get_field_story_trace_slice(slug, selector, value)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Trace file not found: {exc}") from exc


@router.post(
    "/field-stories/{slug}/view-attribution",
    status_code=201,
    summary="Record a compact attributed field-story view and CC flow receipt",
)
async def record_field_story_view_attribution(slug: str, body: FieldStoryViewAttributionIn) -> dict:
    try:
        return field_view_attribution_service.record_presence_view(
            slug=slug,
            surface=body.surface,
            presence_id=body.presence_id,
            target_selector=body.target_selector,
            target_value=body.target_value,
            session_hash=body.session_hash,
            viewer_contributor_id=body.viewer_contributor_id,
            cc_amount=body.cc_amount,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Trace file not found: {exc}") from exc


@router.get(
    "/field-stories/{slug}/view-attribution-policy",
    summary="Describe field-story attribution policy and living adjustment paths",
)
async def get_field_story_view_attribution_policy(slug: str) -> dict:
    return {"story_slug": slug, **field_view_attribution_adjustment_service.policy_summary()}


@router.post(
    "/field-stories/{slug}/view-attribution-adjustments",
    status_code=201,
    summary="Record an append-only living adjustment to an attributed view flow",
)
async def record_field_story_view_attribution_adjustment(
    slug: str,
    body: FieldStoryViewAttributionAdjustmentIn,
) -> dict:
    try:
        return field_view_attribution_adjustment_service.record_flow_adjustment(
            slug=slug,
            event_hash=body.event_hash,
            from_recipient_id=body.from_recipient_id,
            to_recipient_id=body.to_recipient_id,
            amount_cc=body.amount_cc,
            reason_code=body.reason_code,
            attested_by=body.attested_by,
            attestation_type=body.attestation_type,
            note=body.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/field-stories/{slug}/view-attribution/{event_hash:path}",
    summary="Read a compact attributed field-story view receipt",
)
async def get_field_story_view_attribution(slug: str, event_hash: str) -> dict:
    try:
        receipt = field_view_attribution_service.receipt_summary(event_hash)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if receipt["receipt"].get("event_hash") != event_hash:
        raise HTTPException(status_code=404, detail="Receipt mismatch")
    return receipt


@router.get(
    "/field-stories/{slug}/view-attribution-circulation",
    summary="Summarize field-story view CC circulation and sensing signals",
)
async def get_field_story_view_attribution_circulation(slug: str, limit: int = 12) -> dict:
    return field_view_attribution_service.circulation_summary(slug, limit=limit)


@router.post(
    "/field-stories/{slug}/contributions",
    status_code=201,
    summary="Record an attributed field story contribution proposal",
)
async def contribute_field_story(slug: str, body: FieldStoryContributionIn) -> dict:
    try:
        return field_story_service.record_field_story_contribution(
            slug=slug,
            contributor_id=body.contributor_id,
            artifact_id=body.artifact_id,
            contribution_type=body.contribution_type,
            summary=body.summary,
            content_markdown=body.content_markdown,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
