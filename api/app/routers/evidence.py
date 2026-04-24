"""Evidence router — implementation evidence for asset CC-multiplier bonus.

Endpoints:
  POST /api/evidence                          - Submit evidence for an asset
  POST /api/evidence/{evidence_id}/verify     - Run 2-of-3 factor verification
  GET  /api/evidence/{evidence_id}            - Fetch one submission
  GET  /api/evidence/asset/{asset_id}         - List submissions + verifications

See specs/story-protocol-integration.md (R9).
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException
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
    result = evidence_service.run_verification(evidence_id)
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
        submissions=evidence_service.list_evidence_for_asset(asset_id),
        verifications=evidence_service.list_verifications_for_asset(asset_id),
        cc_multiplier_applicable=str(multiplier),
    )
