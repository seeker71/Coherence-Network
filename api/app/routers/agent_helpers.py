"""Shared helpers for agent router and sub-routers. No routes."""

import os
import re
from typing import Any
from urllib.parse import parse_qs

from fastapi import HTTPException, Request

from app.models.agent import AgentTaskUpdate, TaskStatus
from app.services import agent_service

_ISSUE_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def task_status_value(task: dict[str, Any] | None) -> str:
    if not isinstance(task, dict):
        return ""
    task_status = task.get("status")
    return task_status.value if isinstance(task_status, TaskStatus) else str(task_status or "").strip().lower()


def truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def require_execute_token(
    route_name: str,
    x_agent_execute_token: str | None,
    *,
    require_when_token_not_configured: bool,
) -> None:
    import logging
    logger = logging.getLogger(__name__)
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


def require_execute_token_when_unset() -> bool:
    """Whether execute endpoints should require a token when AGENT_EXECUTE_TOKEN is unset."""
    return not truthy(os.environ.get("AGENT_EXECUTE_TOKEN_ALLOW_UNAUTH", ""))


def coerce_force_paid_override(request: Request) -> bool:
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
            if any(truthy(raw_value) for raw_value in raw_values):
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
        if truthy(raw):
            return True
    return False


def force_paid_override(
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
        truthy(x_force_paid_providers)
        or truthy(force_paid_providers)
        or truthy(force_paid_provider)
        or truthy(force_allow_paid_providers)
        or truthy(allow_paid_providers)
        or truthy(allow_paid_provider)
        or coerce_force_paid_override(request)
    )


def task_status(task: dict[str, Any]) -> TaskStatus | None:
    raw = task.get("status")
    if isinstance(raw, TaskStatus):
        return raw
    if raw is None:
        return None
    try:
        return TaskStatus(str(raw))
    except ValueError:
        return None


def requeue_terminal_task_for_execute(task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    status = task_status(task)
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


def task_to_item(task: dict) -> dict:
    """Convert stored task to list item (no command/output).

    IMPORTANT: context MUST be included — it carries idea_id which is
    required for task-to-idea linkage. Without it, list_tasks_for_idea()
    returns empty results and ideas get falsely marked as validated.
    """
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    return {
        "id": task["id"],
        "direction": task["direction"],
        "task_type": task["task_type"],
        "status": task["status"],
        "model": task["model"],
        "context": ctx or None,
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


def task_to_attention_item(task: dict) -> dict:
    """Like task_to_item but includes output (spec 003: GET /attention)."""
    out = task_to_item(task)
    out["output"] = task.get("output")
    return out


def task_to_full(task: dict) -> dict:
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


def task_update_has_fields(data: AgentTaskUpdate) -> bool:
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


def target_state_context_patch(data: AgentTaskUpdate) -> dict:
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


def issue_priority_map() -> dict[str, int]:
    """Return issue severity -> priority for monitor/status helpers."""
    return dict(_ISSUE_PRIORITY)
