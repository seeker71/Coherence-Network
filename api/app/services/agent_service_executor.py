"""Agent executor selection, command templates, and integration gaps.

Provider-specific code is the exception and must live here (or in command_templates).
Allowed: (1) command template selection per executor, (2) apply_resume_to_command,
(3) post_process_command, (4) data maps (RUNNER_AUTH_MODE_*, MODEL_PREFIX_*).
Orchestration/crud must not branch on executor; they call these helpers.
"""

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from app.config_loader import get_bool as _config_bool, get_str as _config_str
from app.models.agent import TaskType
from app.services import agent_routing_service as routing_service
from app.services.agent_routing.executor_routing_loader import (
    get_model_prefix as _loader_model_prefix,
    get_runner_auth_context_key as _loader_runner_auth_key,
)

ROUTING = routing_service.ROUTING

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

# --- Executor-specific data: from config (executor_routing.json); no hardcoded maps. Openrouter uses enforce_openrouter_free_model; no prefix. ---
def _runner_auth_context_key(executor: str) -> str | None:
    return _loader_runner_auth_key(executor)


def _model_prefix(executor: str) -> str:
    return _loader_model_prefix(executor) or ""

_COMMAND_LOCAL_AGENT = 'claude -p "{{direction}}" --dangerously-skip-permissions'
_COMMAND_HEAL = 'claude -p "{{direction}}" --dangerously-skip-permissions'

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
_TASK_CARD_REQUIRED_FIELDS: tuple[str, ...] = (
    "goal",
    "files_allowed",
    "done_when",
    "commands",
    "constraints",
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
    if os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED") is not None:
        return os.environ.get("AGENT_EXECUTOR_POLICY_ENABLED", "").strip().lower() not in {"0", "false", "no", "off"}
    return _config_bool("executor", "policy_enabled", True)


def _normalize_executor(value: str | None, default: str = "claude") -> str:
    return routing_service.normalize_executor(value, default=default)


def _cheap_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_CHEAP_DEFAULT") or _config_str("executor", "cheap_default")
    if configured:
        return _normalize_executor(configured, default="cursor")
    fallback = os.environ.get("AGENT_EXECUTOR_DEFAULT") or _config_str("executor", "default") or "cursor"
    return _normalize_executor(fallback, default="cursor")


def _escalation_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_ESCALATE_TO") or _config_str("executor", "escalate_to")
    if configured:
        return _normalize_executor(configured, default="claude")
    cheap = _cheap_executor_default()
    if cheap == "gemini":
        return "gemini"
    return "claude" if cheap != "claude" else "gemini"


def _executor_binary_name(executor: str) -> str:
    if executor == "cursor":
        return "agent"
    if executor in {"codex", "openrouter", "gemini"}:
        return routing_service.executor_binary_name(executor)
    return "claude"


def _executor_available(executor: str) -> bool:
    if executor == "openrouter":
        return True
    return shutil.which(_executor_binary_name(executor)) is not None


def _allow_unavailable_explicit_executor() -> bool:
    if os.environ.get("AGENT_EXECUTOR_ALLOW_UNAVAILABLE_EXPLICIT") is not None:
        return os.environ.get("AGENT_EXECUTOR_ALLOW_UNAVAILABLE_EXPLICIT", "").strip().lower() not in {"0", "false", "no", "off"}
    return _config_bool("executor", "allow_unavailable_explicit", True)


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _paid_providers_enabled() -> bool:
    if os.environ.get("AGENT_ALLOW_PAID_PROVIDERS") is not None:
        return _truthy_flag(os.environ.get("AGENT_ALLOW_PAID_PROVIDERS"))
    return _config_bool("executor", "allow_paid_providers", True)


def _context_budget_pressure_hint(context: dict[str, Any]) -> bool:
    for key in ("budget_pressure", "budget_status", "budget_state", "cost_pressure", "quota_pressure"):
        value = context.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        normalized = str(value or "").strip().lower()
        if normalized in {"tight", "high", "critical", "exhausted", "out", "out_of_budget", "blocked"}:
            return True
        if _truthy_flag(value):
            return True
    return False


def _context_executor(context: dict[str, Any]) -> str:
    route = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}
    raw = str(context.get("executor") or route.get("executor") or "").strip()
    return _normalize_executor(raw, default="")


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _recent_paid_provider_block_count(tasks: list[dict[str, Any]], *, limit: int = 40) -> int:
    blocked = 0
    inspected = 0
    for task in reversed(tasks):
        status_value = _status_value(task.get("status"))
        if status_value != "failed":
            continue
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        signature = str(context.get("failure_signature") or "").strip().lower()
        if signature.startswith("paid_provider_"):
            blocked += 1
        inspected += 1
        if inspected >= limit:
            break
    return blocked


