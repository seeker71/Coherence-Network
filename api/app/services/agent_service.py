"""Agent orchestration: routing and task tracking."""

import hashlib
import json
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.models.runtime import RuntimeEventCreate
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

# Model fallback chain: local → cloud → claude (see docs/MODEL-ROUTING.md)
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openrouter/free")  # Use OpenRouter free model as default
_OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_CLOUD_MODEL", "openrouter/free")  # Cloud fallback using OpenRouter
_CLAUDE_MODEL = os.environ.get("CLAUDE_FALLBACK_MODEL", "openrouter/free")  # Claude fallback using OpenRouter

# Cursor CLI models (when context.executor == "cursor") — see docs/CURSOR-CLI.md
# Default to OpenRouter free model when using Cursor CLI
_CURSOR_MODEL_DEFAULT = os.environ.get("CURSOR_CLI_MODEL", "openrouter/free")
_CURSOR_MODEL_REVIEW = os.environ.get("CURSOR_CLI_REVIEW_MODEL", "openrouter/free")

# OpenClaw models (when context.executor == "openclaw")
_OPENCLAW_MODEL_DEFAULT = os.environ.get("OPENCLAW_MODEL", "openrouter/free")
_OPENCLAW_MODEL_REVIEW = os.environ.get("OPENCLAW_REVIEW_MODEL", _OPENCLAW_MODEL_DEFAULT)

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
    TaskType.HEAL: "dev-engineer",
}

GUARD_AGENTS_BY_TASK_TYPE: dict[TaskType, list[str]] = {
    TaskType.REVIEW: ["spec-guard"],
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

_OPENCLAW_MODEL_BY_TYPE: dict[TaskType, str] = {
    TaskType.SPEC: _OPENCLAW_MODEL_DEFAULT,
    TaskType.TEST: _OPENCLAW_MODEL_DEFAULT,
    TaskType.IMPL: _OPENCLAW_MODEL_DEFAULT,
    TaskType.REVIEW: _OPENCLAW_MODEL_REVIEW,
    TaskType.HEAL: _OPENCLAW_MODEL_REVIEW,
}

_EXECUTOR_VALUES = ("claude", "cursor", "openclaw")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return max(0, value)


def _executor_policy_enabled() -> bool:
    raw = os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _normalize_executor(value: str | None, default: str = "claude") -> str:
    candidate = (value or "").strip().lower()
    if candidate in _EXECUTOR_VALUES:
        return candidate
    return default


def _cheap_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_CHEAP_DEFAULT")
    if configured:
        return _normalize_executor(configured, default="cursor")
    fallback = os.environ.get("AGENT_EXECUTOR_DEFAULT", "cursor")
    return _normalize_executor(fallback, default="cursor")


def _escalation_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_ESCALATE_TO")
    if configured:
        return _normalize_executor(configured, default="claude")
    cheap = _cheap_executor_default()
    return "claude" if cheap != "claude" else "openclaw"


def _executor_binary_name(executor: str) -> str:
    if executor == "cursor":
        return "agent"
    if executor == "openclaw":
        return "openclaw"
    return "aider"


def _executor_available(executor: str) -> bool:
    return shutil.which(_executor_binary_name(executor)) is not None


def _first_available_executor(preferred: list[str]) -> str:
    for executor in preferred:
        candidate = _normalize_executor(executor, default="")
        if candidate and _executor_available(candidate):
            return candidate
    return _normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="claude")


def _task_fingerprint(task_type: TaskType, direction: str) -> str:
    basis = f"{task_type.value}:{direction.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _task_retry_hint(context: dict[str, Any]) -> int:
    for key in ("retry_count", "retry_index", "attempt", "attempt_count"):
        raw = context.get(key)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)):
            return max(0, int(raw))
        if isinstance(raw, str):
            value = raw.strip()
            if value.isdigit():
                return max(0, int(value))
    return 0


def _prior_attempt_stats(task_fingerprint: str) -> dict[str, int]:
    attempts = 0
    failed = 0
    for task in _store.values():
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if str(context.get("task_fingerprint") or "").strip() != task_fingerprint:
            continue
        attempts += 1
        status = task.get("status")
        status_value = status.value if hasattr(status, "value") else str(status or "")
        if status_value == "failed":
            failed += 1
    return {"attempts": attempts, "failed": failed}


