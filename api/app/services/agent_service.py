"""Agent orchestration: routing and task tracking."""

import hashlib
import json
import os
import re
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.models.runtime import RuntimeEventCreate
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_routing_service as routing_service
from app.services import agent_task_store_service

# Routing decisions and provider classification live in agent_routing_service.
ROUTING = routing_service.ROUTING

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
_COMMAND_LOCAL_AGENT = 'claude -p "{{direction}}" --dangerously-skip-permissions'
_COMMAND_HEAL = 'claude -p "{{direction}}" --dangerously-skip-permissions'

# Cursor CLI: agent "direction" --model X (headless, uses Cursor auth)
_CURSOR_MODEL_BY_TYPE = routing_service.CURSOR_MODEL_BY_TYPE
_OPENCLAW_MODEL_BY_TYPE = routing_service.OPENCLAW_MODEL_BY_TYPE

try:
    _TARGET_STATE_DEFAULT_WINDOW_SEC = int(str(os.environ.get("AGENT_OBSERVATION_WINDOW_SEC", "900")).strip())
except ValueError:
    _TARGET_STATE_DEFAULT_WINDOW_SEC = 900
_TARGET_STATE_DEFAULT_WINDOW_SEC = max(30, min(_TARGET_STATE_DEFAULT_WINDOW_SEC, 7 * 24 * 60 * 60))
_TARGET_STATE_MAX_TEXT = 600
_AGENT_GRAPH_STATE_SCHEMA_ID = "coherence_agent_graph_state_v1"
_AGENT_GRAPH_STATE_REQUIRED_FIELDS: tuple[str, ...] = ("task_id", "task_type", "phase", "direction")
_AGENT_GRAPH_STATE_ALLOWED_PHASES: tuple[str, ...] = (
    "queued",
    "running",
    "needs_decision",
    "completed",
    "failed",
)
# Heuristics to detect prompts that require repository-local context.
_REPO_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bthis repo\b", re.IGNORECASE),
    re.compile(r"\bthis repository\b", re.IGNORECASE),
    re.compile(r"\bcodebase\b", re.IGNORECASE),
    re.compile(r"\bin (?:the )?repo\b", re.IGNORECASE),
    re.compile(r"\bAGENTS\.md\b", re.IGNORECASE),
    re.compile(r"\bCLAUDE\.md\b", re.IGNORECASE),
    re.compile(r"\bdocs/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"\bapi/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"\bweb/[A-Za-z0-9_.\-\/]+\b", re.IGNORECASE),
    re.compile(r"`[^`]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml)`", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_.\-]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml)\b", re.IGNORECASE),
)


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
    return routing_service.normalize_executor(value, default=default)


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
        for candidate in ("openclaw", "codex"):
            if shutil.which(candidate):
                return candidate
        configured = os.environ.get("OPENCLAW_EXECUTABLE")
        return configured.strip() if configured else "openclaw"
    return "claude"


def _executor_available(executor: str) -> bool:
    return shutil.which(_executor_binary_name(executor)) is not None


def _allow_unavailable_explicit_executor() -> bool:
    raw = os.environ.get("AGENT_EXECUTOR_ALLOW_UNAVAILABLE_EXPLICIT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _first_available_executor(preferred: list[str]) -> str:
    for executor in preferred:
        candidate = _normalize_executor(executor, default="")
        if candidate and _executor_available(candidate):
            return candidate
    configured_default = _normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="")
    if configured_default and _executor_available(configured_default):
        return configured_default
    # Final deterministic safety net: prefer codex/openclaw when available.
    for candidate in ("openclaw", "cursor", "claude"):
        if _executor_available(candidate):
            return candidate
    return _normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="openclaw")


def _executor_fallback_candidates() -> list[str]:
    return [
        _cheap_executor_default(),
        _escalation_executor_default(),
        "openclaw",
        "cursor",
        "claude",
    ]


def _select_executor_with_retry_policy(
    *,
    task_fingerprint: str,
    context: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
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
    reason = "retry_threshold" if should_escalate and effective_retry_count >= retry_threshold else (
        "failure_threshold" if should_escalate else "cheap_default"
    )
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


def _is_repo_scoped_question(direction: str, context: dict[str, Any]) -> bool:
    scope_hint = str(context.get("question_scope") or context.get("scope") or "").strip().lower()
    if scope_hint in {"repo", "repository", "codebase"}:
        return True
    if scope_hint in {"open", "general"}:
        return False

    text = direction.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _REPO_SCOPE_PATTERNS)


def _repo_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_REPO_DEFAULT")
    if configured:
        return _normalize_executor(configured, default="cursor")
    return "cursor"


def _open_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT")
    if configured:
        return _normalize_executor(configured, default="openclaw")
    return "openclaw"


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
        if _executor_available(explicit):
            return explicit, {"policy_applied": False, "reason": "explicit_executor"}
        if _allow_unavailable_explicit_executor():
            return explicit, {
                "policy_applied": True,
                "reason": "explicit_executor_forced",
                "explicit_executor": explicit,
                "availability": "unavailable_on_api_node",
            }
        fallback = _first_available_executor(_executor_fallback_candidates())
        return fallback, {
            "policy_applied": True,
            "reason": "explicit_executor_unavailable",
            "explicit_executor": explicit,
            "fallback_executor": fallback,
        }

    if not _executor_policy_enabled():
        default_executor = _normalize_executor(os.environ.get("AGENT_EXECUTOR_DEFAULT"), default="claude")
        if _executor_available(default_executor):
            return default_executor, {"policy_applied": False, "reason": "policy_disabled"}
        fallback = _first_available_executor(_executor_fallback_candidates())
        return fallback, {
            "policy_applied": True,
            "reason": "policy_disabled_default_unavailable",
            "default_executor": default_executor,
            "fallback_executor": fallback,
        }

    task_fingerprint = str(context.get("task_fingerprint") or "").strip()
    if not task_fingerprint:
        task_fingerprint = _task_fingerprint(task_type, direction)
        context["task_fingerprint"] = task_fingerprint

    if _is_repo_scoped_question(direction, context):
        selected = _first_available_executor([
            _repo_question_executor_default(),
            "cursor",
            "claude",
            "openclaw",
        ])
        return selected, {
            "policy_applied": True,
            "reason": "repo_scoped_question",
            "task_fingerprint": task_fingerprint,
            "repo_executor_preference": _repo_question_executor_default(),
        }

    selected_open = _first_available_executor([
        _open_question_executor_default(),
        "openclaw",
        "cursor",
        "claude",
    ])
    if selected_open == "openclaw":
        return selected_open, {
            "policy_applied": True,
            "reason": "open_question_default",
            "task_fingerprint": task_fingerprint,
            "open_question_executor": selected_open,
        }
    return _select_executor_with_retry_policy(
        task_fingerprint=task_fingerprint,
        context=context,
    )


def _command_template(task_type: TaskType) -> str:
    agent = AGENT_BY_TASK_TYPE.get(task_type)
    if agent:
        return _COMMAND_LOCAL_AGENT.replace("{{agent}}", agent)
    return _COMMAND_HEAL


def _cursor_command_template(task_type: TaskType) -> str:
    """Cursor CLI template with explicit model."""
    return routing_service.cursor_command_template(task_type)


def _openclaw_command_template(task_type: TaskType) -> str:
    """OpenClaw CLI template configurable via env; must include {{direction}}."""
    return routing_service.openclaw_command_template(task_type)


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
        "claude": _executor_available("claude"),
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
_store_loaded_test_context: str | None = None
_store_loaded_includes_output = False
_store_loaded_at_monotonic = 0.0
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


def _db_store_reload_ttl_seconds() -> float:
    raw = os.getenv("AGENT_TASKS_DB_RELOAD_TTL_SECONDS", "120").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 30.0
    return max(0.0, min(value, 300.0))


def _max_task_output_chars() -> int:
    raw = os.getenv("AGENT_TASK_OUTPUT_MAX_CHARS", "4000").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 4000
    return max(500, min(value, 200000))


