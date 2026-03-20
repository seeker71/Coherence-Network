"""Routes for grounded idea portfolio metrics (spec 116)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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


@router.post("/ideas/{idea_id}/grounded-metrics/sync")
async def sync_grounded_metrics(idea_id: str) -> dict:
    """Compute grounded metrics and write them back to the idea."""
    data = grounded_idea_metrics_service.collect_all_data()
    metrics = grounded_idea_metrics_service.compute_idea_metrics(idea_id, **data)

    if not metrics:
        raise HTTPException(status_code=404, detail=f"No data found for idea {idea_id}")

    # Regression guard: never overwrite a positive curated value with zero.
    # Grounded metrics may return 0 when data sources are empty, but the
    # idea may already have a hand-entered or previously-computed value.
    current = idea_service.get_idea(idea_id)
    sync_values: dict = {}
    computed_av = metrics["computed_actual_value"]
    computed_ac = metrics["computed_actual_cost"]
    computed_conf = metrics["computed_confidence"]

    if current:
        sync_values["actual_value"] = max(computed_av, current.actual_value)
        sync_values["actual_cost"] = max(computed_ac, current.actual_cost)
        sync_values["confidence"] = max(computed_conf, current.confidence)
    else:
        sync_values["actual_value"] = computed_av
        sync_values["actual_cost"] = computed_ac
        sync_values["confidence"] = computed_conf

    updated = idea_service.update_idea(idea_id, **sync_values)

    return {
        "idea_id": idea_id,
        "synced": True,
        "metrics": metrics,
        "idea_updated": updated is not None,
    }


@router.post("/ideas/grounded-metrics/sync")
async def sync_all_grounded_metrics() -> dict:
    """Compute and write back grounded metrics for all ideas."""
    data = grounded_idea_metrics_service.collect_all_data()
    idea_ids = idea_service.list_tracked_idea_ids()
    results = []
    synced_count = 0

    for idea_id in idea_ids:
        metrics = grounded_idea_metrics_service.compute_idea_metrics(idea_id, **data)
        if not metrics:
            continue
        # Regression guard: never overwrite positive curated values with zero
        current = idea_service.get_idea(idea_id)
        computed_av = metrics["computed_actual_value"]
        computed_ac = metrics["computed_actual_cost"]
        computed_conf = metrics["computed_confidence"]
        if current:
            sync_av = max(computed_av, current.actual_value)
            sync_ac = max(computed_ac, current.actual_cost)
            sync_conf = max(computed_conf, current.confidence)
        else:
            sync_av, sync_ac, sync_conf = computed_av, computed_ac, computed_conf

        updated = idea_service.update_idea(
            idea_id,
            actual_value=sync_av,
            actual_cost=sync_ac,
            confidence=sync_conf,
        )
        results.append({
            "idea_id": idea_id,
            "synced": True,
            "metrics": metrics,
            "idea_updated": updated is not None,
        })
        if updated is not None:
            synced_count += 1

    return {
        "ideas": results,
        "count": len(results),
        "synced_count": synced_count,
    }
