"""Evidence service — submission, verification, and retrieval for asset implementation evidence.

Per specs/story-protocol-integration.md R9. Delegates the actual
verification math to `story_protocol_bridge.verify_evidence()` (the
2-of-3 factor rule with haversine GPS radius and attestation
threshold). This layer wraps it with storage, asset-id linkage, and
known-community-coordinate context.

Storage is in-process for this first slice, matching the pattern of
other route-level slices landing against story-protocol. Graph-
backed persistence is a follow-up.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from app.models.evidence import (
    EvidenceCreate,
    EvidenceVerification,
    ImplementationEvidence,
)
from app.services.story_protocol_bridge import (
    GpsCoordinate,
    ImplementationEvidenceInput,
    verify_evidence as _verify_evidence_raw,
)


# In-process stores, keyed by asset id.
_EVIDENCE: Dict[str, List[ImplementationEvidence]] = defaultdict(list)
_VERIFICATIONS: Dict[UUID, EvidenceVerification] = {}

# Known community coordinates used for GPS-within-radius checks.
# In production this list is read from the graph; for this slice it's
# a small in-process seed that can be extended at runtime via
# register_community_location().
_KNOWN_COMMUNITIES: List[GpsCoordinate] = []


def register_community_location(lat: float, lng: float) -> None:
    """Add a known community coordinate for GPS-based evidence verification."""
    _KNOWN_COMMUNITIES.append(GpsCoordinate(lat=lat, lng=lng))


def submit_evidence(body: EvidenceCreate) -> ImplementationEvidence:
    """Store an evidence submission. Does not verify — that's a separate
    step so the submission can be inspected before verification runs.
    """
    evidence = ImplementationEvidence(**body.model_dump())
    _EVIDENCE[body.asset_id].append(evidence)
    return evidence


def run_verification(evidence_id: UUID) -> Optional[EvidenceVerification]:
    """Run 2-of-3 factor verification on a stored evidence record.

    Returns None if the evidence_id is not found. Otherwise stores
    and returns the verification result.
    """
    record = _find(evidence_id)
    if record is None:
        return None
    factors = ImplementationEvidenceInput(
        photo_urls=record.photo_urls,
        gps=record.gps,
        attestation_count=record.attestation_count,
    )
    raw = _verify_evidence_raw(factors, known_community_coords=_KNOWN_COMMUNITIES)
    result = EvidenceVerification(
        evidence_id=record.id,
        asset_id=record.asset_id,
        verified=raw.verified,
        factors_satisfied=raw.factors_satisfied,
        factors_required=raw.factors_required,
        has_photo_proof=raw.has_photo_proof,
        gps_within_radius=raw.gps_within_radius,
        attestation_met=raw.attestation_met,
        cc_multiplier_applicable=str(raw.cc_multiplier_applicable),
    )
    _VERIFICATIONS[record.id] = result
    return result


def get_evidence(evidence_id: UUID) -> Optional[ImplementationEvidence]:
    return _find(evidence_id)


def get_verification(evidence_id: UUID) -> Optional[EvidenceVerification]:
    return _VERIFICATIONS.get(evidence_id)


def list_evidence_for_asset(asset_id: str) -> List[ImplementationEvidence]:
    return list(_EVIDENCE.get(asset_id, []))


def list_verifications_for_asset(asset_id: str) -> List[EvidenceVerification]:
    return [v for v in _VERIFICATIONS.values() if v.asset_id == asset_id]


def applicable_multiplier_for_asset(asset_id: str) -> Decimal:
    """Highest multiplier among verified evidence for this asset.

    If no verified evidence exists, returns 1.0 (no multiplier).
    Used by the settlement batch to apply the 5× bonus per R9.
    """
    verifications = list_verifications_for_asset(asset_id)
    verified = [v for v in verifications if v.verified]
    if not verified:
        return Decimal("1")
    return max(Decimal(v.cc_multiplier_applicable) for v in verified)


def _find(evidence_id: UUID) -> Optional[ImplementationEvidence]:
    for records in _EVIDENCE.values():
        for r in records:
            if r.id == evidence_id:
                return r
    return None


def _reset_for_tests() -> None:
    """Testing hook. Not part of the public API."""
    _EVIDENCE.clear()
    _VERIFICATIONS.clear()
    _KNOWN_COMMUNITIES.clear()
