"""Beliefs router — per-contributor worldview, interests, and concept preferences.

Implements: spec-169 (belief-system-interface)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.belief import (
    BeliefPatch,
    BeliefProfile,
    BeliefROI,
    ResonanceResult,
)
from app.services import belief_service

router = APIRouter()


@router.get(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Get contributor belief profile",
    tags=["beliefs"],
    responses={404: {"description": "Contributor not found"}},
)
def get_beliefs(contributor_id: str) -> BeliefProfile:
    """Return the full belief profile for a contributor."""
    return belief_service.get_belief_profile(contributor_id)


@router.patch(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Update contributor belief profile",
    tags=["beliefs"],
    responses={
        404: {"description": "Contributor not found"},
        422: {"description": "Validation error"},
    },
)
def patch_beliefs(contributor_id: str, patch: BeliefPatch) -> BeliefProfile:
    """Partially update a contributor's belief profile.

    By default (replace=false) list fields (interest_tags, concept_resonances) are
    appended to, not replaced. Set replace=true to overwrite.
    """
    return belief_service.patch_belief_profile(contributor_id, patch)


@router.get(
    "/contributors/{contributor_id}/beliefs/resonance",
    response_model=ResonanceResult,
    summary="Compute resonance between contributor beliefs and an idea",
    tags=["beliefs"],
    responses={
        404: {"description": "Contributor or idea not found"},
        422: {"description": "idea_id is required"},
    },
)
def get_resonance(
    contributor_id: str,
    idea_id: str = Query(None, description="ID of the idea to match against"),
) -> ResonanceResult:
    """Return a resonance score (0.0–1.0) and breakdown for a contributor × idea pair."""
    if not idea_id:
        raise HTTPException(status_code=422, detail="idea_id is required")
    return belief_service.compute_resonance(contributor_id, idea_id)


@router.get(
    "/beliefs/roi",
    response_model=BeliefROI,
    summary="Belief system network stats",
    tags=["beliefs"],
)
def get_beliefs_roi() -> BeliefROI:
    """Return aggregate belief system stats across the network."""
    return belief_service.get_roi()
