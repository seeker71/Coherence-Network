"""Smart reaper service: diagnose stuck tasks before reaping them.

Spec: smart-reap-diagnose-resume
Before marking a task timed_out, this service:
  1. Queries the runner that claimed the task — is it still alive?
  2. Checks whether the provider process (by PID) is still running.
  3. If provider is still running but slow: signals to extend timeout, not kill.
  4. If provider crashed: captures stderr/partial output from the task log.
  5. Writes structured diagnosis into task context (provider, error_class, partial output).
  6. If partial output >20% of expected: marks task as having resumable checkpoint.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Optional psutil for richer process inspection
try:
    import psutil  # type: ignore[import-untyped]

    _HAVE_PSUTIL = True
except ImportError:
    _HAVE_PSUTIL = False

# Thresholds
DEFAULT_PARTIAL_THRESHOLD = 0.20   # >20% of expected output = resumable
DEFAULT_EXPECTED_OUTPUT_CHARS = 2000
DEFAULT_SLOW_MULTIPLIER = 1.5      # extend if age < max_age * 1.5

# Error class constants
EC_RUNNER_DEAD = "runner_dead"
EC_PROVIDER_CRASHED = "provider_crashed"
EC_SLOW_PROVIDER = "slow_provider"
EC_UNKNOWN = "unknown"


def _is_pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID is currently running."""
    if pid <= 0:
        return False
    if _HAVE_PSUTIL:
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    # Fallback: os.kill signal 0 — works on POSIX; on Windows returns True for any alive PID
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _read_tail(path: Path, chars: int = 3000) -> str:
    """Read the last `chars` characters from a file, returning empty string on error."""
    try:
        content = path.read_text(errors="replace")
        return content[-chars:] if len(content) > chars else content
    except Exception:
        return ""


def _estimate_partial_pct(partial_output: str, expected_chars: int = DEFAULT_EXPECTED_OUTPUT_CHARS) -> float:
    """Estimate how complete the partial output is (0.0–1.0).

    Uses character count relative to expected_chars as a proxy.
    Capped at 1.0 — a long partial is still 100% in this model.
    """
    if expected_chars <= 0:
        return 0.0
    actual = len(partial_output.strip())
    return min(1.0, actual / expected_chars)


def _parse_runner_online(runner_record: dict[str, Any], now: datetime) -> bool | None:
    """Determine if the runner is online from its lease_expires_at field."""
    lease_raw = runner_record.get("lease_expires_at")
    if not lease_raw:
        return None
    try:
        expires = datetime.fromisoformat(str(lease_raw).replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > now
    except Exception:
        return None


def _age_minutes(task: dict[str, Any], now: datetime) -> float:
    """Return how many minutes since the task was started/updated/created."""
    for key in ("started_at", "updated_at", "created_at"):
        raw = task.get(key)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (now - dt).total_seconds() / 60)
        except Exception:
            continue
    return 0.0


