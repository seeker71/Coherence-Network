"""Agent failed-task diagnostics completeness route."""

from fastapi import APIRouter

from app.services import agent_task_store_service, failed_task_diagnostics_service
from app.services.agent_service_list import list_tasks

router = APIRouter()


@router.get("/diagnostics-completeness")
async def get_diagnostics_completeness() -> dict:
    """Diagnostics completeness across all failed tasks."""
    if agent_task_store_service.enabled():
        agent_task_store_service.ensure_schema()
        task_dicts = agent_task_store_service.load_tasks(
            include_output=False,
            include_command=False,
        )
    else:
        items, _, _ = list_tasks(limit=10_000, offset=0)
        task_dicts = []
        for t in items:
            st = t.get("status")
            status_str = st.value if hasattr(st, "value") else str(st or "")
            task_dicts.append(
                {
                    "status": status_str,
                    "error_summary": t.get("error_summary"),
                    "error_category": t.get("error_category"),
                }
            )
    return failed_task_diagnostics_service.compute_diagnostics_completeness(task_dicts)