def _sanitize_task_output(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    max_chars = _max_task_output_chars()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


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
    if not all(isinstance(v, str) and v.strip() for v in (task_id, direction, model)):
        return None
    if not isinstance(command, str):
        command = ""

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
        "command": command.strip() or "PATCH /api/agent/tasks/{task_id}",
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


def _load_store_from_disk(*, include_output: bool = True) -> dict[str, dict[str, Any]]:
    if not _persistence_enabled():
        return {}
    if agent_task_store_service.enabled():
        loaded: dict[str, dict[str, Any]] = {}
        for raw in agent_task_store_service.load_tasks(include_output=include_output):
            task = _deserialize_task(raw)
            if not task:
                continue
            loaded[task["id"]] = task
        return loaded
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
    if agent_task_store_service.enabled():
        for task in _store.values():
            agent_task_store_service.upsert_task(_serialize_task(task))
        return
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tasks": [_serialize_task(task) for task in _store.values()],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_store_loaded(*, force_reload: bool = False, include_output: bool = False) -> None:
    global _store_loaded, _store_loaded_path, _store_loaded_test_context
    global _store_loaded_includes_output, _store_loaded_at_monotonic
    current_path = str(_store_path())
    current_test = os.getenv("PYTEST_CURRENT_TEST")

    # Keep pytest test cases isolated even within a single process:
    # each test gets a fresh in-memory task store when persistence is off.
    if not _persistence_enabled() and current_test and _store_loaded_test_context != current_test:
        _store.clear()
        _store_loaded = False
        _store_loaded_path = None
        _store_loaded_test_context = current_test
        _store_loaded_includes_output = False
        _store_loaded_at_monotonic = 0.0

    if agent_task_store_service.enabled():
        now = time.monotonic()
        need_upgrade = include_output and not _store_loaded_includes_output
        expired = (now - _store_loaded_at_monotonic) >= _db_store_reload_ttl_seconds()
        should_reload = force_reload or not _store_loaded or need_upgrade or expired
        if should_reload:
            _store.clear()
            _store.update(_load_store_from_disk(include_output=include_output))
            _store_loaded = True
            _store_loaded_path = current_path
            _store_loaded_test_context = current_test
            _store_loaded_includes_output = include_output
            _store_loaded_at_monotonic = now
        return

    if _store_loaded and _store_loaded_path == current_path and not force_reload:
        return
    _store.clear()
    _store.update(_load_store_from_disk(include_output=include_output))
    _store_loaded = True
    _store_loaded_path = current_path
    _store_loaded_test_context = current_test
    _store_loaded_includes_output = include_output
    _store_loaded_at_monotonic = time.monotonic()


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
    if (
        model.startswith("openclaw/")
        or model.startswith("clawwork/")
        or command.startswith("openclaw ")
        or command.startswith("clawwork ")
    ):
        return "openclaw"
    if command.startswith("aider "):
        return "aider"
    if command.startswith("claude "):
        return "claude"
    return "unknown"


def _derive_task_provider(task: dict[str, Any], executor: str) -> str:
    provider, _billing_provider, _is_paid_provider = routing_service.classify_provider(
        executor=executor,
        model=str(task.get("model") or ""),
        command=str(task.get("command") or ""),
        worker_id=_normalize_worker_id(task.get("claimed_by")),
    )
    return provider


def _task_duration_ms(task: dict[str, Any]) -> float:
    started = task.get("started_at")
    created = task.get("created_at")
    updated = task.get("updated_at") or _now()
    start_ts = started or created
    if hasattr(start_ts, "timestamp") and hasattr(updated, "timestamp"):
        seconds = max(0.0, float((updated - start_ts).total_seconds()))
        return max(0.1, round(seconds * 1000.0, 4))
    return 0.1


def _phase_for_status(status: Any) -> str:
    value = _status_value(status).strip().lower()
    if value in _AGENT_GRAPH_STATE_ALLOWED_PHASES:
        return value
    return "queued"


def _build_agent_graph_state(task: dict[str, Any], *, phase: str | None = None) -> dict[str, Any]:
    status_phase = phase.strip().lower() if isinstance(phase, str) and phase.strip() else _phase_for_status(task.get("status"))
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}
    attempt = context.get("retry_count", 0)
    try:
        normalized_attempt = max(0, int(attempt))
    except (TypeError, ValueError):
        normalized_attempt = 0
    return {
        "task_id": str(task.get("id") or "").strip(),
        "task_type": _status_value(task.get("task_type")).strip(),
        "phase": status_phase,
        "direction": str(task.get("direction") or "").strip(),
        "attempt": normalized_attempt,
        "model": str(task.get("model") or "").strip(),
        "provider": str(route_decision.get("provider") or "").strip(),
        "route_decision": route_decision,
    }


