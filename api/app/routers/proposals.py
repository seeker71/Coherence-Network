"""Proposals — light governance via the meeting gesture.

Anyone can propose. The collective votes by meeting the proposal and
offering care / amplify / move-on. The tally is a function of the
reaction stream, so there is no separate vote ledger to sync.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import proposal_service

router = APIRouter()


class ProposalCreate(BaseModel):
    title: str = Field(..., description="One-line proposal title")
    body: str = Field("", description="Short rationale, two to five sentences")
    author_name: str = Field(..., description="How this proposer appears on the feed")
    author_id: str | None = Field(None, description="Optional contributor id")
    linked_entity_type: str | None = Field(None)
    linked_entity_id: str | None = Field(None)
    locale: str = Field("en")
    window_days: int = Field(14, ge=1, le=90)


@router.post(
    "/proposals",
    status_code=201,
    summary="Propose a change the collective can vote on by meeting",
)
async def create_proposal(payload: ProposalCreate) -> dict:
    try:
        return proposal_service.create_proposal(
            title=payload.title,
            body=payload.body,
            author_name=payload.author_name,
            author_id=payload.author_id,
            linked_entity_type=payload.linked_entity_type,
            linked_entity_id=payload.linked_entity_id,
            locale=payload.locale,
            window_days=payload.window_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/proposals/{proposal_id}",
    summary="Get a single proposal with its current tally",
)
async def get_proposal(proposal_id: str) -> dict:
    p = proposal_service.get_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="proposal not found")
    p["tally"] = proposal_service.tally(proposal_id)
    return p


@router.get(
    "/proposals",
    summary="List open (or all) proposals, newest first",
)
async def list_proposals(
    limit: int = Query(50, ge=1, le=200),
    only_open: bool = Query(True),
    include_tally: bool = Query(True),
) -> dict:
    rows = proposal_service.list_proposals(limit=limit, only_open=only_open)
    if include_tally:
        for r in rows:
            r["tally"] = proposal_service.tally(r["id"])
    return {"proposals": rows, "count": len(rows)}


@router.get(
    "/proposals/{proposal_id}/tally",
    summary="Just the current tally + status for a proposal",
)
async def tally(proposal_id: str) -> dict:
    p = proposal_service.get_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="proposal not found")
    return proposal_service.tally(proposal_id)


@router.get(
    "/proposals/by-idea/{idea_id}",
    summary="Reverse lookup — the proposal (if any) that was lifted into this idea",
    description=(
        "Returns the proposal with its current tally so an idea page can "
        "render its origin: the whispers that became it. Returns 404 when "
        "the idea was not born from a proposal."
    ),
)
async def proposal_by_idea(idea_id: str) -> dict:
    p = proposal_service.get_proposal_by_idea(idea_id)
    if not p:
        raise HTTPException(status_code=404, detail="no proposal lifted into this idea")
    return p


@router.post(
    "/proposals/{proposal_id}/resolve",
    summary="Lift a resonant proposal into a kinetic idea",
    description=(
        "When the tally reads 'resonant' and the proposal is unresolved, "
        "this seeds an idea from the proposal and records the link. "
        "Idempotent — calling again on an already-resolved proposal "
        "returns the existing idea id without reseeding."
    ),
)
async def resolve(proposal_id: str) -> dict:
    try:
        return proposal_service.resolve_into_idea(proposal_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
