"""Agent orchestration API routes."""

import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from typing import Any, Optional

logger = logging.getLogger(__name__)
from app.routers.agent_telegram import (
    format_task_alert,
    is_runner_task_update,
    router as telegram_router,
)

from app.models.agent import (
    AgentRunnerHeartbeat,
    AgentRunnerList,
    AgentRunnerSnapshot,
    AgentRunStateClaim,
    AgentRunStateHeartbeat,
    AgentRunStateSnapshot,
    AgentRunStateUpdate,
    AgentTask,
    AgentTaskCreate,
    AgentTaskList,
    AgentTaskListItem,
    AgentTaskUpsertActive,
    AgentTaskUpdate,
    RouteResponse,
    TaskStatus,
    TaskType,
)
from app.models.error import ErrorDetail
from app.services import (
    agent_execution_hooks,
    agent_run_state_service,
    agent_runner_registry_service,
    agent_service,
    runner_orphan_recovery_service,
)

router = APIRouter()
router.include_router(telegram_router)

_ISSUE_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _require_execute_token(
    route_name: str,
    x_agent_execute_token: Optional[str],
    *,
    require_when_token_not_configured: bool,
) -> None:
    expected = os.environ.get("AGENT_EXECUTE_TOKEN", "").strip()
    if expected:
        if (x_agent_execute_token or "").strip() != expected:
            raise HTTPException(status_code=403, detail="Forbidden")
        return
    if require_when_token_not_configured:
        logger.warning(
            "%s called without AGENT_EXECUTE_TOKEN configured; denying execution request",
            route_name,
        )
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_execute_token_when_unset() -> bool:
    """Whether execute endpoints should require a token when AGENT_EXECUTE_TOKEN is unset."""
    return not _truthy(os.environ.get("AGENT_EXECUTE_TOKEN_ALLOW_UNAUTH", ""))


def _coerce_force_paid_override(request: Request) -> bool:
    """Read force-paid override flags directly from raw query values."""
    raw_query = request.url.query
    if not raw_query:
        return False

    query_flag_names = {
        "force_paid_providers",
        "force_paid_provider",
        "force_allow_paid_providers",
        "allow_paid_providers",
        "allow_paid_provider",
        "force_paid",
    }

    normalized_queries = parse_qs(raw_query, keep_blank_values=True, strict_parsing=False)
    for raw_key, raw_values in normalized_queries.items():
        normalized_key = re.sub(r"[^a-z0-9]+", "_", raw_key.strip().lower())
        if normalized_key not in query_flag_names:
            continue
        if any(raw_values):
            if any(_truthy(raw_value) for raw_value in raw_values):
                return True
            continue
        return True

    query = request.query_params
    for name in query_flag_names:
        raw = query.get(name)
        if raw is None:
            continue
        if raw == "":
            return True
        if _truthy(raw):
            return True
    return False


def _force_paid_override(
    request: Request,
    x_force_paid_providers: str | None = None,
    force_paid_providers: str | None = None,
    force_paid_provider: str | None = None,
    force_allow_paid_providers: str | None = None,
    allow_paid_providers: str | None = None,
    allow_paid_provider: str | None = None,
) -> bool:
    """Read execute-time paid override from raw query, headers, and compatibility flags."""
    return (
        _truthy(x_force_paid_providers)
        or _truthy(force_paid_providers)
        or _truthy(force_paid_provider)
        or _truthy(force_allow_paid_providers)
        or _truthy(allow_paid_providers)
        or _truthy(allow_paid_provider)
        or _coerce_force_paid_override(request)
    )


def _task_status(task: dict[str, Any]) -> TaskStatus | None:
    raw = task.get("status")
    if isinstance(raw, TaskStatus):
        return raw
    if raw is None:
        return None
    try:
        return TaskStatus(str(raw))
    except ValueError:
        return None