def _validate_agent_graph_state_schema(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _AGENT_GRAPH_STATE_REQUIRED_FIELDS:
        value = state.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing_or_invalid_required_field:{field}")

    phase = str(state.get("phase") or "").strip().lower()
    if phase and phase not in _AGENT_GRAPH_STATE_ALLOWED_PHASES:
        errors.append(f"invalid_phase:{phase}")

    if "attempt" in state:
        attempt = state.get("attempt")
        if not isinstance(attempt, int) or attempt < 0:
            errors.append("invalid_attempt_non_negative_int_required")

    route_decision = state.get("route_decision")
    if route_decision is not None and not isinstance(route_decision, dict):
        errors.append("invalid_route_decision_object_required")
    return errors


def _apply_agent_graph_state_contract(task: dict[str, Any], *, preferred_state: dict[str, Any] | None = None) -> None:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    candidate = preferred_state if isinstance(preferred_state, dict) else _build_agent_graph_state(task)
    errors = _validate_agent_graph_state_schema(candidate)
    context["agent_graph_state_schema"] = {
        "schema_id": _AGENT_GRAPH_STATE_SCHEMA_ID,
        "required_fields": list(_AGENT_GRAPH_STATE_REQUIRED_FIELDS),
        "allowed_phases": list(_AGENT_GRAPH_STATE_ALLOWED_PHASES),
    }
    context["agent_graph_state"] = candidate
    context["agent_graph_state_errors"] = errors
    if errors:
        context["agent_graph_state_status"] = "invalid"
        context["agent_graph_state_last_error"] = (
            "State schema validation failed; update task context/phase before retry."
        )
    else:
        context["agent_graph_state_status"] = "valid"
        context.pop("agent_graph_state_last_error", None)
    task["context"] = context


def _task_output_text(task: dict[str, Any]) -> str:
    output = task.get("output")
    if isinstance(output, str):
        return output
    if output is None and agent_task_store_service.enabled():
        task_id = str(task.get("id") or "").strip()
        if task_id:
            raw = agent_task_store_service.load_task(task_id, include_output=True)
            if isinstance(raw, dict):
                loaded = raw.get("output")
                if isinstance(loaded, str):
                    task["output"] = loaded
                    return loaded
    return str(output or "")


def _context_failure_detail(context: dict[str, Any], key: str) -> str | None:
    value = context.get(key)
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, dict):
        for nested_key in ("error", "message", "detail", "reason"):
            nested = value.get(nested_key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        return None
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "; ".join(parts) if parts else None
    return None


def _derive_failed_task_output(task: dict[str, Any]) -> tuple[str, str]:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    if isinstance(context, dict):
        for key in (
            "error",
            "last_error",
            "failure_reason",
            "runner_error",
            "exception",
            "details",
            "message",
            "agent_graph_state_last_error",
        ):
            detail = _context_failure_detail(context, key)
            if detail:
                return f"Failure diagnostic (context.{key}): {detail}", f"context.{key}"

        graph_errors = context.get("agent_graph_state_errors")
        if isinstance(graph_errors, list):
            normalized = [str(item).strip() for item in graph_errors if str(item).strip()]
            if normalized:
                joined = "; ".join(normalized[:3])
                return (
                    f"Failure diagnostic (context.agent_graph_state_errors): {joined}",
                    "context.agent_graph_state_errors",
                )

    task_type = _status_value(task.get("task_type")) or "unknown"
    worker = _normalize_worker_id(task.get("claimed_by"))
    step = str(task.get("current_step") or "").strip() or "unknown"
    return (
        (
            "Task failed without explicit error output. "
            f"task_type={task_type}; worker={worker}; step={step}."
        ),
        "fallback",
    )


def _ensure_failed_task_diagnostics(task: dict[str, Any]) -> None:
    if _status_value(task.get("status")) != "failed":
        return

    output_text = _task_output_text(task).strip()
    source = "output"
    if not output_text:
        synthesized, source = _derive_failed_task_output(task)
        task["output"] = _sanitize_task_output(synthesized)
        output_text = _task_output_text(task).strip()

    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    next_context = dict(context) if isinstance(context, dict) else {}
    next_context["failure_reason_bucket"] = _failure_reason_bucket(task)
    next_context["failure_diagnostics_source"] = source
    next_context["failure_diagnostics_present"] = bool(output_text)
    task["context"] = next_context


def _load_task_from_db(task_id: str, *, include_output: bool) -> dict[str, Any] | None:
    if not agent_task_store_service.enabled():
        return None
    raw = agent_task_store_service.load_task(task_id, include_output=include_output)
    if not isinstance(raw, dict):
        return None
    task = _deserialize_task(raw)
    if task is None:
        return None
    _store[task["id"]] = task
    return task


def _has_completion_tracking_event(task_id: str, final_status: str) -> bool:
    try:
        from app.services import runtime_service

        events = runtime_service.list_events(limit=5000, source="worker")
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
    provider, billing_provider, is_paid_provider = routing_service.classify_provider(
        executor=executor,
        model=str(task.get("model") or ""),
        command=command,
        worker_id=worker_id,
    )
    runtime_ms = _task_duration_ms(task)
    status_code = 200 if final_status == "completed" else 500
    task_context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = (
        task_context.get("route_decision")
        if isinstance(task_context.get("route_decision"), dict)
        else {}
    )
    normalized_response_call = (
        task_context.get("normalized_response_call")
        if isinstance(task_context.get("normalized_response_call"), dict)
        else {}
    )
    request_schema = str(
        route_decision.get("request_schema")
        or normalized_response_call.get("request_schema")
        or "open_responses_v1"
    ).strip()
    normalized_model = str(
        normalized_response_call.get("model")
        or routing_service.normalize_open_responses_model(str(task.get("model") or ""))
    ).strip()
    normalized_provider = str(
        normalized_response_call.get("provider")
        or route_decision.get("provider")
        or provider
    ).strip()

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
                    "provider": provider,
                    "billing_provider": billing_provider,
                    "is_paid_provider": is_paid_provider,
                    "is_openai_codex": worker_id == "openai-codex"
                    or worker_id.startswith("openai-codex:"),
                    "request_schema": request_schema,
                    "normalized_model": normalized_model,
                    "normalized_provider": normalized_provider,
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
    """Build command for task. executor: 'claude' (default), 'cursor', or 'openclaw' (clawwork alias)."""
    if executor == "cursor":
        template = _cursor_command_template(task_type)
    elif executor == "openclaw":
        template = _openclaw_command_template(task_type)
    elif executor == "claude":
        template = routing_service.claude_command_template(task_type)
    else:
        template = COMMAND_TEMPLATES[task_type]
    # Escape direction for shell in a double-quoted template placeholder.
    escaped = (
        direction.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    return template.replace("{{direction}}", escaped)


def _resolve_task_route(
    *,
    data: AgentTaskCreate,
    executor: str,
    policy_meta: dict[str, Any],
    ctx: dict[str, Any],
    primary_agent: str | None,
    guard_agents: list[str],
) -> tuple[str, str, str, dict[str, Any], dict[str, Any]]:
    route_info = routing_service.route_for_executor(
        data.task_type,
        executor,
        COMMAND_TEMPLATES[data.task_type],
    )
    model = str(route_info["model"])
    tier = str(route_info["tier"])
    command = (
        (data.context or {}).get("command_override")
        if isinstance(data.context, dict)
        else None
    )
    normalized_direction = data.direction
    if not command:
        direction = _with_agent_roles(
            data.direction,
            data.task_type,
            primary_agent=primary_agent,
            guard_agents=guard_agents,
        )
        normalized_direction = direction
        command = _build_command(direction, data.task_type, executor=executor)
        if ctx.get("model_override"):
            override = str(ctx["model_override"]).strip()
            command, applied_override = routing_service.apply_model_override(command, override)
            if applied_override:
                if executor == "openclaw":
                    model = f"openclaw/{applied_override}"
                elif executor == "cursor":
                    model = f"cursor/{applied_override}"
                else:
                    model = applied_override
        if "claude -p" in command and "--dangerously-skip-permissions" not in command:
            command = command.rstrip() + " --dangerously-skip-permissions"
    provider, billing_provider, is_paid_provider = routing_service.classify_provider(
        executor=executor,
        model=model,
        command=str(command),
        worker_id=None,
    )
    route_decision = {
        "executor": executor,
        "task_type": data.task_type.value,
        "tier": tier,
        "model": model,
        "provider": provider,
        "billing_provider": billing_provider,
        "is_paid_provider": is_paid_provider,
        "request_schema": "open_responses_v1",
        "policy": policy_meta,
    }
    normalized_response_call = routing_service.build_normalized_response_call(
        task_id="",
        executor=executor,
        provider=provider,
        model=model,
        direction=normalized_direction,
    )
    return model, tier, str(command), route_decision, normalized_response_call


def _apply_runner_auth_mode_defaults(ctx: dict[str, Any], executor: str) -> None:
    if executor != "openclaw":
        return
    current = str(ctx.get("runner_codex_auth_mode") or "").strip().lower()
    if current in {"api_key", "oauth", "auto"}:
        ctx["runner_codex_auth_mode"] = current
        return
    configured = str(os.environ.get("AGENT_TASK_DEFAULT_RUNNER_CODEX_AUTH_MODE", "api_key")).strip().lower()
    if configured not in {"api_key", "oauth", "auto"}:
        configured = "api_key"
    ctx["runner_codex_auth_mode"] = configured


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    _ensure_store_loaded(include_output=False)
    task_id = _generate_id()
    ctx = dict(data.context or {}) if isinstance(data.context, dict) else {}
    target_contract = _normalize_target_state_contract(
        direction=data.direction,
        task_type=data.task_type,
        target_state=data.target_state if data.target_state is not None else ctx.get("target_state"),
        success_evidence=(
            data.success_evidence if data.success_evidence is not None else ctx.get("success_evidence")
        ),
        abort_evidence=data.abort_evidence if data.abort_evidence is not None else ctx.get("abort_evidence"),
        observation_window_sec=(
            data.observation_window_sec
            if data.observation_window_sec is not None
            else ctx.get("observation_window_sec")
        ),
    )
    ctx.update(target_contract)
    ctx["target_state_contract"] = dict(target_contract)
    executor, policy_meta = _select_executor(data.task_type, data.direction, ctx)
    if policy_meta.get("policy_applied"):
        ctx["executor_policy"] = policy_meta
    if "task_fingerprint" in policy_meta:
        ctx.setdefault("task_fingerprint", policy_meta["task_fingerprint"])
    ctx["executor"] = executor
    _apply_runner_auth_mode_defaults(ctx, executor)
    primary_agent = AGENT_BY_TASK_TYPE.get(data.task_type)
    guard_agents = GUARD_AGENTS_BY_TASK_TYPE.get(data.task_type, [])
    if primary_agent:
        ctx["task_agent"] = primary_agent
    if guard_agents:
        ctx["guard_agents"] = list(guard_agents)

    model, tier, command, route_decision, normalized_response_call = _resolve_task_route(
        data=data,
        executor=executor,
        policy_meta=policy_meta,
        ctx=ctx,
        primary_agent=primary_agent,
        guard_agents=guard_agents,
    )
    normalized_response_call["task_id"] = task_id
    ctx["route_decision"] = route_decision
    ctx["normalized_response_call"] = normalized_response_call
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
    _apply_agent_graph_state_contract(task)
    _store[task_id] = task
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(task))
    else:
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
    if agent_task_store_service.enabled():
        loaded = _load_task_from_db(task_id, include_output=True)
        if loaded is not None:
            return loaded
    _ensure_store_loaded(include_output=True)
    task = _store.get(task_id)
    if task is not None:
        return task
    if os.getenv("PYTEST_CURRENT_TEST") and os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_IN_TESTS", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    # Fallback for multi-instance deploys: tasks may not be present on this instance's local store,
    # but completion tracking events are persisted in the runtime event store.
    try:
        from app.services import runtime_service

        events = runtime_service.list_events(limit=2000)
    except Exception:
        return None

    for event in events:
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("tracking_kind") or "").strip() != "agent_task_completion":
            continue
        if str(metadata.get("task_id") or "").strip() != task_id:
            continue
        # Minimal reconstruction for UI and diagnostics.
        status_raw = str(metadata.get("task_final_status") or "").strip()
        try:
            status = TaskStatus(status_raw) if status_raw else TaskStatus.COMPLETED
        except ValueError:
            status = TaskStatus.COMPLETED
        task_type_raw = str(metadata.get("task_type") or "").strip()
        try:
            task_type = TaskType(task_type_raw) if task_type_raw else TaskType.IMPL
        except ValueError:
            task_type = TaskType.IMPL
        recorded_at = getattr(event, "recorded_at", None) or _now()
        model = str(metadata.get("model") or "unknown").strip() or "unknown"
        command = str(metadata.get("repeatable_tool_call") or "").strip()
        direction = str(metadata.get("direction") or "").strip()
        if not direction and command:
            direction = command[:240]
        return {
            "id": task_id,
            "direction": direction or "(tracked completion)",
            "task_type": task_type,
            "status": status,
            "model": model,
            "command": command or "PATCH /api/agent/tasks/{task_id}",
            "started_at": None,
            "output": None,
            "context": {"source": "runtime_event_fallback"},
            "progress_pct": 100 if status == TaskStatus.COMPLETED else None,
            "current_step": "completed" if status == TaskStatus.COMPLETED else None,
            "decision_prompt": None,
            "decision": None,
            "claimed_by": str(metadata.get("worker_id") or metadata.get("agent_id") or "unknown"),
            "claimed_at": None,
            "created_at": recorded_at,
            "updated_at": recorded_at,
            "tier": str(metadata.get("provider") or "") or "unknown",
        }
    return None


