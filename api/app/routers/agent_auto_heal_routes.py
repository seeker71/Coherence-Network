"""Agent auto-heal stats route."""

from fastapi import APIRouter

from app.services import auto_heal_service
from app.services.agent_service import list_tasks

router = APIRouter()


@router.get("/auto-heal/stats")
async def get_auto_heal_stats() -> dict:
    """Auto-heal statistics: heals created, rates, by-category breakdown."""
    tasks_response = list_tasks()
    failed = [t.model_dump() for t in tasks_response.tasks if t.status.value == "failed"]
    return auto_heal_service.compute_auto_heal_stats(failed)
