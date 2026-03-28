"""Marketplace router: OpenClaw Idea Marketplace endpoints (spec 121)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.models.marketplace import (
    AuthorReputation,
    BrowseResponse,
    ForkRequest,
    MarketplaceFork,
    MarketplaceListing,
    MarketplaceManifest,
    PublishRequest,
)
from app.services import marketplace_service

router = APIRouter()


@router.post(
    "/marketplace/publish",
    status_code=201,
    summary="Publish an idea to the marketplace",
    tags=["marketplace"],
)
def publish_idea(body: PublishRequest):
    """Publish a local idea to the cross-instance marketplace.

    - Returns 201 with listing on success.
    - Returns 404 if idea_id does not exist.
    - Returns 409 if a listing with the same content hash already exists.
    - Returns 422 if the idea fails the quality gate (confidence < 0.3 or no value_basis).
    """
    result, status, extra = marketplace_service.publish_idea(
        idea_id=body.idea_id,
        tags=body.tags,
        author_display_name=body.author_display_name,
        visibility=body.visibility,
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Idea not found")

    if status == "quality_gate":
        # result is a list of error dicts
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Idea does not meet marketplace quality gate",
                "errors": result,
            },
        )

    if status == "duplicate":
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Duplicate listing exists",
                "existing_listing_id": extra,
            },
        )

    return JSONResponse(
        status_code=201,
        content=result.model_dump(mode="json"),
    )


@router.get(
    "/marketplace/browse",
    response_model=BrowseResponse,
    summary="Browse marketplace listings",
    tags=["marketplace"],
)
def browse_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tags: Optional[str] = Query(default=None, description="Comma-separated tag filter"),
    sort: str = Query(default="recent", pattern="^(recent|popular|value)$"),
    search: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
):
    """Browse published marketplace listings with pagination, filtering, and sorting."""
    return marketplace_service.browse_listings(
        page=page,
        page_size=page_size,
        tags=tags,
        sort=sort,
        search=search,
        min_confidence=min_confidence,
    )


@router.post(
    "/marketplace/fork/{listing_id}",
    status_code=201,
    summary="Fork a marketplace listing",
    tags=["marketplace"],
)
def fork_listing(listing_id: str, body: ForkRequest):
    """Fork a published idea into the local instance.

    Creates a local copy of the idea linked to the original listing.
    Records a value lineage link with origin_author role (10% weight).
    - Returns 201 with fork details on success.
    - Returns 404 if the listing_id does not exist.
    """
    fork, status = marketplace_service.fork_listing(
        listing_id=listing_id,
        forker_id=body.forker_id,
        notes=body.notes,
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Marketplace listing not found")

    return JSONResponse(
        status_code=201,
        content=fork.model_dump(mode="json"),
    )


@router.get(
    "/marketplace/authors/{author_id}/reputation",
    response_model=AuthorReputation,
    summary="Get author reputation score",
    tags=["marketplace"],
)
def get_author_reputation(author_id: str):
    """Compute and return the reputation score for a marketplace author.

    Reputation = sum(adoption_value_cc * confidence) / (1 + age_penalty)
    across all published ideas.
    """
    reputation = marketplace_service.get_author_reputation(author_id)
    if reputation is None:
        raise HTTPException(status_code=404, detail="Author not found")
    return reputation


@router.get(
    "/marketplace/manifest",
    response_model=MarketplaceManifest,
    summary="OpenClaw plugin manifest",
    tags=["marketplace"],
)
def get_manifest():
    """Return the OpenClaw plugin manifest for Coherence Network marketplace integration."""
    return MarketplaceManifest()