def _should_backfill_runtime_tasks(existing_count: int) -> bool:
    fallback_mode = str(os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_MODE", "empty_only")).strip().lower()
    if fallback_mode in {"0", "off", "false", "disabled", "none"}:
        return False
    if fallback_mode in {"always", "all", "1", "on", "true"}:
        return True
    return existing_count == 0


def _runtime_fallback_events_for_tasks(existing_count: int) -> list[Any]:
    fallback_in_tests = os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_IN_TESTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if os.getenv("PYTEST_CURRENT_TEST") and not fallback_in_tests:
        return []
    if not _should_backfill_runtime_tasks(existing_count):
        return []
    try:
        from app.services import runtime_service

        runtime_fallback_limit = max(
            50,
            min(int(os.getenv("AGENT_TASKS_RUNTIME_FALLBACK_LIMIT", "200")), 5000),
        )
        return runtime_service.list_events(limit=runtime_fallback_limit)
    except Exception:
        return []


def _runtime_completion_event_to_task(event: Any, seen: set[str]) -> dict[str, Any] | None:
    metadata = getattr(event, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("tracking_kind") or "").strip() != "agent_task_completion":
        return None
    task_id = str(metadata.get("task_id") or "").strip()
    if not task_id or task_id in seen:
        return None
    status_raw = str(metadata.get("task_final_status") or "").strip()
    try:
        derived_status = TaskStatus(status_raw) if status_raw else TaskStatus.COMPLETED
    except ValueError:
        derived_status = TaskStatus.COMPLETED
    task_type_raw = str(metadata.get("task_type") or "").strip()
    try:
        derived_type = TaskType(task_type_raw) if task_type_raw else TaskType.IMPL
    except ValueError:
        derived_type = TaskType.IMPL
    recorded_at = getattr(event, "recorded_at", None) or _now()
    model = str(metadata.get("model") or "unknown").strip() or "unknown"
    command = str(metadata.get("repeatable_tool_call") or "").strip()
    direction = str(metadata.get("direction") or "").strip()
    if not direction and command:
        direction = command[:240]
    return {
        "id": task_id,
        "direction": direction or "(tracked completion)",
        "task_type": derived_type,
        "status": derived_status,
        "model": model,
        "command": command or "PATCH /api/agent/tasks/{task_id}",
        "started_at": None,
        "output": None,
        "context": {"source": "runtime_event_fallback"},
        "progress_pct": 100 if derived_status == TaskStatus.COMPLETED else None,
        "current_step": "completed" if derived_status == TaskStatus.COMPLETED else None,
        "decision_prompt": None,
        "decision": None,
        "claimed_by": str(metadata.get("worker_id") or metadata.get("agent_id") or "unknown"),
        "claimed_at": None,
        "created_at": recorded_at,
        "updated_at": recorded_at,
        "tier": str(metadata.get("provider") or "") or "unknown",
    }


def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple:
    """List tasks with optional filters. Sorted by created_at descending (newest first)."""
    if agent_task_store_service.enabled():
        status_value = status.value if isinstance(status, TaskStatus) else None
        task_type_value = task_type.value if isinstance(task_type, TaskType) else None
        rows, total = agent_task_store_service.load_tasks_page(
            status=status_value,
            task_type=task_type_value,
            limit=limit,
            offset=offset,
            include_output=False,
            include_command=False,
        )
        items: list[dict[str, Any]] = []
        for raw in rows:
            task = _deserialize_task(raw)
            if task is None:
                continue
            _store[task["id"]] = task
            items.append(task)
        # Runtime fallback only when the DB-backed task list is empty and unfiltered.
        if total == 0 and status is None and task_type is None and offset == 0:
            events = _runtime_fallback_events_for_tasks(0)
            seen: set[str] = {str(t.get("id") or "") for t in items if isinstance(t, dict)}
            for event in events:
                derived = _runtime_completion_event_to_task(event, seen)
                if derived is None:
                    continue
                items.append(derived)
                seen.add(str(derived.get("id") or ""))
            items.sort(key=lambda t: t["created_at"], reverse=True)
            items = items[:limit]
            total = len(items)
        return items, total

    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    events = _runtime_fallback_events_for_tasks(len(items))

    seen: set[str] = {str(t.get("id") or "") for t in items if isinstance(t, dict)}
    for event in events:
        derived = _runtime_completion_event_to_task(event, seen)
        if derived is None:
            continue
        items.append(derived)
        seen.add(str(derived.get("id") or ""))

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
    context: Optional[dict[str, Any]] = None,
    worker_id: Optional[str] = None,
) -> Optional[dict]:
    """Update task. Returns updated task or None if not found.
    When decision is present and task is needs_decision, set status→running and store decision.
    Note: Caller should trigger Telegram alert for needs_decision/failed (see router).
    """
    _ensure_store_loaded(include_output=False)
    task = _load_task_from_db(task_id, include_output=False) if agent_task_store_service.enabled() else None
    if task is None:
        task = _store.get(task_id)
    if task is None:
        return None
    previous_status_value = _status_value(task.get("status"))

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
        task["output"] = _sanitize_task_output(output)
    if progress_pct is not None:
        task["progress_pct"] = progress_pct
    if current_step is not None:
        task["current_step"] = current_step
    if decision_prompt is not None:
        task["decision_prompt"] = decision_prompt
    if decision is not None and task.get("decision") is None:
        task["decision"] = decision
    if context is not None:
        existing = task.get("context")
        if isinstance(existing, dict):
            next_context = dict(existing)
            next_context.update(context)
        else:
            next_context = dict(context)
        if any(
            key in next_context
            for key in ("target_state", "success_evidence", "abort_evidence", "observation_window_sec")
        ):
            normalized_contract = _normalize_target_state_contract(
                direction=str(task.get("direction") or ""),
                task_type=task.get("task_type") if isinstance(task.get("task_type"), TaskType) else TaskType.IMPL,
                target_state=next_context.get("target_state"),
                success_evidence=next_context.get("success_evidence"),
                abort_evidence=next_context.get("abort_evidence"),
                observation_window_sec=next_context.get("observation_window_sec"),
            )
            next_context.update(normalized_contract)
            next_context["target_state_contract"] = dict(normalized_contract)
        task["context"] = next_context
    preferred_graph_state = None
    task_context = task.get("context") if isinstance(task.get("context"), dict) else {}
    if isinstance(task_context.get("agent_graph_state"), dict):
        preferred_graph_state = dict(task_context.get("agent_graph_state") or {})
    _apply_agent_graph_state_contract(task, preferred_state=preferred_graph_state)
    _ensure_failed_task_diagnostics(task)
    task["updated_at"] = _now()
    _record_completion_tracking_event(task)
    current_status_value = _status_value(task.get("status"))
    if current_status_value == "failed" and previous_status_value != "failed":
        _record_task_failure_friction(task)
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(task))
    else:
        _save_store_to_disk()
    return task


def get_attention_tasks(limit: int = 20) -> Tuple[List[dict], int]:
    """List tasks with status needs_decision or failed (for /attention)."""
    if agent_task_store_service.enabled():
        rows, total = agent_task_store_service.load_attention_tasks(limit=limit)
        items: list[dict[str, Any]] = []
        for raw in rows:
            task = _deserialize_task(raw)
            if task is None:
                continue
            _store[task["id"]] = task
            items.append(task)
        return items, total
    _ensure_store_loaded(include_output=True)
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
    if agent_task_store_service.enabled():
        return agent_task_store_service.load_status_counts()
    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    by_status: dict[str, int] = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    return {"total": len(items), "by_status": by_status}