def _requeue_terminal_task_for_execute(task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    status = _task_status(task)
    if status not in {TaskStatus.FAILED, TaskStatus.COMPLETED}:
        return task

    refreshed = agent_service.update_task(
        task_id,
        status=TaskStatus.PENDING,
        current_step="requeued for manual execute",
        context={
            "manual_reexecute_requested": True,
            "manual_reexecute_from_status": status.value,
        },
    )
    if isinstance(refreshed, dict):
        return refreshed
    return task


def _task_to_item(task: dict) -> dict:
    """Convert stored task to list item (no command/output)."""
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    return {
        "id": task["id"],
        "direction": task["direction"],
        "task_type": task["task_type"],
        "status": task["status"],
        "model": task["model"],
        "progress_pct": task.get("progress_pct"),
        "current_step": task.get("current_step"),
        "decision_prompt": task.get("decision_prompt"),
        "decision": task.get("decision"),
        "target_state": ctx.get("target_state"),
        "success_evidence": ctx.get("success_evidence"),
        "abort_evidence": ctx.get("abort_evidence"),
        "observation_window_sec": ctx.get("observation_window_sec"),
        "claimed_by": task.get("claimed_by"),
        "claimed_at": task.get("claimed_at"),
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at"),
    }


def _task_to_attention_item(task: dict) -> dict:
    """Like _task_to_item but includes output (spec 003: GET /attention)."""
    out = _task_to_item(task)
    out["output"] = task.get("output")
    return out


def _task_to_full(task: dict) -> dict:
    """Convert stored task to full response."""
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    return {
        "id": task["id"],
        "direction": task["direction"],
        "task_type": task["task_type"],
        "status": task["status"],
        "model": task["model"],
        "command": task["command"],
        "output": task.get("output"),
        "context": task.get("context"),
        "progress_pct": task.get("progress_pct"),
        "current_step": task.get("current_step"),
        "decision_prompt": task.get("decision_prompt"),
        "decision": task.get("decision"),
        "target_state": ctx.get("target_state"),
        "success_evidence": ctx.get("success_evidence"),
        "abort_evidence": ctx.get("abort_evidence"),
        "observation_window_sec": ctx.get("observation_window_sec"),
        "claimed_by": task.get("claimed_by"),
        "claimed_at": task.get("claimed_at"),
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at"),
    }


def _task_update_has_fields(data: AgentTaskUpdate) -> bool:
    keys = (
        "status",
        "output",
        "progress_pct",
        "current_step",
        "decision_prompt",
        "decision",
        "context",
        "worker_id",
        "target_state",
        "success_evidence",
        "abort_evidence",
        "observation_window_sec",
    )
    return any(getattr(data, key) is not None for key in keys)


def _target_state_context_patch(data: AgentTaskUpdate) -> dict:
    context_patch = dict(data.context) if isinstance(data.context, dict) else {}
    if data.target_state is not None:
        context_patch["target_state"] = data.target_state
    if data.success_evidence is not None:
        context_patch["success_evidence"] = data.success_evidence
    if data.abort_evidence is not None:
        context_patch["abort_evidence"] = data.abort_evidence
    if data.observation_window_sec is not None:
        context_patch["observation_window_sec"] = data.observation_window_sec
    return context_patch


@router.post(
    "/agent/tasks",
    status_code=201,
    responses={422: {"description": "Invalid task_type, empty direction, or validation error (detail: list of {loc, msg, type})"}},
)
async def create_task(data: AgentTaskCreate, background_tasks: BackgroundTasks) -> AgentTask:
    """Submit a task and get routed model + command.

    When AGENT_AUTO_EXECUTE=1, tasks are executed server-side in the background using the
    OpenRouter free model, and completion is tracked via runtime events.
    """
    auto = _truthy(os.environ.get("AGENT_AUTO_EXECUTE", "0"))
    if auto:
        ctx = data.context if isinstance(data.context, dict) else {}
        patched_ctx = dict(ctx)
        patched_ctx.setdefault("executor", "openclaw")
        patched_ctx.setdefault("model_override", os.environ.get("AGENT_AUTO_EXECUTE_MODEL", "openrouter/free"))
        patched = data.model_copy(update={"context": patched_ctx})
        task = agent_service.create_task(patched)
        try:
            from app.services import agent_execution_service

            background_tasks.add_task(agent_execution_service.execute_task, task["id"])
        except Exception:
            # Task creation should remain usable even if the executor module is unavailable.
            pass
    else:
        task = agent_service.create_task(data)
    return AgentTask(**_task_to_full(task))


@router.post("/agent/run-state/claim", response_model=AgentRunStateSnapshot)
async def claim_run_state(data: AgentRunStateClaim) -> dict:
    """Claim or refresh an execution lease for task-level run ownership."""
    return agent_run_state_service.claim_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        lease_seconds=data.lease_seconds,
        attempt=data.attempt,
        branch=data.branch or "",
        repo_path=data.repo_path or "",
        metadata=data.metadata if isinstance(data.metadata, dict) else None,
    )


@router.post("/agent/run-state/heartbeat", response_model=AgentRunStateSnapshot)
async def heartbeat_run_state(data: AgentRunStateHeartbeat) -> dict:
    return agent_run_state_service.heartbeat_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        lease_seconds=data.lease_seconds,
    )


@router.post("/agent/run-state/update", response_model=AgentRunStateSnapshot)
async def update_run_state(data: AgentRunStateUpdate) -> dict:
    return agent_run_state_service.update_run_state(
        task_id=data.task_id,
        run_id=data.run_id,
        worker_id=data.worker_id,
        patch=data.patch if isinstance(data.patch, dict) else {},
        lease_seconds=data.lease_seconds,
        require_owner=bool(data.require_owner),
    )


