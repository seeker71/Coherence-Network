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