def get_review_summary() -> dict[str, Any]:
    """Summary of tasks needing attention (for /status and alerts)."""
    _ensure_store_loaded(include_output=False)
    items = list(_store.values())
    by_status = {}
    for t in items:
        s = t["status"].value if hasattr(t["status"], "value") else str(t["status"])
        by_status[s] = by_status.get(s, 0) + 1
    needs = [t for t in items if t["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)]
    return {"by_status": by_status, "needs_attention": needs, "total": len(items)}


def get_route(task_type: TaskType, executor: str = "claude") -> dict[str, Any]:
    """Return routing info for a task type (no persistence). executor: auto|claude|cursor|openclaw|clawwork."""
    executor = (executor or "auto").strip().lower()
    if executor == "auto":
        executor = _cheap_executor_default()
    return routing_service.route_for_executor(
        task_type,
        _normalize_executor(executor, default="claude"),
        COMMAND_TEMPLATES[task_type],
    )


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


def _normalize_evidence_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned[:_TARGET_STATE_MAX_TEXT])
    return out


def _normalize_observation_window(raw: Any) -> int:
    if isinstance(raw, bool):
        return _TARGET_STATE_DEFAULT_WINDOW_SEC
    if isinstance(raw, (int, float)):
        value = int(raw)
    elif isinstance(raw, str):
        value_text = raw.strip()
        value = int(value_text) if value_text.isdigit() else _TARGET_STATE_DEFAULT_WINDOW_SEC
    else:
        value = _TARGET_STATE_DEFAULT_WINDOW_SEC
    return max(30, min(value, 7 * 24 * 60 * 60))


def _normalize_target_state_contract(
    *,
    direction: str,
    task_type: TaskType,
    target_state: Any,
    success_evidence: Any,
    abort_evidence: Any,
    observation_window_sec: Any,
) -> dict[str, Any]:
    candidate = str(target_state or "").strip()
    if not candidate:
        direction_hint = " ".join((direction or "").split())[:220]
        base = f"{task_type.value} task reaches intended target state"
        candidate = f"{base}: {direction_hint}" if direction_hint else base
    target_state_value = candidate[:_TARGET_STATE_MAX_TEXT]
    success = _normalize_evidence_list(success_evidence)
    abort = _normalize_evidence_list(abort_evidence)
    window = _normalize_observation_window(observation_window_sec)
    return {
        "target_state": target_state_value,
        "success_evidence": success,
        "abort_evidence": abort,
        "observation_window_sec": window,
    }


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

        events = runtime_service.list_events(limit=5000, source="worker")
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
        provider = _metadata_text(metadata.get("provider"), default="")
        if not provider:
            if is_openai_codex:
                provider = "openai-codex"
            elif executor == "claude":
                provider = "claude"
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
                "provider": provider,
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


def _task_activity_time(task: dict[str, Any]) -> datetime | None:
    for key in ("updated_at", "created_at", "started_at"):
        value = task.get(key)
        if isinstance(value, datetime):
            return value
        parsed = _parse_dt(value)
        if parsed is not None:
            return parsed
    return None


def _is_host_runner_claimant(claimed_by: str) -> bool:
    cleaned = claimed_by.strip().lower()
    if not cleaned:
        return False
    return "railway-runner" in cleaned or cleaned.startswith("openai-codex:")


def _host_runner_usage_summary(tasks: list[dict[str, Any]], *, window_hours: int = 24) -> dict[str, Any]:
    now = _now()
    cutoff = now - timedelta(hours=max(1, min(int(window_hours), 24 * 30)))
    host_tasks: list[dict[str, Any]] = []
    for task in tasks:
        claimed_by = str(task.get("claimed_by") or "")
        if not _is_host_runner_claimant(claimed_by):
            continue
        task_time = _task_activity_time(task)
        if task_time is None or task_time < cutoff:
            continue
        host_tasks.append(task)

    status_counts: dict[str, int] = {}
    task_type_counts: dict[str, dict[str, int]] = {}
    for task in host_tasks:
        status = _status_value(task.get("status")) or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        task_type_value = _status_value(task.get("task_type")) or "unknown"
        row = task_type_counts.setdefault(task_type_value, {"total": 0})
        row["total"] += 1
        row[status] = row.get(status, 0) + 1

    return {
        "window_hours": max(1, min(int(window_hours), 24 * 30)),
        "generated_at": now.isoformat(),
        "total_runs": len(host_tasks),
        "failed_runs": status_counts.get("failed", 0),
        "completed_runs": status_counts.get("completed", 0),
        "running_runs": status_counts.get("running", 0),
        "pending_runs": status_counts.get("pending", 0) + status_counts.get("needs_decision", 0),
        "status_counts": status_counts,
        "by_task_type": task_type_counts,
    }


def _linked_task_ids_from_friction_events() -> set[str]:
    try:
        from app.services import friction_service

        events, _ignored = friction_service.load_events()
    except Exception:
        return set()
    linked_ids: set[str] = set()
    for event in events:
        linked_task_id = str(getattr(event, "task_id", "") or "").strip()
        if linked_task_id:
            linked_ids.add(linked_task_id)
    return linked_ids


def _record_task_failure_friction(task: dict[str, Any], *, linked_task_ids: set[str] | None = None) -> bool:
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return False
    if linked_task_ids is None:
        linked_task_ids = _linked_task_ids_from_friction_events()
    if task_id in linked_task_ids:
        return False

    notes_parts = [
        f"task_id={task_id}",
        f"task_type={_status_value(task.get('task_type')) or 'unknown'}",
        f"claimed_by={_normalize_worker_id(task.get('claimed_by'))}",
        "failure_reason=task transitioned to failed without linked friction event",
    ]
    output = _task_output_text(task).strip()
    if output:
        notes_parts.append(f"output_preview={output[:400]}")

    try:
        from uuid import uuid4

        from app.models.friction import FrictionEvent
        from app.services import friction_service
    except Exception:
        return False

    event = FrictionEvent(
        id=f"fric_{uuid4().hex[:12]}",
        timestamp=_now(),
        task_id=task_id,
        endpoint="tool:agent-task-completion",
        stage="agent_runner",
        block_type="task_failure",
        severity="high",
        owner="agent_pipeline",
        unblock_condition="Investigate failed task output, then rerun or close with a documented resolution.",
        energy_loss_estimate=0.0,
        cost_of_delay=0.0,
        status="open",
        notes=" | ".join(notes_parts)[:1200],
        resolved_at=None,
        time_open_hours=None,
        resolution_action=None,
    )
    try:
        friction_service.append_event(event)
    except Exception:
        return False
    linked_task_ids.add(task_id)
    return True


def backfill_host_runner_failure_observability(*, window_hours: int = 24) -> dict[str, Any]:
    """Ensure host-runner failed tasks are linked to completion + friction telemetry."""
    _ensure_store_loaded()
    bounded_window = max(1, min(int(window_hours), 24 * 30))
    now = _now()
    cutoff = now - timedelta(hours=bounded_window)

    host_failed_tasks: list[dict[str, Any]] = []
    for task in _store.values():
        if _status_value(task.get("status")) != "failed":
            continue
        if not _is_host_runner_claimant(str(task.get("claimed_by") or "")):
            continue
        task_time = _task_activity_time(task)
        if task_time is None or task_time < cutoff:
            continue
        host_failed_tasks.append(task)

    completion_backfilled = 0
    friction_backfilled = 0
    affected_task_ids: list[str] = []
    linked_task_ids = _linked_task_ids_from_friction_events()
    for task in host_failed_tasks:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        had_completion = _has_completion_tracking_event(task_id, "failed")
        if not had_completion:
            _record_completion_tracking_event(task)
            completion_backfilled += 1
            affected_task_ids.append(task_id)
        if _record_task_failure_friction(task, linked_task_ids=linked_task_ids):
            friction_backfilled += 1
            if task_id not in affected_task_ids:
                affected_task_ids.append(task_id)

    return {
        "window_hours": bounded_window,
        "host_failed_tasks": len(host_failed_tasks),
        "completion_events_backfilled": completion_backfilled,
        "friction_events_backfilled": friction_backfilled,
        "affected_task_ids": affected_task_ids[:50],
    }


def _pipeline_task_status_item(
    task: dict[str, Any], now: datetime
) -> tuple[str, dict[str, Any]]:
    created = task.get("created_at")
    updated = task.get("updated_at")
    started = task.get("started_at")
    st = task.get("status")
    st_val = st.value if hasattr(st, "value") else str(st)

    def _ts(obj: Any) -> str:
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)

    def _seconds_ago(ts: Any) -> int | None:
        if ts is None:
            return None
        try:
            delta = now - ts
            return int(delta.total_seconds())
        except Exception:
            return None

    def _duration(start_ts: Any, end_ts: Any) -> int | None:
        if start_ts is None or end_ts is None:
            return None
        try:
            delta = end_ts - start_ts
            return int(delta.total_seconds())
        except Exception:
            return None

    item = {
        "id": task.get("id"),
        "task_type": task.get("task_type"),
        "model": task.get("model"),
        "direction": (task.get("direction") or "")[:100],
        "claimed_by": task.get("claimed_by"),
        "created_at": _ts(created),
        "updated_at": _ts(updated),
        "wait_seconds": _seconds_ago(created) if st_val == "pending" else None,
        "running_seconds": _seconds_ago(started) if st_val == "running" and started else None,
        "duration_seconds": _duration(started, updated)
        if st_val in ("completed", "failed") and started and updated
        else None,
    }
    return st_val, item


