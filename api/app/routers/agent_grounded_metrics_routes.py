"""Routes for grounded idea portfolio metrics (spec 116)."""

from __future__ import annotations

from fastapi import APIRouter

from app.services import grounded_idea_metrics_service
from app.services import idea_service

router = APIRouter(tags=["ideas"])


@router.get("/ideas/grounded-metrics")
async def get_all_grounded_metrics() -> dict:
    """Return grounded metrics for all tracked ideas."""
    data = grounded_idea_metrics_service.collect_all_data()
    idea_ids = idea_service.list_tracked_idea_ids()
    results = grounded_idea_metrics_service.compute_all_idea_metrics(
        idea_ids, **data
    )
    return {"ideas": results, "count": len(results)}


@router.get("/ideas/{idea_id}/grounded-metrics")
async def get_idea_grounded_metrics(idea_id: str) -> dict:
    """Return grounded metrics for a single idea."""
    data = grounded_idea_metrics_service.collect_all_data()
    return grounded_idea_metrics_service.compute_idea_metrics(idea_id, **data)