def _budget_pressure_signals(context: dict[str, Any], tasks: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if _truthy_flag(context.get("force_paid_providers")):
        return False, ["force_paid_providers_override"]
    if not _paid_providers_enabled():
        reasons.append("paid_provider_policy_disabled")
    if _context_budget_pressure_hint(context):
        reasons.append("context_budget_pressure_hint")
    if _recent_paid_provider_block_count(tasks, limit=40) > 0:
        reasons.append("recent_paid_provider_blocks")
    return bool(reasons), reasons


def _first_available_executor(preferred: list[str]) -> str:
    for executor in preferred:
        candidate = _normalize_executor(executor, default="")
        if candidate and _executor_available(candidate):
            return candidate
    configured_default = _normalize_executor(
        os.environ.get("AGENT_EXECUTOR_DEFAULT") or _config_str("executor", "default"), default=""
    )
    if configured_default and _executor_available(configured_default):
        return configured_default
    for candidate in ("gemini", "cursor", "claude", "openrouter"):
        if _executor_available(candidate):
            return candidate
    return _normalize_executor(
        os.environ.get("AGENT_EXECUTOR_DEFAULT") or _config_str("executor", "default"), default="claude"
    )


def _executor_fallback_candidates() -> list[str]:
    return [
        _cheap_executor_default(),
        _escalation_executor_default(),
        "gemini",
        "codex",
        "openrouter",
        "cursor",
        "claude",
    ]


def _dedupe_executors(candidates: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_executor(candidate, default="")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _task_fingerprint(task_type: TaskType, direction: str) -> str:
    basis = f"{task_type.value}:{direction.strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _task_retry_hint(context: dict[str, Any]) -> int:
    for key in ("retry_count", "retry_index", "attempt", "attempt_count"):
        raw = context.get(key)
        if raw is None:
            continue
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            continue
    return 0


def _task_card_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(str(value).strip())


def _task_card_field_value(context: dict[str, Any], field: str) -> Any:
    """Resolve task card field from context or context.task_card."""
    v = context.get(field)
    if _task_card_value_present(v):
        return v
    task_card = context.get("task_card") if isinstance(context.get("task_card"), dict) else {}
    return task_card.get(field)


def _task_card_validation(context: dict[str, Any]) -> dict[str, Any]:
    """Return validation dict: present=True, score in [0,1], missing=list (and missing_fields for compat)."""
    required = list(_TASK_CARD_REQUIRED_FIELDS)
    missing: list[str] = []
    for field in required:
        if not _task_card_value_present(_task_card_field_value(context, field)):
            missing.append(field)
    n = len(required)
    score = 1.0 if n == 0 else round(1.0 - float(len(missing)) / float(n), 6)
    return {
        "present": True,
        "score": score,
        "missing": missing,
        "missing_fields": missing,
        "required": required,
    }


def _prior_attempt_stats(task_fingerprint: str, tasks: list[dict[str, Any]]) -> dict[str, int]:
    attempts = 0
    failed = 0
    for task in tasks:
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if str(context.get("task_fingerprint") or "").strip() != task_fingerprint:
            continue
        attempts += 1
        status = task.get("status")
        status_value = _status_value(status)
        if status_value == "failed":
            failed += 1
    return {"attempts": attempts, "failed": failed}


def _executor_attempt_stats(
    task_fingerprint: str, executor: str, tasks: list[dict[str, Any]]
) -> dict[str, float | int]:
    attempts = 0
    failed = 0
    retry_total = 0
    normalized_executor = _normalize_executor(executor, default="")
    for task in tasks:
        context = task.get("context")
        if not isinstance(context, dict):
            continue
        if str(context.get("task_fingerprint") or "").strip() != task_fingerprint:
            continue
        if _context_executor(context) != normalized_executor:
            continue
        attempts += 1
        retry_total += _task_retry_hint(context)
        status_value = _status_value(task.get("status"))
        if status_value == "failed":
            failed += 1
    success = max(0, attempts - failed)
    success_rate = 1.0 if attempts == 0 else round(float(success) / float(attempts), 4)
    avg_retry = 0.0 if attempts == 0 else round(float(retry_total) / float(attempts), 4)
    return {
        "attempts": attempts,
        "failed": failed,
        "success": success,
        "success_rate": success_rate,
        "avg_retry": avg_retry,
    }


def _routing_experiment_summary(
    *,
    task_fingerprint: str,
    candidates: list[str],
    selected: str,
    budget_pressure: bool,
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    pair = candidates[:2]
    if len(pair) < 2:
        return {
            "active": False,
            "mode": "advisory",
            "selected_executor": selected,
            "budget_pressure": budget_pressure,
        }
    digest = hashlib.sha256(task_fingerprint.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 2
    variant = "A" if bucket == 0 else "B"
    assigned_executor = pair[bucket]
    left_stats = _executor_attempt_stats(task_fingerprint, pair[0], tasks)
    right_stats = _executor_attempt_stats(task_fingerprint, pair[1], tasks)
    return {
        "active": True,
        "mode": "advisory",
        "variant": variant,
        "pair": pair,
        "assigned_executor": assigned_executor,
        "selected_executor": selected,
        "budget_pressure": budget_pressure,
        "executor_samples": {
            pair[0]: int(left_stats.get("attempts") or 0),
            pair[1]: int(right_stats.get("attempts") or 0),
        },
        "open_question": (
            "Should execution follow the assigned variant next run to gather speed/cost/retry evidence?"
        ),
    }


def _select_executor_with_retry_policy(
    *,
    task_fingerprint: str,
    context: dict[str, Any],
    budget_pressure: bool,
    budget_reasons: list[str],
    tasks: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    retry_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", 2)
    failure_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", 1)
    cheap = _cheap_executor_default()
    escalate_to = _escalation_executor_default()
    if escalate_to == cheap:
        if cheap == "gemini":
            escalate_to = "gemini"
        else:
            escalate_to = "claude" if cheap != "claude" else "gemini"

    stats = _prior_attempt_stats(task_fingerprint, tasks)
    retry_hint = _task_retry_hint(context)
    effective_retry_count = max(retry_hint, max(0, stats["attempts"]))
    should_escalate = stats["failed"] >= failure_threshold or effective_retry_count >= retry_threshold
    candidates = _dedupe_executors(
        [cheap, escalate_to, "gemini", "cursor", "claude"] + (["openrouter"] if budget_pressure else [])
    )
    selected = escalate_to if should_escalate else cheap
    if selected == "openrouter" and not budget_pressure:
        replacement = _first_available_executor([item for item in candidates if item != "openrouter"])
        selected = replacement
    reason = "retry_threshold" if should_escalate and effective_retry_count >= retry_threshold else (
        "failure_threshold" if should_escalate else "cheap_default"
    )
    if not _executor_available(selected):
        fallback = _first_available_executor(
            candidates if budget_pressure else [item for item in candidates if item != "openrouter"]
        )
        experiment = _routing_experiment_summary(
            task_fingerprint=task_fingerprint,
            candidates=candidates,
            selected=fallback,
            budget_pressure=budget_pressure,
            tasks=tasks,
        )
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
            "candidate_executors": candidates,
            "budget_pressure": budget_pressure,
            "budget_reasons": list(budget_reasons),
            "routing_experiment": experiment,
        }

    experiment = _routing_experiment_summary(
        task_fingerprint=task_fingerprint,
        candidates=candidates,
        selected=selected,
        budget_pressure=budget_pressure,
        tasks=tasks,
    )
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
        "candidate_executors": candidates,
        "budget_pressure": budget_pressure,
        "budget_reasons": list(budget_reasons),
        "routing_experiment": experiment,
        "selection_engine": "budget-aware-router-lite-v1",
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
    configured = os.environ.get("AGENT_EXECUTOR_REPO_DEFAULT") or _config_str("executor", "repo_default")
    if configured:
        return _normalize_executor(configured, default="cursor")
    return "cursor"


def _open_question_executor_default() -> str:
    configured = os.environ.get("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT") or _config_str("executor", "open_question_default")
    if configured:
        return _normalize_executor(configured, default="cursor")
    return "cursor"


def select_executor(
    task_type: TaskType, direction: str, context: dict[str, Any], tasks: list[dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    """Select executor and return (executor, policy_meta). Caller passes current task list for retry/budget stats."""
    explicit = _normalize_executor(context.get("executor"), default="")
    if explicit:
        # Always honor client-requested executor so local runners get the right command
        # (API node may not have claude in PATH; runner often does).
        if _executor_available(explicit):
            return explicit, {"policy_applied": False, "reason": "explicit_executor"}
        return explicit, {
            "policy_applied": True,
            "reason": "explicit_executor_forced",
            "explicit_executor": explicit,
            "availability": "unavailable_on_api_node",
        }

    if not _executor_policy_enabled():
        default_executor = _normalize_executor(
            os.environ.get("AGENT_EXECUTOR_DEFAULT") or _config_str("executor", "default"), default="claude"
        )
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

    budget_pressure, budget_reasons = _budget_pressure_signals(context, tasks)

    if _is_repo_scoped_question(direction, context):
        selected = _first_available_executor(
            [
                _repo_question_executor_default(),
                "cursor",
                "claude",
                "gemini",
            ]
            + (["openrouter"] if budget_pressure else [])
        )
        return selected, {
            "policy_applied": True,
            "reason": "repo_scoped_question",
            "task_fingerprint": task_fingerprint,
            "repo_executor_preference": _repo_question_executor_default(),
            "budget_pressure": budget_pressure,
            "budget_reasons": list(budget_reasons),
            "selection_engine": "budget-aware-router-lite-v1",
        }

    open_candidates = [
        _open_question_executor_default(),
        "cursor",
        "claude",
        "gemini",
    ]
    if budget_pressure:
        open_candidates = ["openrouter"] + open_candidates
    selected_open = _first_available_executor(open_candidates)
    failure_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", 1)
    retry_threshold = _int_env("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", 2)
    stats = _prior_attempt_stats(task_fingerprint, tasks)
    retry_hint = _task_retry_hint(context)
    effective_retry_count = max(retry_hint, max(0, stats["attempts"]))
    should_escalate = stats["failed"] >= failure_threshold or effective_retry_count >= retry_threshold
    if selected_open and not should_escalate:
        experiment = _routing_experiment_summary(
            task_fingerprint=task_fingerprint,
            candidates=open_candidates,
            selected=selected_open,
            budget_pressure=budget_pressure,
            tasks=tasks,
        )
        return selected_open, {
            "policy_applied": True,
            "reason": "open_question_default",
            "task_fingerprint": task_fingerprint,
            "open_question_executor": selected_open,
            "budget_pressure": budget_pressure,
            "budget_reasons": list(budget_reasons),
            "routing_experiment": experiment,
            "selection_engine": "budget-aware-router-lite-v1",
        }
    return _select_executor_with_retry_policy(
        task_fingerprint=task_fingerprint,
        context=context,
        budget_pressure=budget_pressure,
        budget_reasons=budget_reasons,
        tasks=tasks,
    )


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


def list_available_task_execution_providers() -> list[str]:
    """Return available task execution providers in deterministic order."""
    configured = list(routing_service.EXECUTOR_VALUES)
    candidates = configured if configured else ["claude", "cursor", "codex", "gemini", "openrouter"]
    providers: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_executor(candidate, default="")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if _executor_available(normalized):
            providers.append(normalized)
    return providers


def _cursor_command_template(task_type: TaskType) -> str:
    return routing_service.cursor_command_template(task_type)


def _openrouter_command_template(task_type: TaskType) -> str:
    return routing_service.openrouter_command_template(task_type)


def _with_agent_roles(
    direction: str, task_type: TaskType, primary_agent: str | None, guard_agents: list[str]
) -> str:
    """Wrap direction with role/contract lines from config (prompt_templates.json). No prompt data in code."""
    from app.services.agent_routing.prompt_templates_loader import build_direction_with_roles

    return build_direction_with_roles(
        direction, task_type, primary_agent, guard_agents if guard_agents else None
    )


def apply_runner_auth_defaults(executor: str, ctx: dict[str, Any]) -> None:
    """Set runner auth context key from config (executor_routing.json). No per-executor branching in callers."""
    key = _runner_auth_context_key(executor)
    if key:
        ctx[key] = "oauth"


def format_model_override(executor: str, applied_override: str) -> str:
    """Return model string for storage/display. Openrouter uses enforce_openrouter_free_model; others use config model_prefix."""
    if executor == "openrouter":
        return routing_service.enforce_openrouter_free_model(applied_override)
    prefix = _model_prefix(executor)
    return f"{prefix}/{applied_override}" if prefix else applied_override


def post_process_command(executor: str, command: str) -> str:
    """Only place for executor-specific command-line post-processing (e.g. add required flags). All such logic lives here."""
    if executor == "claude" and "claude -p" in command and "--dangerously-skip-permissions" not in command:
        return command.rstrip() + " --dangerously-skip-permissions"
    return command


def apply_resume_to_command(executor: str, command: str, context: dict[str, Any]) -> str:
    """Apply executor-specific resume/continue flag (command construction). Only exception: how to build the CLI invocation."""
    if not context.get("resume") and not context.get("resume_session_id"):
        return command
    if executor == "claude" and "claude -p" in command:
        return command.replace("claude -p", "claude -c -p", 1)
    return command


def build_command(direction: str, task_type: TaskType, executor: str = "claude") -> str:
    """Build command for task."""
    if executor == "cursor":
        template = _cursor_command_template(task_type)
    elif executor == "codex":
        template = routing_service.codex_command_template(task_type)
    elif executor == "gemini":
        template = routing_service.gemini_command_template(task_type)
    elif executor == "openrouter":
        template = _openrouter_command_template(task_type)
    elif executor == "claude":
        template = routing_service.claude_command_template(task_type)
    else:
        template = COMMAND_TEMPLATES[task_type]
    escaped = (
        direction.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    return template.replace("{{direction}}", escaped)


def _agent_profiles_dir() -> Path:
    return Path(__file__).resolve().parents[3] / ".claude" / "agents"


def _agent_profile_names() -> list[str]:
    root = _agent_profiles_dir()
    if not root.exists():
        return []
    return [path.stem for path in sorted(root.glob("*.md"))]


def get_integration_gaps() -> dict[str, Any]:
    """Report role-agent coverage, executor availability, and integration gaps."""
    profiles = _agent_profile_names()
    profile_set = set(profiles)
    primary_bindings = {t.value: (agent or "") for t, agent in AGENT_BY_TASK_TYPE.items()}
    guard_bindings = {t.value: list(GUARD_AGENTS_BY_TASK_TYPE.get(t, [])) for t in TaskType}
    bound_primary = {agent for agent in AGENT_BY_TASK_TYPE.values() if agent}
    bound_guard = {agent for items in GUARD_AGENTS_BY_TASK_TYPE.values() for agent in items}
    bound_agents = bound_primary.union(bound_guard)
    missing_profile_files = sorted(agent for agent in bound_agents if agent not in profile_set)
    unbound_profiles = sorted(name for name in profile_set if name not in bound_agents)
    unmapped_task_types = sorted(t.value for t in TaskType if not AGENT_BY_TASK_TYPE.get(t))

    binary_checks = {
        "claude": _executor_available("claude"),
        "agent": _executor_available("cursor"),
        "gemini": _executor_available("gemini"),
        "openrouter": _executor_available("openrouter"),
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
        "policy_defaults": {"cheap_executor": cheap, "escalation_executor": escalate},
        "gaps": gaps,
    }


def get_route(task_type: TaskType, executor: str = "claude") -> dict[str, Any]:
    """Return routing info for a task type (no persistence)."""
    executor = (executor or "auto").strip().lower()
    if executor == "auto":
        executor = _cheap_executor_default()
        if executor == "openrouter":
            executor = _first_available_executor(["gemini", "cursor", "claude", "openrouter"])
    return routing_service.route_for_executor(
        task_type,
        _normalize_executor(executor, default="claude"),
        COMMAND_TEMPLATES[task_type],
    )


def task_card_validation(context: dict[str, Any]) -> dict[str, Any]:
    """Return validation dict: present, score, missing (and missing_fields/required)."""
    return _task_card_validation(context)


def executor_binary_name(executor: str) -> str:
    """Public alias for command/routing display."""
    return _executor_binary_name(executor)


def cheap_executor_default() -> str:
    return _cheap_executor_default()


def escalation_executor_default() -> str:
    return _escalation_executor_default()
