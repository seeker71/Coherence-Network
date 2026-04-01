"""Agent task CRUD and list routes."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.models.agent import (
    AgentTask,
    AgentTaskCreate,
    AgentTaskList,
    AgentTaskListItem,
    AgentTaskUpdate,
    AgentTaskUpsertActive,
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
)
from app.routers.agent_telegram import format_task_alert, is_runner_task_update
from app.services import agent_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/tasks",
    status_code=201,
    responses={422: {"description": "Invalid task_type, empty direction, or validation error (detail: list of {loc, msg, type})"}},
)
async def create_task(data: AgentTaskCreate, background_tasks: BackgroundTasks) -> AgentTask:
    """Submit a task. Execution is handled by federation node runners, not server-side.

    Tasks are created as pending and picked up by node runners via polling.
    The slot selector on each node determines the provider based on capabilities.
    No server-side auto-execution — openrouter is not hardcoded as default.
    """
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
    return AgentTaskList(
        tasks=[AgentTaskListItem(**task_to_item(t)) for t in items],
        total=total,
        meta={"runtime_fallback_backfill_count": runtime_fallback_backfill}
        if runtime_fallback_backfill > 0
        else None,
    )


@router.get("/reap-history")
async def get_reap_history(
    idea_id: Optional[str] = Query(None),
    needs_attention: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return per-idea reap summary for the last 30 days (Spec 169 R7).

    Aggregates timed_out tasks grouped by (idea_id, task_type).
    Each item includes timeout_count, last_reaped_at, needs_human_attention,
    last_error_class, and last_partial_output_pct.
    """
    from app.services.smart_reap_service import aggregate_reap_history

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Fetch all timed_out tasks within 30 days (up to 500)
    raw = agent_service.list_tasks(status="timed_out", limit=500, offset=0)
    if isinstance(raw, tuple):
        timed_out_tasks, *_ = raw
    else:
        timed_out_tasks = raw

    # Filter to last 30 days
    def _within_30_days(t: dict) -> bool:
        updated = t.get("updated_at") or t.get("created_at") or ""
        return str(updated) >= cutoff

    timed_out_tasks = [t for t in timed_out_tasks if _within_30_days(t)]

    items = aggregate_reap_history(
        timed_out_tasks,
        idea_id_filter=idea_id,
        needs_attention_filter=needs_attention,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


@router.get(
    "/tasks/{task_id}/reap-diagnosis",
    responses={404: {"description": "Task not reaped or not found", "model": ErrorDetail}},
)
async def get_reap_diagnosis(task_id: str) -> dict:
    """Return the reap_diagnosis sub-object for a reaped task (Spec 169 R9).

    Returns 404 if the task was never reaped or has no diagnosis.
    """
    task = agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} has no reap diagnosis (never reaped or not found)",
        )
    ctx = task.get("context") or {}
    diagnosis = ctx.get("reap_diagnosis")
    if not diagnosis:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} has no reap diagnosis (never reaped or not found)",
        )
    return {"task_id": task_id, **diagnosis}


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
    # Pre-completion gate: reject hollow completions before they stick
    if data.status == TaskStatus.COMPLETED:
        output_text = (data.output or "").strip()
        task_type_val = existing_task.get("task_type", "") if existing_task else ""
        if hasattr(task_type_val, "value"):
            task_type_val = task_type_val.value
        min_output = {"spec": 100, "impl": 200, "test": 100, "code-review": 30, "review": 30}.get(str(task_type_val).lower(), 30)
        if len(output_text) < min_output:
            logger.warning(
                "HOLLOW_GATE task=%s type=%s output=%d chars < %d min — rejecting completion, marking failed",
                task_id, task_type_val, len(output_text), min_output,
            )
            data.status = TaskStatus.FAILED
            data.output = f"Hollow completion rejected: {len(output_text)} chars < {min_output} min for {task_type_val}. Provider must produce meaningful output."
            if context_patch is None:
                context_patch = {}
            context_patch["hollow_rejection"] = True
            context_patch["hollow_output_chars"] = len(output_text)
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
            error_category=data.error_category,  # DG-015 fix: pass through from runner
            error_summary=data.error_summary,     # DG-015 fix: pass through from runner
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
