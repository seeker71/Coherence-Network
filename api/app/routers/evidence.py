"""Evidence router — implementation evidence for asset CC-multiplier bonus.

Endpoints:
  POST /api/evidence                          - Submit evidence for an asset
  GET  /api/evidence?asset_id=...             - List submissions, optionally per asset
  POST /api/evidence/{evidence_id}/verify     - Run 2-of-3 factor verification
  GET  /api/evidence/{evidence_id}            - Fetch one submission
  GET  /api/evidence/asset/{asset_id}         - Per-asset composite view (submissions + verifications + applicable multiplier)

See specs/story-protocol-integration.md (R9). The two handler names
the spec source: map claims for this file are `submit_evidence` and
`list_evidence`; both are defined below as the public router surface.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.evidence import (
    EvidenceCreate,
    EvidenceVerification,
    ImplementationEvidence,
)
from app.services import evidence_service

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceAssetView(BaseModel):
    asset_id: str
    submissions: List[ImplementationEvidence]
    verifications: List[EvidenceVerification]
    cc_multiplier_applicable: str


@router.post(
    "",
    response_model=ImplementationEvidence,
    status_code=201,
    summary="Submit implementation evidence for an asset",
)
async def submit_evidence(body: EvidenceCreate) -> ImplementationEvidence:
    """Store an evidence submission. Verification is a separate step —
    callers POST to /api/evidence/{id}/verify when ready.
    """
    return evidence_service.submit_evidence(body)


@router.get(
    "",
    response_model=List[ImplementationEvidence],
    summary="List evidence submissions, optionally filtered by asset",
)
async def list_evidence(
    asset_id: Optional[str] = Query(
        default=None,
        description="If set, restrict results to evidence for this asset.",
    ),
) -> List[ImplementationEvidence]:
    """Return every evidence submission, or — with ``asset_id`` set —
    just those for the named asset. Per spec R9 source: map.
    """
    return evidence_service.list_evidence(asset_id)


@router.post(
    "/{evidence_id}/verify",
    response_model=EvidenceVerification,
    summary="Run 2-of-3 factor verification on a submission",
)
async def verify_evidence(evidence_id: UUID) -> EvidenceVerification:
    """Runs the verification rule from story_protocol_bridge.
    Verified evidence applies a 5× CC multiplier via the
    applicable_multiplier_for_asset() lookup used by settlement.
    """
    result = evidence_service.verify_evidence(evidence_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"evidence '{evidence_id}' not found",
        )
    return result


@router.get(
    "/{evidence_id}",
    response_model=ImplementationEvidence,
    summary="Fetch an evidence submission",
)
async def get_evidence(evidence_id: UUID) -> ImplementationEvidence:
    record = evidence_service.get_evidence(evidence_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"evidence '{evidence_id}' not found",
        )
    return record


@router.get(
    "/asset/{asset_id:path}",
    response_model=EvidenceAssetView,
    summary="List evidence submissions and verifications for an asset",
)
async def list_for_asset(asset_id: str) -> EvidenceAssetView:
    """Returns every submission + every verification + the currently
    applicable CC multiplier (highest among verified evidence).
    """
    multiplier = evidence_service.applicable_multiplier_for_asset(asset_id)
    return EvidenceAssetView(
        asset_id=asset_id,
        submissions=evidence_service.list_evidence(asset_id),
        verifications=evidence_service.list_verifications_for_asset(asset_id),
        cc_multiplier_applicable=str(multiplier),
    )