def _select_executor(task_type: TaskType, direction: str, context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    explicit = _normalize_executor(context.get("executor"), default="")
    if explicit:
        return explicit, {"policy_applied": False, "reason": "explicit_executor"}

    if not _executor_policy_enabled():
        default_executor = _normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="claude")
        return default_executor, {"policy_applied": False, "reason": "policy_disabled"}

    task_fingerprint = str(context.get("task_fingerprint") or "").strip()
    if not task_fingerprint:
        task_fingerprint = _task_fingerprint(task_type, direction)
        context["task_fingerprint"] = task_fingerprint

    retry_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", 2)
    failure_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", 1)
    cheap = _cheap_executor_default()
    escalate_to = _escalation_executor_default()
    if escalate_to == cheap:
        escalate_to = "claude" if cheap != "claude" else "openclaw"

    stats = _prior_attempt_stats(task_fingerprint)
    retry_hint = _task_retry_hint(context)
    effective_retry_count = max(retry_hint, max(0, stats["attempts"]))

    should_escalate = stats["failed"] >= failure_threshold or effective_retry_count >= retry_threshold
    selected = escalate_to if should_escalate else cheap
    reason = "cheap_default"
    if should_escalate:
        reason = "retry_threshold" if effective_retry_count >= retry_threshold else "failure_threshold"
    if not _executor_available(selected):
        fallback = _first_available_executor([cheap, escalate_to, "cursor", "claude", "openclaw"])
        return fallback, {
            "policy_applied": True,
            "reason": "selected_executor_unavailable",
            "selected_executor": selected,
            "fallback_executor": fallback,
            "task_fingerprint": task_fingerprint,
            "retry_threshold": retry_threshold,
            "failure_threshold": failure_threshold,
            "historical_attempts": stats["attempts"],
            "historical_failures": stats["failed"],
            "retry_hint": retry_hint,
            "effective_retry_count": effective_retry_count,
            "cheap_executor": cheap,
            "escalation_executor": escalate_to,
        }

    return selected, {
        "policy_applied": True,
        "reason": reason,
        "task_fingerprint": task_fingerprint,
        "retry_threshold": retry_threshold,
        "failure_threshold": failure_threshold,
        "historical_attempts": stats["attempts"],
        "historical_failures": stats["failed"],
        "retry_hint": retry_hint,
        "effective_retry_count": effective_retry_count,
        "cheap_executor": cheap,
        "escalation_executor": escalate_to,
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


def _openclaw_command_template(task_type: TaskType) -> str:
    """OpenClaw CLI template configurable via env; must include {{direction}}."""
    model = _OPENCLAW_MODEL_BY_TYPE[task_type]
    template = os.environ.get(
        "OPENCLAW_COMMAND_TEMPLATE",
        'openclaw run "{{direction}}" --model {{model}}',
    )
    if "{{direction}}" not in template:
        template = template.strip() + ' "{{direction}}"'
    return template.replace("{{model}}", model)


def _with_agent_roles(direction: str, task_type: TaskType, primary_agent: str | None, guard_agents: list[str]) -> str:
    lines: list[str] = []
    if primary_agent:
        lines.append(f"Role agent: {primary_agent}.")
    if guard_agents:
        lines.append(f"Guard agents: {', '.join(guard_agents)}.")
    lines.append(f"Task type: {task_type.value}.")
    lines.append("Respect role boundaries, spec scope, and acceptance criteria.")
    lines.append(f"Direction: {direction}")
    return " ".join(lines)


def _agent_profiles_dir() -> Path:
    return Path(__file__).resolve().parents[3] / ".claude" / "agents"


def _agent_profile_names() -> list[str]:
    root = _agent_profiles_dir()
    if not root.exists():
        return []
    names: list[str] = []
    for path in sorted(root.glob("*.md")):
        names.append(path.stem)
    return names


def _integration_gaps() -> dict[str, Any]:
    profiles = _agent_profile_names()
    profile_set = set(profiles)
    primary_bindings = {
        task_type.value: (agent or "")
        for task_type, agent in AGENT_BY_TASK_TYPE.items()
    }
    guard_bindings = {
        task_type.value: list(GUARD_AGENTS_BY_TASK_TYPE.get(task_type, []))
        for task_type in TaskType
    }
    bound_primary = {agent for agent in AGENT_BY_TASK_TYPE.values() if agent}
    bound_guard = {agent for items in GUARD_AGENTS_BY_TASK_TYPE.values() for agent in items}
    bound_agents = bound_primary.union(bound_guard)
    missing_profile_files = sorted(agent for agent in bound_agents if agent not in profile_set)
    unbound_profiles = sorted(name for name in profile_set if name not in bound_agents)
    unmapped_task_types = sorted(
        task_type.value for task_type in TaskType if not AGENT_BY_TASK_TYPE.get(task_type)
    )

    binary_checks = {
        "aider": _executor_available("claude"),
        "agent": _executor_available("cursor"),
        "openclaw": _executor_available("openclaw"),
    }

    gaps: list[dict[str, str]] = []
    for task in unmapped_task_types:
        gaps.append(
            {
                "id": f"unmapped-task-type:{task}",
                "severity": "high",
                "message": f"Task type '{task}' has no primary role agent binding.",
                "fix_hint": "Add role binding in AGENT_BY_TASK_TYPE.",
            }
        )
    for agent in missing_profile_files:
        gaps.append(
            {
                "id": f"missing-agent-profile:{agent}",
                "severity": "high",
                "message": f"Bound role agent profile '{agent}' is missing in .claude/agents.",
                "fix_hint": "Add the missing agent profile file.",
            }
        )
    for profile in unbound_profiles:
        gaps.append(
            {
                "id": f"unbound-agent-profile:{profile}",
                "severity": "medium",
                "message": f"Agent profile '{profile}' exists but is not bound to any task flow.",
                "fix_hint": "Bind it to a task type primary/guard flow or remove it.",
            }
        )
    cheap = _cheap_executor_default()
    escalate = _escalation_executor_default()
    critical_tools: dict[str, str] = {
        _executor_binary_name(cheap): "high",
        _executor_binary_name(escalate): "medium",
    }
    for tool, present in binary_checks.items():
        if present:
            continue
        severity = critical_tools.get(tool, "low")
        gaps.append(
            {
                "id": f"missing-executor-binary:{tool}",
                "severity": severity,
                "message": f"Executor binary '{tool}' is not available in PATH.",
                "fix_hint": f"Install '{tool}' or adjust executor policy defaults.",
            }
        )

    return {
        "primary_bindings": primary_bindings,
        "guard_bindings": guard_bindings,
        "agent_profiles": profiles,
        "missing_profile_files": missing_profile_files,
        "unbound_profiles": unbound_profiles,
        "unmapped_task_types": unmapped_task_types,
        "binary_checks": binary_checks,
        "policy_defaults": {
            "cheap_executor": cheap,
            "escalation_executor": escalate,
        },
        "gaps": gaps,
    }


COMMAND_TEMPLATES: dict[TaskType, str] = {
    TaskType.SPEC: _command_template(TaskType.SPEC),
    TaskType.TEST: _command_template(TaskType.TEST),
    TaskType.IMPL: _command_template(TaskType.IMPL),
    TaskType.REVIEW: _command_template(TaskType.REVIEW),
    TaskType.HEAL: _command_template(TaskType.HEAL),
}

# In-memory store (MVP); keyed by id
_store: dict[str, dict[str, Any]] = {}
_store_loaded = False
_store_loaded_path: str | None = None
ACTIVE_TASK_STATUSES = {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.NEEDS_DECISION}


class TaskClaimConflictError(RuntimeError):
    """Raised when attempting to start/claim a task already claimed by another worker."""

    def __init__(self, message: str, claimed_by: str | None = None):
        super().__init__(message)
        self.claimed_by = claimed_by


def _default_store_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "agent_tasks.json"


def _store_path() -> Path:
    configured = os.getenv("AGENT_TASKS_PATH")
    if configured:
        return Path(configured)
    return _default_store_path()


def _persistence_enabled() -> bool:
    configured = os.getenv("AGENT_TASKS_PERSIST")
    if configured is not None:
        return configured.strip().lower() not in {"0", "false", "no", "off"}
    # Keep tests deterministic unless explicitly opted in.
    return os.getenv("PYTEST_CURRENT_TEST") is None


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in task.items():
        if isinstance(value, (TaskStatus, TaskType)):
            out[key] = value.value
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _deserialize_task(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    task_id = raw.get("id")
    direction = raw.get("direction")
    command = raw.get("command")
    model = raw.get("model")
    if not all(isinstance(v, str) and v.strip() for v in (task_id, direction, command, model)):
        return None

    task_type_raw = raw.get("task_type")
    status_raw = raw.get("status")
    try:
        task_type = task_type_raw if isinstance(task_type_raw, TaskType) else TaskType(str(task_type_raw))
        status = status_raw if isinstance(status_raw, TaskStatus) else TaskStatus(str(status_raw))
    except ValueError:
        return None

    created_at = _parse_dt(raw.get("created_at"))
    if created_at is None:
        created_at = _now()

    task: dict[str, Any] = {
        "id": task_id.strip(),
        "direction": direction.strip(),
        "task_type": task_type,
        "status": status,
        "model": model.strip(),
        "command": command.strip(),
        "output": raw.get("output"),
        "context": raw.get("context") if isinstance(raw.get("context"), dict) else None,
        "progress_pct": raw.get("progress_pct"),
        "current_step": raw.get("current_step"),
        "decision_prompt": raw.get("decision_prompt"),
        "decision": raw.get("decision"),
        "claimed_by": raw.get("claimed_by"),
        "claimed_at": _parse_dt(raw.get("claimed_at")),
        "created_at": created_at,
        "updated_at": _parse_dt(raw.get("updated_at")),
        "started_at": _parse_dt(raw.get("started_at")),
        "tier": raw.get("tier") if isinstance(raw.get("tier"), str) else "openrouter",
    }
    return task


def _load_store_from_disk() -> dict[str, dict[str, Any]]:
    if not _persistence_enabled():
        return {}
    path = _store_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    loaded: dict[str, dict[str, Any]] = {}
    for raw in rows:
        task = _deserialize_task(raw)
        if not task:
            continue
        loaded[task["id"]] = task
    return loaded


def _save_store_to_disk() -> None:
    if not _persistence_enabled():
        return
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tasks": [_serialize_task(task) for task in _store.values()],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_store_loaded() -> None:
    global _store_loaded, _store_loaded_path
    current_path = str(_store_path())
    if _store_loaded and _store_loaded_path == current_path:
        return
    _store.clear()
    _store.update(_load_store_from_disk())
    _store_loaded = True
    _store_loaded_path = current_path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    return f"task_{secrets.token_hex(8)}"


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _is_active_status(status: Any) -> bool:
    value = _status_value(status)
    return value in {s.value for s in ACTIVE_TASK_STATUSES}


def _normalize_worker_id(worker_id: str | None) -> str:
    cleaned = (worker_id or "").strip()
    return cleaned or "unknown"


def _derive_task_executor(task: dict[str, Any]) -> str:
    model = str(task.get("model") or "").strip().lower()
    command = str(task.get("command") or "").strip()
    if model.startswith("cursor/") or command.startswith("agent "):
        return "cursor"
    if model.startswith("openclaw/") or command.startswith("openclaw "):
        return "openclaw"
    if command.startswith("aider "):
        return "aider"
    if command.startswith("claude "):
        return "claude"
    return "unknown"


def _task_duration_ms(task: dict[str, Any]) -> float:
    started = task.get("started_at")
    created = task.get("created_at")
    updated = task.get("updated_at") or _now()
    start_ts = started or created
    if hasattr(start_ts, "timestamp") and hasattr(updated, "timestamp"):
        seconds = max(0.0, float((updated - start_ts).total_seconds()))
        return max(0.1, round(seconds * 1000.0, 4))
    return 0.1


def _has_completion_tracking_event(task_id: str, final_status: str) -> bool:
    try:
        from app.services import runtime_service

        events = runtime_service.list_events(limit=5000)
    except Exception:
        return False
    for event in events:
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("tracking_kind") or "").strip() != "agent_task_completion":
            continue
        if str(metadata.get("task_id") or "").strip() != task_id:
            continue
        if str(metadata.get("task_final_status") or "").strip() != final_status:
            continue
        return True
    return False


def _record_completion_tracking_event(task: dict[str, Any]) -> None:
    status_value = task.get("status")
    final_status = status_value.value if hasattr(status_value, "value") else str(status_value or "")
    if final_status not in {"completed", "failed"}:
        return

    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return
    if _has_completion_tracking_event(task_id, final_status):
        return

    command = str(task.get("command") or "").strip()
    command_sha = hashlib.sha256(command.encode("utf-8")).hexdigest() if command else ""
    worker_id = _normalize_worker_id(task.get("claimed_by"))
    executor = _derive_task_executor(task)
    runtime_ms = _task_duration_ms(task)
    status_code = 200 if final_status == "completed" else 500

    try:
        from app.services import runtime_service

        runtime_service.record_event(
            RuntimeEventCreate(
                source="worker",
                endpoint="tool:agent-task-completion",
                method="RUN",
                status_code=status_code,
                runtime_ms=runtime_ms,
                idea_id="coherence-network-agent-pipeline",
                metadata={
                    "task_id": task_id,
                    "task_type": str(task.get("task_type") or ""),
                    "task_final_status": final_status,
                    "model": str(task.get("model") or "unknown"),
                    "worker_id": worker_id,
                    "agent_id": "openai-codex"
                    if worker_id == "openai-codex" or worker_id.startswith("openai-codex:")
                    else worker_id,
                    "executor": executor,
                    "is_openai_codex": worker_id == "openai-codex"
                    or worker_id.startswith("openai-codex:"),
                    "tracking_kind": "agent_task_completion",
                    "repeatable_tool_name": "agent_task_completion",
                    "repeatable_tool_call": command or "PATCH /api/agent/tasks/{task_id}",
                    "repeatable_tool_call_sha256": command_sha,
                    "repeatable_replay_hint": command
                    or "Replay by patching the task to completed/failed with the same task id.",
                },
            )
        )
    except Exception:
        # Tracking should never block task state transitions.
        return


def _claim_running_task(task: dict[str, Any], worker_id: str | None) -> None:
    now = _now()
    claimant = _normalize_worker_id(worker_id)
    current_status = task.get("status")
    existing_claimant = task.get("claimed_by")

    if current_status in (TaskStatus.PENDING, TaskStatus.NEEDS_DECISION):
        task["status"] = TaskStatus.RUNNING
        if task.get("started_at") is None:
            task["started_at"] = now
        if not existing_claimant:
            task["claimed_by"] = claimant
            task["claimed_at"] = now
        elif existing_claimant != claimant:
            raise TaskClaimConflictError(
                f"Task already claimed by {existing_claimant}",
                claimed_by=existing_claimant,
            )
        return

    if current_status == TaskStatus.RUNNING:
        if existing_claimant and existing_claimant != claimant:
            raise TaskClaimConflictError(
                f"Task already running by {existing_claimant}",
                claimed_by=existing_claimant,
            )
        if not existing_claimant:
            task["claimed_by"] = claimant
            task["claimed_at"] = now
        if task.get("started_at") is None:
            task["started_at"] = now
        return

    raise TaskClaimConflictError(
        f"Task is not claimable from status {_status_value(current_status)}",
        claimed_by=existing_claimant,
    )


def _build_command(
    direction: str, task_type: TaskType, executor: str = "claude"
) -> str:
    """Build command for task. executor: 'claude' (default), 'cursor', or 'openclaw'."""
    if executor == "cursor":
        template = _cursor_command_template(task_type)
    elif executor == "openclaw":
        template = _openclaw_command_template(task_type)
    else:
        template = COMMAND_TEMPLATES[task_type]
    # Escape direction for shell (double-quoted string)
    escaped = direction.replace("\\", "\\\\").replace('"', '\\"')
    return template.replace("{{direction}}", escaped)


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    _ensure_store_loaded()
    task_id = _generate_id()
    ctx = dict(data.context or {}) if isinstance(data.context, dict) else {}
    executor, policy_meta = _select_executor(data.task_type, data.direction, ctx)
    if policy_meta.get("policy_applied"):
        ctx["executor_policy"] = policy_meta
    if "task_fingerprint" in policy_meta:
        ctx.setdefault("task_fingerprint", policy_meta["task_fingerprint"])
    ctx["executor"] = executor
    primary_agent = AGENT_BY_TASK_TYPE.get(data.task_type)
    guard_agents = GUARD_AGENTS_BY_TASK_TYPE.get(data.task_type, [])
    if primary_agent:
        ctx["task_agent"] = primary_agent
    if guard_agents:
        ctx["guard_agents"] = list(guard_agents)

    model, tier = ROUTING[data.task_type]
    if executor == "cursor":
        model = f"cursor/{_CURSOR_MODEL_BY_TYPE[data.task_type]}"
        tier = "cursor"
    elif executor == "openclaw":
        model = f"openclaw/{_OPENCLAW_MODEL_BY_TYPE[data.task_type]}"
        tier = "openclaw"
    # Smoke test: context.command_override runs raw bash, bypassing Claude
    command = (
        (data.context or {}).get("command_override")
        if isinstance(data.context, dict)
        else None
    )
    if not command:
        direction = _with_agent_roles(
            data.direction,
            data.task_type,
            primary_agent=primary_agent,
            guard_agents=guard_agents,
        )
        command = _build_command(direction, data.task_type, executor=executor)
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
        "context": ctx,
        "progress_pct": None,
        "current_step": None,
        "decision_prompt": None,
        "decision": None,
        "claimed_by": None,
        "claimed_at": None,
        "created_at": now,
        "updated_at": None,
        "tier": tier,
    }
    _store[task_id] = task
    _save_store_to_disk()
    return task


