"""Agent collective health route — coherence, resonance, flow, friction."""

from fastapi import APIRouter, Query

from app.services import collective_health_service

router = APIRouter()


@router.get("/collective-health")
async def get_collective_health(
    window_days: int = Query(default=7, ge=1, le=30),
) -> dict:
    """Return collective health scores for coherence, resonance, flow, and friction."""
    return collective_health_service.get_collective_health(window_days=window_days)
