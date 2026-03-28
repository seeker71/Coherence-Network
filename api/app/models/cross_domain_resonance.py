"""Cross-Domain Concept Resonance (CDCR) Pydantic models — Spec 179.

Pydantic response/request models for the CDCR API.
ORM models live in app.services.cross_domain_resonance_service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeSummary(BaseModel):
    """Lightweight node reference embedded in a resonance item."""
    id: str
    name: str
    domain: str


class CrossDomainResonanceItem(BaseModel):
    """A single discovered cross-domain resonance pair."""
    id: str
    node_a: NodeSummary
    node_b: NodeSummary
    domain_a: str
    domain_b: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    structural_sim: float = Field(ge=0.0, le=1.0)
    depth2_sim: float = Field(ge=0.0, le=1.0)
    crk_score: float = Field(ge=0.0, le=1.0)
    edge_id: Optional[str] = None
    discovered_at: datetime
    last_confirmed: datetime
    scan_mode: str
    source: str = "cdcr"


class CrossDomainResonanceList(BaseModel):
    """Paginated list of cross-domain resonances."""
    items: list[CrossDomainResonanceItem]
    total: int
    limit: int
    offset: int


class ScanRequest(BaseModel):
    """Request body for POST /api/resonance/cross-domain/scan."""
    mode: str = Field(
        default="incremental",
        description="Scan mode: full | seed | incremental",
        pattern="^(full|seed|incremental)$",
    )
    seed_node_id: Optional[str] = Field(
        None,
        description="Required for mode=seed. Node ID to use as scan origin.",
    )


class ScanResponse(BaseModel):
    """Response for POST /api/resonance/cross-domain/scan (202 Accepted)."""
    scan_id: str
    mode: str
    seed_node_id: Optional[str] = None
    status: str
    message: str


class ScanStatus(BaseModel):
    """Scan job status (GET /api/resonance/cross-domain/scans/{scan_id})."""
    scan_id: str
    status: str
    mode: str
    nodes_evaluated: int = 0
    pairs_compared: int = 0
    resonances_found: int = 0
    resonances_created: int = 0
    resonances_updated: int = 0
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DomainPairCount(BaseModel):
    domain_a: str
    domain_b: str
    count: int


class DiscoveryEntry(BaseModel):
    date: str
    new_resonances: int


class TopResonanceEntry(BaseModel):
    node_a: str
    node_b: str
    score: float
    domain_pair: str


class ProofResponse(BaseModel):
    """Aggregate proof that organic resonance discovery is active — Spec 179."""
    total_resonances: int
    total_analogous_to_edges: int
    analogous_to_edges_from_cdcr: int
    domain_pairs_covered: list[dict[str, Any]]
    discovery_timeline: list[dict[str, Any]]
    top_resonances: list[dict[str, Any]]
    avg_score: float
    nodes_with_cross_domain_bridge: int
    organic_growth_rate: float
    proof_status: str  # "active" | "stale"