def _collect_pipeline_status_items(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    running: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for t in _store.values():
        st_val, item = _pipeline_task_status_item(t, now=now)
        if st_val == "running":
            running.append(item)
        elif st_val == "pending":
            pending.append(item)
        else:
            completed.append(item)
    return running, pending, completed


def _pipeline_latest_activity(
    running: list[dict[str, Any]],
    completed: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    latest_request: dict[str, Any] | None = None
    latest_response: dict[str, Any] | None = None

    if running:
        task = _store.get(running[0]["id"])
        if task:
            latest_request = {
                "task_id": task.get("id"),
                "status": "running",
                "direction": task.get("direction"),
                "prompt_preview": (task.get("command") or "")[:500],
            }

    if completed:
        task = _store.get(completed[0]["id"])
        if task:
            if not latest_request:
                latest_request = {
                    "task_id": task.get("id"),
                    "status": task.get("status"),
                    "direction": task.get("direction"),
                    "prompt_preview": (task.get("command") or "")[:500],
                }
            out = _task_output_text(task)
            latest_response = {
                "task_id": task.get("id"),
                "status": task.get("status"),
                "output_preview": out[:2000],
                "output_len": len(out),
            }

    return latest_request, latest_response


def _pipeline_attention_summary(
    running: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    completed: list[dict[str, Any]],
) -> dict[str, Any]:
    attention_flags: list[str] = []
    stuck = False
    if pending and not running:
        wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
        if wait_secs and max(wait_secs) > 600:
            stuck = True
            attention_flags.append("stuck")

    repeated_failures = False
    if len(completed) >= 3:
        last_three = completed[:3]
        if all(_status_value(_store.get(c["id"]) or {}) == "failed" for c in last_three):
            repeated_failures = True
            attention_flags.append("repeated_failures")

    output_empty = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(_task_output_text(t)) == 0 and _status_value(t) == "completed":
            output_empty = True
            attention_flags.append("output_empty")
            break

    executor_fail = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(_task_output_text(t)) == 0 and _status_value(t) == "failed":
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
        # Spec 032: when metrics unavailable, low_success_rate remains false; do not raise.
        pass

    by_phase = {"spec": 0, "impl": 0, "test": 0, "review": 0}
    for item in running + pending:
        task_type = item.get("task_type")
        task_type_value = task_type.value if hasattr(task_type, "value") else str(task_type)
        if task_type_value in by_phase:
            by_phase[task_type_value] += 1

    return {
        "stuck": stuck,
        "repeated_failures": repeated_failures,
        "output_empty": output_empty,
        "executor_fail": executor_fail,
        "low_success_rate": low_success_rate,
        "flags": attention_flags,
        "by_phase": by_phase,
    }


def _task_type_name(value: Any) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value") or "").strip().lower()
    return str(value or "").strip().lower()


def _failure_reason_bucket(task: dict[str, Any]) -> str:
    output = _task_output_text(task).lower()
    if not output:
        return "empty_output"
    if "timeout" in output or "timed out" in output:
        return "timeout"
    if (
        "unauthorized" in output
        or "forbidden" in output
        or "api key" in output
        or "invalid api key" in output
        or "status=401" in output
        or "status=403" in output
    ):
        return "auth"
    if "rate limit" in output or "429" in output or "quota" in output:
        return "rate_limit"
    if (
        "command not found" in output
        or "module not found" in output
        or "no module named" in output
        or "no such file or directory" in output
    ):
        return "dependency_or_tooling"
    if "assertionerror" in output or "test failed" in output or "pytest" in output:
        return "test_failure"
    if "merge conflict" in output or "rebase" in output:
        return "git_conflict"
    return "other"


def _pipeline_queue_diagnostics(
    running: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    completed: list[dict[str, Any]],
) -> dict[str, Any]:
    pending_by_task_type: dict[str, int] = {}
    running_by_task_type: dict[str, int] = {}
    for item in pending:
        task_type = _task_type_name(item.get("task_type"))
        key = task_type or "unknown"
        pending_by_task_type[key] = pending_by_task_type.get(key, 0) + 1
    for item in running:
        task_type = _task_type_name(item.get("task_type"))
        key = task_type or "unknown"
        running_by_task_type[key] = running_by_task_type.get(key, 0) + 1

    reason_counts: dict[str, int] = {}
    recent_failed: list[dict[str, Any]] = []
    for completed_item in completed[:12]:
        task = _store.get(completed_item["id"]) or {}
        if _status_value(task.get("status")) != "failed":
            continue
        reason = _failure_reason_bucket(task)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        recent_failed.append(
            {
                "task_id": task.get("id"),
                "task_type": _task_type_name(task.get("task_type")) or "unknown",
                "reason": reason,
            }
        )

    recent_failed_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda row: (-row[1], row[0]))
    ]

    total_pending = sum(pending_by_task_type.values())
    dominant_pending_type = ""
    dominant_pending_share = 0.0
    if total_pending > 0:
        dominant_pending_type, dominant_count = max(
            pending_by_task_type.items(),
            key=lambda row: row[1],
        )
        dominant_pending_share = round(float(dominant_count) / float(total_pending), 4)
    queue_mix_warning = bool(total_pending >= 5 and dominant_pending_share >= 0.8)

    return {
        "pending_by_task_type": pending_by_task_type,
        "running_by_task_type": running_by_task_type,
        "recent_failed_count": len(recent_failed),
        "recent_failed_reasons": recent_failed_reasons,
        "queue_mix_warning": queue_mix_warning,
        "dominant_pending_task_type": dominant_pending_type,
        "dominant_pending_share": dominant_pending_share,
    }


def get_usage_summary() -> dict[str, Any]:
    """Per-model usage derived from tasks (for /usage and API)."""
    _ensure_store_loaded(include_output=False)
    by_model: dict[str, dict[str, Any]] = {}
    completed_or_failed_task_ids: list[str] = []
    tasks = list(_store.values())
    for t in tasks:
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
        "host_runner": _host_runner_usage_summary(tasks, window_hours=24),
    }


def _friction_note_value(notes: str, key: str) -> str:
    pattern = rf"(?:^|\s){re.escape(key)}=([^\s]+)"
    match = re.search(pattern, notes or "")
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _friction_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(float(numerator) / float(denominator), 4)


def _event_has_task_model_tool_trace(event: Any) -> bool:
    notes = str(getattr(event, "notes", "") or "")
    task_id = str(getattr(event, "task_id", "") or "").strip() or _friction_note_value(notes, "task_id")
    model = str(getattr(event, "model", "") or "").strip() or _friction_note_value(notes, "model")
    tool = str(getattr(event, "tool", "") or "").strip() or _friction_note_value(notes, "tool")
    return bool(task_id and model and tool)


def _partition_events_by_recent(
    events: list[Any],
    *,
    cutoff: datetime,
    timestamp_field: str = "timestamp",
) -> tuple[list[Any], list[Any]]:
    recent: list[Any] = []
    prior: list[Any] = []
    for event in events:
        ts = getattr(event, timestamp_field, None)
        if not isinstance(ts, datetime):
            prior.append(event)
            continue
        ts_norm = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if ts_norm >= cutoff:
            recent.append(event)
        else:
            prior.append(event)
    return recent, prior


