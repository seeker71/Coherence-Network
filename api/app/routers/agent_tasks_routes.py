"""Agent task CRUD and list routes."""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.models.agent import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskList,
    AgentTaskListItem,
    AgentTaskUpdate,
    AgentTaskUpsertActive,
    TaskStatusCounts,
    TaskStatus,
    TaskType,
)
from app.models.error import ErrorDetail
from app.routers.agent_helpers import (
    target_state_context_patch,
    task_to_attention_item,
    task_to_full,
    task_to_item,
    task_status_value,
    task_update_has_fields,
    truthy,
)
from app.routers.agent_telegram import format_task_alert, is_runner_task_update
from app.services import agent_service
from app.services.agent_routing.model_routing_loader import get_auto_execute_default_model

logger = logging.getLogger(__name__)

router = APIRouter()


def _aggregate_task_status_counts(by_status: dict[str, int]) -> TaskStatusCounts:
    """Map raw by_status keys into UI buckets (spec 156)."""

    def _n(key: str) -> int:
        return int(by_status.get(key, 0) or 0)

    return TaskStatusCounts(
        pending=_n("pending") + _n("queued"),
        running=_n("running") + _n("claimed") + _n("in_progress"),
        completed=_n("completed"),
        failed=_n("failed") + _n("needs_decision") + _n("timed_out"),
    )


@router.post(
    "/tasks",
    status_code=201,
    responses={422: {"description": "Invalid task_type, empty direction, or validation error (detail: list of {loc, msg, type})"}},
)
async def create_task(data: AgentTaskCreate, background_tasks: BackgroundTasks) -> AgentTask:
    """Submit a task and get routed model + command.

    When AGENT_AUTO_EXECUTE=1, tasks are executed server-side in the background using the
    OpenRouter free model, and completion is tracked via runtime events.
    """
    auto = truthy(os.environ.get("AGENT_AUTO_EXECUTE", "0"))
    if auto:
        ctx = data.context if isinstance(data.context, dict) else {}
        patched_ctx = dict(ctx)
        patched_ctx.setdefault("executor", "openrouter")
        patched_ctx.setdefault(
            "model_override",
            os.environ.get("AGENT_AUTO_EXECUTE_MODEL") or get_auto_execute_default_model(),
        )
        patched = data.model_copy(update={"context": patched_ctx})
        task = agent_service.create_task(patched)
        try:
            from app.services import agent_execution_service

            background_tasks.add_task(agent_execution_service.execute_task, task["id"])
        except Exception:
            logger.warning("Auto-execution of task failed", exc_info=True)
    else:
        task = agent_service.create_task(data)
    return AgentTask(**task_to_full(task))


@router.post(
    "/tasks/upsert-active",
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
        "task": AgentTask(**task_to_full(task)).model_dump(mode="json"),
    }


@router.delete(
    "/tasks",
    status_code=204,
    responses={400: {"description": "Missing confirm=clear query parameter"}},
)
async def clear_all_tasks(confirm: Optional[str] = Query(None)) -> None:
    """Clear the entire task queue (in-memory and persistence). Use before a fresh pipeline run.
    Requires ?confirm=clear to avoid accidental use."""
    if confirm != "clear":
        raise HTTPException(
            status_code=400,
            detail="Refusing to clear all tasks without confirm=clear query parameter",
        )
    agent_service.clear_store()


@router.get("/tasks")
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    task_type: Optional[TaskType] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentTaskList:
    """List tasks with optional filters. Pagination: limit, offset."""
    items, total, runtime_fallback_backfill = agent_service.list_tasks(
        status=status, task_type=task_type, limit=limit, offset=offset
    )
    count_data = agent_service.get_task_count()
    by_status_raw = count_data.get("by_status") or {}
    by_status = {str(k): int(v or 0) for k, v in by_status_raw.items()}
    counts = _aggregate_task_status_counts(by_status)
    return AgentTaskList(
        tasks=[AgentTaskListItem(**task_to_item(t)) for t in items],
        total=total,
        meta={"runtime_fallback_backfill_count": runtime_fallback_backfill}
        if runtime_fallback_backfill > 0
        else None,
        counts=counts,
    )


@router.get("/tasks/attention")
async def get_attention_tasks(limit: int = Query(20, ge=1, le=100)) -> dict:
    """List tasks with status needs_decision or failed only (spec 003: includes output, decision_prompt)."""
    items, total = agent_service.get_attention_tasks(limit=limit)
    return {
        "tasks": [task_to_attention_item(t) for t in items],
        "total": total,
    }


@router.get("/tasks/count")
async def get_task_count() -> dict:
    """Lightweight task counts for dashboards (total, by_status)."""
    return agent_service.get_task_count()


