"""Agent task CRUD: create_task, get_task, update_task, claim, resolve_route, target state."""

import os
from typing import Any, Optional

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

from app.services import agent_routing_service as routing_service
from app.services import agent_task_store_service
from app.services.agent_service_executor import (
    AGENT_BY_TASK_TYPE,
    COMMAND_TEMPLATES,
    GUARD_AGENTS_BY_TASK_TYPE,
    build_command,
    select_executor,
    task_card_validation,
    _with_agent_roles,
)
from app.services.agent_service_store import (
    TaskClaimConflictError,
    _ensure_store_loaded,
    _generate_id,
    _load_task_from_db,
    _now,
    _save_store_to_disk,
    _sanitize_task_output,
    _serialize_task,
    _store,
)
from app.services.agent_service_task_derive import (
    apply_agent_graph_state_contract,
    ensure_failed_task_diagnostics,
    status_value,
    normalize_worker_id,
)
from app.services.agent_service_completion_tracking import record_completion_tracking_event
from app.services.agent_service_friction import record_task_failure_friction

_TARGET_STATE_DEFAULT_WINDOW_SEC = 900
_TARGET_STATE_MAX_TEXT = 600


def _normalize_evidence_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    out = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        out.append(cleaned[:_TARGET_STATE_MAX_TEXT])
    return out


def _normalize_observation_window(raw: Any) -> int:
    if isinstance(raw, bool):
        return _TARGET_STATE_DEFAULT_WINDOW_SEC
    if isinstance(raw, (int, float)):
        value = int(raw)
    elif isinstance(raw, str):
        value = int(raw.strip()) if raw.strip().isdigit() else _TARGET_STATE_DEFAULT_WINDOW_SEC
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
    return {
        "target_state": candidate[:_TARGET_STATE_MAX_TEXT],
        "success_evidence": _normalize_evidence_list(success_evidence),
        "abort_evidence": _normalize_evidence_list(abort_evidence),
        "observation_window_sec": _normalize_observation_window(observation_window_sec),
    }


def _apply_runner_auth_mode_defaults(ctx: dict[str, Any], executor: str) -> None:
    if executor == "codex":
        ctx["runner_codex_auth_mode"] = "oauth"
    elif executor == "cursor":
        ctx["runner_cursor_auth_mode"] = "oauth"
    elif executor == "gemini":
        ctx["runner_gemini_auth_mode"] = "oauth"
    elif executor == "claude":
        ctx["runner_claude_auth_mode"] = "oauth"


def _enforce_openrouter_executor_policy(ctx: dict[str, Any], executor: str) -> str:
    requested_override_raw = str(ctx.get("model_override") or "").strip()
    requested_override = routing_service.normalize_model_name(requested_override_raw)
    requested_executor = str(executor or "").strip().lower()
    wants_openrouter = requested_executor == "openrouter" or requested_override.startswith("openrouter/")
    if not wants_openrouter:
        return executor
    enforced_model = routing_service.enforce_openrouter_free_model(requested_override or "openrouter/free")
    previous_override = requested_override or ""
    ctx["model_override"] = enforced_model
    if previous_override != enforced_model:
        ctx["model_override_policy"] = {
            "kind": "openrouter_free_only",
            "requested_model_override": requested_override_raw or previous_override,
            "applied_model_override": enforced_model,
        }
    if requested_executor != "openrouter":
        ctx["executor_override_reason"] = "openrouter_model_override_requires_openrouter_executor"
    return "openrouter"


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
        data.task_type, executor, COMMAND_TEMPLATES[data.task_type]
    )
    model = str(route_info["model"])
    tier = str(route_info["tier"])
    command = (data.context or {}).get("command_override") if isinstance(data.context, dict) else None
    normalized_direction = data.direction
    if not command:
        direction = _with_agent_roles(
            data.direction, data.task_type, primary_agent=primary_agent, guard_agents=guard_agents
        )
        normalized_direction = direction
        command = build_command(direction, data.task_type, executor=executor)
        if ctx.get("model_override"):
            override = str(ctx["model_override"]).strip()
            command, applied_override = routing_service.apply_model_override(command, override)
            if applied_override:
                if executor == "codex":
                    model = f"codex/{applied_override}"
                elif executor == "cursor":
                    model = f"cursor/{applied_override}"
                elif executor == "gemini":
                    model = f"gemini/{applied_override}"
                elif executor == "openrouter":
                    model = routing_service.enforce_openrouter_free_model(applied_override)
                else:
                    model = applied_override
        if "claude -p" in command and "--dangerously-skip-permissions" not in command:
            command = command.rstrip() + " --dangerously-skip-permissions"
    provider, billing_provider, is_paid_provider = routing_service.classify_provider(
        executor=executor, model=model, command=str(command), worker_id=None
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
        task_id="", executor=executor, provider=provider, model=model, direction=normalized_direction
    )
    return model, tier, str(command), route_decision, normalized_response_call


