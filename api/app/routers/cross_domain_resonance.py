"""Cross-domain concept resonance API — ideas that structurally align across domains."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.cross_domain_resonance import CrossDomainResonanceList, ProofResponse
from app.services import cross_domain_resonance_service
from app.services import graph_service

router = APIRouter()


@router.get("/resonance/status")
async def get_resonance_status():
    proof = cross_domain_resonance_service.get_proof_summary()
    return {
        "status": "active",
        "kernel": "structural-resonance",
        "total_cross_domain_pairs": proof.total_resonances,
        "proof_status": proof.proof_status,
    }


@router.get("/resonance/cross-domain", response_model=CrossDomainResonanceList)
async def list_cross_domain(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0.12, ge=0.0, le=1.0),
):
    """List idea pairs from different domains with analogous graph structure (not keyword match)."""
    return cross_domain_resonance_service.list_cross_domain_resonances(
        limit=limit,
        offset=offset,
        min_score=min_score,
    )


@router.get("/resonance/cross-domain/proof", response_model=ProofResponse)
async def cross_domain_proof():
    """Aggregate stats proving resonance discovery is computable on the live graph."""
    return cross_domain_resonance_service.get_proof_summary()


@router.get("/resonance/cross-domain/ideas/{idea_id}", response_model=CrossDomainResonanceList)
async def resonances_for_idea(
    idea_id: str,
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(0.12, ge=0.0, le=1.0),
):
    """Resonant cross-domain ideas for one idea node."""
    n = graph_service.get_node(idea_id)
    if not n:
        raise HTTPException(status_code=404, detail="idea not found")
    if n.get("type") != "idea":
        raise HTTPException(status_code=400, detail="node is not an idea")
    return cross_domain_resonance_service.resonances_for_idea(
        idea_id, limit=limit, min_score=min_score
    )