@router.get(
    "/tasks/{task_id}",
    responses={404: {"description": "Task not found", "model": ErrorDetail}},
)
async def get_task(task_id: str) -> AgentTask:
    """Get task by id."""
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return AgentTask(**task_to_full(task))


@router.patch(
    "/tasks/{task_id}",
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
    if not task_update_has_fields(data):
        raise HTTPException(status_code=400, detail="At least one field required")
    # Block unknown workers from claiming tasks — only registered nodes or API key holders
    # Skip guard for decisions (no status change) and completions (task already claimed)
    worker_hint = data.worker_id or ""
    is_claim = data.status == TaskStatus.RUNNING and not data.decision
    if is_claim and worker_hint:
        from app.services import federation_service
        try:
            known = federation_service.list_nodes()
            known_ids = {n["node_id"] for n in known}
            known_hosts = {n.get("hostname", "") for n in known if n.get("hostname")}
            worker_host = worker_hint.split(":")[0] if ":" in worker_hint else worker_hint
            is_known = any([
                any(worker_hint.startswith(nid) for nid in known_ids),
                worker_host in known_hosts,
                worker_hint.startswith("manual"),
                worker_hint.startswith("proof"),
                worker_hint.startswith("claude"),
            ])
            if not is_known and known_ids:
                logger.warning("BLOCKED_CLAIM task=%s worker=%s — not a registered node", task_id, worker_hint)
                raise HTTPException(status_code=403, detail=f"Worker '{worker_hint}' is not a registered federation node")
        except HTTPException:
            raise
        except Exception:
            pass  # Don't block on federation service errors
    existing_task = agent_service.get_task(task_id)
    previous_status_value = task_status_value(existing_task)
    context_patch = target_state_context_patch(data)
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
        if data.decision:
            # Decisions bypass claim check — resolves the block regardless of who claimed
            task = agent_service.update_task(task_id, decision=data.decision, context=context_patch if context_patch else None)
        else:
            claimed = exc.claimed_by or "another worker"
            raise HTTPException(status_code=409, detail=f"Task already claimed by {claimed}") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    runner_update = is_runner_task_update(
        worker_id=data.worker_id,
        context_patch=context_patch if context_patch else data.context,
    )
    task_status_val = task_status_value(task)
    entered_attention_state = (
        task_status_val in {TaskStatus.NEEDS_DECISION.value, TaskStatus.FAILED.value}
        and task_status_val != previous_status_value
    )
    if entered_attention_state:
        from app.services import telegram_adapter

        if telegram_adapter.is_configured():
            msg = format_task_alert(task, runner_update=runner_update)
            if data.output:
                msg += f"\n\nOutput: {data.output[:200]}"
            background_tasks.add_task(telegram_adapter.send_alert, msg)
    # Process escalation decisions (A/B/C/D from needs_decision tasks)
    if (data.decision
            and previous_status_value == TaskStatus.NEEDS_DECISION.value
            and (task.get("context") or {}).get("escalation_source") == "pipeline_advance_service"):
        try:
            from app.services import pipeline_advance_service
            pipeline_advance_service.handle_decision(task, data.decision)
        except Exception:
            logger.warning("Decision handling failed for task %s", task_id, exc_info=True)
    if data.status == TaskStatus.COMPLETED:
        # Auto-advance: create next phase task (spec→impl→test→review)
        try:
            from app.services import pipeline_advance_service
            advanced = pipeline_advance_service.maybe_advance(task)
            if advanced:
                logger.info("Auto-advanced task %s → %s", task_id, advanced.get("id", "?"))
        except Exception:
            logger.warning("Auto-advance failed for task %s", task_id, exc_info=True)
    if data.status in (TaskStatus.TIMED_OUT, TaskStatus.FAILED):
        # Auto-retry: create retry task with different provider (up to 2 retries)
        try:
            from app.services import pipeline_advance_service
            retried = pipeline_advance_service.maybe_retry(task)
            if retried:
                logger.info("Auto-retried task %s → %s", task_id, retried.get("id", "?"))
        except Exception:
            logger.warning("Auto-retry failed for task %s", task_id, exc_info=True)
    if data.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT):
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
            logger.info("Metrics module not available, skipping recording")
        # Record provider outcome for Thompson Sampling learning
        try:
            from app.services.slot_selection_service import SlotSelector
            success = status_str == "completed"
            model = task.get("model", "unknown")
            slot = SlotSelector(f"provider_{task_type_str}")
            slot.record(
                slot_id=model,
                value_score=1.0 if success else 0.0,
                resource_cost=max(duration_seconds, 0.1),
                error_class=None if success else "timed_out" if status_str == "timed_out" else "failed",
                duration_s=duration_seconds,
            )
            logger.info("SLOT_RECORD type=%s model=%s success=%s dur=%.0fs", task_type_str, model, success, duration_seconds)
        except Exception:
            pass  # Non-critical — don't break task completion
    return AgentTask(**task_to_full(task))
