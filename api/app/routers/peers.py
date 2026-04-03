"""Peers router — contributor discovery via resonance and proximity."""

from __future__ import annotations

import math
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.models.contributor import Contributor
from app.models.belief import BeliefProfile
from app.services import graph_service, belief_service, geolocation_service

router = APIRouter()

class PeerMatch(BaseModel):
    contributor_id: str
    name: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    shared_tags: List[str] = Field(default_factory=list)
    distance_km: Optional[float] = None
    city: Optional[str] = None

class PeerDiscoveryResponse(BaseModel):
    peers: List[PeerMatch]
    total: int

def _compute_peer_resonance(profile_a: BeliefProfile, profile_b: BeliefProfile) -> float:
    """Compute structural resonance score between two contributor profiles."""
    # 1. Tag overlap (Jaccard)
    tags_a = set(profile_a.interest_tags)
    tags_b = set(profile_b.interest_tags)
    tag_score = 0.5
    if tags_a or tags_b:
        union = tags_a | tags_b
        intersection = tags_a & tags_b
        tag_score = len(intersection) / len(union) if union else 0.5

    # 2. Worldview alignment (Dot product)
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    axes = ["scientific", "spiritual", "pragmatic", "holistic", "relational", "systemic"]
    for axis in axes:
        va = profile_a.worldview_axes.get(axis, 0.0)
        vb = profile_b.worldview_axes.get(axis, 0.0)
        dot += va * vb
        norm_a += va * va
        norm_b += vb * vb
    
    denom = (norm_a ** 0.5) * (norm_b ** 0.5)
    worldview_score = dot / denom if denom > 0 else 0.5

    # 3. Concept resonance overlap
    concepts_a = {r.concept_id: r.weight for r in profile_a.concept_resonances}
    concepts_b = {r.concept_id: r.weight for r in profile_b.concept_resonances}
    concept_score = 0.5
    if concepts_a and concepts_b:
        shared = set(concepts_a.keys()) & set(concepts_b.keys())
        if shared:
            weighted_intersection = sum(min(concepts_a[c], concepts_b[c]) for c in shared)
            weighted_union = sum(max(concepts_a.get(c, 0), concepts_b.get(c, 0)) for c in (set(concepts_a.keys()) | set(concepts_b.keys())))
            concept_score = weighted_intersection / weighted_union if weighted_union > 0 else 0.0
        else:
            concept_score = 0.0

    # Final weighted average
    return round((tag_score * 0.2) + (worldview_score * 0.4) + (concept_score * 0.4), 4)

@router.get(
    "/peers/resonant",
    response_model=PeerDiscoveryResponse,
    summary="Find contributors with similar interests (resonance)",
)
async def get_resonant_peers(
    contributor_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> PeerDiscoveryResponse:
    """Return contributors ranked by structural resonance with the given contributor."""
    try:
        source_profile = belief_service.get_belief_profile(contributor_id)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Source contributor not found")

    # Fetch all contributors
    result = graph_service.list_nodes(type="contributor", limit=500)
    nodes = result.get("items") or []
    
    matches = []
    for node in nodes:
        cid = node["id"].removeprefix("contributor:")
        if cid == contributor_id:
            continue
        
        try:
            peer_profile = belief_service._node_to_belief_profile(node)
            score = _compute_peer_resonance(source_profile, peer_profile)
            
            if score > 0.1:  # Only include if there's some resonance
                shared_tags = list(set(source_profile.interest_tags) & set(peer_profile.interest_tags))
                matches.append(PeerMatch(
                    contributor_id=cid,
                    name=node.get("name", cid),
                    resonance_score=score,
                    shared_tags=shared_tags
                ))
        except Exception:
            continue

    # Sort by score desc
    matches.sort(key=lambda x: x.resonance_score, reverse=True)
    return PeerDiscoveryResponse(peers=matches[:limit], total=len(matches))

@router.get(
    "/peers/nearby",
    response_model=PeerDiscoveryResponse,
    summary="Find nearby contributors",
)
async def get_nearby_peers(
    contributor_id: str,
    radius_km: float = Query(100.0, gt=0),
    limit: int = Query(20, ge=1, le=100),
) -> PeerDiscoveryResponse:
    """Find peers physically close to the given contributor."""
    loc = geolocation_service.get_contributor_location(contributor_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Source contributor has no location set")

    nearby_data = geolocation_service.find_nearby(
        lat=loc.latitude, lon=loc.longitude, radius_km=radius_km, limit=limit
    )
    
    peers = []
    for c in nearby_data.contributors:
        if c.contributor_id == contributor_id:
            continue
        peers.append(PeerMatch(
            contributor_id=c.contributor_id,
            name=c.name or c.contributor_id,
            resonance_score=0.0, # Not computed for nearby search
            distance_km=c.distance_km,
            city=c.city
        ))
        
    return PeerDiscoveryResponse(peers=peers, total=len(peers))
