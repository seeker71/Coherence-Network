"""Agent failed-task diagnostics completeness route."""

from fastapi import APIRouter

from app.services import failed_task_diagnostics_service
from app.services.agent_service import list_tasks

router = APIRouter()


@router.get("/diagnostics-completeness")
async def get_diagnostics_completeness() -> dict:
    """Diagnostics completeness across all failed tasks."""
    tasks_response = list_tasks()
    task_dicts = [t.model_dump() for t in tasks_response.tasks]
    return failed_task_diagnostics_service.compute_diagnostics_completeness(task_dicts)
