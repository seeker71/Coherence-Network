"""Agent prompt A/B ROI stats route."""

from fastapi import APIRouter

from app.services import prompt_ab_roi_service

router = APIRouter()


@router.get("/prompt-ab/stats")
async def get_prompt_ab_stats() -> dict:
    """Per-variant ROI stats with Thompson Sampling selection probabilities."""
    return prompt_ab_roi_service.get_variant_stats()
