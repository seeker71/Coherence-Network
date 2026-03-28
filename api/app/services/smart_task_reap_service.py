"""Smart stale-task reaping: runner/process checks, log diagnosis, partial-output metrics.

Used by ``local_runner._reap_stale_tasks`` via HTTP runner list + pure helpers (testable).
"""

from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def task_stale_age_minutes(task: dict[str, Any], now: datetime | None = None) -> float | None:
    """Minutes since last activity (updated_at → started_at → created_at)."""
    now = now or datetime.now(timezone.utc)
    for key in ("updated_at", "started_at", "created_at"):
        raw = task.get(key)
        dt: datetime | None = None
        if isinstance(raw, str):
            dt = _parse_iso_dt(raw)
        elif isinstance(raw, datetime):
            dt = raw
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (now - dt).total_seconds() / 60.0)
    return None


def normalize_claim_key(claimed_by: str | None) -> str:
    return (claimed_by or "").strip().lower()


def runners_matching_claim(claimed_by: str | None, runners: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick registry row for this task's claimant (exact / case-insensitive / substring)."""
    cb = normalize_claim_key(claimed_by)
    if not cb:
        return None
    exact: dict[str, Any] | None = None
    for r in runners:
        if not isinstance(r, dict):
            continue
        rid = normalize_claim_key(str(r.get("runner_id") or ""))
        if not rid:
            continue
        if rid == cb:
            return r
        if exact is None and (cb in rid or rid in cb):
            exact = r
    return exact


def local_pid_alive(host: str | None, pid: int | None) -> bool | None:
    """If this machine matches *host* and *pid* is set, return True/False; else None (unknown)."""
    if pid is None or int(pid) <= 0:
        return None
    local = socket.gethostname().lower()
    h = (host or "").strip().lower()
    if h and h.split(".")[0] != local.split(".")[0]:
        return None
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    except OSError:
        return None
    return True


def classify_log_error_class(log_tail: str) -> str:
    """Coarse error bucket from combined task log tail (stderr is often interleaved)."""
    t = (log_tail or "").lower()
    if not t.strip():
        return "empty_log"
    if re.search(r"\b(killed|sigkill|sigsegv|signal 9|oom|out of memory)\b", t):
        return "process_crash_or_oom"
    if "traceback" in t or "error:" in t or "exception" in t:
        return "runtime_exception"
    if "429" in t or "rate limit" in t or "too many requests" in t:
        return "rate_limit"
    if "timeout" in t or "timed out" in t:
        return "timeout_signal"
    if "modulenotfounderror" in t or "cannot find module" in t:
        return "import_error"
    if "permission denied" in t or "eacces" in t:
        return "permission"
    return "unknown_or_progress"


def read_task_log_tail(log_path: Path, *, max_bytes: int = 48_000) -> str:
    if not log_path.exists():
        return ""
    try:
        raw = log_path.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def expected_output_budget_chars(ctx: dict[str, Any], *, task_type: str) -> int:
    """Expected minimum meaningful output for partial ratio (context override → task-type default)."""
    for key in ("expected_output_chars", "min_output_chars", "task_card_min_chars"):
        v = ctx.get(key)
        if v is not None:
            try:
                n = int(v)
                if n > 0:
                    return min(n, 500_000)
            except (TypeError, ValueError):
                pass
    defaults = {"spec": 800, "impl": 2000, "test": 800, "review": 500, "code-review": 500, "heal": 500}
    return int(defaults.get(str(task_type).lower().strip(), 2000))


def partial_output_ratio(log_text: str, expected_chars: int) -> float:
    exp = max(int(expected_chars), 1)
    return min(1.0, len(log_text) / float(exp))


@dataclass
class ReapDiagnosis:
    provider: str
    error_class: str
    runner_id: str | None
    runner_online: bool | None
    runner_status: str | None
    active_task_id: str | None
    local_pid_alive: bool | None
    log_tail_excerpt: str
    partial_output_ratio: float
    has_partial_output: bool
    skip_reap_runner_active: bool
    diagnosis_summary: str


def build_reap_diagnosis(
    *,
    task_id: str,
    task: dict[str, Any],
    runner: dict[str, Any] | None,
    log_path: Path,
) -> ReapDiagnosis:
    ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    provider = str((ctx or {}).get("provider") or task.get("tier") or "unknown")
    raw_tt = task.get("task_type")
    task_type = str(raw_tt.value) if hasattr(raw_tt, "value") else str(raw_tt or "impl")

    log_tail = read_task_log_tail(log_path)
    err_cls = classify_log_error_class(log_tail[-8000:] if len(log_tail) > 8000 else log_tail)
    exp = expected_output_budget_chars(ctx or {}, task_type=task_type)
    ratio = partial_output_ratio(log_tail, exp)
    has_partial = ratio >= 0.20

    runner_online: bool | None = None
    runner_status: str | None = None
    active_tid: str | None = None
    rid: str | None = None
    pid_ok: bool | None = None

    if runner and isinstance(runner, dict):
        rid = str(runner.get("runner_id") or "") or None
        runner_online = bool(runner.get("online"))
        runner_status = str(runner.get("status") or "")
        active_tid = str(runner.get("active_task_id") or "") or None
        pid_ok = local_pid_alive(runner.get("host"), runner.get("pid"))

    skip = False
    if runner_online and runner_status == "running" and active_tid == task_id:
        skip = True
    if pid_ok is False:
        skip = False

    excerpt = log_tail[-3500:] if log_tail else ""
    parts = [
        f"provider={provider}",
        f"error_class={err_cls}",
        f"runner={rid or 'unmatched'}",
        f"online={runner_online}",
        f"partial_ratio={ratio:.3f}",
        f"partial_ge_20pct={has_partial}",
    ]
    summary = "; ".join(parts)

    return ReapDiagnosis(
        provider=provider,
        error_class=err_cls,
        runner_id=rid,
        runner_online=runner_online,
        runner_status=runner_status,
        active_task_id=active_tid,
        local_pid_alive=pid_ok,
        log_tail_excerpt=excerpt,
        partial_output_ratio=ratio,
        has_partial_output=has_partial,
        skip_reap_runner_active=skip,
        diagnosis_summary=summary,
    )


def context_patch_for_skip_reap(d: ReapDiagnosis, *, iso_now: str) -> dict[str, Any]:
    return {
        "smart_reap_diagnosis": {
            "action": "timeout_extended",
            "checked_at": iso_now,
            "provider": d.provider,
            "error_class": "none_skip",
            "runner_id": d.runner_id,
            "runner_online": d.runner_online,
            "runner_status": d.runner_status,
            "active_task_id": d.active_task_id,
            "local_pid_alive": d.local_pid_alive,
            "reason": "runner_alive_and_active_on_task",
        }
    }


def context_patch_for_reap(
    d: ReapDiagnosis,
    *,
    iso_now: str,
    stale_minutes: int,
    threshold_minutes: int,
) -> dict[str, Any]:
    return {
        "smart_reap_diagnosis": {
            "action": "reaped_timed_out",
            "checked_at": iso_now,
            "provider": d.provider,
            "error_class": d.error_class,
            "runner_id": d.runner_id,
            "runner_online": d.runner_online,
            "runner_status": d.runner_status,
            "active_task_id": d.active_task_id,
            "local_pid_alive": d.local_pid_alive,
            "partial_output_ratio": round(d.partial_output_ratio, 4),
            "has_partial_output": d.has_partial_output,
            "stale_minutes": stale_minutes,
            "threshold_minutes": threshold_minutes,
            "log_tail_excerpt": d.log_tail_excerpt[:4000],
        },
        "resume_from_partial_output": bool(d.has_partial_output),
    }
