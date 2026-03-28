"""Agent orchestration: routing and task tracking (facade).

Public API and store re-exports for backward compatibility.
Implementation lives in agent_service_*.py modules.
"""

from typing import Any, Optional

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
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

# CRUD (wrapped below to record Open Responses interop evidence)
from app.services.agent_service_crud import (
    create_task as _crud_create_task,
    get_task,
    update_task as _crud_update_task,
)

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


def adapt_task_execution_payload_to_open_responses_request(task: dict[str, Any]) -> dict[str, Any]:
    """Map a stored task execution record to an Open Responses-compatible request body (v1).

    Executors share the same envelope; task-level prompts are not rewritten per provider.
    """
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    nrc = ctx.get("normalized_response_call") if isinstance(ctx.get("normalized_response_call"), dict) else {}
    rd = ctx.get("route_decision") if isinstance(ctx.get("route_decision"), dict) else {}
    direction = str(task.get("direction") or "").strip()
    if nrc.get("input"):
        return {
            "schema": "open_responses_v1",
            "model": str(
                nrc.get("model") or routing_service.normalize_open_responses_model(str(task.get("model") or ""))
            ),
            "input": nrc.get("input"),
        }
    built = routing_service.build_normalized_response_call(
        task_id=str(task.get("id") or ""),
        executor=str(rd.get("executor") or ctx.get("executor") or "claude"),
        provider=str(rd.get("provider") or "unknown"),
        model=str(task.get("model") or ""),
        direction=direction,
    )
    return {
        "schema": built["request_schema"],
        "model": built["model"],
        "input": built["input"],
    }


def adapt_provider_output_to_open_responses_output(_task: dict[str, Any], output_text: str) -> dict[str, Any]:
    """Map provider output text into a normalized Open Responses output shape."""
    text = (output_text or "").strip() or "(empty)"
    if len(text) > 50000:
        text = text[:49990] + "…(truncated)"
    return {
        "schema": "open_responses_v1",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
    }


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create agent task and persist normalized route/model evidence."""
    task = _crud_create_task(data)
    from app.services import provider_usage_service

    provider_usage_service.persist_normalized_call_from_task(task, phase="routed")
    return task


def update_task(
    task_id: str,
    status: Optional[TaskStatus] = None,
    output: Optional[str] = None,
    progress_pct: Optional[int] = None,
    current_step: Optional[str] = None,
    decision_prompt: Optional[str] = None,
    decision: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    worker_id: Optional[str] = None,
) -> Optional[dict]:
    """Update task; on terminal status, persist normalized completion evidence."""
    task = _crud_update_task(
        task_id,
        status=status,
        output=output,
        progress_pct=progress_pct,
        current_step=current_step,
        decision_prompt=decision_prompt,
        decision=decision,
        context=context,
        worker_id=worker_id,
    )
    if task is not None:
        st = task.get("status")
        final = getattr(st, "value", st) if st is not None else None
        if str(final or "") in {"completed", "failed"}:
            from app.services import provider_usage_service

            provider_usage_service.persist_normalized_call_from_task(task, phase="completed")
    return task


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
