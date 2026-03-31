"""Coherence score endpoint — real-time computed coherence signal depth."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import coherence_signal_depth_service

router = APIRouter()


class SignalDetail(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    details: dict


class CoherenceScoreResponse(BaseModel):
    """Real-time coherence score computed from actual system data."""

    score: float = Field(ge=0.0, le=1.0, description="Aggregate coherence score 0.0-1.0")
    signals: dict[str, SignalDetail] = Field(
        description="Per-signal breakdown with scores, weights, and details"
    )
    signals_with_data: int = Field(
        ge=0, description="Count of signals backed by real measured data"
    )
    total_signals: int = Field(ge=0, description="Total number of signals computed")
    computed_at: str = Field(description="ISO 8601 UTC timestamp of computation")


@router.get(
    "/coherence/score",
    response_model=CoherenceScoreResponse,
    summary="Real-time coherence score",
    description=(
        "Returns a coherence score 0.0-1.0 computed from actual system data: "
        "task completion rates, spec coverage, contribution activity, "
        "runtime health, and value realization."
    ),
)
async def get_coherence_score() -> CoherenceScoreResponse:
    result = coherence_signal_depth_service.compute_coherence_score()
    return CoherenceScoreResponse(**result)
