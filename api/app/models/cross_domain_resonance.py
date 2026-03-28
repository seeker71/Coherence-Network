"""Pydantic models for Cross-Domain Concept Resonance (CDCR) — Spec 179."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NodeSummary(BaseModel):
    id: str
    name: str
    domain: str


class CrossDomainResonanceItem(BaseModel):
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
    items: list[CrossDomainResonanceItem]
    total: int
    limit: int
    offset: int


class ScanRequest(BaseModel):
    seed_node_id: Optional[str] = None
    mode: str = "full"  # "full" | "seed" | "incremental"


class ScanResponse(BaseModel):
    scan_id: str
    mode: str
    seed_node_id: Optional[str] = None
    status: str
    message: str


class ScanStatus(BaseModel):
    scan_id: str
    status: str  # "queued" | "running" | "complete" | "failed"
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


class DiscoveryDay(BaseModel):
    date: str
    new_resonances: int


class TopResonance(BaseModel):
    node_a: str
    node_b: str
    score: float
    domain_pair: str


class ProofResponse(BaseModel):
    total_resonances: int
    total_analogous_to_edges: int
    analogous_to_edges_from_cdcr: int
    domain_pairs_covered: list[DomainPairCount]
    discovery_timeline: list[DiscoveryDay]
    top_resonances: list[TopResonance]
    avg_score: float
    nodes_with_cross_domain_bridge: int
    organic_growth_rate: float
    proof_status: str  # "active" | "stale"
