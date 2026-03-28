"""Cross-Domain Concept Resonance (CDCR) — Pydantic models + ORM.

Spec 179: ideas attract related ideas across domains via structural similarity
in the graph. Two ideas resonate when they solve analogous problems in
different domains.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from sqlalchemy import Column, DateTime, Float, Index, String, Text, func
from sqlalchemy import JSON as _JSON

try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = _JSON  # type: ignore[misc,assignment]

import os as _os

_PortableJSON = JSONB if "postgresql" in _os.environ.get("DATABASE_URL", "") else _JSON

from sqlalchemy.orm import Mapped, mapped_column

from app.services.unified_db import Base


# ── Enums ──────────────────────────────────────────────────────────────────


class ScanMode(str, Enum):
    FULL = "full"
    SEED = "seed"
    INCREMENTAL = "incremental"


class ScanStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# ── ORM Model ──────────────────────────────────────────────────────────────


class CrossDomainResonance(Base):
    """Persisted cross-domain resonance pair.

    Records two nodes that were found to be structurally similar across
    different ontology domains, plus scoring breakdown and the resulting
    graph edge.
    """
    __tablename__ = "cross_domain_resonances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    node_a_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_b_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain_a: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    domain_b: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")

    # Score breakdown
    resonance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    structural_sim: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    depth2_sim: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    crk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    domain_bonus: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metadata
    edge_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scan_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scan_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="incremental")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="cdcr")

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_cdcr_score", "resonance_score"),
        Index("ix_cdcr_domains", "domain_a", "domain_b"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "domain_a": self.domain_a,
            "domain_b": self.domain_b,
            "resonance_score": self.resonance_score,
            "score_breakdown": {
                "structural_sim": self.structural_sim,
                "depth2_sim": self.depth2_sim,
                "crk_score": self.crk_score,
                "domain_bonus": self.domain_bonus,
            },
            "edge_id": self.edge_id,
            "scan_id": self.scan_id,
            "scan_mode": self.scan_mode,
            "source": self.source,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


# ── Scan ORM Model ─────────────────────────────────────────────────────────


class ResonanceScan(Base):
    """Scan job lifecycle record."""
    __tablename__ = "resonance_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:12])
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="incremental")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    seed_node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nodes_scanned: Mapped[int] = mapped_column(nullable=False, default=0)
    resonances_found: Mapped[int] = mapped_column(nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "status": self.status,
            "seed_node_id": self.seed_node_id,
            "nodes_scanned": self.nodes_scanned,
            "resonances_found": self.resonances_found,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Pydantic Response Models ───────────────────────────────────────────────


class NodeSummary(BaseModel):
    id: str
    name: str
    domain: str


class ScoreBreakdown(BaseModel):
    structural_sim: float = Field(ge=0.0, le=1.0)
    depth2_sim: float = Field(ge=0.0, le=1.0)
    crk_score: float = Field(ge=0.0, le=1.0)
    domain_bonus: float = Field(ge=0.0, le=1.0)


class CrossDomainResonanceItem(BaseModel):
    id: str
    node_a_id: str
    node_b_id: str
    domain_a: str
    domain_b: str
    resonance_score: float = Field(ge=0.0, le=1.0)
    score_breakdown: ScoreBreakdown
    edge_id: str | None = None
    scan_id: str | None = None
    scan_mode: str
    source: str
    discovered_at: str


class CrossDomainResonanceList(BaseModel):
    items: list[CrossDomainResonanceItem]
    total: int
    limit: int
    offset: int


class ScanRequest(BaseModel):
    mode: ScanMode = ScanMode.INCREMENTAL
    seed_node_id: str | None = Field(
        None,
        description="Required for mode=seed. Node ID to use as scan origin.",
    )


class ScanResponse(BaseModel):
    scan_id: str
    mode: str
    status: str
    message: str


class ScanStatusResponse(BaseModel):
    id: str
    mode: str
    status: str
    seed_node_id: str | None
    nodes_scanned: int
    resonances_found: int
    error: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class ProofResponse(BaseModel):
    total_resonances: int
    unique_domain_pairs: int
    average_score: float
    top_resonances: list[CrossDomainResonanceItem]
    domain_pair_counts: dict[str, int]
    organic_growth_rate: float
    proof_status: str  # "active" | "stale" | "empty"