def _resolved_with_action(event: Any) -> bool:
    return (
        str(getattr(event, "status", "")).strip() == "resolved"
        and bool(str(getattr(event, "resolution_action", "") or "").strip())
    )


def _count_runs_with_provider_trace(recent_runs: list[dict[str, Any]]) -> int:
    traced = 0
    for run in recent_runs:
        if not isinstance(run, dict):
            continue
        if (
            str(run.get("task_id") or "").strip()
            and str(run.get("tool") or "").strip()
            and str(run.get("provider") or "").strip()
        ):
            traced += 1
    return traced


def _visibility_area_rows(
    *,
    hosted_events: list[Any],
    hosted_recent: list[Any],
    hosted_prior: list[Any],
    hosted_with_trace: int,
    hosted_recent_with_trace: int,
    hosted_prior_with_trace: int,
    recent_runs: list[dict[str, Any]],
    recent_with_provider: int,
    recoverable_events: list[Any],
    recoverable_recent: list[Any],
    recoverable_prior: list[Any],
    recovered_or_learned: int,
    recovered_recent: int,
    recovered_prior: int,
    threshold: float,
) -> list[dict[str, Any]]:
    return [
        {
            "id": "hosted_failure_reporting",
            "label": "Hosted Worker Failure Reporting",
            "numerator": hosted_with_trace,
            "denominator": len(hosted_events),
            "rate": _friction_rate(hosted_with_trace, len(hosted_events)),
            "recent_rate": _friction_rate(hosted_recent_with_trace, len(hosted_recent)),
            "prior_rate": _friction_rate(hosted_prior_with_trace, len(hosted_prior)),
            "threshold": threshold,
        },
        {
            "id": "provider_task_visibility",
            "label": "Task-Provider Visibility",
            "numerator": recent_with_provider,
            "denominator": len(recent_runs),
            "rate": _friction_rate(recent_with_provider, len(recent_runs)),
            "recent_rate": _friction_rate(recent_with_provider, len(recent_runs)),
            "prior_rate": None,
            "threshold": threshold,
        },
        {
            "id": "recovery_learning_capture",
            "label": "Recovery/Learning Capture",
            "numerator": recovered_or_learned,
            "denominator": len(recoverable_events),
            "rate": _friction_rate(recovered_or_learned, len(recoverable_events)),
            "recent_rate": _friction_rate(recovered_recent, len(recoverable_recent)),
            "prior_rate": _friction_rate(recovered_prior, len(recoverable_prior)),
            "threshold": threshold,
        },
    ]


def _visibility_proof_summary(usage: dict[str, Any]) -> dict[str, Any]:
    from app.services import friction_service

    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    recent_runs = execution.get("recent_runs") if isinstance(execution.get("recent_runs"), list) else []
    events, _ignored = friction_service.load_events()
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=3)

    hosted_events = [
        event for event in events if str(getattr(event, "stage", "")).strip() == "agent_runner"
    ]
    hosted_recent, hosted_prior = _partition_events_by_recent(hosted_events, cutoff=recent_cutoff)
    hosted_with_trace = sum(1 for event in hosted_events if _event_has_task_model_tool_trace(event))
    hosted_recent_with_trace = sum(1 for event in hosted_recent if _event_has_task_model_tool_trace(event))
    hosted_prior_with_trace = sum(1 for event in hosted_prior if _event_has_task_model_tool_trace(event))
    recent_with_provider = _count_runs_with_provider_trace(recent_runs)

    recoverable_events = [
        event for event in hosted_events if str(getattr(event, "block_type", "")).strip() == "tool_failure"
    ]
    recoverable_recent, recoverable_prior = _partition_events_by_recent(
        recoverable_events,
        cutoff=recent_cutoff,
    )
    recovered_or_learned = sum(1 for event in recoverable_events if _resolved_with_action(event))
    recovered_recent = sum(1 for event in recoverable_recent if _resolved_with_action(event))
    recovered_prior = sum(1 for event in recoverable_prior if _resolved_with_action(event))

    threshold = 0.75
    areas = _visibility_area_rows(
        hosted_events=hosted_events,
        hosted_recent=hosted_recent,
        hosted_prior=hosted_prior,
        hosted_with_trace=hosted_with_trace,
        hosted_recent_with_trace=hosted_recent_with_trace,
        hosted_prior_with_trace=hosted_prior_with_trace,
        recent_runs=recent_runs,
        recent_with_provider=recent_with_provider,
        recoverable_events=recoverable_events,
        recoverable_recent=recoverable_recent,
        recoverable_prior=recoverable_prior,
        recovered_or_learned=recovered_or_learned,
        recovered_recent=recovered_recent,
        recovered_prior=recovered_prior,
        threshold=threshold,
    )
    for row in areas:
        row["pass"] = bool(row["rate"] >= row["threshold"])
        row["guidance_status"] = "on_track" if row["pass"] else "below_target"
        row["progress_to_target"] = round(min(1.0, float(row["rate"]) / float(row["threshold"])), 4)
        row["gap_to_target"] = round(max(0.0, float(row["threshold"]) - float(row["rate"])), 4)
        prior_rate = row.get("prior_rate")
        if isinstance(prior_rate, (int, float)):
            row["trend_delta"] = round(float(row["recent_rate"]) - float(prior_rate), 4)
        else:
            row["trend_delta"] = None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "all_pass": all(bool(row["pass"]) for row in areas),
        "mode": "guidance",
        "note": "Guidance target only: these metrics are for awareness and prioritization, not automatic blocking.",
        "areas": areas,
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
        "proof": _visibility_proof_summary(usage),
        "remaining_usage": {
            "coverage_rate": coverage_rate,
            "remaining_to_full_coverage": remaining_to_full_coverage,
            "untracked_task_ids": normalized_untracked_ids,
            "health": health,
        },
    }


def _route_guidance_view(route: dict[str, Any]) -> dict[str, Any]:
    executor = str(route.get("executor") or "").strip()
    return {
        "executor": executor,
        "tool": _executor_binary_name(executor) if executor else "",
        "model": str(route.get("model") or ""),
        "tier": str(route.get("tier") or ""),
        "provider": str(route.get("provider") or ""),
        "is_paid_provider": bool(route.get("is_paid_provider")),
        "command_template": str(route.get("command_template") or ""),
    }


def _orchestration_route_matrix(cheap_executor: str, escalation_executor: str) -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for task_type in TaskType:
        cheap_route = get_route(task_type, executor=cheap_executor)
        escalation_route = get_route(task_type, executor=escalation_executor)
        matrix[task_type.value] = {
            "cheap": _route_guidance_view(cheap_route),
            "escalation": _route_guidance_view(escalation_route),
            "escalation_changes_route": bool(
                cheap_route.get("executor") != escalation_route.get("executor")
                or cheap_route.get("model") != escalation_route.get("model")
            ),
        }
    return matrix


