"""Unified system inventory routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Body, Query, Request

from app.adapters.graph_store import GraphStore
from app.config_loader import get_bool
from app.services import agent_execution_service
from app.services import agent_service
from app.services import commit_evidence_registry_service
from app.services import inventory_service
from app.services import page_lineage_service
from app.services import route_registry_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


def _extract_created_task_ids(payload: dict) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def _append(candidate: str | None) -> None:
        task_id = str(candidate or "").strip()
        if not task_id or task_id in seen:
            return
        seen.add(task_id)
        ids.append(task_id)

    created_task = payload.get("created_task")
    if isinstance(created_task, dict):
        _append(created_task.get("id"))

    created_tasks = payload.get("created_tasks")
    if isinstance(created_tasks, list):
        for row in created_tasks:
            if not isinstance(row, dict):
                continue
            _append(row.get("task_id") or row.get("id"))

    return ids


def _queue_inventory_auto_execute(payload: dict, background_tasks: BackgroundTasks) -> None:
    """Queue API-side execution only when config explicitly enables it."""
    if not get_bool("agent_executor", "auto_execute", default=False):
        return
    for task_id in _extract_created_task_ids(payload):
        background_tasks.add_task(agent_execution_service.execute_task, task_id)


@router.get("/inventory/system-lineage", summary="System Lineage Inventory")
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


@router.get("/inventory/routes/canonical", summary="Canonical Routes")
async def canonical_routes() -> dict:
    return route_registry_service.get_canonical_routes()


@router.get("/inventory/page-lineage", summary="Page Lineage")
async def page_lineage() -> dict:
    return page_lineage_service.get_page_lineage()


@router.post("/inventory/questions/next-highest-roi-task", summary="Next Highest Roi Task")
async def next_highest_roi_task(
    background_tasks: BackgroundTasks,
    create_task: bool = Query(False),
) -> dict:
    payload = inventory_service.next_highest_roi_task_from_answered_questions(create_task=create_task)
    if create_task:
        _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.post("/inventory/questions/sync-implementation-tasks", summary="Sync Implementation Request Tasks")
async def sync_implementation_request_tasks(background_tasks: BackgroundTasks) -> dict:
    payload = inventory_service.sync_implementation_request_question_tasks()
    _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.post("/inventory/specs/sync-implementation-tasks", summary="Sync Spec Implementation Gap Tasks")
async def sync_spec_implementation_gap_tasks(
    background_tasks: BackgroundTasks,
    create_task: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    payload = inventory_service.sync_spec_implementation_gap_tasks(
        create_task=create_task,
        limit=limit,
    )
    if create_task:
        _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.post("/inventory/roi/sync-progress", summary="Sync Roi Progress Tasks")
async def sync_roi_progress_tasks(
    background_tasks: BackgroundTasks,
    create_task: bool = Query(False),
    per_category: int = Query(4, ge=1, le=20),
    normalize_missing_roi: bool = Query(True),
    calibrate_estimators: bool = Query(True),
    calibration_alpha: float = Query(0.35, ge=0.0, le=1.0),
) -> dict:
    payload = inventory_service.sync_roi_progress_tasks(
        create_task=create_task,
        per_category=per_category,
        normalize_missing_roi=normalize_missing_roi,
        calibrate_estimators=calibrate_estimators,
        calibration_alpha=calibration_alpha,
    )
    if create_task:
        _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.get("/inventory/questions/proactive", summary="Proactive Questions")
async def proactive_questions(
    limit: int = Query(20, ge=1, le=200),
    top: int = Query(20, ge=1, le=200),
    include_internal_ideas: bool = Query(False),
) -> dict:
    return inventory_service.derive_proactive_questions_from_recent_changes(
        limit=limit,
        top=top,
        include_internal_ideas=include_internal_ideas,
    )


@router.post("/inventory/questions/sync-proactive", summary="Sync Proactive Questions")
async def sync_proactive_questions(
    limit: int = Query(20, ge=1, le=200),
    max_add: int = Query(20, ge=1, le=200),
    include_internal_ideas: bool = Query(False),
) -> dict:
    return inventory_service.sync_proactive_questions_from_recent_changes(
        limit=limit,
        max_add=max_add,
        include_internal_ideas=include_internal_ideas,
    )


@router.post("/inventory/gaps/sync-traceability", summary="Sync Traceability Gap Artifacts")
async def sync_traceability_gap_artifacts(
    background_tasks: BackgroundTasks,
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(0, ge=0, le=2000),
) -> dict:
    payload = inventory_service.sync_traceability_gap_artifacts(
        runtime_window_seconds=runtime_window_seconds,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )
    _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.get("/pipeline/pulse", summary="Pipeline self-awareness digest: what's working, what's stuck, what to do next")
async def pipeline_pulse(
    window_days: int = Query(7, ge=1, le=90),
    task_limit: int = Query(500, ge=10, le=5000),
) -> dict:
    """Pipeline self-awareness digest: what's working, what's stuck, what to do next."""
    from app.services import pipeline_pulse_service
    return pipeline_pulse_service.compute_pulse(
        window_days=window_days,
        task_limit=task_limit,
    )


@router.post("/pipeline/fix-hollow-completions", summary="Reclassify hollow completions as broken_provider. Fixes Thompson Sampling data")
async def fix_hollow_completions(
    min_output_chars: int = Query(30, ge=1),
    batch_size: int = Query(200, ge=1, le=1000),
    dry_run: bool = Query(False),
) -> dict:
    """Reclassify hollow completions as broken_provider. Fixes Thompson Sampling data."""
    from app.services import agent_service

    all_tasks, _total, _backfill = agent_service.list_tasks(limit=batch_size, offset=0)
    hollow = []
    for t in all_tasks:
        status = t.get("status", "")
        if hasattr(status, "value"):
            status = status.value
        if status != "completed":
            continue
        output = (t.get("output") or "").strip()
        if len(output) < min_output_chars:
            hollow.append(t)

    fixed = 0
    if not dry_run:
        for t in hollow:
            task_id = t.get("id", "")
            model = t.get("model", "unknown")
            task_type = t.get("task_type", "")
            if hasattr(task_type, "value"):
                task_type = task_type.value
            try:
                agent_service.update_task(
                    task_id,
                    status="failed",
                    output=f"Reclassified: hollow completion ({len((t.get('output') or '').strip())} chars). Provider {model} produced no meaningful output.",
                    context={
                        **(t.get("context") or {}),
                        "hollow_reclassified": True,
                        "original_status": "completed",
                        "broken_provider": model,
                    },
                )
                # Record failure for Thompson Sampling
                try:
                    from app.services.slot_selection_service import SlotSelector
                    slot = SlotSelector(f"provider_{task_type}")
                    slot.record(
                        slot_id=model,
                        value_score=0.0,
                        resource_cost=1.0,
                        error_class="hollow_completion",
                        duration_s=0.0,
                    )
                except Exception:
                    pass
                fixed += 1
            except Exception:
                pass

    return {
        "result": "hollow_completions_fixed" if not dry_run else "dry_run",
        "total_completed_scanned": len([t for t in all_tasks if str(t.get("status","")).replace("TaskStatus.","") == "completed"]),
        "hollow_found": len(hollow),
        "fixed": fixed,
        "dry_run": dry_run,
        "samples": [
            {
                "task_id": t.get("id", "")[:20],
                "task_type": str(t.get("task_type", "")),
                "model": t.get("model", "?"),
                "output_len": len((t.get("output") or "").strip()),
                "idea_id": (t.get("context") or {}).get("idea_id", ""),
            }
            for t in hollow[:10]
        ],
    }


@router.post("/inventory/gaps/bootstrap-specs", summary="Create spec tasks for the highest-ROI ideas that don't have a spec yet")
async def bootstrap_spec_tasks(
    max_tasks: int = Query(20, ge=1, le=100),
    min_value_gap: float = Query(10.0, ge=0),
) -> dict:
    """Create spec tasks for the highest-ROI ideas that don't have a spec yet."""
    return inventory_service.bootstrap_spec_tasks(
        max_tasks=max_tasks,
        min_value_gap=min_value_gap,
    )


