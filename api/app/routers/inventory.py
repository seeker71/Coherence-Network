"""Unified system inventory routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import inventory_service
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


@router.post("/inventory/questions/next-highest-roi-task")
async def next_highest_roi_task(create_task: bool = Query(False)) -> dict:
    return inventory_service.next_highest_roi_task_from_answered_questions(create_task=create_task)


@router.post("/inventory/roi/next-task")
async def next_highest_estimated_roi_task(create_task: bool = Query(False)) -> dict:
    return inventory_service.next_highest_estimated_roi_task(create_task=create_task)


@router.post("/inventory/issues/scan")
async def scan_inventory_issues(create_tasks: bool = Query(False)) -> dict:
    return inventory_service.scan_inventory_issues(create_tasks=create_tasks)


@router.post("/inventory/evidence/scan")
async def scan_evidence_contract(create_tasks: bool = Query(False)) -> dict:
    return inventory_service.scan_evidence_contract(create_tasks=create_tasks)


@router.post("/inventory/questions/auto-answer")
async def auto_answer_high_roi_questions(
    limit: int = Query(3, ge=1, le=25),
    create_derived_ideas: bool = Query(False),
) -> dict:
    return inventory_service.auto_answer_high_roi_questions(
        limit=limit,
        create_derived_ideas=create_derived_ideas,
    )
