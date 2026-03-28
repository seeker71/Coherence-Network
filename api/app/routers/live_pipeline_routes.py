"""Live pipeline aggregate API for the /live dashboard."""

from fastapi import APIRouter

from app.services.live_pipeline_service import get_live_pipeline_snapshot

router = APIRouter()


@router.get("/live-pipeline")
async def get_live_pipeline() -> dict:
    """Aggregated live view: runners, tasks, providers, effectiveness, prompt A/B, idea activity."""
    return get_live_pipeline_snapshot()