def _top_failing_tools(execution: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    by_tool = execution.get("by_tool") if isinstance(execution.get("by_tool"), dict) else {}
    rows: list[dict[str, Any]] = []
    for tool, payload in by_tool.items():
        if not isinstance(payload, dict):
            continue
        failed = int(payload.get("failed") or 0)
        if failed <= 0:
            continue
        rows.append(
            {
                "tool": str(tool or ""),
                "failed": failed,
                "count": int(payload.get("count") or 0),
                "success_rate": float(payload.get("success_rate") or 0.0),
            }
        )
    rows.sort(key=lambda row: (-int(row["failed"]), float(row["success_rate"]), -int(row["count"]), str(row["tool"])))
    return rows[:limit]


def _guidance_item(
    *,
    item_id: str,
    severity: str,
    title: str,
    detail: str,
    action: str,
) -> dict[str, str]:
    return {
        "id": item_id,
        "severity": severity,
        "title": title,
        "detail": detail,
        "action": action,
    }


def _dedupe_guidance_rows(guidance_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in guidance_rows:
        item_id = str(row.get("id") or "").strip()
        if item_id and item_id in seen_ids:
            continue
        if item_id:
            seen_ids.add(item_id)
        deduped.append(row)
    return deduped


def _lifecycle_awareness_snapshot(window_seconds: int, sample_limit: int) -> dict[str, Any]:
    from app.services import agent_execution_hooks

    lifecycle = agent_execution_hooks.summarize_lifecycle_events(
        seconds=window_seconds,
        limit=sample_limit,
        source="auto",
    )
    by_event = lifecycle.get("by_event") if isinstance(lifecycle.get("by_event"), dict) else {}
    by_status = lifecycle.get("by_status") if isinstance(lifecycle.get("by_status"), dict) else {}
    finalized_events = int(by_event.get("finalized") or 0)
    failed_finalized_events = int(by_status.get("failed") or 0)
    lifecycle_failure_ratio = (
        round(float(failed_finalized_events) / float(finalized_events), 4) if finalized_events > 0 else 0.0
    )
    return {
        "lifecycle": lifecycle,
        "finalized_events": finalized_events,
        "failed_finalized_events": failed_finalized_events,
        "lifecycle_failure_ratio": lifecycle_failure_ratio,
    }


def _build_orchestration_guidance_rows(
    *,
    execution_success_rate: float,
    coverage_rate: float,
    top_failing_tools: list[dict[str, Any]],
    finalized_events: int,
    lifecycle_failure_ratio: float,
    lifecycle_guidance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    guidance_rows: list[dict[str, Any]] = [dict(row) for row in lifecycle_guidance[:5] if isinstance(row, dict)]

    if execution_success_rate < 0.8:
        guidance_rows.append(
            _guidance_item(
                item_id="execution_success_low",
                severity="medium",
                title="Execution success rate is below target",
                detail=f"Execution success rate is {round(execution_success_rate * 100.0, 1)}% in the current window.",
                action="Prefer cheap executor path first, narrow task scopes, and escalate once for reasoning-heavy failures.",
            )
        )
    if coverage_rate < 0.95:
        guidance_rows.append(
            _guidance_item(
                item_id="coverage_gap",
                severity="medium",
                title="Execution tracking coverage is incomplete",
                detail=f"Coverage rate is {round(coverage_rate * 100.0, 1)}% for completed/failed tasks.",
                action="Ensure worker runtime events include task_id, executor, and provider metadata.",
            )
        )
    if top_failing_tools:
        top_tools = ", ".join(str(row.get("tool") or "") for row in top_failing_tools[:3] if str(row.get("tool") or ""))
        guidance_rows.append(
            _guidance_item(
                item_id="tool_failure_hotspots",
                severity="medium",
                title="Tool failure hotspots detected",
                detail=f"Most frequent failing tools: {top_tools or 'unknown'}.",
                action="Run failing tools in smaller deterministic loops before broad orchestration retries.",
            )
        )
    if finalized_events > 0 and lifecycle_failure_ratio >= 0.25:
        guidance_rows.append(
            _guidance_item(
                item_id="lifecycle_failures_present",
                severity="medium",
                title="Lifecycle failures are elevated",
                detail=f"Lifecycle finalized failure ratio is {round(lifecycle_failure_ratio * 100.0, 1)}%.",
                action="Inspect /api/agent/lifecycle/summary guidance and resolve repeated guard/validation causes first.",
            )
        )
    if not guidance_rows:
        guidance_rows.append(
            _guidance_item(
                item_id="stable_guidance_baseline",
                severity="info",
                title="Signals are stable",
                detail="Current orchestration signals are stable and guidance targets are on track.",
                action="Continue cheap-first routing with one escalation only when needed.",
            )
        )
    return _dedupe_guidance_rows(guidance_rows)


def get_orchestration_guidance_summary(*, seconds: int = 6 * 3600, limit: int = 500) -> dict[str, Any]:
    """Guidance-first orchestration summary for model/tool routing and awareness signals."""
    from app.services import friction_service

    window_seconds = max(300, min(int(seconds), 30 * 24 * 3600))
    sample_limit = max(1, min(int(limit), 5000))
    window_days = max(1, min(30, int((window_seconds + 86399) // 86400)))

    cheap_executor = _cheap_executor_default()
    escalation_executor = _escalation_executor_default()
    usage = get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    coverage = execution.get("coverage") if isinstance(execution.get("coverage"), dict) else {}
    execution_success_rate = float(execution.get("success_rate") or 0.0)
    coverage_rate = float(coverage.get("coverage_rate") or 0.0)
    top_failing_tools = _top_failing_tools(execution, limit=5)

    lifecycle_snapshot = _lifecycle_awareness_snapshot(window_seconds, sample_limit)
    lifecycle = lifecycle_snapshot["lifecycle"]
    finalized_events = int(lifecycle_snapshot["finalized_events"])
    failed_finalized_events = int(lifecycle_snapshot["failed_finalized_events"])
    lifecycle_failure_ratio = float(lifecycle_snapshot["lifecycle_failure_ratio"])

    friction_events, _ignored = friction_service.load_events()
    friction_summary = friction_service.summarize(friction_events, window_days=window_days)
    top_friction_blocks = list(friction_summary.get("top_block_types") or [])[:5]
    lifecycle_guidance = lifecycle.get("guidance") if isinstance(lifecycle.get("guidance"), list) else []
    guidance = _build_orchestration_guidance_rows(
        execution_success_rate=execution_success_rate,
        coverage_rate=coverage_rate,
        top_failing_tools=top_failing_tools,
        finalized_events=finalized_events,
        lifecycle_failure_ratio=lifecycle_failure_ratio,
        lifecycle_guidance=lifecycle_guidance,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "guidance",
        "enforcement": "advisory",
        "window_seconds": window_seconds,
        "defaults": {
            "cheap_executor": cheap_executor,
            "escalation_executor": escalation_executor,
            "repo_question_executor": routing_service.repo_question_executor_default(),
            "open_question_executor": routing_service.open_question_executor_default(),
        },
        "recommended_routes": _orchestration_route_matrix(cheap_executor, escalation_executor),
        "awareness": {
            "execution_success_rate": round(execution_success_rate, 4),
            "coverage_rate": round(coverage_rate, 4),
            "lifecycle_failure_ratio": lifecycle_failure_ratio,
            "finalized_events": finalized_events,
            "failed_finalized_events": failed_finalized_events,
            "subscribers": lifecycle.get("subscribers") if isinstance(lifecycle.get("subscribers"), dict) else {},
            "summary_source": str(lifecycle.get("summary_source") or "none"),
            "top_failing_tools": top_failing_tools,
            "top_friction_blocks": top_friction_blocks,
        },
        "guidance": guidance[:10],
    }


def find_active_task_by_fingerprint(task_fingerprint: str) -> dict[str, Any] | None:
    _ensure_store_loaded(include_output=False)
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
    _ensure_store_loaded(include_output=False)
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
    _ensure_store_loaded(
        force_reload=agent_task_store_service.enabled(),
        include_output=False,
    )
    normalized_key = (session_key or "").strip()
    if not normalized_key:
        raise ValueError("session_key is required")

    existing = find_active_task_by_session_key(normalized_key)
    if existing is not None:
        _claim_running_task(existing, worker_id)
        existing["updated_at"] = _now()
        if agent_task_store_service.enabled():
            agent_task_store_service.upsert_task(_serialize_task(existing))
        else:
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
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(created))
    else:
        _save_store_to_disk()
    return created, True


def get_pipeline_status(now_utc=None) -> dict[str, Any]:
    """Pipeline visibility: running, pending with wait times, recent completed with duration."""
    _ensure_store_loaded(include_output=False)
    now = now_utc or datetime.now(timezone.utc)

    running, pending, completed = _collect_pipeline_status_items(now)
    completed.sort(key=lambda x: x.get("updated_at") or x.get("created_at", ""), reverse=True)

    latest_request, latest_response = _pipeline_latest_activity(running, completed)
    attention = _pipeline_attention_summary(running, pending, completed)
    diagnostics = _pipeline_queue_diagnostics(running, pending, completed)

    return {
        "running": running[:10],
        "pending": sorted(pending, key=lambda x: x.get("created_at", ""))[:20],
        "running_by_phase": attention.pop("by_phase"),
        "recent_completed": [
            {
                **c,
                "output_len": len(_task_output_text(_store.get(c["id"]) or {})),
            }
            for c in completed[:10]
        ],
        "latest_request": latest_request,
        "latest_response": latest_response,
        "attention": {
            "stuck": attention["stuck"],
            "repeated_failures": attention["repeated_failures"],
            "output_empty": attention["output_empty"],
            "executor_fail": attention["executor_fail"],
            "low_success_rate": attention["low_success_rate"],
            "flags": attention["flags"],
        },
        "diagnostics": diagnostics,
    }


def clear_store() -> None:
    """Clear in-memory store (for testing)."""
    _ensure_store_loaded(
        force_reload=agent_task_store_service.enabled(),
        include_output=False,
    )
    _store.clear()
    if agent_task_store_service.enabled():
        agent_task_store_service.clear_tasks()
    else:
        _save_store_to_disk()
