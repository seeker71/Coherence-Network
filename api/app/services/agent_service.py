"""Agent orchestration: routing and task tracking."""

import os
import secrets
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

# Override via OLLAMA_MODEL (e.g. granite3.3:latest, qwen3-coder:30b)
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")

# Routing from docs/MODEL-ROUTING.md
ROUTING: dict[TaskType, tuple[str, str]] = {
    TaskType.SPEC: (f"ollama/{_OLLAMA_MODEL}", "local"),
    TaskType.TEST: (f"ollama/{_OLLAMA_MODEL}", "local"),
    TaskType.IMPL: (f"ollama/{_OLLAMA_MODEL}", "local"),
    TaskType.REVIEW: (f"ollama/{_OLLAMA_MODEL}", "local"),
    TaskType.HEAL: ("claude-3-5-haiku", "subscription"),
}

# Subagent mapping: task_type → Claude Code --agent name (from .claude/agents/)
# HEAL uses default tools, no subagent
AGENT_BY_TASK_TYPE: dict[TaskType, Optional[str]] = {
    TaskType.SPEC: "product-manager",
    TaskType.TEST: "qa-engineer",
    TaskType.IMPL: "dev-engineer",
    TaskType.REVIEW: "reviewer",
    TaskType.HEAL: None,
}

# Command templates: {{direction}} placeholder; uses --agent when subagent defined
_COMMAND_LOCAL_AGENT = f'claude -p "{{{{direction}}}}" --agent {{{{agent}}}} --model {_OLLAMA_MODEL}'
_COMMAND_HEAL = 'claude -p "{{direction}}" --model claude-3-5-haiku-20241022 --allowedTools Read,Edit,Bash'


def _command_template(task_type: TaskType) -> str:
    agent = AGENT_BY_TASK_TYPE.get(task_type)
    if agent:
        return _COMMAND_LOCAL_AGENT.replace("{{agent}}", agent)
    return _COMMAND_HEAL


COMMAND_TEMPLATES: dict[TaskType, str] = {
    TaskType.SPEC: _command_template(TaskType.SPEC),
    TaskType.TEST: _command_template(TaskType.TEST),
    TaskType.IMPL: _command_template(TaskType.IMPL),
    TaskType.REVIEW: _command_template(TaskType.REVIEW),
    TaskType.HEAL: _command_template(TaskType.HEAL),
}

# In-memory store (MVP); keyed by id
_store: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    return f"task_{secrets.token_hex(8)}"


def _build_command(direction: str, task_type: TaskType) -> str:
    template = COMMAND_TEMPLATES[task_type]
    return template.replace("{{direction}}", direction.replace('"', '\\"'))


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    task_id = _generate_id()
    model, tier = ROUTING[data.task_type]
    command = _build_command(data.direction, data.task_type)
    now = _now()
    task = {
        "id": task_id,
        "direction": data.direction,
        "task_type": data.task_type,
        "status": TaskStatus.PENDING,
        "model": model,
        "command": command,
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
) -> tuple:
    """List tasks with optional filters."""
    items = list(_store.values())
    if status is not None:
        items = [t for t in items if t["status"] == status]
    if task_type is not None:
        items = [t for t in items if t["task_type"] == task_type]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    items = items[:limit]
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


def get_attention_tasks(limit: int = 20) -> Tuple[List[dict], int]:
    """List tasks with status needs_decision or failed (for /attention)."""
    items = [
        t
        for t in _store.values()
        if t.get("status") in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)
    ]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    items = items[:limit]
    return items, total


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention (for /status and alerts)."""
    items = list(_store.values())
    by_status = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    needs = [t for t in items if t["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)]
    return {"by_status": by_status, "needs_attention": needs, "total": len(items)}


def get_route(task_type: TaskType) -> dict[str, Any]:
    """Return routing info for a task type (no persistence)."""
    model, tier = ROUTING[task_type]
    template = COMMAND_TEMPLATES[task_type]
    return {
        "task_type": task_type.value,
        "model": model,
        "command_template": template,
        "tier": tier,
    }


def get_usage_summary() -> dict[str, Any]:
    """Per-model usage derived from tasks (for /usage and API)."""
    by_model: dict[str, dict[str, Any]] = {}
    for t in _store.values():
        m = t.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"count": 0, "by_status": {}, "last_used": None}
        u = by_model[m]
        u["count"] += 1
        s = (t.get("status").value if hasattr(t.get("status"), "value") else str(t.get("status", ""))) or "pending"
        u["by_status"][s] = u["by_status"].get(s, 0) + 1
        ts = t.get("updated_at") or t.get("created_at")
        if ts:
            u["last_used"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return {
        "by_model": by_model,
        "routing": {t.value: {"model": ROUTING[t][0], "tier": ROUTING[t][1]} for t in TaskType},
    }


def clear_store() -> None:
    """Clear in-memory store (for testing)."""
    _store.clear()
