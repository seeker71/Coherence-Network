"""Creator resonance report routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.creator_resonance import (
    CreatorResonanceReport,
    CreatorResonanceReportRequest,
)
from app.services import creator_resonance_service

router = APIRouter(prefix="/creator-economy", tags=["creator-economy"])


@router.post(
    "/resonance-report",
    response_model=CreatorResonanceReport,
    summary="Build a creator resonance report from platform snapshots",
)
async def create_creator_resonance_report(
    body: CreatorResonanceReportRequest,
) -> CreatorResonanceReport:
    """Return attention, conversion, income, proof, and next-action signals."""
    return creator_resonance_service.build_creator_resonance_report(body)
