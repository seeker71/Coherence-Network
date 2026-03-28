"""Contributor belief profile — GET/PATCH /beliefs, resonance vs ideas."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.belief import BeliefProfile, BeliefProfileUpdate, BeliefResonanceResponse
from app.models.error import ErrorDetail
from app.services import belief_service

router = APIRouter()


@router.get(
    "/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Get contributor belief profile",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_beliefs(contributor_id: str) -> BeliefProfile:
    prof = belief_service.get_belief_profile(contributor_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return prof


@router.patch(
    "/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Update contributor belief preferences",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def patch_contributor_beliefs(contributor_id: str, body: BeliefProfileUpdate) -> BeliefProfile:
    prof = belief_service.patch_belief_profile(contributor_id, body)
    if not prof:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return prof


@router.get(
    "/{contributor_id}/beliefs/resonance",
    response_model=BeliefResonanceResponse,
    summary="Belief alignment with an idea",
    responses={404: {"model": ErrorDetail, "description": "Contributor or idea not found"}},
)
def get_belief_resonance(
    contributor_id: str,
    idea_id: str = Query(..., min_length=1, description="Idea id to compare against"),
) -> BeliefResonanceResponse:
    out = belief_service.compute_resonance(contributor_id, idea_id)
    if not out:
        raise HTTPException(status_code=404, detail="Contributor or idea not found")
    return out
