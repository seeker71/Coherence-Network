"""Agent orchestration: routing and task tracking."""

import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

# Model fallback chain: local → cloud → claude (see docs/MODEL-ROUTING.md)
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openrouter/free")  # Use OpenRouter free model as default
_OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_CLOUD_MODEL", "openrouter/free")  # Cloud fallback using OpenRouter
_CLAUDE_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "openrouter/free")  # Claude fallback using OpenRouter

# Cursor CLI models (when context.executor == "cursor") — see docs/CURSOR-CLI.md
# Default to OpenRouter free model when using Cursor CLI
_CURSOR_MODEL_DEFAULT = os.environ.get("CURSOR_CLI_MODEL", "openrouter/free")
_CURSOR_MODEL_REVIEW = os.environ.get("CURSOR_CLI_REVIEW_MODEL", "openrouter/free")

# Routing: local first; use model_override in context for cloud/claude
ROUTING: dict[TaskType, tuple[str, str]] = {
    TaskType.SPEC: (f"openrouter/free", "openrouter"),
    TaskType.TEST: (f"openrouter/free", "openrouter"),
    TaskType.IMPL: (f"openrouter/free", "openrouter"),
    TaskType.REVIEW: (f"openrouter/free", "openrouter"),
    TaskType.HEAL: (f"openrouter/free", "openrouter"),
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
# --allowedTools + --dangerously-skip-permissions required for headless (-p) so Edit runs without prompts
# _COMMAND_LOCAL_AGENT = f'claude -p "{{{{direction}}}}" --agent {{{{agent}}}} --model {_OLLAMA_MODEL} --allowedTools Read,Edit,Grep,Glob,Bash --dangerously-skip-permissions'
# _COMMAND_HEAL = f'claude -p "{{{{direction}}}}" --model {_CLAUDE_MODEL} --allowedTools Read,Edit,Bash --dangerously-skip-permissions'
_COMMAND_LOCAL_AGENT = 'aider --model ollama/glm-4.7-flash:q8_0 --map-tokens 8192 --reasoning-effort high --yes "{{direction}}"'
_COMMAND_HEAL = 'aider --model ollama/glm-4.7-flash:q8_0 --map-tokens 8192 --reasoning-effort high --yes "{{direction}}"'

# Cursor CLI: agent "direction" --model X (headless, uses Cursor auth)
_CURSOR_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _CURSOR_MODEL_DEFAULT,
    TaskType.TEST: _CURSOR_MODEL_DEFAULT,
    TaskType.IMPL: _CURSOR_MODEL_DEFAULT,
    TaskType.REVIEW: _CURSOR_MODEL_REVIEW,
    TaskType.HEAL: _CURSOR_MODEL_REVIEW,
}


def _command_template(task_type: TaskType) -> str:
    agent = AGENT_BY_TASK_TYPE.get(task_type)
    if agent:
        return _COMMAND_LOCAL_AGENT.replace("{{agent}}", agent)
    return _COMMAND_HEAL


def _cursor_command_template(task_type: TaskType) -> str:
    """Cursor CLI: agent "{{direction}}" --model X. Escapes direction for shell."""
    model = _CURSOR_MODEL_BY_TYPE[task_type]
    return f'agent "{{{{direction}}}}" --model {model}'


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


def _build_command(
    direction: str, task_type: TaskType, executor: str = "claude"
) -> str:
    """Build command for task. executor: 'claude' (default) or 'cursor'."""
    if executor == "cursor":
        template = _cursor_command_template(task_type)
    else:
        template = COMMAND_TEMPLATES[task_type]
    # Escape direction for shell (double-quoted string)
    escaped = direction.replace("\\", "\\\\").replace('"', '\\"')
    return template.replace("{{direction}}", escaped)


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    task_id = _generate_id()
    ctx = data.context if isinstance(data.context, dict) else {}
    executor = (ctx.get("executor") or os.environ.get("AGENT_EXECUTOR_DEFAULT", "claude")).lower()
    if executor not in ("claude", "cursor"):
        executor = "claude"
    model, tier = ROUTING[data.task_type]
    if executor == "cursor":
        model = f"cursor/{_CURSOR_MODEL_BY_TYPE[data.task_type]}"
        tier = "cursor"
    # Smoke test: context.command_override runs raw bash, bypassing Claude
    command = (
        (data.context or {}).get("command_override")
        if isinstance(data.context, dict)
        else None
    )
    if not command:
        command = _build_command(data.direction, data.task_type, executor=executor)
        # Model override for testing (e.g. glm-4.7:cloud for better tool use)
        if ctx.get("model_override"):
            override = ctx["model_override"]
            command = re.sub(r"--model\s+\S+", f"--model {override}", command)
            # Cloud models need ANTHROPIC_BASE_URL=https://ollama.com when using glm-5:cloud etc.
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


