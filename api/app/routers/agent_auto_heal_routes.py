"""Agent auto-heal stats route."""

from fastapi import APIRouter

from app.services import agent_runner_registry_service, agent_service
from app.services import auto_heal_service
from app.services.agent_service import list_tasks

router = APIRouter()


@router.get("/auto-heal/stats")
async def get_auto_heal_stats() -> dict:
    """Auto-heal statistics: heals created, rates, by-category breakdown."""
    items, _total, _runtime_backfill = list_tasks()
    failed = [
        dict(task)
        for task in items
        if isinstance(task, dict) and str(task.get("status") or "") == "failed"
    ]
    running = [
        dict(task)
        for task in items
        if isinstance(task, dict) and str(task.get("status") or "").strip().lower() == "running"
    ]
    return auto_heal_service.compute_auto_heal_stats(
        failed,
        task_counts=agent_service.get_task_count(),
        runner_rows=agent_runner_registry_service.list_runners(include_stale=True, limit=100),
        running_tasks=running,
    )
