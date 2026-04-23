"""Peers router — contributor discovery via resonance and proximity."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

from app.services import graph_service, belief_service, geolocation_service
from app.services.peer_resonance_service import compute_peer_resonance

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
            score = compute_peer_resonance(source_profile, peer_profile)
            
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
