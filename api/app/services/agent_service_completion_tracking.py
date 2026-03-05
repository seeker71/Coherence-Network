"""Agent task completion tracking: runtime events, idea_id resolution."""

import hashlib
from typing import Any

from app.models.runtime import RuntimeEventCreate

from app.services import agent_routing_service as routing_service
from app.services.agent_service_store import _now
from app.services.agent_service_task_derive import (
    derive_task_executor,
    normalize_worker_id,
    task_duration_ms,
    task_output_text,
)


def has_completion_tracking_event(task_id: str, final_status: str) -> bool:
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


def _idea_id_from_spec_context(task_context: dict[str, Any]) -> str:
    spec_id = str(task_context.get("spec_id") or "").strip()
    if not spec_id:
        return ""
    try:
        from app.services import spec_registry_service
        spec = spec_registry_service.get_spec(spec_id)
    except Exception:
        return ""
    if spec is None:
        return ""
    return str(getattr(spec, "idea_id", "") or "").strip()


def _idea_id_from_task_fingerprint(task_context: dict[str, Any]) -> str:
    fingerprint = str(task_context.get("task_fingerprint") or "").strip()
    if not fingerprint:
        return ""
    for prefix in ("roi_idea_progress::", "flow-unblock::"):
        if not fingerprint.startswith(prefix):
            continue
        parts = fingerprint.split("::", 2)
        if len(parts) >= 2:
            candidate = str(parts[1] or "").strip()
            if candidate:
                return candidate
    return ""


def _task_runtime_idea_id(task: dict[str, Any], task_context: dict[str, Any]) -> str:
    del task
    for key in ("idea_id", "origin_idea_id", "primary_idea_id", "tracking_idea_id"):
        candidate = str(task_context.get(key) or "").strip()
        if candidate:
            return candidate
    for key in ("idea_ids", "tracked_idea_ids", "related_idea_ids"):
        values = task_context.get(key)
        if not isinstance(values, list):
            continue
        for raw in values:
            candidate = str(raw or "").strip()
            if candidate:
                return candidate
    fingerprint_idea = _idea_id_from_task_fingerprint(task_context)
    if fingerprint_idea:
        return fingerprint_idea
    spec_idea = _idea_id_from_spec_context(task_context)
    if spec_idea:
        return spec_idea
    return "coherence-network-agent-pipeline"


def resolve_runtime_idea_id_for_context(context: dict[str, Any] | None) -> str:
    context_map = context if isinstance(context, dict) else {}
    return _task_runtime_idea_id({}, context_map)


def resolve_runtime_idea_id_for_task(task: dict[str, Any] | None) -> str:
    task_map = task if isinstance(task, dict) else {}
    context = task_map.get("context") if isinstance(task_map.get("context"), dict) else {}
    return _task_runtime_idea_id(task_map, context)


def _task_failure_metadata(task: dict[str, Any], task_context: dict[str, Any]) -> dict[str, Any]:
    output_text = task_output_text(task).strip()
    summary = str(task_context.get("failure_summary") or "").strip()
    if not summary:
        first_line = next(
            (line.strip() for line in output_text.splitlines() if line.strip()),
            "",
        )
        summary = first_line
    detail = str(task_context.get("failure_detail") or "").strip()
    if not detail:
        detail = output_text
    payload: dict[str, Any] = {}
    if summary:
        payload["failure_summary"] = summary[:320]
    if detail:
        payload["failure_detail"] = detail[:1600]
    for key in ("failure_signature", "failure_reason_bucket", "failure_diagnostics_source"):
        value = str(task_context.get(key) or "").strip()
        if value:
            payload[key] = value[:240]
    return payload


def record_completion_tracking_event(task: dict[str, Any]) -> None:
    status_value = task.get("status")
    final_status = status_value.value if hasattr(status_value, "value") else str(status_value or "")
    if final_status not in {"completed", "failed"}:
        return
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        return
    if has_completion_tracking_event(task_id, final_status):
        return

    command = str(task.get("command") or "").strip()
    command_sha = hashlib.sha256(command.encode("utf-8")).hexdigest() if command else ""
    worker_id = normalize_worker_id(task.get("claimed_by"))
    executor = derive_task_executor(task)
    provider, billing_provider, is_paid_provider = routing_service.classify_provider(
        executor=executor,
        model=str(task.get("model") or ""),
        command=command,
        worker_id=worker_id,
    )
    runtime_ms = task_duration_ms(task)
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
    runtime_idea_id = _task_runtime_idea_id(task, task_context)
    failure_metadata = _task_failure_metadata(task, task_context) if final_status == "failed" else {}
    metadata: dict[str, Any] = {
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
        "is_openai_codex": worker_id == "openai-codex" or worker_id.startswith("openai-codex:"),
        "request_schema": request_schema,
        "normalized_model": normalized_model,
        "normalized_provider": normalized_provider,
        "tracking_kind": "agent_task_completion",
        "repeatable_tool_name": "agent_task_completion",
        "repeatable_tool_call": command or "PATCH /api/agent/tasks/{task_id}",
        "repeatable_tool_call_sha256": command_sha,
        "repeatable_replay_hint": command
        or "Replay by patching the task to completed/failed with the same task id.",
    }
    if failure_metadata:
        metadata.update(failure_metadata)

    mutable_context = dict(task_context) if isinstance(task_context, dict) else {}
    try:
        from app.services import runtime_service
        runtime_service.record_event(
            RuntimeEventCreate(
                source="worker",
                endpoint="tool:agent-task-completion",
                method="RUN",
                status_code=status_code,
                runtime_ms=runtime_ms,
                idea_id=runtime_idea_id,
                metadata=metadata,
            )
        )
        mutable_context["completion_tracking_event_status"] = "recorded"
        mutable_context.pop("completion_tracking_event_error_type", None)
        mutable_context.pop("completion_tracking_event_error", None)
        task["context"] = mutable_context
    except Exception:
        mutable_context["completion_tracking_event_status"] = "failed"
        mutable_context["completion_tracking_event_error_type"] = "runtime_event_record_failure"
        mutable_context["completion_tracking_event_error"] = (
            "Failed to record runtime completion event; task transition preserved."
        )
        task["context"] = mutable_context
