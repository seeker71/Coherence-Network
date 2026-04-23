"""Story Protocol Bridge — pure-logic pieces of the story-protocol-integration spec.

Covers the parts that don't require external systems (Story Protocol SDK,
Arweave/Irys/IPFS, x402 facilitator). These can be tested without
network mocks and land the core invariants cleanly:

  - Concept-weighted CC flow computation (R6)
  - Derivative royalty split math (R7)
  - Evidence verification threshold (R9)
  - Content integrity check via SHA-256 (R10)
  - x402 payment header formation (R4 header-formation half)

The on-chain registration, Arweave/IPFS upload, x402 payment verification,
and community attestation cryptography all need external-system integration
and belong in follow-up PRs with their own partner-selection or design
gates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


# ---------- Constants ----------

DEFAULT_PARENT_ROYALTY_SHARE_PCT = Decimal("15.0")
EVIDENCE_MIN_VERIFIED_FACTORS = 2
EVIDENCE_GPS_RADIUS_KM = 50.0
EVIDENCE_MIN_ATTESTATIONS = 3
EVIDENCE_CC_MULTIPLIER = Decimal("5.0")


# ---------- Concept-weighted CC flow (R6) ----------


class AssetConceptTag(BaseModel):
    concept_id: str
    weight: float = Field(ge=0.0, le=1.0)


class ReaderConceptResonance(BaseModel):
    """Reader's belief profile as concept-weight pairs."""
    weights: Dict[str, float] = Field(default_factory=dict)


def compute_concept_weighted_cc_flow(
    base_cc: Decimal,
    asset_tags: List[AssetConceptTag],
    reader_resonance: ReaderConceptResonance,
) -> Decimal:
    """CC flow to the creator is the sum over shared concepts of
       base_cc * asset_weight * reader_weight.

    Per spec R6: creators producing content aligned with what readers
    value earn proportionally more. Concepts the asset tags but the
    reader has no weight for contribute zero; concepts the reader
    values but the asset doesn't tag contribute zero.
    """
    if base_cc < 0:
        raise ValueError("base_cc must be non-negative")
    total = Decimal("0")
    for tag in asset_tags:
        reader_weight = reader_resonance.weights.get(tag.concept_id, 0.0)
        if reader_weight < 0 or reader_weight > 1:
            raise ValueError(
                f"reader weight for {tag.concept_id} out of [0,1]: {reader_weight}"
            )
        contribution = base_cc * Decimal(str(tag.weight)) * Decimal(str(reader_weight))
        total += contribution
    return total


# ---------- Derivative royalty split (R7) ----------


@dataclass(frozen=True)
class RoyaltySplit:
    """Split of a derivative work's CC earnings between parent and derivative."""

    parent_share_pct: Decimal
    derivative_share_pct: Decimal
    parent_cc: Decimal
    derivative_cc: Decimal


def compute_derivative_royalty(
    total_cc: Decimal,
    *,
    parent_share_pct: Decimal = DEFAULT_PARENT_ROYALTY_SHARE_PCT,
) -> RoyaltySplit:
    """Split CC between a derivative work and its parent.

    Default 15% to parent, 85% to derivative. The split is configurable
    per-derivative but must sum to 100%.
    """
    if parent_share_pct < 0 or parent_share_pct > 100:
        raise ValueError("parent_share_pct must be in [0, 100]")
    if total_cc < 0:
        raise ValueError("total_cc must be non-negative")
    derivative_share_pct = Decimal("100") - parent_share_pct
    parent_cc = total_cc * parent_share_pct / Decimal("100")
    derivative_cc = total_cc * derivative_share_pct / Decimal("100")
    return RoyaltySplit(
        parent_share_pct=parent_share_pct,
        derivative_share_pct=derivative_share_pct,
        parent_cc=parent_cc,
        derivative_cc=derivative_cc,
    )


# ---------- Evidence verification (R9) ----------


