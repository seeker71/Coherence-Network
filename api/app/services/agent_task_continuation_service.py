"""Post-execution task continuation helpers.

When the queue is empty after a task finishes, seed follow-up work from
spec/idea inventories and optionally execute the next task automatically.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from app.services import agent_execution_service as execution_service


def _continuous_flag(env_name: str) -> bool:
    configured = execution_service.os.getenv(env_name)
    if configured is not None and str(configured).strip():
        return execution_service._truthy(str(configured))
    return bool(str(execution_service.os.getenv("RAILWAY_ENVIRONMENT") or "").strip())


def _continuous_autofill_enabled() -> bool:
    return _continuous_flag("AGENT_CONTINUOUS_AUTOFILL")


def _continuous_autofill_autorun_enabled() -> bool:
    return _continuous_flag("AGENT_CONTINUOUS_AUTOFILL_AUTORUN")


def _open_task_count() -> int:
    total = 0
    for status in (
        execution_service.TaskStatus.PENDING,
        execution_service.TaskStatus.RUNNING,
        execution_service.TaskStatus.NEEDS_DECISION,
    ):
        _, count = execution_service.agent_service.list_tasks(status=status, limit=1, offset=0)
        total += int(count)
    return total


def _extract_created_task_ids(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return []

    ids: list[str] = []
    seen: set[str] = set()

    def _append(candidate: Any) -> None:
        task_id = str(candidate or "").strip()
        if not task_id or task_id in seen:
            return
        seen.add(task_id)
        ids.append(task_id)

    created = payload.get("created_task")
    if isinstance(created, dict):
        _append(created.get("id"))

    created_many = payload.get("created_tasks")
    if isinstance(created_many, list):
        for row in created_many:
            if not isinstance(row, dict):
                continue
            _append(row.get("task_id") or row.get("id"))
    return ids


def _seed_next_tasks() -> tuple[list[str], str]:
    from app.services import inventory_service

    spec_report = inventory_service.sync_spec_implementation_gap_tasks(create_task=True, limit=80)
    spec_ids = _extract_created_task_ids(spec_report)
    if spec_ids:
        return spec_ids, "spec_implementation_gap"

    roi_report = inventory_service.next_highest_roi_task_from_answered_questions(create_task=True)
    roi_ids = _extract_created_task_ids(roi_report)
    if roi_ids:
        return roi_ids, "idea_answered_question_roi"

    flow_report = inventory_service.next_unblock_task_from_flow(
        create_task=True,
        runtime_window_seconds=86400,
    )
    flow_ids = _extract_created_task_ids(flow_report)
    if flow_ids:
        return flow_ids, "idea_unblock_flow"
    return [], "none"


def _schedule_followup_execution(
    *,
    task_id: str,
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    execute_callback: Callable[..., dict[str, Any]],
) -> None:
    def _runner() -> None:
        try:
            execute_callback(
                task_id,
                worker_id=worker_id,
                force_paid_providers=force_paid_providers,
                max_cost_usd=max_cost_usd,
                estimated_cost_usd=estimated_cost_usd,
                cost_slack_ratio=cost_slack_ratio,
            )
        except Exception:
            return

    threading.Thread(target=_runner, name=f"agent-followup-{task_id}", daemon=True).start()


def _record_continuation_event(
    *,
    previous_task_id: str,
    source: str,
    created_ids: list[str],
    auto_run: bool,
) -> None:
    execution_service.runtime_service.record_event(
        execution_service.RuntimeEventCreate(
            source="worker",
            endpoint="tool:agent-task-continuation",
            method="RUN",
            status_code=200,
            runtime_ms=1.0,
            idea_id="coherence-network-agent-pipeline",
            metadata=execution_service._compact_metadata(
                {
                    "tracking_kind": "agent_task_continuation",
                    "task_id": previous_task_id,
                    "source": source,
                    "created_count": len(created_ids),
                    "created_task_ids": ",".join(created_ids[:10]),
                    "auto_run": auto_run,
                }
            ),
        )
    )


def maybe_continue_after_finish(
    *,
    previous_task_id: str,
    result: dict[str, Any],
    worker_id: str,
    force_paid_providers: bool,
    max_cost_usd: float | None,
    estimated_cost_usd: float | None,
    cost_slack_ratio: float | None,
    execute_callback: Callable[..., dict[str, Any]],
) -> None:
    if not _continuous_autofill_enabled():
        return
    if str(result.get("status") or "").strip().lower() not in {"completed", "failed"}:
        return

    try:
        if _open_task_count() > 0:
            return

        created_ids, source = _seed_next_tasks()
        if not created_ids:
            return

        auto_run = _continuous_autofill_autorun_enabled()
        if auto_run:
            _schedule_followup_execution(
                task_id=created_ids[0],
                worker_id=f"{worker_id}:autofill",
                force_paid_providers=force_paid_providers,
                max_cost_usd=max_cost_usd,
                estimated_cost_usd=estimated_cost_usd,
                cost_slack_ratio=cost_slack_ratio,
                execute_callback=execute_callback,
            )
        _record_continuation_event(
            previous_task_id=previous_task_id,
            source=source,
            created_ids=created_ids,
            auto_run=auto_run,
        )
    except Exception:
        return
