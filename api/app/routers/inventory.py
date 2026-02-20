"""Unified system inventory routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.adapters.graph_store import GraphStore
from app.services import inventory_service
from app.services import page_lineage_service
from app.services import route_registry_service

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.get("/inventory/system-lineage")
async def system_lineage_inventory(
    runtime_window_seconds: int = Query(3600, ge=60, le=2592000),
    lineage_link_limit: int = Query(300, ge=1, le=1000),
    usage_event_limit: int = Query(1000, ge=1, le=5000),
    runtime_event_limit: int = Query(2000, ge=1, le=5000),
) -> dict:
    return inventory_service.build_system_lineage_inventory(
        runtime_window_seconds=runtime_window_seconds,
        lineage_link_limit=lineage_link_limit,
        usage_event_limit=usage_event_limit,
        runtime_event_limit=runtime_event_limit,
    )


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


@router.post("/inventory/specs/sync-implementation-tasks")
async def sync_spec_implementation_gap_tasks(
    create_task: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    return inventory_service.sync_spec_implementation_gap_tasks(
        create_task=create_task,
        limit=limit,
    )


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


@router.post("/inventory/gaps/sync-process-tasks")
async def sync_process_gap_tasks(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    auto_sync: bool = Query(True),
    max_tasks: int = Query(50, ge=1, le=500),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(200, ge=1, le=2000),
) -> dict:
    return inventory_service.sync_process_completeness_gap_tasks(
        runtime_window_seconds=runtime_window_seconds,
        auto_sync=auto_sync,
        max_tasks=max_tasks,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )


@router.get("/inventory/asset-modularity")
async def asset_modularity(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_implementation_files: int = Query(5000, ge=100, le=20000),
) -> dict:
    return inventory_service.evaluate_asset_modularity(
        runtime_window_seconds=runtime_window_seconds,
        max_implementation_files=max_implementation_files,
    )


@router.post("/inventory/gaps/sync-asset-modularity-tasks")
async def sync_asset_modularity_tasks(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_tasks: int = Query(50, ge=1, le=500),
) -> dict:
    return inventory_service.sync_asset_modularity_tasks(
        runtime_window_seconds=runtime_window_seconds,
        max_tasks=max_tasks,
    )


@router.get("/inventory/flow")
def spec_process_implementation_validation_flow(
    request: Request,
    idea_id: str | None = Query(default=None),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    contributor_limit: int = Query(500, ge=1, le=10000),
    contribution_limit: int = Query(2000, ge=1, le=20000),
    asset_limit: int = Query(500, ge=1, le=10000),
    spec_limit: int = Query(200, ge=1, le=2000),
    lineage_link_limit: int = Query(300, ge=1, le=1000),
    usage_event_limit: int = Query(1200, ge=1, le=5000),
    commit_evidence_limit: int = Query(500, ge=1, le=3000),
    runtime_event_limit: int = Query(2000, ge=1, le=5000),
) -> dict:
    store = get_store(request)
    contributor_rows = [item.model_dump(mode="json") for item in store.list_contributors(limit=contributor_limit)]
    contribution_rows = [item.model_dump(mode="json") for item in store.list_contributions(limit=contribution_limit)]
    asset_rows = [item.model_dump(mode="json") for item in store.list_assets(limit=asset_limit)]
    return inventory_service.build_spec_process_implementation_validation_flow(
        idea_id=idea_id,
        runtime_window_seconds=runtime_window_seconds,
        contributor_rows=contributor_rows,
        contribution_rows=contribution_rows,
        asset_rows=asset_rows,
        spec_registry_limit=spec_limit,
        lineage_link_limit=lineage_link_limit,
        usage_event_limit=usage_event_limit,
        commit_evidence_limit=commit_evidence_limit,
        runtime_event_limit=runtime_event_limit,
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


@router.get("/inventory/route-evidence")
async def route_evidence_inventory(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_route_evidence_inventory(runtime_window_seconds=runtime_window_seconds)


@router.get("/inventory/commit-evidence")
async def commit_evidence_inventory(
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    return inventory_service.build_commit_evidence_inventory(limit=limit)
