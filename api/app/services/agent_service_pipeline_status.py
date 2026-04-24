"""Agent pipeline status: running, pending, completed with attention and diagnostics."""

from datetime import datetime, timezone
from typing import Any

from app.services.agent_service_store import _ensure_store_loaded, _store
from app.services.agent_service_task_derive import (
    failure_classification,
    status_value,
    task_output_text,
    task_type_name,
)


def _pipeline_task_status_item(task: dict[str, Any], now: datetime) -> tuple[str, dict[str, Any]]:
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
            return int((now - ts).total_seconds())
        except Exception:
            return None

    def _duration(start_ts: Any, end_ts: Any) -> int | None:
        if start_ts is None or end_ts is None:
            return None
        try:
            return int((end_ts - start_ts).total_seconds())
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


def _collect_pipeline_status_items(now: datetime) -> tuple[list[dict], list[dict], list[dict]]:
    running, pending, completed = [], [], []
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
    running: list[dict], completed: list[dict]
) -> tuple[dict | None, dict | None]:
    latest_request = latest_response = None
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
            out = task_output_text(task)
            latest_response = {
                "task_id": task.get("id"),
                "status": task.get("status"),
                "output_preview": out[:2000],
                "output_len": len(out),
            }
    return latest_request, latest_response


def _pipeline_attention_summary(
    running: list[dict], pending: list[dict], completed: list[dict]
) -> dict[str, Any]:
    attention_flags = []
    stuck = False
    if pending and not running:
        wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
        if wait_secs and max(wait_secs) > 600:
            stuck = True
            attention_flags.append("stuck")
    repeated_failures = False
    if len(completed) >= 3:
        last_three = completed[:3]
        if all(status_value((_store.get(c["id"]) or {}).get("status")) == "failed" for c in last_three):
            repeated_failures = True
            attention_flags.append("repeated_failures")
    output_empty = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(task_output_text(t)) == 0 and status_value(t.get("status")) == "completed":
            output_empty = True
            attention_flags.append("output_empty")
            break
    executor_fail = False
    for completed_item in completed[:5]:
        t = _store.get(completed_item["id"]) or {}
        if len(task_output_text(t)) == 0 and status_value(t.get("status")) == "failed":
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
        pass
    by_phase = {"spec": 0, "impl": 0, "test": 0, "review": 0}
    for item in running + pending:
        tt = item.get("task_type")
        tt_val = tt.value if hasattr(tt, "value") else str(tt)
        if tt_val in by_phase:
            by_phase[tt_val] += 1
    return {
        "stuck": stuck,
        "repeated_failures": repeated_failures,
        "output_empty": output_empty,
        "executor_fail": executor_fail,
        "low_success_rate": low_success_rate,
        "flags": attention_flags,
        "by_phase": by_phase,
    }


def _pipeline_queue_diagnostics(
    running: list[dict], pending: list[dict], completed: list[dict]
) -> dict[str, Any]:
    pending_by_task_type = {}
    running_by_task_type = {}
    for item in pending:
        key = task_type_name(item.get("task_type")) or "unknown"
        pending_by_task_type[key] = pending_by_task_type.get(key, 0) + 1
    for item in running:
        key = task_type_name(item.get("task_type")) or "unknown"
        running_by_task_type[key] = running_by_task_type.get(key, 0) + 1
    reason_counts: dict[str, int] = {}
    signature_counts: dict[str, int] = {}
    recent_failed: list[dict[str, Any]] = []
    recent_zero_output_resolved: list[dict[str, Any]] = []
    for item in completed[:20]:
        task = _store.get(item.get("id")) or {}
        st = status_value(task.get("status"))
        if st not in {"completed", "failed"}:
            continue
        if len(task_output_text(task).strip()) > 0:
            continue
        recent_zero_output_resolved.append(
            {
                "task_id": task.get("id"),
                "task_type": task_type_name(task.get("task_type")) or "unknown",
                "status": st,
            }
        )
    for task in _recent_failed_tasks(limit=12):
        classified = failure_classification(task)
        reason = classified["bucket"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        ctx = task.get("context") or {}
        failure_signature = str(ctx.get("failure_signature") or "").strip() if isinstance(ctx, dict) else ""
        signature = classified.get("signature") or failure_signature
        if signature:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
        recent_failed.append({
            "task_id": task.get("id"),
            "task_type": task_type_name(task.get("task_type")) or "unknown",
            "reason": reason,
            "signature": signature,
        })
    recent_failed_reasons = [
        {"reason": r, "count": c} for r, c in sorted(reason_counts.items(), key=lambda row: (-row[1], row[0]))
    ]
    recent_failed_signatures = [
        {"signature": r, "count": c} for r, c in sorted(signature_counts.items(), key=lambda row: (-row[1], row[0]))
    ]
    total_pending = sum(pending_by_task_type.values())
    dominant_pending_type = ""
    dominant_pending_share = 0.0
    if total_pending > 0:
        dominant_pending_type, dominant_count = max(pending_by_task_type.items(), key=lambda row: row[1])
        dominant_pending_share = round(float(dominant_count) / float(total_pending), 4)
    queue_mix_warning = bool(total_pending >= 5 and dominant_pending_share >= 0.8)
    return {
        "pending_by_task_type": pending_by_task_type,
        "running_by_task_type": running_by_task_type,
        "recent_failed_count": len(recent_failed),
        "recent_failed": recent_failed[:5],
        "recent_failed_reasons": recent_failed_reasons,
        "recent_failed_signatures": recent_failed_signatures,
        "recent_zero_output_resolved_count": len(recent_zero_output_resolved),
        "recent_zero_output_resolved": recent_zero_output_resolved[:5],
        "queue_mix_warning": queue_mix_warning,
        "dominant_pending_task_type": dominant_pending_type,
        "dominant_pending_share": dominant_pending_share,
    }


def _task_updated_timestamp(task: dict[str, Any]) -> float:
    value = task.get("updated_at") or task.get("created_at")
    if hasattr(value, "timestamp"):
        try:
            return float(value.timestamp())
        except Exception:
            return 0.0
    return 0.0


def _recent_failed_tasks(*, limit: int) -> list[dict[str, Any]]:
    failed = [task for task in _store.values() if status_value(task.get("status")) == "failed"]
    failed.sort(key=_task_updated_timestamp, reverse=True)
    return failed[:limit]


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
            {**c, "output_len": len(task_output_text(_store.get(c["id"]) or {}))}
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
