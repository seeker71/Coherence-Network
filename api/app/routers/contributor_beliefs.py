"""Contributor belief profile and idea resonance routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.belief import BeliefProfile, BeliefProfileUpdate, BeliefResonanceResponse
from app.models.error import ErrorDetail
from app.services import belief_service

router = APIRouter()


@router.get(
    "/contributors/{contributor_id}/beliefs/resonance",
    response_model=BeliefResonanceResponse,
    summary="Resonance between contributor beliefs and an idea",
    responses={404: {"model": ErrorDetail, "description": "Contributor or idea not found"}},
)
def get_belief_resonance(
    contributor_id: str,
    idea_id: str = Query(..., min_length=1, description="Idea id to compare against"),
) -> BeliefResonanceResponse:
    result = belief_service.compute_resonance(contributor_id, idea_id)
    if not result:
        raise HTTPException(status_code=404, detail="Contributor or idea not found")
    return result


@router.get(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Get contributor belief profile",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def get_contributor_beliefs(contributor_id: str) -> BeliefProfile:
    profile = belief_service.get_beliefs(contributor_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return profile


@router.patch(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Update contributor belief preferences",
    responses={404: {"model": ErrorDetail, "description": "Contributor not found"}},
)
def patch_contributor_beliefs(contributor_id: str, body: BeliefProfileUpdate) -> BeliefProfile:
    updated = belief_service.patch_beliefs(contributor_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return updated