@router.get("/inventory/process-completeness", summary="Process Completeness")
async def process_completeness(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    auto_sync: bool = Query(False),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(0, ge=0, le=2000),
) -> dict:
    return inventory_service.evaluate_process_completeness(
        runtime_window_seconds=runtime_window_seconds,
        auto_sync=auto_sync,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )


@router.post("/inventory/gaps/sync-process-tasks", summary="Sync Process Gap Tasks")
async def sync_process_gap_tasks(
    background_tasks: BackgroundTasks,
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    auto_sync: bool = Query(True),
    max_tasks: int = Query(50, ge=1, le=500),
    max_spec_idea_links: int = Query(150, ge=1, le=1000),
    max_missing_endpoint_specs: int = Query(200, ge=1, le=2000),
    max_spec_process_backfills: int = Query(500, ge=1, le=5000),
    max_usage_gap_tasks: int = Query(0, ge=0, le=2000),
) -> dict:
    payload = inventory_service.sync_process_completeness_gap_tasks(
        runtime_window_seconds=runtime_window_seconds,
        auto_sync=auto_sync,
        max_tasks=max_tasks,
        max_spec_idea_links=max_spec_idea_links,
        max_missing_endpoint_specs=max_missing_endpoint_specs,
        max_spec_process_backfills=max_spec_process_backfills,
        max_usage_gap_tasks=max_usage_gap_tasks,
    )
    _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.get("/inventory/asset-modularity", summary="Asset Modularity")
async def asset_modularity(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_implementation_files: int = Query(5000, ge=100, le=20000),
) -> dict:
    return inventory_service.evaluate_asset_modularity(
        runtime_window_seconds=runtime_window_seconds,
        max_implementation_files=max_implementation_files,
    )


@router.post("/inventory/gaps/sync-asset-modularity-tasks", summary="Sync Asset Modularity Tasks")
async def sync_asset_modularity_tasks(
    background_tasks: BackgroundTasks,
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    max_tasks: int = Query(50, ge=1, le=500),
) -> dict:
    payload = inventory_service.sync_asset_modularity_tasks(
        runtime_window_seconds=runtime_window_seconds,
        max_tasks=max_tasks,
    )
    _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.get("/inventory/flow", summary="Spec Process Implementation Validation Flow")
