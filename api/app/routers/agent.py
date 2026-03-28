"""Agent orchestration API routes. Composes sub-routers and Telegram webhook."""

from fastapi import APIRouter

from app.services.collective_health_service import build_collective_health
from app.routers.agent_telegram import router as telegram_router
from app.routers.agent_execute_routes import router as execute_router
from app.routers.agent_task_log_routes import router as task_log_router
from app.routers.agent_tasks_routes import router as tasks_router
from app.routers.task_activity_routes import router as task_activity_router
from app.routers.agent_run_state_routes import router as run_state_router
from app.routers.agent_usage_routes import router as usage_router
from app.routers.agent_issues_routes import router as issues_router
from app.routers.agent_status_routes import router as status_router
from app.routers.agent_route_telegram_routes import router as route_telegram_router
from app.routers.agent_prompt_ab_routes import router as prompt_ab_router
from app.routers.agent_diagnostics_routes import router as diagnostics_router
from app.routers.agent_auto_heal_routes import router as auto_heal_router

router = APIRouter()

_collective_health_router = APIRouter()


@_collective_health_router.get("/collective-health")
async def get_collective_health() -> dict:
    """Collective coherence, resonance, flow, friction, and derived collective_value from live telemetry."""
    return build_collective_health()


router.include_router(telegram_router)
router.include_router(_collective_health_router, prefix="/agent")

# Prefix /agent for all agent sub-routers. Order: more specific paths first.
router.include_router(execute_router, prefix="/agent")
router.include_router(task_log_router, prefix="/agent")
router.include_router(task_activity_router, prefix="/agent")
router.include_router(tasks_router, prefix="/agent")
router.include_router(run_state_router, prefix="/agent")
router.include_router(usage_router, prefix="/agent")
router.include_router(issues_router, prefix="/agent")
router.include_router(status_router, prefix="/agent")
router.include_router(route_telegram_router, prefix="/agent")
router.include_router(prompt_ab_router, prefix="/agent")
router.include_router(diagnostics_router, prefix="/agent")
router.include_router(auto_heal_router, prefix="/agent")
