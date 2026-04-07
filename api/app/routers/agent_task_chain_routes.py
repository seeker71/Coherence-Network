"""Agent task-chain stats endpoint (spec: cross-task-outcome-correlation, R6)."""

from fastapi import APIRouter

router = APIRouter(tags=["agent-task-chains"])


@router.get("/task-chains/stats", summary="Chain stats (cross-task-outcome-correlation R6)")
async def get_task_chain_stats() -> dict:
    """Return aggregate chain metrics: total_chains, avg_chain_length, etc."""
    from app.services.task_chain_correlation_service import get_chain_stats

    return get_chain_stats()
