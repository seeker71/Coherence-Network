"""Agent orchestration: routing and task tracking (facade).

Public API and store re-exports for backward compatibility.
Implementation lives in agent_service_*.py modules.
"""

from typing import Any

from app.models.agent import TaskType
from app.services import agent_routing_service as routing_service

# Re-export routing for tests and consumers
ROUTING = routing_service.ROUTING

# Store state (tests touch these)
from app.services.agent_service_store import (
    ACTIVE_TASK_STATUSES,
    TaskClaimConflictError,
    _store,
    _store_loaded,
    _store_loaded_at_monotonic,
    _store_loaded_includes_output,
    _store_loaded_path,
    _store_loaded_test_context,
    clear_store,
    _default_store_path,
    _store_path,
    _now,
)

# Executor / integration
from app.services.agent_service_executor import (
    AGENT_BY_TASK_TYPE,
    GUARD_AGENTS_BY_TASK_TYPE,
    get_integration_gaps,
    list_available_task_execution_providers,
    get_route,
)

# CRUD
from app.services.agent_service_crud import create_task, get_task, update_task


def apply_decision(task_id: str, decision: str) -> dict[str, Any] | None:
    """Record a user decision on a needs_decision task and set status→running.

    Convenience wrapper over update_task for the /reply Telegram command
    and PATCH decision-only payloads.  Returns the updated task or None if
    not found.
    """
    return update_task(task_id, decision=decision)

# List / counts
from app.services.agent_service_list import (
    get_attention_tasks,
    get_review_summary,
    get_task_count,
    list_tasks,
    list_tasks_for_idea,
)

# Completion / idea_id
from app.services.agent_service_completion_tracking import (
    resolve_runtime_idea_id_for_context,
    resolve_runtime_idea_id_for_task,
)

# Active task
from app.services.agent_service_active_task import (
    find_active_task_by_fingerprint,
    find_active_task_by_session_key,
    upsert_active_task,
)

# Pipeline status
from app.services.agent_service_pipeline_status import get_pipeline_status


def get_agent_integration_status() -> dict[str, Any]:
    """Report role-agent coverage, executor availability, and integration gaps."""
    report = get_integration_gaps()
    gaps = report.get("gaps", [])
    high_count = sum(1 for gap in gaps if gap.get("severity") == "high")
    status = "healthy" if high_count == 0 else "needs_attention"
    return {
        "generated_at": _now().isoformat(),
        "status": status,
        "summary": {
            "task_types": len(TaskType),
            "profiles": len(report.get("agent_profiles", [])),
            "gap_count": len(gaps),
            "high_gap_count": high_count,
        },
        "integration": report,
    }


def get_usage_summary() -> dict[str, Any]:
    """Per-model usage derived from tasks (for /usage and API)."""
    from app.services.agent_service_usage_visibility import get_usage_summary as _get_usage_summary
    return _get_usage_summary()


def get_visibility_summary() -> dict[str, Any]:
    """Combined pipeline + usage visibility with remaining tracking gap."""
    from app.services.agent_service_usage_visibility import get_visibility_summary as _get_visibility_summary
    return _get_visibility_summary()


def get_orchestration_guidance_summary(*, seconds: int = 6 * 3600, limit: int = 500) -> dict[str, Any]:
    """Guidance-first orchestration summary for model/tool routing and awareness signals."""
    from app.services.agent_service_usage_visibility import get_orchestration_guidance_summary as _get_guidance
    return _get_guidance(seconds=seconds, limit=limit)


def backfill_host_runner_failure_observability(*, window_hours: int = 24) -> dict[str, Any]:
    """Ensure host-runner failed tasks are linked to completion + friction telemetry."""
    from app.services.agent_service_usage_visibility import backfill_host_runner_failure_observability as _backfill
    return _backfill(window_hours=window_hours)
