"""Agent task state derivation: phase, graph state, failure diagnostics."""

from typing import Any

from app.services import agent_routing_service as routing_service
from app.services import agent_task_store_service
from app.services import failure_taxonomy_service

from app.services.agent_service_store import (
    ACTIVE_TASK_STATUSES,
    _sanitize_task_output,
    _now,
)

_AGENT_GRAPH_STATE_SCHEMA_ID = "coherence_agent_graph_state_v1"
_AGENT_GRAPH_STATE_REQUIRED_FIELDS: tuple[str, ...] = ("task_id", "task_type", "phase", "direction")
_AGENT_GRAPH_STATE_ALLOWED_PHASES: tuple[str, ...] = (
    "queued",
    "running",
    "needs_decision",
    "completed",
    "failed",
)


def status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def is_active_status(status: Any) -> bool:
    value = status_value(status)
    return value in {s.value for s in ACTIVE_TASK_STATUSES}


def normalize_worker_id(worker_id: str | None) -> str:
    cleaned = (worker_id or "").strip()
    return cleaned or "unknown"


def derive_task_executor(task: dict[str, Any]) -> str:
    model = str(task.get("model") or "").strip().lower()
    command = str(task.get("command") or "").strip()
    if model.startswith("cursor/") or command.startswith("agent "):
        return "cursor"
    if model.startswith("gemini/") or command.startswith("gemini "):
        return "gemini"
    if model.startswith("openrouter/") or command.startswith("openrouter-exec "):
        return "openrouter"
    if model.startswith("codex/") or command.startswith("codex "):
        return "codex"
    if command.startswith("aider "):
        return "aider"
    if command.startswith("claude "):
        return "claude"
    return "unknown"


def derive_task_provider(task: dict[str, Any], executor: str) -> str:
    provider, _b, _p = routing_service.classify_provider(
        executor=executor,
        model=str(task.get("model") or ""),
        command=str(task.get("command") or ""),
        worker_id=normalize_worker_id(task.get("claimed_by")),
    )
    return provider


def task_duration_ms(task: dict[str, Any]) -> float:
    started = task.get("started_at")
    created = task.get("created_at")
    updated = task.get("updated_at") or _now()
    start_ts = started or created
    if hasattr(start_ts, "timestamp") and hasattr(updated, "timestamp"):
        seconds = max(0.0, float((updated - start_ts).total_seconds()))
        return max(0.1, round(seconds * 1000.0, 4))
    return 0.1


def phase_for_status(status: Any) -> str:
    value = status_value(status).strip().lower()
    if value in _AGENT_GRAPH_STATE_ALLOWED_PHASES:
        return value
    return "queued"


def build_agent_graph_state(task: dict[str, Any], *, phase: str | None = None) -> dict[str, Any]:
    status_phase = (
        phase.strip().lower() if isinstance(phase, str) and phase.strip() else phase_for_status(task.get("status"))
    )
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    route_decision = context.get("route_decision") if isinstance(context.get("route_decision"), dict) else {}
    attempt = context.get("retry_count", 0)
    try:
        normalized_attempt = max(0, int(attempt))
    except (TypeError, ValueError):
        normalized_attempt = 0
    return {
        "task_id": str(task.get("id") or "").strip(),
        "task_type": status_value(task.get("task_type")).strip(),
        "phase": status_phase,
        "direction": str(task.get("direction") or "").strip(),
        "attempt": normalized_attempt,
        "model": str(task.get("model") or "").strip(),
        "provider": str(route_decision.get("provider") or "").strip(),
        "route_decision": route_decision,
    }


def validate_agent_graph_state_schema(state: dict[str, Any]) -> list[str]:
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


def apply_agent_graph_state_contract(
    task: dict[str, Any], *, preferred_state: dict[str, Any] | None = None
) -> None:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    candidate = preferred_state if isinstance(preferred_state, dict) else build_agent_graph_state(task)
    errors = validate_agent_graph_state_schema(candidate)
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