def _claim_running_task(task: dict[str, Any], worker_id: str | None) -> None:
    now = _now()
    claimant = normalize_worker_id(worker_id)
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
            raise TaskClaimConflictError(f"Task already claimed by {existing_claimant}", claimed_by=existing_claimant)
        return

    if current_status == TaskStatus.RUNNING:
        if existing_claimant and existing_claimant != claimant:
            raise TaskClaimConflictError(f"Task already running by {existing_claimant}", claimed_by=existing_claimant)
        if not existing_claimant:
            task["claimed_by"] = claimant
            task["claimed_at"] = now
        if task.get("started_at") is None:
            task["started_at"] = now
        return

    raise TaskClaimConflictError(
        f"Task is not claimable from status {status_value(current_status)}", claimed_by=existing_claimant
    )


def create_task(data: AgentTaskCreate) -> dict[str, Any]:
    """Create task and return full task dict."""
    _ensure_store_loaded(include_output=False)
    task_id = _generate_id()
    ctx = dict(data.context or {}) if isinstance(data.context, dict) else {}
    validation = task_card_validation(ctx)
    if validation is not None:
        ctx["task_card_validation"] = validation
    target_contract = _normalize_target_state_contract(
        direction=data.direction,
        task_type=data.task_type,
        target_state=data.target_state if data.target_state is not None else ctx.get("target_state"),
        success_evidence=data.success_evidence if data.success_evidence is not None else ctx.get("success_evidence"),
        abort_evidence=data.abort_evidence if data.abort_evidence is not None else ctx.get("abort_evidence"),
        observation_window_sec=(
            data.observation_window_sec
            if data.observation_window_sec is not None
            else ctx.get("observation_window_sec")
        ),
    )
    ctx.update(target_contract)
    ctx["target_state_contract"] = dict(target_contract)

    tasks = list(_store.values())
    executor, policy_meta = select_executor(data.task_type, data.direction, ctx, tasks)
    executor = _enforce_openrouter_executor_policy(ctx, executor)
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
    apply_agent_graph_state_contract(task)
    _store[task_id] = task
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(task))
    else:
        _save_store_to_disk()
    return task


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
        "1", "true", "yes", "on",
    }:
        return None
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
    """Update task. Returns updated task or None if not found."""
    _ensure_store_loaded(include_output=False)
    task = _load_task_from_db(task_id, include_output=False) if agent_task_store_service.enabled() else None
    if task is None:
        task = _store.get(task_id)
    if task is None:
        return None
    previous_status_value = status_value(task.get("status"))

    if decision is not None and task.get("status") == TaskStatus.NEEDS_DECISION:
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
            k in next_context for k in ("target_state", "success_evidence", "abort_evidence", "observation_window_sec")
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
    apply_agent_graph_state_contract(task, preferred_state=preferred_graph_state)
    ensure_failed_task_diagnostics(task)
    task["updated_at"] = _now()
    record_completion_tracking_event(task)
    if status_value(task.get("status")) == "failed" and previous_status_value != "failed":
        record_task_failure_friction(task)
    if agent_task_store_service.enabled():
        agent_task_store_service.upsert_task(_serialize_task(task))
    else:
        _save_store_to_disk()
    return task
