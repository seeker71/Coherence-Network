"""Task store: in-memory storage and CRUD operations for agent tasks."""

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services.agent_config import apply_model_override, build_command, get_model_and_tier

# In-memory store (MVP); keyed by id
_store: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Generate unique task ID."""
    return f"task_{secrets.token_hex(8)}"


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    task_id = _generate_id()
    ctx = data.context if isinstance(data.context, dict) else {}
    executor = (ctx.get("executor") or os.environ.get("AGENT_EXECUTOR_DEFAULT", "claude")).lower()
    if executor not in ("claude", "cursor"):
        executor = "claude"

    model, tier = get_model_and_tier(data.task_type, executor)

    # Smoke test: context.command_override runs raw bash, bypassing Claude
    command = ctx.get("command_override") if isinstance(data.context, dict) else None
    if not command:
        command = build_command(data.direction, data.task_type, executor=executor)
        # Model override for testing (e.g. glm-4.7:cloud for better tool use)
        if ctx.get("model_override"):
            override = ctx["model_override"]
            command = apply_model_override(command, override)
        # Headless claude needs --dangerously-skip-permissions for Edit to run
        if "claude -p" in command and "--dangerously-skip-permissions" not in command:
            command = command.rstrip() + " --dangerously-skip-permissions"

    now = _now()
    task = {
        "id": task_id,
        "direction": data.direction,
        "task_type": data.task_type,
        "status": TaskStatus.PENDING,
        "model": model,
        "command": command,
        "started_at": None,
        "output": None,
        "context": data.context,
        "progress_pct": None,
        "current_step": None,
        "decision_prompt": None,
        "decision": None,
        "created_at": now,
        "updated_at": None,
        "tier": tier,
    }
    _store[task_id] = task
    return task


def get_task(task_id: str) -> Optional[dict]:
    """Get task by id."""
    return _store.get(task_id)


def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple:
    """List tasks with optional filters. Sorted by created_at descending (newest first)."""
    items = list(_store.values())
    if status is not None:
        items = [t for t in items if t["status"] == status]
    if task_type is not None:
        items = [t for t in items if t["task_type"] == task_type]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    items = items[offset : offset + limit]
    return items, total


def update_task(
    task_id: str,
    status: Optional[TaskStatus] = None,
    output: Optional[str] = None,
    progress_pct: Optional[int] = None,
    current_step: Optional[str] = None,
    decision_prompt: Optional[str] = None,
    decision: Optional[str] = None,
) -> Optional[dict]:
    """Update task. Returns updated task or None if not found.
    When decision is present and task is needs_decision, set status→running and store decision.
    Note: Caller should trigger Telegram alert for needs_decision/failed (see router).
    """
    task = _store.get(task_id)
    if task is None:
        return None
    if decision is not None and task.get("status") == TaskStatus.NEEDS_DECISION:
        task["status"] = TaskStatus.RUNNING
        task["decision"] = decision
    if status is not None:
        task["status"] = status
        if status == TaskStatus.RUNNING and task.get("started_at") is None:
            task["started_at"] = _now()
    if output is not None:
        task["output"] = output
    if progress_pct is not None:
        task["progress_pct"] = progress_pct
    if current_step is not None:
        task["current_step"] = current_step
    if decision_prompt is not None:
        task["decision_prompt"] = decision_prompt
    if decision is not None and task.get("decision") is None:
        task["decision"] = decision
    task["updated_at"] = _now()
    return task


def get_all_tasks() -> list[dict[str, Any]]:
    """Get all tasks from store (for analytics)."""
    return list(_store.values())


def clear_store() -> None:
    """Clear in-memory store (for testing)."""
    _store.clear()