def task_output_text(task: dict[str, Any]) -> str:
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


def context_failure_detail(context: dict[str, Any], key: str) -> str | None:
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


def derive_failed_task_output(task: dict[str, Any]) -> tuple[str, str]:
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    if isinstance(context, dict):
        for key in (
            "error",
            "last_error",
            "failure_reason",
            "last_failure_class",
            "failure_class",
            "runner_error",
            "exception",
            "details",
            "message",
            "agent_graph_state_last_error",
        ):
            detail = context_failure_detail(context, key)
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
    task_type = status_value(task.get("task_type")) or "unknown"
    worker = normalize_worker_id(task.get("claimed_by"))
    step = str(task.get("current_step") or "").strip() or "unknown"
    return (
        f"Task failed without explicit error output. task_type={task_type}; worker={worker}; step={step}.",
        "fallback",
    )


def failure_classification(task: dict[str, Any], *, output_text: str | None = None) -> dict[str, str]:
    output_value = task_output_text(task) if output_text is None else str(output_text or "")
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    detail = ""
    if isinstance(context, dict):
        for key in ("last_error", "error", "failure_reason", "runner_error", "message", "details", "exception"):
            maybe = context_failure_detail(context, key)
            if maybe:
                detail = maybe
                break
    class_parts = [
        str((context or {}).get("last_failure_class") or "").strip(),
        str((context or {}).get("failure_class") or "").strip(),
        str((context or {}).get("failure_signature") or "").strip(),
        str((context or {}).get("failure_summary") or "").strip(),
    ]
    failure_class = "\n".join(part for part in class_parts if part)
    return failure_taxonomy_service.classify_failure(
        output_text=output_value,
        result_error=detail,
        failure_class=failure_class,
    )


def ensure_failed_task_diagnostics(task: dict[str, Any]) -> None:
    if status_value(task.get("status")) != "failed":
        return
    output_text = task_output_text(task).strip()
    source = "output"
    if not output_text:
        synthesized, source = derive_failed_task_output(task)
        task["output"] = _sanitize_task_output(synthesized)
        output_text = task_output_text(task).strip()
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    next_context = dict(context) if isinstance(context, dict) else {}
    classified = failure_classification(task, output_text=output_text)
    next_context["failure_reason_bucket"] = classified["bucket"]
    next_context["failure_signature"] = classified["signature"]
    next_context["failure_summary"] = classified["summary"]
    next_context["failure_action"] = classified.get("action") or ""
    next_context["failure_diagnostics_source"] = source
    next_context["failure_diagnostics_present"] = bool(output_text)
    next_context["failure_context_packet"] = {
        "bucket": classified["bucket"],
        "signature": classified["signature"],
        "summary": classified["summary"],
        "action": classified.get("action") or "",
        "source": source,
    }
    task["context"] = next_context
    # DG-015 fix: also populate top-level error_category and error_summary if not already set.
    # These are persisted to DB columns and returned by the API — they must be populated
    # for observability (circuit breaker classification, monitoring, dashboards).
    if not task.get("error_category"):
        bucket = classified["bucket"]
        # Map failure_classification bucket to valid API error_category values
        _bucket_to_category = {
            "timeout": "timeout",
            "provider_error": "execution_error",
            "no_code": "no_diff",
            "hollow": "no_diff",
            "impl_branch_missing": "impl_branch_missing",
            "worktree_failed": "worktree_failed",
            "push_failed": "push_failed",
        }
        task["error_category"] = _bucket_to_category.get(bucket, "execution_error")
    if not task.get("error_summary"):
        task["error_summary"] = classified["summary"][:500]


def task_type_name(value: Any) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value") or "").strip().lower()
    return str(value or "").strip().lower()


def failure_reason_bucket(task: dict[str, Any]) -> str:
    return failure_classification(task)["bucket"]
