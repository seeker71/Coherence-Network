"""Routes for execution value and income proof."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.execution_value import ExecutionValueProofResponse
from app.services import execution_value_proof_service

router = APIRouter(prefix="/execution", tags=["execution-value"])


@router.get(
    "/value-proof",
    response_model=ExecutionValueProofResponse,
    summary="Return measured execution value and income proof",
)
async def get_execution_value_proof(
    window_days: int = Query(30, ge=1, le=90),
    daily_nutrition_usd: float | None = Query(None, ge=0.0),
) -> ExecutionValueProofResponse:
    """Compose execution, grounded value, paid-read income, and nutrition coverage."""
    return execution_value_proof_service.build_execution_value_proof(
        window_days=window_days,
        daily_nutrition_usd=daily_nutrition_usd,
    )
