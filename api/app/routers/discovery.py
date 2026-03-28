"""Tunable resonance discovery API (spec 166)."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.resonance_navigation import ResonanceDiscoveryRequest, ResonanceDiscoveryResponse
from app.services import resonance_navigation_service

router = APIRouter()


@router.post("/discovery/resonance", response_model=ResonanceDiscoveryResponse)
async def post_resonance_discovery(body: ResonanceDiscoveryRequest) -> ResonanceDiscoveryResponse:
    """Rank ideas by alignment with a resonance vector over curiosity, serendipity, depth, coherence, and recency."""
    return resonance_navigation_service.discover(body)
