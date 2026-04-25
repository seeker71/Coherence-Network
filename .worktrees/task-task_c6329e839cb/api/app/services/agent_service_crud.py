"""Agent task CRUD: create_task, get_task, update_task, claim, resolve_route, target state."""

import logging
from typing import Any, Optional

from app.config_loader import get_bool
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType

from app.services import agent_routing_service as routing_service
from app.services import agent_task_store_service
from app.services.app_mode import running_under_test
from app.services.agent_service_executor import (
    AGENT_BY_TASK_TYPE,
    COMMAND_TEMPLATES,
    GUARD_AGENTS_BY_TASK_TYPE,
    apply_resume_to_command,
    apply_runner_auth_defaults,
    build_command,
    format_model_override,
    post_process_command,
    select_executor,
    task_card_validation,
    _with_agent_roles,
)
from app.services.agent_routing.prompt_templates_loader import build_default_task_card_context
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
from app.services.context_hygiene_service import annotate_task_context

log = logging.getLogger(__name__)

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


def _enforce_openrouter_executor_policy(ctx: dict[str, Any], executor: str) -> str:
    # Pipeline tasks run on federation nodes, not openrouter
    if ctx.get("auto_advance_source") or ctx.get("auto_retry_source") or ctx.get("bootstrap_source"):
        ctx.pop("model_override", None)
        ctx.pop("executor", None)
        return "federation"

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
        command = apply_resume_to_command(executor, command, ctx)
        command = post_process_command(executor, command)
        if ctx.get("model_override"):
            override = str(ctx["model_override"]).strip()
            command, applied_override = routing_service.apply_model_override(command, override)
            if applied_override:
                model = format_model_override(executor, applied_override)
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
    """Create task and return full task dict. Reuses existing active task when context has task_fingerprint."""
    _ensure_store_loaded(include_output=False)
    ctx = dict(data.context or {}) if isinstance(data.context, dict) else {}
    ctx = build_default_task_card_context(data.task_type, data.direction, ctx)
    fingerprint = (ctx.get("task_fingerprint") or "").strip()
    if fingerprint:
        from app.services.agent_service_active_task import find_active_task_by_fingerprint
        existing = find_active_task_by_fingerprint(fingerprint)
        if existing is not None:
            existing["updated_at"] = _now()
            if agent_task_store_service.enabled():
                agent_task_store_service.upsert_task(_serialize_task(existing))
            else:
                _save_store_to_disk()
            return existing
    task_id = _generate_id()
    ctx["task_card_validation"] = task_card_validation(ctx)
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
    apply_runner_auth_defaults(executor, ctx)
    primary_agent = AGENT_BY_TASK_TYPE.get(data.task_type)
    guard_agents = GUARD_AGENTS_BY_TASK_TYPE.get(data.task_type, [])
    if primary_agent:
        ctx["task_agent"] = primary_agent
    if guard_agents:
        # Phase 4: Tool Overhead Controls (Context Efficiency)
        # Prune guard agents if the task is simple to save tokens
        files_allowed = _normalize_evidence_list(ctx.get("files_allowed") or ctx.get("task_card", {}).get("files_allowed"))
        is_simple = len(data.direction) < 400 and len(files_allowed) <= 2
        if is_simple and data.task_type not in (TaskType.REVIEW, TaskType.CODE_REVIEW):
            ctx["guard_agents_pruned"] = list(guard_agents)
            guard_agents = []
        else:
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
    # Resolve workspace_id from linked idea (if any) at creation time so
    # the tenant mapping is stable and filterable at the SQL layer.
    task_workspace_id: str | None = None
    linked_idea_id = str(ctx.get("idea_id") or "").strip() or str((data.context or {}).get("idea_id") or "").strip()
    if linked_idea_id:
        try:
            from app.services import idea_service
            linked_idea = idea_service.get_idea(linked_idea_id)
            if linked_idea is not None:
                resolved_ws = getattr(linked_idea, "workspace_id", None)
                if isinstance(resolved_ws, str) and resolved_ws.strip():
                    task_workspace_id = resolved_ws.strip()
        except Exception:
            task_workspace_id = None
    # Also honor an explicit workspace_id on the task context (caller-supplied override).
    explicit_ws = str(ctx.get("workspace_id") or "").strip()
    if explicit_ws:
        task_workspace_id = explicit_ws
    # Default tenant fallback keeps legacy tasks discoverable by the default workspace.
    if not task_workspace_id:
        task_workspace_id = "coherence-network"

    # Workspace-scoped provider preference
    if task_workspace_id and not explicit_ws:
        # Only look up workspace provider if we resolved from idea (not explicit)
        pass  # Provider already inherited from workspace
    if task_workspace_id and not ctx.get("executor"):
        try:
            from app.services import workspace_service
            ws_data = workspace_service.get_workspace(task_workspace_id)
            if ws_data and hasattr(ws_data, "default_provider") and ws_data.default_provider:
                ctx["executor"] = ws_data.default_provider
                log.info("TASK workspace_provider=%s from workspace=%s", ws_data.default_provider, task_workspace_id)
        except Exception:
            pass

    # Workspace-scoped repo_url injection
    if task_workspace_id and not ctx.get("repo_url"):
        try:
            from app.services import workspace_service
            ws_data = workspace_service.get_workspace(task_workspace_id)
            if ws_data and hasattr(ws_data, "repo_url") and ws_data.repo_url:
                ctx["repo_url"] = ws_data.repo_url
        except Exception:
            pass

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
        "workspace_id": task_workspace_id,
    }
    apply_agent_graph_state_contract(task)
    task["context"] = annotate_task_context(task)
    
    # Phase 2: Enforcement (Lean Task-Card & File-Scope Gates)
    hygiene = task["context"].get("context_hygiene", {})
    task_card_val = task["context"].get("task_card_validation", {})
    file_scope_count = hygiene.get("file_scope_count", 0)

    # Hard limit: reject tasks with >40 files outright
    if file_scope_count > 40:
        task["status"] = TaskStatus.FAILED
        task["output"] = (
            f"FILE_SCOPE_HARD_LIMIT: Task lists {file_scope_count} files. "
            f"Maximum allowed is 40. Split this into smaller tasks with exact file paths."
        )
    # Soft gate: broad file scope (>20 files)
    elif file_scope_count > 20:
        task["status"] = TaskStatus.NEEDS_DECISION
        task["decision_prompt"] = (
            f"BROAD_FILE_SCOPE: Task touches {file_scope_count} files. "
            f"Narrow files_allowed to ≤20 exact paths before execution."
        )
    # Soft gate: weak task card (score <0.4 = ≤1 of 5 required fields)
    # Only fires when caller provided structured context (task_card or files_allowed),
    # not for bare API-created tasks with empty context.
    elif (
        task_card_val.get("score", 1.0) < 0.4
        and (ctx.get("task_card") or ctx.get("files_allowed"))
    ):
        missing = task_card_val.get("missing", [])
        task["status"] = TaskStatus.NEEDS_DECISION
        task["decision_prompt"] = (
            f"WEAK_TASK_CARD: Task card is missing {', '.join(missing)}. "
            f"Add goal/files_allowed/done_when/commands/constraints before execution."
        )
    # Soft gate: oversized direction (>3000 chars)
    elif len(task.get("direction", "")) > 3000:
        task["status"] = TaskStatus.NEEDS_DECISION
        task["decision_prompt"] = (
            f"OVERSIZED_DIRECTION: Direction is {len(task['direction'])} chars. "
            f"Summarize into a shorter task card (<3000 chars)."
        )
    # Catch-all: overall hygiene score <40
    elif hygiene.get("score", 100) < 40:
        task["status"] = TaskStatus.NEEDS_DECISION
        task["decision_prompt"] = (
            f"LOW_CONTEXT_HYGIENE (Score: {hygiene.get('score')}). "
            f"This task is too bloated to execute efficiently. "
            f"Flags: {', '.join([flag['id'] for flag in hygiene.get('flags', [])])}. "
            f"Please narrow the file scope or shorten the direction before continuing."
        )

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
    if running_under_test() and not get_bool(
        "agent_tasks",
        "runtime_fallback_in_tests",
        default=False,
    ):
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
    error_category: Optional[str] = None,
    error_summary: Optional[str] = None,
) -> Optional[dict]:
    """Update task. Returns updated task or None if not found."""
    _ensure_store_loaded(include_output=False)
    task = _load_task_from_db(task_id, include_output=True) if agent_task_store_service.enabled() else None
    if task is None:
        task = _store.get(task_id)
    if task is None:
        return None
    previous_status_value = status_value(task.get("status"))

    if decision is not None and task.get("status") == TaskStatus.NEEDS_DECISION:
        # Decisions bypass claim check — the decision resolves the block
        task["status"] = TaskStatus.RUNNING
        task["decision"] = decision

    if status is not None:
        if status == TaskStatus.RUNNING:
            _claim_running_task(task, worker_id)
        else:
            task["status"] = status

    if output is not None:
        task["output"] = _sanitize_task_output(output)
        from app.services.context_hygiene_service import generate_output_summary
        task["output_summary"] = generate_output_summary(
            task.get("output"),
            str(task.get("status", "")),
            task.get("error_category"),
        )
    if progress_pct is not None:
        task["progress_pct"] = progress_pct
    if current_step is not None:
        task["current_step"] = current_step
    if decision_prompt is not None:
        task["decision_prompt"] = decision_prompt
    if decision is not None and task.get("decision") is None:
        task["decision"] = decision
    # DG-015 fix: persist error_category and error_summary from runner
    if error_category is not None:
        task["error_category"] = error_category
    if error_summary is not None:
        task["error_summary"] = error_summary
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
    task["context"] = annotate_task_context(task)
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