def spec_process_implementation_validation_flow(
    request: Request,
    idea_id: str | None = Query(default=None),
    include_internal_ideas: bool = Query(False),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
    contributor_limit: int = Query(120, ge=1, le=10000),
    contribution_limit: int = Query(300, ge=1, le=20000),
    asset_limit: int = Query(120, ge=1, le=10000),
    spec_limit: int = Query(160, ge=1, le=2000),
    lineage_link_limit: int = Query(180, ge=1, le=1000),
    usage_event_limit: int = Query(350, ge=1, le=5000),
    commit_evidence_limit: int = Query(200, ge=1, le=3000),
    runtime_event_limit: int = Query(600, ge=1, le=5000),
    list_item_limit: int = Query(12, ge=1, le=200),
) -> dict:
    from app.services import graph_service as _gs
    from app.models.graph import Edge
    from app.services.unified_db import session as _sess

    def _compat_row(node: dict) -> dict:
        """Map graph node to legacy-compatible dict for inventory_service."""
        row = dict(node)
        # Use legacy_id as the primary id if available
        if row.get("legacy_id"):
            row["id"] = row["legacy_id"]
        return row

    contributor_rows = [_compat_row(n) for n in _gs.list_nodes(type="contributor", limit=contributor_limit).get("items", [])]
    asset_rows = [_compat_row(n) for n in _gs.list_nodes(type="asset", limit=asset_limit).get("items", [])]
    def _compat_edge(edge_dict: dict) -> dict:
        """Flatten edge properties for inventory_service compatibility."""
        row = dict(edge_dict)
        props = row.pop("properties", {}) or {}
        row.update(props)
        # Ensure contribution_id maps to id
        if props.get("contribution_id"):
            row["id"] = props["contribution_id"]
        return row

    with _sess() as s:
        contribution_rows = [
            _compat_edge(e.to_dict()) for e in
            s.query(Edge).filter(Edge.type == "contribution").limit(contribution_limit).all()
        ]
    return inventory_service.build_spec_process_implementation_validation_flow(
        idea_id=idea_id,
        include_internal_ideas=include_internal_ideas,
        runtime_window_seconds=runtime_window_seconds,
        contributor_rows=contributor_rows,
        contribution_rows=contribution_rows,
        asset_rows=asset_rows,
        spec_registry_limit=spec_limit,
        lineage_link_limit=lineage_link_limit,
        usage_event_limit=usage_event_limit,
        commit_evidence_limit=commit_evidence_limit,
        runtime_event_limit=runtime_event_limit,
        list_item_limit=list_item_limit,
    )


@router.post("/inventory/flow/next-unblock-task", summary="Next Unblock Task")
async def next_unblock_task(
    background_tasks: BackgroundTasks,
    create_task: bool = Query(False),
    idea_id: str | None = Query(default=None),
    include_internal_ideas: bool = Query(False),
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    payload = inventory_service.next_unblock_task_from_flow(
        create_task=create_task,
        idea_id=idea_id,
        include_internal_ideas=include_internal_ideas,
        runtime_window_seconds=runtime_window_seconds,
    )
    if create_task:
        _queue_inventory_auto_execute(payload, background_tasks)
    return payload


@router.get("/inventory/endpoint-traceability", summary="Endpoint Traceability Inventory")
async def endpoint_traceability_inventory(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_endpoint_traceability_inventory(
        runtime_window_seconds=runtime_window_seconds
    )


@router.get("/inventory/route-evidence", summary="Route Evidence Inventory")
async def route_evidence_inventory(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_route_evidence_inventory(runtime_window_seconds=runtime_window_seconds)


@router.get("/inventory/commit-evidence", summary="Commit Evidence Inventory")
async def commit_evidence_inventory(
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    return inventory_service.build_commit_evidence_inventory(limit=limit)


@router.post("/inventory/commit-evidence", summary="Accept a batch of commit records from external tools")
async def post_commit_evidence(
    body: dict = Body(...),
) -> dict:
    """Accept a batch of commit records from external tools."""
    commits = body.get("commits")
    if not isinstance(commits, list):
        return {"stored": 0, "duplicates_skipped": 0, "error": "commits must be a list"}

    stored = 0
    duplicates_skipped = 0
    for entry in commits:
        if not isinstance(entry, dict):
            continue
        payload = {
            "date": entry.get("date", ""),
            "commit_scope": entry.get("message", ""),
            "change_files": [],
            "idea_ids": [],
            "spec_ids": [],
            "task_ids": [],
            "thread_branch": "",
            "sha": entry.get("sha", ""),
            "author": entry.get("author", ""),
            "message": entry.get("message", ""),
        }
        source_key = f"git-commit:{entry.get('sha', '')}"
        changed = commit_evidence_registry_service.upsert_record(
            payload, source_file=source_key
        )
        if changed:
            stored += 1
        else:
            duplicates_skipped += 1

    return {"stored": stored, "duplicates_skipped": duplicates_skipped}