@router.get("/agent/run-state/{task_id}", response_model=AgentRunStateSnapshot)
async def get_run_state(task_id: str) -> dict:
    state = agent_run_state_service.get_run_state(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run state not found")
    return state


@router.post("/agent/runners/heartbeat", response_model=AgentRunnerSnapshot)
async def heartbeat_runner(data: AgentRunnerHeartbeat, background_tasks: BackgroundTasks) -> dict:
    snapshot = agent_runner_registry_service.heartbeat_runner(
        runner_id=data.runner_id,
        status=data.status,
        lease_seconds=data.lease_seconds,
        host=data.host or "",
        pid=data.pid,
        version=data.version or "",
        active_task_id=data.active_task_id or "",
        active_run_id=data.active_run_id or "",
        last_error=data.last_error or "",
        capabilities=data.capabilities if isinstance(data.capabilities, dict) else None,
        metadata=data.metadata if isinstance(data.metadata, dict) else None,
    )
    await runner_orphan_recovery_service.maybe_recover_on_idle_heartbeat(
        snapshot=snapshot,
        background_tasks=background_tasks,
        alert_builder=lambda task: format_task_alert(task, runner_update=False),
    )
    return snapshot


@router.get("/agent/runners", response_model=AgentRunnerList)
async def list_runners(
    include_stale: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
) -> AgentRunnerList:
    rows = agent_runner_registry_service.list_runners(include_stale=include_stale, limit=limit)
    return AgentRunnerList(
        runners=[AgentRunnerSnapshot(**row) for row in rows],
        total=len(rows),
    )


@router.get("/agent/lifecycle/summary")
async def agent_lifecycle_summary(
    seconds: int = Query(3600, ge=60, le=2592000),
    limit: int = Query(500, ge=1, le=5000),
    task_id: str | None = Query(None),
    source: str = Query("auto"),
) -> dict:
    return agent_execution_hooks.summarize_lifecycle_events(
        seconds=seconds,
        limit=limit,
        task_id=task_id,
        source=source,
    )


@router.post(
    "/agent/tasks/{task_id}/execute",
    responses={
        403: {"description": "Forbidden (missing or invalid execute token)", "model": ErrorDetail},
        404: {"description": "Task not found", "model": ErrorDetail},
    },
)
async def execute_task(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_agent_execute_token: Optional[str] = Header(None, alias="X-Agent-Execute-Token"),
    x_force_paid_providers: Optional[str] = Header(None, alias="X-Force-Paid-Providers"),
    force_paid_providers: str | None = Query(None),
    force_paid_provider: str | None = Query(None),
    force_allow_paid_providers: str | None = Query(None),
    allow_paid_providers: str | None = Query(None),
    allow_paid_provider: str | None = Query(None),
    max_cost_usd: float | None = Query(None, ge=0.0),
    estimated_cost_usd: float | None = Query(None, ge=0.0),
    cost_slack_ratio: float | None = Query(None, ge=1.0),
) -> dict:
    """Execute a task server-side (background).

    If AGENT_EXECUTE_TOKEN is set, callers must provide header X-Agent-Execute-Token.
    """
    _require_execute_token(
        "execute_task",
        x_agent_execute_token,
        require_when_token_not_configured=_require_execute_token_when_unset(),
    )

    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _requeue_terminal_task_for_execute(task_id, task)

    from app.services import agent_execution_service

    force_paid_override = _force_paid_override(
        request,
        x_force_paid_providers=x_force_paid_providers,
        force_paid_providers=force_paid_providers,
        force_paid_provider=force_paid_provider,
        force_allow_paid_providers=force_allow_paid_providers,
        allow_paid_providers=allow_paid_providers,
        allow_paid_provider=allow_paid_provider,
    )
    if force_paid_override:
        task_ctx = task.get("context")
        ctx: dict[str, object] = task_ctx if isinstance(task_ctx, dict) else {}
        if not _truthy(str(ctx.get("force_paid_providers") or "")):
            agent_service.update_task(
                task_id,
                context={
                    "force_paid_providers": True,
                    "force_paid_override_source": "query"
                    if _coerce_force_paid_override(request)
                    else "header",
                },
            )

    background_tasks.add_task(
        agent_execution_service.execute_task,
        task_id,
        force_paid_providers=force_paid_override,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    return {"ok": True, "task_id": task_id}


@router.post(
    "/agent/tasks/pickup-and-execute",
    responses={
        403: {"description": "Forbidden (missing or invalid execute token)", "model": ErrorDetail},
        404: {"description": "No pending task found", "model": ErrorDetail},
        409: {"description": "Task already claimed/running by another worker", "model": ErrorDetail},
    },
)
async def pickup_and_execute_task(
    request: Request,
    background_tasks: BackgroundTasks,
    task_id: Optional[str] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    x_agent_execute_token: Optional[str] = Header(None, alias="X-Agent-Execute-Token"),
    x_force_paid_providers: Optional[str] = Header(None, alias="X-Force-Paid-Providers"),
    force_paid_providers: str | None = Query(None),
    force_paid_provider: str | None = Query(None),
    force_allow_paid_providers: str | None = Query(None),
    allow_paid_providers: str | None = Query(None),
    allow_paid_provider: str | None = Query(None),
    max_cost_usd: float | None = Query(None, ge=0.0),
    estimated_cost_usd: float | None = Query(None, ge=0.0),
    cost_slack_ratio: float | None = Query(None, ge=1.0),
) -> dict:
    """Pick a pending task (oldest-first fallback) and execute it via Codex/API worker flow."""
    _require_execute_token(
        "pickup_and_execute_task",
        x_agent_execute_token,
        require_when_token_not_configured=True,
    )

    if task_id:
        task = agent_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task = _requeue_terminal_task_for_execute(task_id, task)
    else:
        pending, _ = agent_service.list_tasks(status=TaskStatus.PENDING, task_type=task_type, limit=200, offset=0)
        if not pending:
            return {"ok": False, "picked": False, "reason": "No pending tasks"}
        task = pending[-1]

    task_ctx = task.get("context")
    selected_task_id = str(task.get("id") or "").strip()
    if not selected_task_id:
        raise HTTPException(status_code=404, detail="Task id missing")

    force_paid_override = _force_paid_override(
        request,
        x_force_paid_providers=x_force_paid_providers,
        force_paid_providers=force_paid_providers,
        force_paid_provider=force_paid_provider,
        force_allow_paid_providers=force_allow_paid_providers,
        allow_paid_providers=allow_paid_providers,
        allow_paid_provider=allow_paid_provider,
    )
    if force_paid_override:
        ctx: dict[str, object] = task_ctx if isinstance(task_ctx, dict) else {}
        if not _truthy(str(ctx.get("force_paid_providers") or "")):
            agent_service.update_task(
                selected_task_id,
                context={
                    "force_paid_providers": True,
                    "force_paid_override_source": "query",
                },
            )

    from app.services import agent_execution_service

    background_tasks.add_task(
        agent_execution_service.execute_task,
        selected_task_id,
        force_paid_providers=force_paid_override,
        max_cost_usd=max_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cost_slack_ratio=cost_slack_ratio,
    )
    return {"ok": True, "picked": True, "task": _task_to_item(task)}


@router.post(
    "/agent/tasks/upsert-active",
    responses={
        409: {"description": "Task already claimed/running by another worker", "model": ErrorDetail},
    },
)
async def upsert_active_task(data: AgentTaskUpsertActive) -> dict:
    """Ensure an external work session is represented as a running task."""
    try:
        task, created = agent_service.upsert_active_task(
            session_key=data.session_key,
            direction=data.direction,
            task_type=data.task_type,
            worker_id=data.worker_id,
            context=data.context if isinstance(data.context, dict) else None,
        )
    except agent_service.TaskClaimConflictError as exc:
        claimed = exc.claimed_by or "another worker"
        raise HTTPException(status_code=409, detail=f"Task already claimed by {claimed}") from exc

    return {
        "created": created,
        "task": AgentTask(**_task_to_full(task)).model_dump(mode="json"),
    }


@router.get("/agent/tasks")
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentTaskList:
    """List tasks with optional filters. Pagination: limit, offset."""
    items, total = agent_service.list_tasks(
        status=status, task_type=task_type, limit=limit, offset=offset
    )
    return AgentTaskList(
        tasks=[AgentTaskListItem(**_task_to_item(t)) for t in items],
        total=total,
    )


@router.get("/agent/tasks/attention")
async def get_attention_tasks(limit: int = Query(20, ge=1, le=100)) -> dict:
    """List tasks with status needs_decision or failed only (spec 003: includes output, decision_prompt)."""
    items, total = agent_service.get_attention_tasks(limit=limit)
    return {
        "tasks": [_task_to_attention_item(t) for t in items],
        "total": total,
    }


@router.get("/agent/tasks/count")
async def get_task_count() -> dict:
    """Lightweight task counts for dashboards (total, by_status)."""
    return agent_service.get_task_count()


@router.get(
    "/agent/tasks/{task_id}",
    responses={404: {"description": "Task not found", "model": ErrorDetail}},
)
async def get_task(task_id: str) -> AgentTask:
    """Get task by id."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTask(**_task_to_full(task))


@router.patch(
    "/agent/tasks/{task_id}",
    responses={
        400: {"description": "At least one field required", "model": ErrorDetail},
        404: {"description": "Task not found", "model": ErrorDetail},
        409: {"description": "Task already claimed/running by another worker", "model": ErrorDetail},
    },
)
async def update_task(
    task_id: str,
    data: AgentTaskUpdate,
    background_tasks: BackgroundTasks,
) -> AgentTask:
    """Update task. Supports status, output, progress_pct, current_step, decision_prompt, decision.
    Sends Telegram alerts for needs_decision/failed status only.
    When decision present and task needs_decision, sets status→running.
    """
    if not _task_update_has_fields(data):
        raise HTTPException(status_code=400, detail="At least one field required")
    context_patch = _target_state_context_patch(data)
    try:
        task = agent_service.update_task(
            task_id,
            status=data.status,
            output=data.output,
            progress_pct=data.progress_pct,
            current_step=data.current_step,
            decision_prompt=data.decision_prompt,
            decision=data.decision,
            context=context_patch if context_patch else None,
            worker_id=data.worker_id,
        )
    except agent_service.TaskClaimConflictError as exc:
        claimed = exc.claimed_by or "another worker"
        raise HTTPException(status_code=409, detail=f"Task already claimed by {claimed}") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    runner_update = is_runner_task_update(
        worker_id=data.worker_id,
        context_patch=context_patch if context_patch else data.context,
    )
    task_status = task.get("status")
    task_status_value = (
        task_status.value
        if isinstance(task_status, TaskStatus)
        else str(task_status or "").strip().lower()
    )
    if task_status_value in {TaskStatus.NEEDS_DECISION.value, TaskStatus.FAILED.value}:
        from app.services import telegram_adapter

        if telegram_adapter.is_configured():
            msg = format_task_alert(task, runner_update=runner_update)
            if data.output:
                msg += f"\n\nOutput: {data.output[:200]}"
            background_tasks.add_task(telegram_adapter.send_alert, msg)
    if data.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        try:
            from app.services.metrics_service import record_task

            created = task.get("created_at")
            updated = task.get("updated_at")
            end_ts = updated if updated is not None else datetime.now(timezone.utc)
            if created is not None:
                if hasattr(created, "timestamp") and hasattr(end_ts, "timestamp"):
                    duration_seconds = (end_ts - created).total_seconds()
                else:
                    created_dt = created if isinstance(created, datetime) else datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    updated_dt = end_ts if isinstance(end_ts, datetime) else datetime.fromisoformat(str(end_ts).replace("Z", "+00:00"))
                    duration_seconds = (updated_dt - created_dt).total_seconds()
                duration_seconds = max(0.0, duration_seconds)
            else:
                duration_seconds = 0.0
            task_type_str = task["task_type"].value if hasattr(task["task_type"], "value") else str(task["task_type"])
            status_str = task["status"].value if hasattr(task["status"], "value") else str(task["status"])
            record_task(
                task_id=task_id,
                task_type=task_type_str,
                model=task.get("model", "unknown"),
                duration_seconds=round(duration_seconds, 1),
                status=status_str,
            )
        except ImportError:
            pass
    return AgentTask(**_task_to_full(task))


@router.get("/agent/usage")
async def get_usage() -> dict:
    """Per-model usage and routing. For /usage bot command and dashboards."""
    return agent_service.get_usage_summary()


@router.get("/agent/visibility")
async def get_visibility() -> dict:
    """Unified visibility for pipeline execution, usage telemetry, and remaining tracking gaps."""
    return agent_service.get_visibility_summary()


@router.get("/agent/orchestration/guidance")
async def get_orchestration_guidance(
    seconds: int = Query(21600, ge=300, le=2592000),
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    """Guidance-first routing and awareness summary (advisory, non-blocking)."""
    return agent_service.get_orchestration_guidance_summary(seconds=seconds, limit=limit)


@router.get("/agent/integration")
async def get_agent_integration() -> dict:
    """Role-agent integration coverage and remaining gaps."""
    return agent_service.get_agent_integration_status()


@router.get("/agent/fatal-issues")
async def get_fatal_issues() -> dict:
    """Unrecoverable failures. Check when autonomous; no user interaction needed until fatal."""
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    path = os.path.join(logs_dir, "fatal_issues.json")
    if not os.path.isfile(path):
        return {"fatal": False}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {"fatal": True, **data}
    except Exception:
        return {"fatal": False}


@router.get("/agent/monitor-issues")
async def get_monitor_issues() -> dict:
    """Monitor issues from automated pipeline check. Checkable; use to react and improve. Spec 027."""
    logs_dir = _agent_logs_dir()
    return _resolve_monitor_issues_payload(logs_dir, now=datetime.now(timezone.utc))


@router.get("/agent/metrics")
async def get_metrics() -> dict:
    """Task metrics: success rate, execution time, by task_type, by model. Spec 026 Phase 1."""
    try:
        from app.services.metrics_service import get_aggregates

        return get_aggregates()
    except ImportError:
        return {
            "success_rate": {"completed": 0, "failed": 0, "total": 0, "rate": 0.0},
            "execution_time": {"p50_seconds": 0, "p95_seconds": 0},
            "by_task_type": {},
            "by_model": {},
        }


@router.get("/agent/effectiveness")
async def get_effectiveness() -> dict:
    """Pipeline effectiveness: throughput, success rate, issue tracking, progress, goal proximity.
    Use to measure and improve the pipeline, agents, and progress toward overall goal."""
    try:
        from app.services.effectiveness_service import get_effectiveness as _get

        return _get()
    except ImportError:
        return {
            "throughput": {"completed_7d": 0, "tasks_per_day": 0},
            "success_rate": 0.0,
            "issues": {"open": 0, "resolved_7d": 0},
            "progress": {},
            "goal_proximity": 0.0,
            "heal_resolved_count": 0,
            "top_issues_by_priority": [],
        }


@router.get("/agent/collective-health")
async def get_collective_health(
    window_days: int = Query(7, ge=1, le=30),
) -> dict:
    """Collective health scorecard focused on coherence, resonance, flow, and friction."""
    try:
        from app.services.collective_health_service import get_collective_health as _get

        return _get(window_days=window_days)
    except ImportError:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "window_days": window_days,
            "scores": {
                "coherence": 0.0,
                "resonance": 0.0,
                "flow": 0.0,
                "friction": 0.0,
                "collective_value": 0.0,
            },
            "coherence": {},
            "resonance": {},
            "flow": {},
            "friction": {},
            "top_friction_queue": [],
            "top_opportunities": [],
        }


def _agent_logs_dir() -> str:
    """Logs directory for status-report and meta_questions; overridable in tests."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


def _orphan_threshold_seconds() -> int:
    try:
        return max(
            60,
            int(
                os.environ.get(
                    "PIPELINE_ORPHAN_RUNNING_SECONDS",
                    os.environ.get("PIPELINE_STALE_RUNNING_SECONDS", "1800"),
                )
            ),
        )
    except (TypeError, ValueError):
        return 1800


def _monitor_max_age_seconds() -> int:
    raw = os.environ.get(
        "MONITOR_ISSUES_MAX_AGE_SECONDS",
        os.environ.get("PIPELINE_MONITOR_MAX_AGE_SECONDS", "900"),
    )
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return 900


def _status_report_max_age_seconds() -> int:
    raw = os.environ.get("PIPELINE_STATUS_REPORT_MAX_AGE_SECONDS", str(_monitor_max_age_seconds()))
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return _monitor_max_age_seconds()


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_is_fresh(value: Any, *, now: datetime, max_age_seconds: int) -> bool:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return False
    age_seconds = (now - parsed).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def _read_json_dict(path: str) -> dict[str, Any] | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _derived_issue(
    condition: str,
    severity: str,
    message: str,
    suggested_action: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    normalized_severity = str(severity or "medium").strip().lower()
    priority = _ISSUE_PRIORITY.get(normalized_severity, 2)
    return {
        "id": f"derived-{condition}",
        "condition": condition,
        "severity": normalized_severity,
        "priority": priority,
        "message": message,
        "suggested_action": suggested_action,
        "created_at": now.isoformat(),
        "resolved_at": None,
        "source": "derived_pipeline_status",
    }


def _running_seconds(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _wait_seconds(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _derive_monitor_issues_from_pipeline_status(status: dict[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    running = status.get("running") if isinstance(status.get("running"), list) else []
    pending = status.get("pending") if isinstance(status.get("pending"), list) else []
    att = status.get("attention") if isinstance(status.get("attention"), dict) else {}
    issues: list[dict[str, Any]] = []

    wait_values = [_wait_seconds(item.get("wait_seconds")) for item in pending if isinstance(item, dict)]
    wait_seconds = [value for value in wait_values if value is not None]
    max_wait = max(wait_seconds) if wait_seconds else 0
    stuck = bool(att.get("stuck")) or (bool(pending) and not bool(running) and max_wait > 600)
    if stuck:
        issues.append(
            _derived_issue(
                "no_task_running",
                "high",
                f"No task running for {max_wait}s despite {len(pending)} pending.",
                "Restart agent runner and verify task claims progress.",
                now=now,
            )
        )

    if bool(att.get("repeated_failures")):
        issues.append(
            _derived_issue(
                "repeated_failures",
                "high",
                "3+ consecutive failed tasks detected in recent completions.",
                "Review recent task logs and isolate root cause before continuing new executions.",
                now=now,
            )
        )
    if bool(att.get("output_empty")):
        issues.append(
            _derived_issue(
                "output_empty",
                "high",
                "Recent completed task has empty output.",
                "Check agent runner log streaming/capture and task log persistence.",
                now=now,
            )
        )
    if bool(att.get("executor_fail")):
        issues.append(
            _derived_issue(
                "executor_fail",
                "high",
                "Recent failed task has empty output (likely executor/tool failure).",
                "Validate executor path and dependency availability in runner environment.",
                now=now,
            )
        )
    if bool(att.get("low_success_rate")):
        issues.append(
            _derived_issue(
                "low_success_rate",
                "medium",
                "7d success rate is below target (<80%).",
                "Run targeted prompt/model diagnostics and capture remediation in the meta pipeline.",
                now=now,
            )
        )

    threshold = _orphan_threshold_seconds()
    stale_running: list[dict[str, Any]] = []
    for item in running:
        if not isinstance(item, dict):
            continue
        run_seconds = _running_seconds(item.get("running_seconds"))
        if run_seconds is None or run_seconds <= threshold:
            continue
        stale_running.append(
            {
                "id": str(item.get("id") or "").strip(),
                "running_seconds": int(run_seconds),
            }
        )
    if stale_running:
        stale_ids = [row["id"] for row in stale_running if row.get("id")]
        preview = ", ".join(stale_ids[:5]) if stale_ids else "unknown"
        if len(stale_ids) > 5:
            preview = f"{preview}, ..."
        longest = max(row["running_seconds"] for row in stale_running)
        threshold_minutes = max(1, int(round(threshold / 60)))
        issues.append(
            _derived_issue(
                "orphan_running",
                "high",
                (
                    f"{len(stale_running)} running task(s) exceeded stale threshold "
                    f"{threshold}s (~{threshold_minutes}m); longest={longest}s; ids={preview}"
                ),
                "Patch stale task(s) to failed and restart runner/watchdog to recover claims.",
                now=now,
            )
        )

    return issues


def _derived_monitor_payload(
    status: dict[str, Any],
    *,
    now: datetime,
    fallback_reason: str,
    prior_last_check: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "issues": _derive_monitor_issues_from_pipeline_status(status, now=now),
        "last_check": now.isoformat(),
        "history": [],
        "source": "derived_pipeline_status",
        "fallback_reason": fallback_reason,
    }
    prior_last = str(prior_last_check or "").strip()
    if prior_last:
        payload["monitor_last_check"] = prior_last
    return payload


def _resolve_monitor_issues_payload(logs_dir: str, *, now: datetime) -> dict[str, Any]:
    path = os.path.join(logs_dir, "monitor_issues.json")
    raw_payload = _read_json_dict(path)
    if raw_payload is not None and _timestamp_is_fresh(
        raw_payload.get("last_check"),
        now=now,
        max_age_seconds=_monitor_max_age_seconds(),
    ):
        return raw_payload

    if not os.path.isfile(path):
        reason = "missing_monitor_issues_file"
        prior_last_check = None
    elif raw_payload is None:
        reason = "unreadable_monitor_issues_file"
        prior_last_check = None
    else:
        reason = "stale_monitor_issues_file"
        prior_last_check = raw_payload.get("last_check")

    status = agent_service.get_pipeline_status()
    return _derived_monitor_payload(
        status,
        now=now,
        fallback_reason=reason,
        prior_last_check=prior_last_check,
    )


def _build_fallback_status_report(
    *,
    now: datetime,
    fallback_reason: str,
    monitor_payload: dict[str, Any],
    effectiveness: dict[str, Any] | None,
    stale_report_generated_at: Any = None,
) -> dict[str, Any]:
    status = agent_service.get_pipeline_status()
    issues = (
        monitor_payload.get("issues")
        if isinstance(monitor_payload.get("issues"), list)
        else []
    )
    running = status.get("running") if isinstance(status.get("running"), list) else []
    pending = status.get("pending") if isinstance(status.get("pending"), list) else []
    recent_completed = (
        status.get("recent_completed")
        if isinstance(status.get("recent_completed"), list)
        else []
    )
    pm = status.get("project_manager") if isinstance(status.get("project_manager"), dict) else {}

    layer0: dict[str, Any] = {
        "status": "unknown",
        "summary": "Derived from live pipeline state; monitor report unavailable.",
    }
    if effectiveness:
        gp = float(effectiveness.get("goal_proximity", 0.0) or 0.0)
        throughput = (
            effectiveness.get("throughput")
            if isinstance(effectiveness.get("throughput"), dict)
            else {}
        )
        success_rate = float(effectiveness.get("success_rate", 0.0) or 0.0)
        layer0 = {
            "status": "ok" if gp >= 0.7 and not issues else "needs_attention",
            "goal_proximity": gp,
            "throughput_7d": throughput.get("completed_7d", 0),
            "tasks_per_day": throughput.get("tasks_per_day", 0),
            "success_rate": success_rate,
            "summary": (
                f"{throughput.get('completed_7d', 0)} tasks (7d), "
                f"{int(success_rate * 100)}% success"
            ),
        }
    elif issues:
        layer0["status"] = "needs_attention"
        layer0["summary"] = "Monitor report unavailable and live pipeline indicates active issues."

    pm_seen = bool(pm) and (
        pm.get("backlog_index") is not None
        or pm.get("phase") is not None
        or pm.get("in_flight")
    )
    runner_seen = bool(running)
    layer1 = {
        "status": "ok" if (pm_seen or runner_seen or not pending) else "needs_attention",
        "project_manager": "running" if pm_seen else ("idle" if pm else "unknown"),
        "pm_in_flight": len(pm.get("in_flight") or []) if isinstance(pm.get("in_flight"), list) else 0,
        "agent_runner": "running" if runner_seen else ("unknown" if not pending else "not_seen"),
        "runner_workers": None,
        "pm_parallel": None,
        "summary": (
            f"running={len(running)}, pending={len(pending)}, "
            f"pm_phase={pm.get('phase', '?') if isinstance(pm, dict) else '?'}"
        ),
    }

    issue_conditions = {
        str(item.get("condition") or "").strip()
        for item in issues
        if isinstance(item, dict)
    }
    execution_needs_attention = bool(
        {"api_unreachable", "metrics_unavailable", "no_task_running", "orphan_running"}
        & issue_conditions
    )
    layer2 = {
        "status": "needs_attention" if execution_needs_attention else "ok",
        "running": running,
        "pending": pending,
        "recent_completed": recent_completed,
        "summary": (
            f"running={len(running)}, pending={len(pending)}, recent_completed={len(recent_completed)}"
        ),
    }

    layer3 = {
        "status": "ok" if not issues else "needs_attention",
        "issues_count": len(issues),
        "issues": [
            {
                "priority": item.get("priority"),
                "condition": item.get("condition"),
                "severity": item.get("severity"),
                "message": (item.get("message") or "")[:120],
            }
            for item in issues[:10]
            if isinstance(item, dict)
        ],
        "summary": "No issues" if not issues else f"{len(issues)} issue(s) need attention",
    }

    going_well: list[str] = []
    if layer0.get("status") == "ok":
        going_well.append("goal_proximity")
    if layer1.get("status") == "ok":
        going_well.append("orchestration_active")
    if layer2.get("status") == "ok":
        going_well.append("execution_flow")
    if layer3.get("status") == "ok":
        going_well.append("no_issues")

    overall_status = "needs_attention" if any(
        layer.get("status") == "needs_attention"
        for layer in (layer0, layer1, layer2, layer3)
    ) else "ok"

    report: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "overall": {
            "status": overall_status,
            "going_well": going_well,
            "needs_attention": [cond for cond in sorted(issue_conditions) if cond],
        },
        "layer_0_goal": layer0,
        "layer_1_orchestration": layer1,
        "layer_2_execution": layer2,
        "layer_3_attention": layer3,
        "source": "derived_pipeline_status",
        "fallback_reason": fallback_reason,
    }
    stale_generated = str(stale_report_generated_at or "").strip()
    if stale_generated:
        report["monitor_report_generated_at"] = stale_generated
    return report


def _merge_meta_questions_into_report(report: dict, logs_dir: str) -> dict:
    """If report lacks meta_questions but api/logs/meta_questions.json exists, merge it (surface unanswered/failed)."""
    if "meta_questions" in report:
        return report
    mq_path = os.path.join(logs_dir, "meta_questions.json")
    if not os.path.isfile(mq_path):
        return report
    try:
        with open(mq_path, encoding="utf-8") as f:
            mq = json.load(f)
    except Exception:
        return report
    summary = mq.get("summary") or {}
    unanswered = summary.get("unanswered") or []
    failed = summary.get("failed") or []
    mq_status = "ok" if not unanswered and not failed else "needs_attention"
    report["meta_questions"] = {
        "status": mq_status,
        "last_run": mq.get("run_at"),
        "unanswered": unanswered,
        "failed": failed,
    }
    if mq_status == "needs_attention":
        report.setdefault("overall", {})
        report["overall"].setdefault("needs_attention", [])
        if "meta_questions" not in report["overall"]["needs_attention"]:
            report["overall"]["needs_attention"] = report["overall"]["needs_attention"] + ["meta_questions"]
        report["overall"]["status"] = "needs_attention"
    return report


@router.get("/agent/status-report")
async def get_status_report() -> dict:
    """Hierarchical pipeline status (Layer 0 Goal → 1 Orchestration → 2 Execution → 3 Attention).
    Machine and human readable. Written by monitor each check. Includes meta_questions (unanswered/failed) when present."""
    logs_dir = _agent_logs_dir()
    path = os.path.join(logs_dir, "pipeline_status_report.json")
    now = datetime.now(timezone.utc)
    report = _read_json_dict(path)
    if report is not None and _timestamp_is_fresh(
        report.get("generated_at"),
        now=now,
        max_age_seconds=_status_report_max_age_seconds(),
    ):
        return _merge_meta_questions_into_report(report, logs_dir)

    if not os.path.isfile(path):
        fallback_reason = "missing_status_report_file"
        stale_generated_at = None
    elif report is None:
        fallback_reason = "unreadable_status_report_file"
        stale_generated_at = None
    else:
        fallback_reason = "stale_status_report_file"
        stale_generated_at = report.get("generated_at")

    monitor_payload = _resolve_monitor_issues_payload(logs_dir, now=now)
    try:
        from app.services.effectiveness_service import get_effectiveness as _get_effectiveness

        effectiveness = _get_effectiveness()
    except Exception:
        effectiveness = None

    fallback_report = _build_fallback_status_report(
        now=now,
        fallback_reason=fallback_reason,
        monitor_payload=monitor_payload,
        effectiveness=effectiveness if isinstance(effectiveness, dict) else None,
        stale_report_generated_at=stale_generated_at,
    )
    return _merge_meta_questions_into_report(fallback_report, logs_dir)


@router.get("/agent/pipeline-status")
async def get_pipeline_status() -> dict:
    """Pipeline visibility: running task, pending with wait times, recent completed with duration.
    Includes project manager state when available. For running tasks, includes live_tail (last 20 lines of streamed log).
    Returns 200 in empty state (no running task) per spec 039; body always includes running, pending, recent_completed, attention, running_by_phase."""
    status = agent_service.get_pipeline_status()
    # Guarantee contract keys for empty state (spec 039): scripts/monitors rely on 200 with full shape
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase", "diagnostics"):
        if key not in status:
            if key in ("running", "pending", "recent_completed"):
                status[key] = []
            elif key == "attention":
                status[key] = {}
            elif key == "running_by_phase":
                status[key] = {"spec": 0, "impl": 0, "test": 0, "review": 0}
            else:
                status[key] = {}
    if "attention" in status and isinstance(status["attention"], dict):
        for att_key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
            if att_key not in status["attention"]:
                status["attention"][att_key] = False if att_key != "flags" else []
    # Add PM state from file if present (prefer overnight state when running overnight)
    import json
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    state_file = os.path.join(logs_dir, "project_manager_state.json")
    overnight_file = os.path.join(logs_dir, "project_manager_state_overnight.json")
    if os.path.isfile(overnight_file) and (
        not os.path.isfile(state_file) or os.path.getmtime(overnight_file) > os.path.getmtime(state_file)
    ):
        state_file = overnight_file
    if os.path.isfile(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                status["project_manager"] = json.load(f)
        except Exception:
            status["project_manager"] = None
    else:
        status["project_manager"] = None
    # Add live tail from running task's log (streamed during execution)
    running = status.get("running") or []
    if running:
        rid = running[0].get("id")
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{rid}.log")
        if os.path.isfile(log_path):
            try:
                with open(log_path, encoding="utf-8") as f:
                    lines = f.readlines()
                status["running"][0]["live_tail"] = [ln.rstrip() for ln in lines[-20:] if ln.strip()]
            except Exception:
                status["running"][0]["live_tail"] = None
        else:
            status["running"][0]["live_tail"] = None
    return status


@router.get(
    "/agent/tasks/{task_id}/log",
    responses={404: {"description": "Task not found or task log not found", "model": ErrorDetail}},
)
async def get_task_log(task_id: str) -> dict:
    """Full task log (prompt, command, output). File is streamed during execution, complete on finish."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", f"task_{task_id}.log")
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as f:
            log_content = f.read()
        return {
            "task_id": task_id,
            "log": log_content,
            "command": task.get("command"),
            "output": task.get("output"),
            "log_source": "file",
        }

    # Keep task-log links useful even when per-task log files are unavailable.
    fallback_lines: list[str] = []
    status = task.get("status")
    current_step = task.get("current_step")
    updated_at = task.get("updated_at")
    if status is not None:
        fallback_lines.append(f"status: {status}")
    if current_step:
        fallback_lines.append(f"current_step: {current_step}")
    if updated_at:
        fallback_lines.append(f"updated_at: {updated_at}")
    output = str(task.get("output") or "").strip()
    if output:
        fallback_lines.append("")
        fallback_lines.append("output:")
        fallback_lines.append(output[:5000])
    fallback = "\n".join(fallback_lines).strip() or "No task log file is available for this task yet."

    return {
        "task_id": task_id,
        "log": fallback,
        "command": task.get("command"),
        "output": task.get("output"),
        "log_source": "task_snapshot",
    }


@router.get("/agent/route", response_model=RouteResponse)
async def route(
    task_type: TaskType = Query(...),
    executor: Optional[str] = Query(
        "auto",
        description="Executor: auto (default policy), claude, cursor, openclaw, or clawwork (alias).",
    ),
) -> RouteResponse:
    """Get routing for a task type (no persistence). Use executor=cursor|openclaw|clawwork for alternate CLIs."""
    return RouteResponse(**agent_service.get_route(task_type, executor=executor or "auto"))


@router.get("/agent/telegram/diagnostics")
async def telegram_diagnostics() -> dict:
    """Diagnostics: last webhook events, send results, config (masked). For debugging."""
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics as diag

    def _iso_ts(raw: object) -> str | None:
        try:
            ts = float(raw)  # type: ignore[arg-type]
        except Exception:
            return None
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    webhook_events = diag.get_webhook_events()
    send_results = diag.get_send_results()
    report_log = diag.get_report_log()

    webhook_events_out = []
    for row in webhook_events:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            webhook_events_out.append(out)
        else:
            webhook_events_out.append(row)

    send_results_out = []
    for row in send_results:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            send_results_out.append(out)
        else:
            send_results_out.append(row)

    report_log_out = []
    for row in report_log:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            report_log_out.append(out)
        else:
            report_log_out.append(row)

    send_success = sum(1 for item in send_results if isinstance(item, dict) and bool(item.get("ok")))
    send_failures = sum(1 for item in send_results if isinstance(item, dict) and not bool(item.get("ok")))

    token = (
        (os.environ.get("TELEGRAM_BOT_TOKEN") or "")[:8] + "..." if os.environ.get("TELEGRAM_BOT_TOKEN") else None
    )
    return {
        "config": {
            "has_token": telegram_adapter.has_token(),
            "token_prefix": token,
            "chat_ids": os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if os.environ.get("TELEGRAM_CHAT_IDS") else [],
            "allowed_user_ids": (
                os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
                if os.environ.get("TELEGRAM_ALLOWED_USER_IDS") else []
            ),
        },
        "summary": {
            "webhook_event_count": len(webhook_events),
            "send_count": len(send_results),
            "send_success_count": send_success,
            "send_failure_count": send_failures,
            "report_count": len(report_log),
            "last_webhook_at": _iso_ts(webhook_events[-1].get("ts")) if webhook_events and isinstance(webhook_events[-1], dict) else None,
            "last_send_at": _iso_ts(send_results[-1].get("ts")) if send_results and isinstance(send_results[-1], dict) else None,
            "last_report_at": _iso_ts(report_log[-1].get("ts")) if report_log and isinstance(report_log[-1], dict) else None,
        },
        "webhook_events": webhook_events_out,
        "send_results": send_results_out,
        "report_log": report_log_out,
    }


@router.post("/agent/telegram/test-send")
async def telegram_test_send(
    text: Optional[str] = Query(None, description="Optional message text"),
) -> dict:
    """Send a test message to TELEGRAM_CHAT_IDS. Returns raw Telegram API response for debugging."""
    import httpx
    from app.services import telegram_diagnostics as diag

    message_text = text or "Test from diagnostics"
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids = [s.strip() for s in (os.environ.get("TELEGRAM_CHAT_IDS") or "").split(",") if s.strip()]
    if not token or not chat_ids:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS not set"}

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for cid in chat_ids[:3]:
            r = await client.post(url, json={"chat_id": cid, "text": message_text})
            response_text = (
                r.text[:500]
                if not r.headers.get("content-type", "").startswith("application/json")
                else str(r.json())[:500]
            )
            diag.record_send(cid, r.status_code == 200, r.status_code, response_text)
            results.append({
                "chat_id": cid,
                "status_code": r.status_code,
                "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
            })
    return {"ok": all(r["status_code"] == 200 for r in results), "results": results}