class GpsCoordinate(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class ImplementationEvidenceInput(BaseModel):
    photo_urls: List[str] = Field(default_factory=list)
    gps: Optional[GpsCoordinate] = None
    attestation_count: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class EvidenceVerificationResult:
    verified: bool
    factors_satisfied: int
    factors_required: int
    has_photo_proof: bool
    gps_within_radius: bool
    attestation_met: bool
    cc_multiplier_applicable: Decimal


def _haversine_km(a: GpsCoordinate, b: GpsCoordinate) -> float:
    """Great-circle distance between two lat/lng points in kilometers."""
    from math import asin, cos, radians, sin, sqrt

    lat1, lng1 = radians(a.lat), radians(a.lng)
    lat2, lng2 = radians(b.lat), radians(b.lng)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def verify_evidence(
    evidence: ImplementationEvidenceInput,
    *,
    known_community_coords: Optional[List[GpsCoordinate]] = None,
    radius_km: float = EVIDENCE_GPS_RADIUS_KM,
    min_attestations: int = EVIDENCE_MIN_ATTESTATIONS,
    min_factors: int = EVIDENCE_MIN_VERIFIED_FACTORS,
) -> EvidenceVerificationResult:
    """Verify implementation evidence per spec R9.

    Requires at least `min_factors` (default 2) of three:
      1. photo proof (any non-empty URL list)
      2. GPS within `radius_km` (default 50km) of a known community
      3. attestation count >= `min_attestations` (default 3)

    Returns a verification result. A verified result carries
    EVIDENCE_CC_MULTIPLIER (5x) applicable to the asset's next
    settlement period.
    """
    has_photo = len(evidence.photo_urls) > 0

    gps_ok = False
    if evidence.gps is not None and known_community_coords:
        for community in known_community_coords:
            if _haversine_km(evidence.gps, community) <= radius_km:
                gps_ok = True
                break

    attestation_ok = evidence.attestation_count >= min_attestations

    factors = int(has_photo) + int(gps_ok) + int(attestation_ok)
    verified = factors >= min_factors

    return EvidenceVerificationResult(
        verified=verified,
        factors_satisfied=factors,
        factors_required=min_factors,
        has_photo_proof=has_photo,
        gps_within_radius=gps_ok,
        attestation_met=attestation_ok,
        cc_multiplier_applicable=EVIDENCE_CC_MULTIPLIER if verified else Decimal("1"),
    )


# ---------- Content integrity (R10) ----------


@dataclass(frozen=True)
class ContentIntegrityResult:
    ok: bool
    expected_hash: str
    actual_hash: str


def compute_content_hash(content: bytes) -> str:
    """Return the sha256 hex digest prefixed with 'sha256:'."""
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def verify_content_integrity(
    expected_hash: str,
    actual_content: bytes,
) -> ContentIntegrityResult:
    """Compare the stored content hash against a recomputed hash from
    the retrieved content. Used to detect tampering between local
    store, Arweave TX, and IPFS CID per spec R10.
    """
    actual = compute_content_hash(actual_content)
    return ContentIntegrityResult(
        ok=expected_hash == actual,
        expected_hash=expected_hash,
        actual_hash=actual,
    )


# ---------- x402 payment headers (R4) ----------


def build_x402_payment_required_headers(
    *,
    amount_cc: Decimal,
    payment_address: str,
    network: str = "base-l2",
) -> Dict[str, str]:
    """Build the HTTP headers for a 402 Payment Required response per
    the x402 spec. Returned as a plain dict that the router attaches
    to the response.
    """
    if amount_cc <= 0:
        raise ValueError("amount_cc must be positive")
    if not payment_address:
        raise ValueError("payment_address required")
    return {
        "X-Payment-Amount": str(amount_cc),
        "X-Payment-Currency": "CC",
        "X-Payment-Address": payment_address,
        "X-Payment-Network": network,
    }