def diagnose_task(
    task: dict[str, Any],
    *,
    log_dir: Path,
    runner_map: dict[str, dict[str, Any]],
    now: datetime | None = None,
    max_age_minutes: int = 15,
    slow_multiplier: float = DEFAULT_SLOW_MULTIPLIER,
    partial_threshold: float = DEFAULT_PARTIAL_THRESHOLD,
    expected_output_chars: int = DEFAULT_EXPECTED_OUTPUT_CHARS,
) -> dict[str, Any]:
    """Diagnose a potentially stuck task before deciding to reap it.

    Args:
        task: Task dict as returned by the API (id, claimed_by, context, …).
        log_dir: Directory where per-task log files live (``task_{id}.log``).
        runner_map: Dict keyed by runner_id → runner record (from registry).
        now: Current UTC datetime (default: datetime.now(utc)).
        max_age_minutes: Age threshold used for normal reaping.
        slow_multiplier: If age < max_age * slow_multiplier, extend instead of reap.
        partial_threshold: Fraction (0–1) above which output is considered resumable.
        expected_output_chars: Expected output size used for completeness estimate.

    Returns a dict with keys:
        should_reap (bool): Task should be marked timed_out.
        should_extend (bool): Timeout should be extended — do NOT reap yet.
        runner_alive (bool | None): Whether the claiming runner is still online.
        provider_pid_alive (bool | None): Whether the runner PID is still alive.
        partial_output (str): Captured tail of the task log file.
        partial_pct (float): Estimated output completeness (0.0–1.0).
        has_partial (bool): True if partial_pct >= partial_threshold.
        error_class (str): Classification: runner_dead / provider_crashed /
                           slow_provider / unknown.
        diagnosis_text (str): Human-readable summary for storage.
        checkpoint_summary (str): Contents of .task-checkpoint.md if found.
        context_patch (dict): Fields to merge into the task context dict.
    """
    _now = now or datetime.now(timezone.utc)

    task_id = str(task.get("id") or "").strip()
    ctx = task.get("context") or {}
    claimed_by = str(task.get("claimed_by") or ctx.get("claimed_by") or "").strip()
    provider = str(ctx.get("provider") or task.get("provider") or "unknown").strip()

    # ── 1. Runner liveness ──────────────────────────────────────────────────
    runner_alive: bool | None = None
    runner_pid: int | None = None

    runner_record = runner_map.get(claimed_by)
    if runner_record is None and ":" in claimed_by:
        # Some runner IDs are "hostname:uuid" — try prefix lookup
        runner_record = runner_map.get(claimed_by.split(":")[0])
    if runner_record:
        runner_alive = _parse_runner_online(runner_record, _now)
        pid_val = runner_record.get("pid")
        if pid_val:
            try:
                runner_pid = int(pid_val)
            except Exception:
                pass

    # ── 2. Provider process liveness (PID check) ───────────────────────────
    provider_pid_alive: bool | None = None
    if runner_pid:
        provider_pid_alive = _is_pid_alive(runner_pid)
        # If lease is expired but PID is alive, treat runner as alive
        if runner_alive is None:
            runner_alive = provider_pid_alive

    # ── 3. Capture partial output from log ────────────────────────────────
    log_path = log_dir / f"task_{task_id}.log"
    partial_output = _read_tail(log_path) if log_path.exists() else ""
    partial_pct = _estimate_partial_pct(partial_output, expected_output_chars)
    has_partial = partial_pct >= partial_threshold

    # ── 4. Read checkpoint if present in worktree ─────────────────────────
    checkpoint_summary = ""
    slug = task_id[:16]
    # worktree_base lives two levels above log_dir: api/logs → api → repo/.worktrees
    worktree_base = log_dir.parent.parent / ".worktrees"
    wt_path = worktree_base / f"task-{slug}"
    if wt_path.exists():
        cp_file = wt_path / ".task-checkpoint.md"
        if cp_file.exists():
            try:
                checkpoint_summary = cp_file.read_text(errors="replace")[:2000]
            except Exception:
                pass

    # ── 5. Age ────────────────────────────────────────────────────────────
    age_min = _age_minutes(task, _now)

    # ── 6. Classify ───────────────────────────────────────────────────────
    should_reap = False
    should_extend = False
    error_class = EC_UNKNOWN

    if runner_alive is False:
        # Runner has gone offline — no point waiting
        should_reap = True
        error_class = EC_RUNNER_DEAD
    elif provider_pid_alive is True:
        # Process is confirmed alive — maybe just slow
        if age_min < max_age_minutes * slow_multiplier:
            should_extend = True
            error_class = EC_SLOW_PROVIDER
        else:
            # Even with extended patience, it's way overdue
            should_reap = True
            error_class = EC_SLOW_PROVIDER
    else:
        # Cannot confirm process running — default to reap
        should_reap = True
        if partial_output and (
            "traceback" in partial_output.lower()
            or "exit code" in partial_output.lower()
            or "killed" in partial_output.lower()
            or "signal" in partial_output.lower()
        ):
            error_class = EC_PROVIDER_CRASHED
        else:
            error_class = EC_UNKNOWN

    # ── 7. Build human-readable diagnosis ─────────────────────────────────
    parts = [f"Stuck {int(age_min)}m (threshold {max_age_minutes}m)"]
    if runner_alive is not None:
        parts.append(f"runner_alive={runner_alive}")
    if provider_pid_alive is not None:
        parts.append(f"pid_alive={provider_pid_alive}")
    parts.append(f"error_class={error_class}")
    parts.append(f"provider={provider}")
    if partial_pct > 0:
        parts.append(f"partial={int(partial_pct * 100)}%")
    if checkpoint_summary:
        parts.append("checkpoint=captured")
    diagnosis_text = " | ".join(parts)

    # ── 8. Build context patch ────────────────────────────────────────────
    diag_block: dict[str, Any] = {
        "error_class": error_class,
        "runner_alive": runner_alive,
        "provider_pid_alive": provider_pid_alive,
        "partial_pct": round(partial_pct, 3),
        "has_partial": has_partial,
        "age_min": round(age_min, 1),
        "reaped_at": _now.isoformat().replace("+00:00", "Z"),
        "provider": provider,
    }
    if has_partial:
        diag_block["partial_output_snippet"] = partial_output[-500:]
    if checkpoint_summary:
        diag_block["checkpoint_captured"] = True

    context_patch: dict[str, Any] = {"smart_reap_diagnosis": diag_block}
    if checkpoint_summary:
        context_patch["checkpoint_summary"] = checkpoint_summary[:2000]

    return {
        "should_reap": should_reap,
        "should_extend": should_extend,
        "runner_alive": runner_alive,
        "provider_pid_alive": provider_pid_alive,
        "partial_output": partial_output,
        "partial_pct": partial_pct,
        "has_partial": has_partial,
        "error_class": error_class,
        "diagnosis_text": diagnosis_text,
        "checkpoint_summary": checkpoint_summary,
        "context_patch": context_patch,
    }


def build_runner_map(runners: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a lookup dict from a list of runner records (keyed by runner_id)."""
    result: dict[str, dict[str, Any]] = {}
    for r in runners:
        rid = str(r.get("runner_id") or "").strip()
        if rid:
            result[rid] = r
    return result


def diagnose_batch(
    tasks: list[dict[str, Any]],
    *,
    log_dir: Path,
    runners: list[dict[str, Any]],
    now: datetime | None = None,
    max_age_minutes: int = 15,
    slow_multiplier: float = DEFAULT_SLOW_MULTIPLIER,
    partial_threshold: float = DEFAULT_PARTIAL_THRESHOLD,
) -> list[dict[str, Any]]:
    """Diagnose a batch of stuck tasks. Returns a list of diagnosis results.

    Each result dict includes the original task under key ``task``.
    """
    _now = now or datetime.now(timezone.utc)
    runner_map = build_runner_map(runners)
    results = []
    for task in tasks:
        diag = diagnose_task(
            task,
            log_dir=log_dir,
            runner_map=runner_map,
            now=_now,
            max_age_minutes=max_age_minutes,
            slow_multiplier=slow_multiplier,
            partial_threshold=partial_threshold,
        )
        diag["task"] = task
        results.append(diag)
    return results
