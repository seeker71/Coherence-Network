"""Task analytics: counts, summaries, and usage statistics."""

from typing import Any, List, Tuple

from app.models.agent import TaskStatus, TaskType
from app.services.agent_config import COMMAND_TEMPLATES, ROUTING, _CURSOR_MODEL_BY_TYPE
from app.services.task_store import get_all_tasks


def get_attention_tasks(limit: int = 20) -> Tuple[List[dict], int]:
    """List tasks with status needs_decision or failed (for /attention)."""
    items = [
        t
        for t in get_all_tasks()
        if t.get("status") in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)
    ]
    total = len(items)
    items.sort(key=lambda t: t["created_at"], reverse=True)
    items = items[:limit]
    return items, total


def get_task_count() -> dict[str, Any]:
    """Lightweight task counts for dashboards."""
    items = get_all_tasks()
    by_status: dict[str, int] = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status}


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention (for /status and alerts)."""
    items = get_all_tasks()
    by_status = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    needs = [t for t in items if t["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)]
    return {"by_status": by_status, "needs_attention": needs, "total": len(items)}


def get_route(task_type: TaskType, executor: str = "claude") -> dict[str, Any]:
    """Return routing info for a task type (no persistence). executor: 'claude' or 'cursor'."""
    if executor == "cursor":
        model = f"cursor/{_CURSOR_MODEL_BY_TYPE[task_type]}"
        from app.services.agent_config import _cursor_command_template
        template = _cursor_command_template(task_type)
        tier = "cursor"
    else:
        model, tier = ROUTING[task_type]
        template = COMMAND_TEMPLATES[task_type]
    return {
        "task_type": task_type.value,
        "model": model,
        "command_template": template,
        "tier": tier,
        "executor": executor,
    }


def get_usage_summary() -> dict[str, Any]:
    """Per-model usage derived from tasks (for /usage and API)."""
    by_model: dict[str, dict[str, Any]] = {}
    for t in get_all_tasks():
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
