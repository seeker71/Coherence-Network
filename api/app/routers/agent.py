"""Agent orchestration API routes."""

import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from typing import Optional

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
from app.services import agent_run_state_service, agent_runner_registry_service, agent_service

router = APIRouter()
router.include_router(telegram_router)


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


def _task_to_item(task: dict) -> dict:
    """Convert stored task to list item (no command/output)."""
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
        "claimed_by": task.get("claimed_by"),
        "claimed_at": task.get("claimed_at"),
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at"),
    }


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
async def heartbeat_runner(data: AgentRunnerHeartbeat) -> dict:
    return agent_runner_registry_service.heartbeat_runner(
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
        require_when_token_not_configured=False,
    )

    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

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
    Sends Telegram alerts for needs_decision/failed and all runner-driven updates.
    When decision present and task needs_decision, sets status→running.
    """
    if all(
        getattr(data, f) is None
        for f in ("status", "output", "progress_pct", "current_step", "decision_prompt", "decision", "context", "worker_id")
    ):
        raise HTTPException(status_code=400, detail="At least one field required")
    try:
        task = agent_service.update_task(
            task_id,
            status=data.status,
            output=data.output,
            progress_pct=data.progress_pct,
            current_step=data.current_step,
            decision_prompt=data.decision_prompt,
            decision=data.decision,
            context=data.context,
            worker_id=data.worker_id,
        )
    except agent_service.TaskClaimConflictError as exc:
        claimed = exc.claimed_by or "another worker"
        raise HTTPException(status_code=409, detail=f"Task already claimed by {claimed}") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    runner_update = is_runner_task_update(worker_id=data.worker_id, context_patch=data.context)
    if runner_update or data.status in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED):
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
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    path = os.path.join(logs_dir, "monitor_issues.json")
    if not os.path.isfile(path):
        return {"issues": [], "last_check": None}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"issues": [], "last_check": None}


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


def _agent_logs_dir() -> str:
    """Logs directory for status-report and meta_questions; overridable in tests."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


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
    if not os.path.isfile(path):
        out = {
            "generated_at": None,
            "overall": {"status": "unknown", "going_well": [], "needs_attention": []},
            "layer_0_goal": {"status": "unknown", "summary": "Report not yet generated by monitor"},
            "layer_1_orchestration": {"status": "unknown", "summary": ""},
            "layer_2_execution": {"status": "unknown", "summary": ""},
            "layer_3_attention": {"status": "unknown", "summary": ""},
        }
        return _merge_meta_questions_into_report(out, logs_dir)
    try:
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        return _merge_meta_questions_into_report(report, logs_dir)
    except Exception:
        out = {"generated_at": None, "overall": {"status": "unknown", "going_well": [], "needs_attention": []}, "error": "Could not read report"}
        return _merge_meta_questions_into_report(out, logs_dir)


@router.get("/agent/pipeline-status")
async def get_pipeline_status() -> dict:
    """Pipeline visibility: running task, pending with wait times, recent completed with duration.
    Includes project manager state when available. For running tasks, includes live_tail (last 20 lines of streamed log).
    Returns 200 in empty state (no running task) per spec 039; body always includes running, pending, recent_completed, attention, running_by_phase."""
    status = agent_service.get_pipeline_status()
    # Guarantee contract keys for empty state (spec 039): scripts/monitors rely on 200 with full shape
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase"):
        if key not in status:
            status[key] = [] if key in ("running", "pending", "recent_completed") else ({} if key == "attention" else {"spec": 0, "impl": 0, "test": 0, "review": 0})
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
    if not os.path.isfile(log_path):
        raise HTTPException(status_code=404, detail="Task log not found")
    with open(log_path, encoding="utf-8") as f:
        log_content = f.read()
    return {"task_id": task_id, "log": log_content, "command": task.get("command"), "output": task.get("output")}


@router.get("/agent/route", response_model=RouteResponse)
async def route(
    task_type: TaskType = Query(...),
    executor: Optional[str] = Query("auto", description="Executor: auto (default policy), claude, cursor, or openclaw"),
) -> RouteResponse:
    """Get routing for a task type (no persistence). Use executor=cursor|openclaw for alternate CLIs."""
    return RouteResponse(**agent_service.get_route(task_type, executor=executor or "auto"))


@router.get("/agent/telegram/diagnostics")
async def telegram_diagnostics() -> dict:
    """Diagnostics: last webhook events, send results, config (masked). For debugging."""
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics as diag

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
        "webhook_events": diag.get_webhook_events(),
        "send_results": diag.get_send_results(),
    }


@router.post("/agent/telegram/test-send")
async def telegram_test_send(
    text: Optional[str] = Query(None, description="Optional message text"),
) -> dict:
    """Send a test message to TELEGRAM_CHAT_IDS. Returns raw Telegram API response for debugging."""
    import httpx

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
            results.append({
                "chat_id": cid,
                "status_code": r.status_code,
                "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
            })
    return {"ok": all(r["status_code"] == 200 for r in results), "results": results}