def get_task_count() -> dict[str, Any]:
    """Lightweight task counts for dashboards."""
    items = list(_store.values())
    by_status: dict[str, int] = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status}


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention (for /status and alerts)."""
    items = list(_store.values())
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


def get_pipeline_status(now_utc=None) -> dict[str, Any]:
    """Pipeline visibility: running, pending with wait times, recent completed with duration."""
    from datetime import timezone
    now = now_utc or datetime.now(timezone.utc)

    def _ts(obj):
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)

    def _seconds_ago(ts):
        if ts is None:
            return None
        try:
            delta = now - ts
            return int(delta.total_seconds())
        except Exception:
            return None

    def _duration(start_ts, end_ts):
        if start_ts is None or end_ts is None:
            return None
        try:
            delta = end_ts - start_ts
            return int(delta.total_seconds())
        except Exception:
            return None

    running = []
    pending = []
    completed = []

    for t in _store.values():
        st = t.get("status")
        st_val = st.value if hasattr(st, "value") else str(st)
        created = t.get("created_at")
        updated = t.get("updated_at")
        started = t.get("started_at")

        item = {
            "id": t.get("id"),
            "task_type": t.get("task_type"),
            "model": t.get("model"),
            "direction": (t.get("direction") or "")[:100],
            "created_at": _ts(created),
            "updated_at": _ts(updated),
            "wait_seconds": _seconds_ago(created) if st_val == "pending" else None,
            "running_seconds": _seconds_ago(started) if st_val == "running" and started else None,
            "duration_seconds": _duration(started, updated) if st_val in ("completed", "failed") and started and updated else None,
        }
        if st_val == "running":
            running.append(item)
        elif st_val == "pending":
            pending.append(item)
        else:
            completed.append(item)

    # Most recently completed first (by completion order / updated_at per spec 032)
    completed.sort(
        key=lambda x: x.get("updated_at") or x.get("created_at", ""),
        reverse=True,
    )

    # Latest request/response for visibility into actual LLM activity
    latest_request = None
    latest_response = None
    if running:
        t = _store.get(running[0]["id"])
        if t:
            latest_request = {
                "task_id": t.get("id"),
                "status": "running",
                "direction": t.get("direction"),
                "prompt_preview": (t.get("command") or "")[:500],
            }
    if completed:
        t = _store.get(completed[0]["id"])
        if t:
            if not latest_request:
                latest_request = {
                    "task_id": t.get("id"),
                    "status": t.get("status"),
                    "direction": t.get("direction"),
                    "prompt_preview": (t.get("command") or "")[:500],
                }
            out = t.get("output") or ""
            latest_response = {
                "task_id": t.get("id"),
                "status": t.get("status"),
                "output_preview": out[:2000],
                "output_len": len(out),
            }

    # Attention flags (spec 027, 032: stuck, repeated_failures, low_success_rate)
    def _status_val(task: dict) -> str:
        """Normalize task status to string (handles TaskStatus enum or string)."""
        s = (task or {}).get("status", "")
        if hasattr(s, "value"):
            return getattr(s, "value", str(s))
        return str(s) if s else ""

    attention_flags = []
    stuck = False
    if pending and not running:
        wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
        if wait_secs and max(wait_secs) > 600:  # 10 min (spec 032)
            stuck = True
            attention_flags.append("stuck")
    repeated_failures = False
    if len(completed) >= 3:
        last_three = completed[:3]
        if all(_status_val(_store.get(c["id"]) or {}) == "failed" for c in last_three):
            repeated_failures = True
            attention_flags.append("repeated_failures")
    output_empty = False
    for c in completed[:5]:
        t = _store.get(c["id"]) or {}
        if len(t.get("output") or "") == 0 and _status_val(t) == "completed":
            output_empty = True
            attention_flags.append("output_empty")
            break
    executor_fail = False
    for c in completed[:5]:
        t = _store.get(c["id"]) or {}
        if len(t.get("output") or "") == 0 and _status_val(t) == "failed":
            executor_fail = True
            attention_flags.append("executor_fail")
            break
    low_success_rate = False
    try:
        from app.services.metrics_service import get_aggregates

        agg = get_aggregates()
        sr = agg.get("success_rate", {}) or {}
        total = sr.get("total", 0) or 0
        rate = float(sr.get("rate", 0) or 0)
        if total >= 10 and rate < 0.8:
            low_success_rate = True
            attention_flags.append("low_success_rate")
    except Exception:
        # Spec 032: when metrics unavailable, low_success_rate remains false; do not raise
        pass

    # Phase coverage: count running+pending by task_type (spec 028)
    by_phase = {"spec": 0, "impl": 0, "test": 0, "review": 0}
    for item in running + pending:
        tt = item.get("task_type")
        tt_str = tt.value if hasattr(tt, "value") else str(tt) if tt is not None else None
        if tt_str in by_phase:
            by_phase[tt_str] = by_phase.get(tt_str, 0) + 1

    return {
        "running": running[:10],
        "pending": sorted(pending, key=lambda x: x.get("created_at", ""))[:20],
        "running_by_phase": by_phase,
        "recent_completed": [
            {**c, "output_len": len((_store.get(c["id"]) or {}).get("output") or "")}
            for c in completed[:10]
        ],
        "latest_request": latest_request,
        "latest_response": latest_response,
        "attention": {
            "stuck": stuck,
            "repeated_failures": repeated_failures,
            "output_empty": output_empty,
            "executor_fail": executor_fail,
            "low_success_rate": low_success_rate,
            "flags": attention_flags,
        },
    }


def clear_store() -> None:
    """Clear in-memory store (for testing)."""
    _store.clear()
