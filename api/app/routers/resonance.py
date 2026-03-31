"""Resonance router — structural cross-domain concept attraction endpoints.

Exposes the Concept Resonance Kernel (CRK) over the idea graph.
Unlike the /ideas/{id}/concept-resonance endpoint (keyword overlap),
these endpoints use harmonic structural similarity to surface connections
between ideas from different domains that solve analogous problems.

Endpoints:
    GET /api/resonance/cross-domain      — top cross-domain pairs (CRK-ranked)
    GET /api/resonance/ideas/{idea_id}   — CRK-ranked resonances for one idea
    GET /api/resonance/proof             — evidence log that resonance is working
    GET /api/resonance/events            — raw resonance discovery event log
    POST /api/resonance/scan             — trigger a full cross-domain scan
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.services import idea_service
from app.services import idea_resonance_service as resonance_svc

router = APIRouter()


# ── Response models ───────────────────────────────────────────────────────────

class ResonancePairOut(BaseModel):
    idea_id_a: str
    name_a: str
    domain_a: list[str]
    idea_id_b: str
    name_b: str
    domain_b: list[str]
    crk_score: float = Field(ge=0.0, le=1.0)
    ot_distance: float = Field(ge=0.0)
    coherence: float = Field(ge=0.0, le=1.0)
    d_codex: float = Field(ge=0.0, le=1.0)
    cross_domain: bool
    strong: bool
    discovered_at: str


class ResonanceForIdeaResponse(BaseModel):
    idea_id: str
    name: str
    domain: list[str]
    matches: list[ResonancePairOut]
    total: int
    algorithm: str = "CRK+OT-phi"


class CrossDomainResponse(BaseModel):
    pairs: list[ResonancePairOut]
    total: int
    min_coherence_used: float
    algorithm: str = "CRK+OT-phi"


class ResonanceProofOut(BaseModel):
    total_pairs_discovered: int
    cross_domain_pairs: int
    strong_pairs: int
    latest_discovery: Optional[str]
    top_pairs: list[ResonancePairOut]
    domain_bridge_count: dict[str, int]
    avg_coherence: float
    proof_quality: str
    interpretation: str


class ScanResult(BaseModel):
    pairs_found: int
    cross_domain_pairs: int
    ideas_scanned: int
    duration_ms: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _idea_to_dict(idea) -> dict:
    """Convert Idea model or dict to plain dict for the resonance service."""
    if isinstance(idea, dict):
        return idea
    return {
        "id": idea.id,
        "name": idea.name,
        "description": idea.description,
        "tags": getattr(idea, "tags", []) or [],
        "interfaces": getattr(idea, "interfaces", []) or [],
    }


def _pair_to_out(pair: "resonance_svc.ResonancePair") -> ResonancePairOut:
    return ResonancePairOut(
        idea_id_a=pair.idea_id_a,
        name_a=pair.name_a,
        domain_a=pair.domain_a,
        idea_id_b=pair.idea_id_b,
        name_b=pair.name_b,
        domain_b=pair.domain_b,
        crk_score=pair.crk_score,
        ot_distance=pair.ot_distance,
        coherence=pair.coherence,
        d_codex=pair.d_codex,
        cross_domain=pair.cross_domain,
        strong=pair.strong,
        discovered_at=pair.discovered_at,
    )


def _all_ideas_as_dicts() -> list[dict]:
    """Load all ideas as plain dicts (suitable for the resonance service)."""
    portfolio = idea_service.list_ideas(limit=500, offset=0, read_only_guard=True)
    return [_idea_to_dict(item) for item in (portfolio.ideas if hasattr(portfolio, "ideas") else [])]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/resonance/cross-domain", response_model=CrossDomainResponse)
async def get_cross_domain_resonances(
    limit: int = Query(20, ge=1, le=100, description="Max pairs to return"),
    min_coherence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum CRK coherence filter"),
) -> CrossDomainResponse:
    """Return top cross-domain idea pairs ranked by CRK coherence.

    Uses the Concept Resonance Kernel (harmonic structural similarity),
    NOT keyword matching. Two ideas resonate when they solve analogous
    problems in different domains — e.g. symbiosis ↔ microservices.

    Results are cached per-pair; first call may be slow for large portfolios.
    """
    all_ideas = _all_ideas_as_dicts()
    pairs = resonance_svc.get_cross_domain_pairs(
        all_ideas=all_ideas,
        limit=limit,
        min_coherence=min_coherence,
    )
    effective_min = max(min_coherence, resonance_svc.CROSS_DOMAIN_MIN_COHERENCE)
    return CrossDomainResponse(
        pairs=[_pair_to_out(p) for p in pairs],
        total=len(pairs),
        min_coherence_used=effective_min,
    )


@router.get("/resonance/ideas/{idea_id}", response_model=ResonanceForIdeaResponse)
async def get_resonance_for_idea(
    idea_id: str,
    limit: int = Query(10, ge=1, le=50),
    min_coherence: float = Query(0.0, ge=0.0, le=1.0),
    cross_domain_only: bool = Query(False, description="Return only cross-domain resonances"),
) -> ResonanceForIdeaResponse:
    """Return ideas that resonate structurally with the given idea.

    Uses CRK (Concept Resonance Kernel) — not keyword overlap.
    Cross-domain resonances are scored with a lower threshold to surface
    surprising connections between biology, software, physics, etc.
    """
    source_raw = idea_service.get_idea(idea_id)
    if source_raw is None:
        raise HTTPException(status_code=404, detail=f"Idea '{idea_id}' not found")

    source_dict = _idea_to_dict(source_raw)
    all_ideas = _all_ideas_as_dicts()

    matches = resonance_svc.find_resonant_ideas(
        source_idea=source_dict,
        all_ideas=all_ideas,
        limit=limit,
        min_coherence=min_coherence,
        cross_domain_only=cross_domain_only,
    )

    domain = resonance_svc._infer_domains(
        source_dict.get("tags", []),
        source_dict.get("interfaces", []),
    )

    return ResonanceForIdeaResponse(
        idea_id=idea_id,
        name=source_dict.get("name", idea_id),
        domain=domain,
        matches=[_pair_to_out(p) for p in matches],
        total=len(matches),
    )


@router.get("/resonance/proof", response_model=ResonanceProofOut)
async def get_resonance_proof() -> ResonanceProofOut:
    """Return evidence that structural cross-domain resonance is working.

    The proof accumulates over time as more pairs are discovered.
    Proof quality transitions: none → weak → emerging → strong.

    Use this endpoint to track whether the ontology is growing organically
    via resonance rather than manual curation.
    """
    all_ideas = _all_ideas_as_dicts()
    proof = resonance_svc.get_resonance_proof(all_ideas)

    interpretations = {
        "none":     "No cross-domain resonances discovered yet. Trigger a /resonance/scan to begin.",
        "weak":     f"{proof.cross_domain_pairs} cross-domain pair(s) found. Resonance is beginning.",
        "emerging": f"{proof.cross_domain_pairs} cross-domain pairs found. The ontology is growing organically.",
        "strong":   f"{proof.cross_domain_pairs} cross-domain pairs found across {len(proof.domain_bridge_count)} domains. "
                    f"Resonance is driving ontology growth.",
    }

    return ResonanceProofOut(
        total_pairs_discovered=proof.total_pairs_discovered,
        cross_domain_pairs=proof.cross_domain_pairs,
        strong_pairs=proof.strong_pairs,
        latest_discovery=proof.latest_discovery,
        top_pairs=[_pair_to_out(p) for p in proof.top_pairs],
        domain_bridge_count=proof.domain_bridge_count,
        avg_coherence=proof.avg_coherence,
        proof_quality=proof.proof_quality,
        interpretation=interpretations.get(proof.proof_quality, ""),
    )


@router.get("/resonance/events")
async def get_resonance_events(
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Return the resonance discovery event log (most recent first).

    Each event records when two ideas were first found to resonate structurally.
    This log is the primary evidence that the CRK is surfacing real connections.
    """
    return resonance_svc.get_event_log(limit=limit)


@router.post("/resonance/scan", response_model=ScanResult)
async def trigger_resonance_scan(
    min_coherence: float = Query(0.0, ge=0.0, le=1.0),
    max_ideas: int = Query(100, ge=1, le=500, description="Cap ideas to scan (prevents timeout)"),
) -> ScanResult:
    """Trigger a full cross-domain resonance scan of the idea portfolio.

    Scans all pairs up to max_ideas using the CRK algorithm. Results are cached
    so subsequent calls to /resonance/cross-domain will be fast.

    Warning: O(n²) complexity. For 100 ideas ≈ 5000 pairs ≈ 2-5 seconds.
    Use max_ideas to control duration.
    """
    import time

    all_ideas = _all_ideas_as_dicts()[:max_ideas]
    t0 = time.perf_counter()

    pairs = resonance_svc.get_cross_domain_pairs(
        all_ideas=all_ideas,
        limit=500,
        min_coherence=min_coherence,
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return ScanResult(
        pairs_found=len(pairs),
        cross_domain_pairs=sum(1 for p in pairs if p.cross_domain),
        ideas_scanned=len(all_ideas),
        duration_ms=elapsed_ms,
    )
