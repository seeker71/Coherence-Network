"""Evidence models — implementation evidence for assets, per story-protocol-integration R9.

Evidence submission carries photo proof, optional GPS, and an
attestation count. Verification uses the 2-of-3 factor rule from
`story_protocol_bridge.verify_evidence()`. Verified evidence applies
a 5x CC multiplier to the asset's next settlement period.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.services.story_protocol_bridge import GpsCoordinate


class EvidenceCreate(BaseModel):
    """Payload for POST /api/evidence."""

    asset_id: str = Field(description="asset:<uuid> identifier")
    submitter_id: str
    photo_urls: List[str] = Field(default_factory=list)
    gps: Optional[GpsCoordinate] = None
    attestation_count: int = Field(default=0, ge=0)
    description: str = ""


class ImplementationEvidence(EvidenceCreate):
    """Server-side evidence record."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceVerification(BaseModel):
    """Outcome of running verification on a submitted evidence record."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    asset_id: str
    verified: bool
    factors_satisfied: int
    factors_required: int
    has_photo_proof: bool
    gps_within_radius: bool
    attestation_met: bool
    cc_multiplier_applicable: str  # Decimal serialized as str to avoid JSON float loss
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