def get_agent_integration_status() -> dict[str, Any]:
    """Report role-agent coverage, executor availability, and integration gaps."""
    report = _integration_gaps()
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


def get_task(task_id: str) -> Optional[dict]:
    """Get task by id."""
    _ensure_store_loaded()
    return _store.get(task_id)


def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple:
    """List tasks with optional filters. Sorted by created_at descending (newest first)."""
    _ensure_store_loaded()
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
    worker_id: Optional[str] = None,
) -> Optional[dict]:
    """Update task. Returns updated task or None if not found.
    When decision is present and task is needs_decision, set status→running and store decision.
    Note: Caller should trigger Telegram alert for needs_decision/failed (see router).
    """
    _ensure_store_loaded()
    task = _store.get(task_id)
    if task is None:
        return None

    decision_promotes_to_running = decision is not None and task.get("status") == TaskStatus.NEEDS_DECISION
    if decision_promotes_to_running:
        _claim_running_task(task, worker_id)
        task["decision"] = decision

    if status is not None:
        if status == TaskStatus.RUNNING:
            _claim_running_task(task, worker_id)
        else:
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
    _record_completion_tracking_event(task)
    _save_store_to_disk()
    return task


def get_attention_tasks(limit: int = 20) -> Tuple[List[dict], int]:
    """List tasks with status needs_decision or failed (for /attention)."""
    _ensure_store_loaded()
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
    _ensure_store_loaded()
    items = list(_store.values())
    by_status: dict[str, int] = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status}


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention (for /status and alerts)."""
    _ensure_store_loaded()
    items = list(_store.values())
    by_status = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    needs = [t for t in items if t["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)]
    return {"by_status": by_status, "needs_attention": needs, "total": len(items)}


def get_route(task_type: TaskType, executor: str = "claude") -> dict[str, Any]:
    """Return routing info for a task type (no persistence). executor: claude|cursor|openclaw."""
    executor = (executor or "auto").strip().lower()
    if executor == "auto":
        executor = _cheap_executor_default()
    executor = _normalize_executor(executor, default="claude")
    if executor == "cursor":
        model = f"cursor/{_CURSOR_MODEL_BY_TYPE[task_type]}"
        template = _cursor_command_template(task_type)
        tier = "cursor"
    elif executor == "openclaw":
        model = f"openclaw/{_OPENCLAW_MODEL_BY_TYPE[task_type]}"
        template = _openclaw_command_template(task_type)
        tier = "openclaw"
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


def _metadata_text(value: Any, default: str = "unknown") -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or default
    if value is None:
        return default
    cleaned = str(value).strip()
    return cleaned or default


def _metadata_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _execution_usage_summary(completed_or_failed_task_ids: list[str]) -> dict[str, Any]:
    tracked_task_ids: set[str] = set()
    by_executor: dict[str, dict[str, int]] = {}
    by_agent: dict[str, dict[str, int]] = {}
    by_tool: dict[str, dict[str, int | float]] = {}
    recent_runs: list[dict[str, Any]] = []
    tracked_runs = 0
    failed_runs = 0
    codex_runs = 0

    try:
        from app.services import runtime_service

        events = runtime_service.list_events(limit=2000)
    except Exception:
        events = []

    for event in events:
        if str(getattr(event, "source", "")).strip() != "worker":
            continue
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        task_id = _metadata_text(metadata.get("task_id"), default="")
        if not task_id:
            continue

        tracked_runs += 1
        tracked_task_ids.add(task_id)

        executor = _metadata_text(metadata.get("executor"))
        agent_id = _metadata_text(metadata.get("agent_id"), default="")
        if not agent_id:
            agent_id = _metadata_text(metadata.get("worker_id"))
        is_openai_codex = _metadata_bool(metadata.get("is_openai_codex")) or (
            agent_id.lower() == "openai-codex"
        )
        if is_openai_codex:
            codex_runs += 1

        status_key = "failed" if int(getattr(event, "status_code", 0)) >= 400 else "completed"
        if status_key == "failed":
            failed_runs += 1

        endpoint = _metadata_text(getattr(event, "endpoint", ""), default="unknown")
        endpoint_norm = endpoint.lstrip("/")
        tool_name = (
            endpoint_norm.split("tool:", 1)[1].strip()
            if endpoint_norm.startswith("tool:")
            else endpoint_norm
        )
        if not tool_name:
            tool_name = "unknown"

        if executor not in by_executor:
            by_executor[executor] = {"count": 0, "completed": 0, "failed": 0}
        by_executor[executor]["count"] += 1
        by_executor[executor][status_key] += 1

        if agent_id not in by_agent:
            by_agent[agent_id] = {"count": 0, "completed": 0, "failed": 0}
        by_agent[agent_id]["count"] += 1
        by_agent[agent_id][status_key] += 1

        if tool_name not in by_tool:
            by_tool[tool_name] = {"count": 0, "completed": 0, "failed": 0}
        by_tool[tool_name]["count"] += 1
        by_tool[tool_name][status_key] += 1

        recent_runs.append(
            {
                "event_id": getattr(event, "id", ""),
                "task_id": task_id,
                "endpoint": endpoint,
                "tool": tool_name,
                "status_code": int(getattr(event, "status_code", 0)),
                "executor": executor,
                "agent_id": agent_id,
                "is_openai_codex": is_openai_codex,
                "runtime_ms": float(getattr(event, "runtime_ms", 0.0)),
                "recorded_at": (
                    getattr(event, "recorded_at").isoformat()
                    if hasattr(getattr(event, "recorded_at"), "isoformat")
                    else str(getattr(event, "recorded_at", ""))
                ),
            }
        )

    completed_or_failed_set = {tid for tid in completed_or_failed_task_ids if tid}
    tracked_completed_or_failed = completed_or_failed_set.intersection(tracked_task_ids)
    completed_or_failed_count = len(completed_or_failed_set)
    tracked_count = len(tracked_completed_or_failed)
    coverage_rate = 1.0 if completed_or_failed_count == 0 else round(tracked_count / completed_or_failed_count, 4)
    success_runs = max(0, tracked_runs - failed_runs)
    success_rate = 1.0 if tracked_runs == 0 else round(success_runs / tracked_runs, 4)

    for values in by_tool.values():
        total = int(values.get("count", 0) or 0)
        failures = int(values.get("failed", 0) or 0)
        successes = max(0, total - failures)
        values["success_rate"] = 1.0 if total == 0 else round(successes / total, 4)

    return {
        "tracked_runs": tracked_runs,
        "failed_runs": failed_runs,
        "success_runs": success_runs,
        "success_rate": success_rate,
        "codex_runs": codex_runs,
        "by_executor": by_executor,
        "by_agent": by_agent,
        "by_tool": by_tool,
        "coverage": {
            "completed_or_failed_tasks": completed_or_failed_count,
            "tracked_task_runs": tracked_count,
            "coverage_rate": coverage_rate,
            "untracked_task_ids": sorted(completed_or_failed_set - tracked_completed_or_failed),
        },
        "recent_runs": recent_runs[:50],
    }


def get_usage_summary() -> dict[str, Any]:
    """Per-model usage derived from tasks (for /usage and API)."""
    _ensure_store_loaded()
    by_model: dict[str, dict[str, Any]] = {}
    completed_or_failed_task_ids: list[str] = []
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
        if s in {"completed", "failed"}:
            completed_or_failed_task_ids.append(str(t.get("id", "")).strip())
    return {
        "by_model": by_model,
        "routing": {t.value: {"model": ROUTING[t][0], "tier": ROUTING[t][1]} for t in TaskType},
        "execution": _execution_usage_summary(completed_or_failed_task_ids),
    }


def get_visibility_summary() -> dict[str, Any]:
    """Combined pipeline + usage visibility with remaining tracking gap."""
    pipeline = get_pipeline_status()
    usage = get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    coverage = execution.get("coverage") if isinstance(execution.get("coverage"), dict) else {}

    untracked_ids = coverage.get("untracked_task_ids")
    if not isinstance(untracked_ids, list):
        untracked_ids = []
    normalized_untracked_ids = [
        str(task_id).strip() for task_id in untracked_ids if str(task_id).strip()
    ]

    coverage_rate = float(coverage.get("coverage_rate", 0.0) or 0.0)
    remaining_to_full_coverage = len(normalized_untracked_ids)
    if remaining_to_full_coverage == 0 and coverage_rate >= 1.0:
        health = "green"
    elif coverage_rate >= 0.7:
        health = "yellow"
    else:
        health = "red"

    running = pipeline.get("running") if isinstance(pipeline.get("running"), list) else []
    pending = pipeline.get("pending") if isinstance(pipeline.get("pending"), list) else []
    recent_completed = (
        pipeline.get("recent_completed")
        if isinstance(pipeline.get("recent_completed"), list)
        else []
    )
    attention = pipeline.get("attention") if isinstance(pipeline.get("attention"), dict) else {}
    attention_flags = attention.get("flags") if isinstance(attention.get("flags"), list) else []

    return {
        "pipeline": {
            "running_count": len(running),
            "pending_count": len(pending),
            "recent_completed_count": len(recent_completed),
            "running_by_phase": pipeline.get("running_by_phase", {}),
            "attention_flags": attention_flags,
        },
        "usage": usage,
        "remaining_usage": {
            "coverage_rate": coverage_rate,
            "remaining_to_full_coverage": remaining_to_full_coverage,
            "untracked_task_ids": normalized_untracked_ids,
            "health": health,
        },
    }


def find_active_task_by_fingerprint(task_fingerprint: str) -> dict[str, Any] | None:
    _ensure_store_loaded()
    fingerprint = (task_fingerprint or "").strip()
    if not fingerprint:
        return None
    for task in _store.values():
        if not _is_active_status(task.get("status")):
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if context.get("task_fingerprint") == fingerprint:
            return task
    return None


def find_active_task_by_session_key(session_key: str) -> dict[str, Any] | None:
    _ensure_store_loaded()
    key = (session_key or "").strip()
    if not key:
        return None
    for task in _store.values():
        if not _is_active_status(task.get("status")):
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if str(context.get("session_key") or "").strip() == key:
            return task
    return None


def upsert_active_task(
    *,
    session_key: str,
    direction: str,
    task_type: TaskType,
    worker_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Ensure a running task exists for a unique session key. Returns (task, created)."""
    _ensure_store_loaded()
    normalized_key = (session_key or "").strip()
    if not normalized_key:
        raise ValueError("session_key is required")

    existing = find_active_task_by_session_key(normalized_key)
    if existing is not None:
        _claim_running_task(existing, worker_id)
        existing["updated_at"] = _now()
        _save_store_to_disk()
        return existing, False

    payload_context = dict(context or {})
    payload_context["session_key"] = normalized_key
    payload_context.setdefault("source", "external_active_session")
    created = create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=task_type,
            context=payload_context,
        )
    )
    _claim_running_task(created, worker_id)
    created["updated_at"] = _now()
    _save_store_to_disk()
    return created, True


def get_pipeline_status(now_utc=None) -> dict[str, Any]:
    """Pipeline visibility: running, pending with wait times, recent completed with duration."""
    _ensure_store_loaded()
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
            "claimed_by": t.get("claimed_by"),
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
    _ensure_store_loaded()
    _store.clear()
    _save_store_to_disk()
