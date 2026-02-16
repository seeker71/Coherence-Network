"""Unified system inventory routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import inventory_service
from app.services import page_lineage_service
from app.services import route_registry_service

router = APIRouter()


@router.get("/inventory/system-lineage")
async def system_lineage_inventory(
    runtime_window_seconds: int = Query(3600, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_system_lineage_inventory(runtime_window_seconds=runtime_window_seconds)


@router.get("/inventory/routes/canonical")
async def canonical_routes() -> dict:
    return route_registry_service.get_canonical_routes()


@router.get("/inventory/page-lineage")
async def page_lineage() -> dict:
    return page_lineage_service.get_page_lineage()


@router.post("/inventory/questions/next-highest-roi-task")
async def next_highest_roi_task(create_task: bool = Query(False)) -> dict:
    return inventory_service.next_highest_roi_task_from_answered_questions(create_task=create_task)


@router.post("/inventory/questions/sync-implementation-tasks")
async def sync_implementation_request_tasks() -> dict:
    return inventory_service.sync_implementation_request_question_tasks()


@router.get("/inventory/questions/proactive")
async def proactive_questions(
    limit: int = Query(20, ge=1, le=200),
    top: int = Query(20, ge=1, le=200),
) -> dict:
    return inventory_service.derive_proactive_questions_from_recent_changes(limit=limit, top=top)


@router.post("/inventory/questions/sync-proactive")
async def sync_proactive_questions(
    limit: int = Query(20, ge=1, le=200),
    max_add: int = Query(20, ge=1, le=200),
) -> dict:
    return inventory_service.sync_proactive_questions_from_recent_changes(
        limit=limit,
        max_add=max_add,
    )


@router.post("/inventory/gaps/sync-traceability")
async def sync_traceability_gap_artifacts(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(200, ge=1, le=2000),
) -> dict:
    return inventory_service.sync_traceability_gap_artifacts(
        runtime_window_seconds=runtime_window_seconds,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )


@router.get("/inventory/process-completeness")
async def process_completeness(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    auto_sync: bool = Query(False),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(200, ge=1, le=2000),
) -> dict:
    return inventory_service.evaluate_process_completeness(
        runtime_window_seconds=runtime_window_seconds,
        auto_sync=auto_sync,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )


@router.get("/inventory/flow")
async def spec_process_implementation_validation_flow(
    idea_id: str | None = Query(default=None),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_spec_process_implementation_validation_flow(
        idea_id=idea_id,
        runtime_window_seconds=runtime_window_seconds,
    )


@router.post("/inventory/flow/next-unblock-task")
async def next_unblock_task(
    create_task: bool = Query(False),
    idea_id: str | None = Query(default=None),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.next_unblock_task_from_flow(
        create_task=create_task,
        idea_id=idea_id,
        runtime_window_seconds=runtime_window_seconds,
    )


@router.get("/inventory/endpoint-traceability")
async def endpoint_traceability_inventory(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_endpoint_traceability_inventory(
        runtime_window_seconds=runtime_window_seconds
    )
