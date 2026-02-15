"""Pipeline monitoring: status, attention flags, and phase coverage."""

from datetime import datetime, timezone
from typing import Any

from app.services.task_store import get_all_tasks, get_task


def get_pipeline_status(now_utc=None) -> dict[str, Any]:
    """Pipeline visibility: running, pending with wait times, recent completed with duration."""
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

    def _status_val(task: dict) -> str:
        """Normalize task status to string (handles TaskStatus enum or string)."""
        s = (task or {}).get("status", "")
        if hasattr(s, "value"):
            return getattr(s, "value", str(s))
        return str(s) if s else ""

    running = []
    pending = []
    completed = []

    for t in get_all_tasks():
        st = t.get("status")
        st_val = _status_val(t)
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
        t = get_task(running[0]["id"])
        if t:
            latest_request = {
                "task_id": t.get("id"),
                "status": "running",
                "direction": t.get("direction"),
                "prompt_preview": (t.get("command") or "")[:500],
            }
    if completed:
        t = get_task(completed[0]["id"])
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
    attention_flags = []

    # Check for stuck pipeline (pending tasks waiting > 10 min with no running tasks)
    stuck = False
    if pending and not running:
        wait_secs = [p.get("wait_seconds") for p in pending if p.get("wait_seconds") is not None]
        if wait_secs and max(wait_secs) > 600:  # 10 min (spec 032)
            stuck = True
            attention_flags.append("stuck")

    # Check for repeated failures (last 3 completed tasks all failed)
    repeated_failures = False
    if len(completed) >= 3:
        last_three = completed[:3]
        all_tasks = [get_task(c["id"]) for c in last_three]
        if all(_status_val(t or {}) == "failed" for t in all_tasks):
            repeated_failures = True
            attention_flags.append("repeated_failures")

    # Check for empty output in completed tasks
    output_empty = False
    for c in completed[:5]:
        t = get_task(c["id"]) or {}
        if len(t.get("output") or "") == 0 and _status_val(t) == "completed":
            output_empty = True
            attention_flags.append("output_empty")
            break

    # Check for executor failures (failed with empty output)
    executor_fail = False
    for c in completed[:5]:
        t = get_task(c["id"]) or {}
        if len(t.get("output") or "") == 0 and _status_val(t) == "failed":
            executor_fail = True
            attention_flags.append("executor_fail")
            break

    # Check for low success rate (requires metrics service)
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
            {**c, "output_len": len((get_task(c["id"]) or {}).get("output") or "")}
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
