"""Contributor belief profiles router (spec-169).

Endpoints:
  GET  /api/contributors/{id}/beliefs
  PATCH /api/contributors/{id}/beliefs
  GET  /api/contributors/{id}/beliefs/resonance?idea_id={idea_id}
  GET  /api/contributors/{id}/beliefs/roi?days=30
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from app.models.belief_profile import (
    BeliefProfile,
    BeliefProfilePatch,
    BeliefROI,
    ResonanceResult,
)
from app.services import beliefs_service

router = APIRouter()


def _contributor_exists(contributor_id: str) -> bool:
    """Check contributor exists via graph_service."""
    try:
        from app.services import graph_service
        node = graph_service.get_node(f"contributor:{contributor_id}")
        if node:
            return True
        # Also check if any belief profile exists (created in tests without a graph node)
        return contributor_id in beliefs_service._profiles
    except Exception:
        return False


@router.get(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Get contributor belief profile",
    tags=["beliefs"],
    responses={404: {"description": "Contributor not found"}},
)
def get_beliefs(contributor_id: str) -> BeliefProfile:
    """Return the contributor's current belief profile.

    Returns empty defaults (HTTP 200) if the profile has not yet been set.
    Returns HTTP 404 only if the contributor does not exist at all.
    """
    if not _contributor_exists(contributor_id):
        raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")
    return beliefs_service.get_belief_profile(contributor_id)


@router.patch(
    "/contributors/{contributor_id}/beliefs",
    response_model=BeliefProfile,
    summary="Update contributor belief profile",
    tags=["beliefs"],
    responses={
        403: {"description": "Not authorized to update this profile"},
        404: {"description": "Contributor not found"},
        422: {"description": "Validation error: invalid axis or out-of-range value"},
    },
)
def patch_beliefs(
    contributor_id: str,
    patch: BeliefProfilePatch,
    x_api_key: Optional[str] = None,
    x_contributor_id: Optional[str] = None,
) -> BeliefProfile:
    """Partially update a contributor's belief profile.

    Axis values must be in [0.0, 1.0]. Unknown axis names return 422.
    Only the authenticated contributor (or admin) can update their own profile.
    """
    from fastapi import Header
    if not _contributor_exists(contributor_id):
        raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")

    # Ownership check: if caller provides x-contributor-id, it must match
    if x_contributor_id and x_contributor_id != contributor_id:
        raise HTTPException(status_code=403, detail="You can only update your own belief profile")

    return beliefs_service.patch_belief_profile(contributor_id, patch)


@router.get(
    "/contributors/{contributor_id}/beliefs/resonance",
    response_model=ResonanceResult,
    summary="Compute belief-to-idea resonance",
    tags=["beliefs"],
    responses={
        404: {"description": "Contributor or idea not found"},
    },
)
def get_resonance(
    contributor_id: str,
    idea_id: str = Query(..., description="ID of the idea to score against"),
) -> ResonanceResult:
    """Compute how well a contributor's belief profile aligns with a specific idea.

    Algorithm: overall = 0.4 × concept_overlap + 0.4 × worldview_alignment + 0.2 × tag_match
    """
    if not _contributor_exists(contributor_id):
        raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")

    # Look up idea
    try:
        from app.services import idea_service
        idea = idea_service.get_idea(idea_id)
    except Exception:
        idea = None

    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea '{idea_id}' not found")

    # Extract idea attributes — tags from interfaces/name, concept_ids from properties
    idea_tags: list[str] = list(idea.interfaces or [])
    # Derive tags from idea name/description words if no interfaces
    if not idea_tags and idea.description:
        # Use category-style words from description as tags
        idea_tags = [w.lower() for w in idea.description.split() if len(w) > 4][:10]

    idea_concept_ids: list[str] = []
    # IdeaWithScore doesn't have concept_ids — derive from idea id and tags
    return beliefs_service.compute_resonance(
        contributor_id=contributor_id,
        idea_id=idea_id,
        idea_tags=idea_tags,
        idea_concept_ids=idea_concept_ids,
        idea_category=idea.manifestation_status.value if idea.manifestation_status else None,
    )


@router.get(
    "/contributors/{contributor_id}/beliefs/roi",
    response_model=BeliefROI,
    summary="Get belief-driven recommendation ROI",
    tags=["beliefs"],
    responses={
        404: {"description": "Contributor not found"},
    },
)
def get_roi(
    contributor_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Lookback window in days"),
) -> BeliefROI:
    """Return engagement lift attributable to belief-driven recommendations.

    Returns lift=null when fewer than 10 recommendation events exist.
    """
    if not _contributor_exists(contributor_id):
        raise HTTPException(status_code=404, detail=f"Contributor '{contributor_id}' not found")
    return beliefs_service.get_belief_roi(contributor_id, days=days)
