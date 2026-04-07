"""Agent orchestration API routes. Composes sub-routers and Telegram webhook."""

import logging

from fastapi import APIRouter

from app.models.metrics import TaskMetricRecord
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
from app.routers.agent_smart_reap_routes import router as smart_reap_router
from app.routers.agent_task_chain_routes import router as task_chain_router

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(telegram_router)

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
router.include_router(smart_reap_router, prefix="/agent")
router.include_router(task_chain_router, prefix="/agent")


# POST /api/agent/metrics — Record a single task metric from agent_runner. Spec 026.
@router.post("/agent/metrics", status_code=201, summary="Record task metric (Spec 026)")
async def record_task_metric(data: TaskMetricRecord) -> dict:
    """Accept task execution metrics from agent_runner. Stores in JSONL/DB for aggregation."""
    from app.services.metrics_service import record_task

    try:
        record_task(
            task_id=data.task_id,
            task_type=data.task_type,
            model=data.model,
            duration_seconds=data.duration_seconds,
            status=data.status,
            executor=data.executor or "",
            prompt_variant=data.prompt_variant,
            skill_version=data.skill_version,
        )
        return {"recorded": True, "task_id": data.task_id}
    except Exception:
        logger.warning("Failed to record task metric for %s", data.task_id, exc_info=True)
        return {"recorded": False, "task_id": data.task_id}


# GET /api/agent/metrics — Aggregate pipeline metrics. Spec 026 Phase 1.
@router.get("/agent/metrics", summary="Pipeline metrics (Spec 026)")
async def get_pipeline_metrics(window_days: int | None = None) -> dict:
    """Return P50/P95 execution time, success rate, and per-type/model breakdowns."""
    from app.services.metrics_service import get_aggregates

    return get_aggregates(window_days=window_days)
