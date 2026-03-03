#!/usr/bin/env python3
"""Agent runner: polls pending tasks, runs commands, PATCHes status.

Usage:
  python scripts/agent_runner.py [--interval 10] [--once] [--verbose] [--workers N]

Requires API running. With Cursor executor, --workers N runs up to N tasks in parallel.
When task reaches needs_decision, runner stops for that task; user replies via /reply.

Debug: Logs to api/logs/agent_runner.log; full output in api/logs/task_{id}.log
"""

import argparse
import base64
import logging
import math
import os
import pwd
import socket
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from typing import Any, Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)
os.chdir(os.path.dirname(_api_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_api_dir, ".env"), override=True)
except ImportError:
    pass

import httpx

BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8000")
LOG_DIR = os.path.join(_api_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "agent_runner.log")
# Local models need longer; cloud/Claude typically faster. Default 1h for local, 10min for cloud.
TASK_TIMEOUT = int(os.environ.get("AGENT_TASK_TIMEOUT", "3600"))
HTTP_TIMEOUT = int(os.environ.get("AGENT_HTTP_TIMEOUT", "30"))
MAX_RETRIES = int(os.environ.get("AGENT_HTTP_RETRIES", "3"))
RETRY_BACKOFF = 2  # seconds between retries
REPO_PATH = os.path.abspath(os.environ.get("AGENT_WORKTREE_PATH", os.path.dirname(_api_dir)))
REPO_GIT_URL = os.environ.get("AGENT_REPO_GIT_URL", "").strip()
DEFAULT_GITHUB_REPO = os.environ.get("AGENT_GITHUB_REPO", "seeker71/Coherence-Network")
DEFAULT_PR_BASE_BRANCH = os.environ.get("AGENT_PR_BASE_BRANCH", "main")
DEFAULT_PR_LOCAL_CHECK_CMD = os.environ.get(
    "AGENT_PR_LOCAL_VALIDATION_CMD",
    "bash ./scripts/verify_worktree_local_web.sh",
)
MAX_PR_GATE_ATTEMPTS = max(1, int(os.environ.get("AGENT_PR_GATE_ATTEMPTS", "8")))
PR_GATE_POLL_SECONDS = max(5, int(os.environ.get("AGENT_PR_GATE_POLL_SECONDS", "30")))
PR_FLOW_TIMEOUT_SECONDS = max(
    5,
    int(os.environ.get("AGENT_PR_FLOW_TIMEOUT_SECONDS", str(60 * 60))),
)
MAX_RESUME_ATTEMPTS = max(0, int(os.environ.get("AGENT_MAX_RESUME_ATTEMPTS", "2")))
RUN_HEARTBEAT_SECONDS = max(5, int(os.environ.get("AGENT_RUN_HEARTBEAT_SECONDS", "15")))
RUN_LEASE_SECONDS = max(15, int(os.environ.get("AGENT_RUN_LEASE_SECONDS", "120")))
PERIODIC_CHECKPOINT_SECONDS = max(0, int(os.environ.get("AGENT_PERIODIC_CHECKPOINT_SECONDS", "300")))
CONTROL_POLL_SECONDS = max(2, int(os.environ.get("AGENT_CONTROL_POLL_SECONDS", "5")))
DIAGNOSTIC_TIMEOUT_SECONDS = max(10, int(os.environ.get("AGENT_DIAGNOSTIC_TIMEOUT_SECONDS", "120")))
TASK_LOG_TAIL_CHARS = max(200, int(os.environ.get("AGENT_TASK_LOG_TAIL_CHARS", "2000")))
MAX_RUN_RECORDS = max(50, int(os.environ.get("AGENT_RUN_RECORDS_MAX", "5000")))
RUN_RECORDS_FILE = os.path.join(LOG_DIR, "agent_runner_runs.json")
RUN_RECORDS_LOCK = threading.Lock()


def _tool_token(command: str) -> str:
    """Extract best-effort tool token from a shell command."""
    s = (command or "").strip()
    if not s:
        return "unknown"
    # Very simple parse: first token.
    return s.split()[0].strip() or "unknown"


def _model_is_paid(model: str) -> bool:
    """Best-effort paid-provider inference for runtime telemetry."""
    normalized = (model or "").strip().lower()
    if not normalized:
        return False
    if "free" in normalized:
        return False
    return True


def _scrub_command(command: str) -> str:
    """Best-effort scrub of secrets in command strings before writing to friction notes."""
    s = (command or "").replace("\n", " ").strip()
    if not s:
        return ""
    # Redact common token prefixes.
    redactions = ("gho_", "ghp_", "github_pat_", "sk-", "rk-", "xoxb-", "xoxp-")
    for pref in redactions:
        if pref in s:
            # Keep prefix visible, redact remainder of token chunk.
            parts = s.split(pref)
            rebuilt = parts[0]
            for tail in parts[1:]:
                # Redact until next whitespace.
                rest = tail.split(None, 1)
                redacted = pref + "REDACTED"
                rebuilt += redacted + ((" " + rest[1]) if len(rest) == 2 else "")
            s = rebuilt
    return s[:240]


def _time_cost_per_second() -> float:
    """Convert wall time into an energy loss estimate. Units are relative (not dollars)."""
    try:
        v = float(os.environ.get("PIPELINE_TIME_COST_PER_SECOND", "0.01"))
    except ValueError:
        v = 0.01
    return max(0.0, v)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "y"}


def _safe_get_task_context(task: object) -> dict[str, Any]:
    if isinstance(task, dict):
        context = task.get("context")
        if isinstance(context, dict):
            return context
    return {}


def _tail_text(value: str, max_chars: int) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _tail_output_lines(lines: list[str], max_chars: int = TASK_LOG_TAIL_CHARS) -> str:
    if not lines:
        return ""
    tail = "".join(lines[-160:])
    return _tail_text(tail, max_chars)


def _safe_get_task_snapshot(client: httpx.Client, task_id: str) -> dict[str, Any] | None:
    getter = getattr(client, "get", None)
    if getter is None:
        return None
    try:
        response = getter(f"{BASE}/api/agent/tasks/{task_id}", timeout=HTTP_TIMEOUT)
    except TypeError:
        try:
            response = getter(f"{BASE}/api/agent/tasks/{task_id}")
        except Exception:
            return None
    except Exception:
        return None
    if getattr(response, "status_code", 0) != 200:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_control_signals(task_snapshot: dict[str, Any] | None) -> tuple[bool, str, dict[str, Any] | None]:
    if not isinstance(task_snapshot, dict):
        return False, "", None
    context = _safe_get_task_context(task_snapshot)
    if not context:
        return False, "", None

    control = context.get("control")
    abort_requested = _as_bool(context.get("abort_requested")) or _as_bool(context.get("control_abort"))
    abort_reason = str(context.get("abort_reason") or "").strip()
    if isinstance(control, dict):
        abort_requested = (
            abort_requested
            or _as_bool(control.get("abort"))
            or str(control.get("action") or "").strip().lower() == "abort"
            or str(control.get("state") or "").strip().lower() == "abort"
        )
        if not abort_reason:
            abort_reason = str(
                control.get("reason")
                or control.get("note")
                or control.get("message")
                or ""
            ).strip()

    diagnostic_request = context.get("diagnostic_request")
    if not isinstance(diagnostic_request, dict):
        command = str(context.get("diagnostic_command") or "").strip()
        if command:
            diagnostic_request = {
                "id": context.get("diagnostic_request_id"),
                "command": command,
            }
        else:
            diagnostic_request = None
    return abort_requested, abort_reason, diagnostic_request


def _diagnostic_request_id(request: dict[str, Any]) -> str:
    explicit = str(request.get("id") or request.get("request_id") or "").strip()
    if explicit:
        return explicit[:160]
    command = str(request.get("command") or "").strip()
    if not command:
        return ""
    return f"cmd:{command[:120]}"


def _run_diagnostic_request(
    request: dict[str, Any],
    *,
    cwd: str,
    env: dict[str, str],
) -> dict[str, Any]:
    req_id = _diagnostic_request_id(request)
    command = str(request.get("command") or "").strip()
    started_at = time.monotonic()
    started_iso = _utc_now_iso()
    if not command:
        return {
            "id": req_id,
            "status": "rejected",
            "error": "diagnostic command is required",
            "ran_at": started_iso,
            "duration_seconds": 0.0,
        }

    timeout_requested = _to_int(request.get("timeout_seconds"), DIAGNOSTIC_TIMEOUT_SECONDS)
    timeout_seconds = max(5, min(DIAGNOSTIC_TIMEOUT_SECONDS, timeout_requested))
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = (result.stdout or "") + (result.stderr or "")
        status = "completed" if result.returncode == 0 else "failed"
        return {
            "id": req_id,
            "status": status,
            "exit_code": int(result.returncode),
            "command": _scrub_command(command),
            "output_tail": _tail_text(output, TASK_LOG_TAIL_CHARS),
            "ran_at": started_iso,
            "duration_seconds": round(time.monotonic() - started_at, 3),
            "timeout_seconds": timeout_seconds,
        }
    except subprocess.TimeoutExpired as exc:
        combined = f"{(exc.stdout or '')}{(exc.stderr or '')}"
        return {
            "id": req_id,
            "status": "timeout",
            "exit_code": -9,
            "command": _scrub_command(command),
            "output_tail": _tail_text(combined, TASK_LOG_TAIL_CHARS),
            "ran_at": started_iso,
            "duration_seconds": round(time.monotonic() - started_at, 3),
            "timeout_seconds": timeout_seconds,
        }
    except Exception as exc:
        return {
            "id": req_id,
            "status": "failed",
            "exit_code": -1,
            "command": _scrub_command(command),
            "error": str(exc)[:800],
            "ran_at": started_iso,
            "duration_seconds": round(time.monotonic() - started_at, 3),
            "timeout_seconds": timeout_seconds,
        }


def _patch_task_progress(
    client: httpx.Client,
    *,
    task_id: str,
    progress_pct: int,
    current_step: str,
    context_patch: dict[str, Any],
) -> None:
    patch_payload: dict[str, Any] = {
        "progress_pct": int(max(0, min(100, progress_pct))),
        "current_step": current_step[:300],
    }
    if context_patch:
        patch_payload["context"] = context_patch
    try:
        client.patch(f"{BASE}/api/agent/tasks/{task_id}", json=patch_payload)
    except Exception:
        return


def _patch_task_context(
    client: httpx.Client,
    *,
    task_id: str,
    context_patch: dict[str, Any],
) -> None:
    if not context_patch:
        return
    try:
        client.patch(f"{BASE}/api/agent/tasks/{task_id}", json={"context": context_patch})
    except Exception:
        return


def _int_or_default(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def _parse_iso_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _append_failure_history(existing: object, entry: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(existing, list):
        for row in existing:
            if isinstance(row, dict):
                items.append(row)
    items.append(entry)
    return items[-limit:]


def _update_task_run_metrics(
    client: httpx.Client,
    *,
    task_id: str,
    task_type: str,
    model: str,
    command: str,
    attempt: int,
    duration_seconds: float,
    attempt_status: str,
    failure_class: str,
) -> dict[str, Any]:
    snapshot = _safe_get_task_snapshot(client, task_id)
    context = _safe_get_task_context(snapshot)
    existing = context.get("runner_metrics")
    metrics = dict(existing) if isinstance(existing, dict) else {}

    runs_total = max(0, _int_or_default(metrics.get("runs_total"), 0)) + 1
    runs_success = max(0, _int_or_default(metrics.get("runs_success"), 0)) + (1 if attempt_status == "completed" else 0)
    runs_failed = max(0, _int_or_default(metrics.get("runs_failed"), 0)) + (1 if attempt_status != "completed" else 0)
    retries_total = max(0, _int_or_default(metrics.get("retries_total"), 0)) + (1 if attempt > 1 else 0)

    paid_call = _model_is_paid(model)
    paid_calls_total = max(0, _int_or_default(metrics.get("paid_calls_total"), 0)) + (1 if paid_call else 0)
    paid_calls_success = max(0, _int_or_default(metrics.get("paid_calls_success"), 0)) + (
        1 if paid_call and attempt_status == "completed" else 0
    )
    paid_calls_failed = max(0, _int_or_default(metrics.get("paid_calls_failed"), 0)) + (
        1 if paid_call and attempt_status != "completed" else 0
    )
    paid_retry_calls = max(0, _int_or_default(metrics.get("paid_retry_calls"), 0)) + (
        1 if paid_call and attempt > 1 else 0
    )

    total_runtime_seconds = round(
        float(metrics.get("total_runtime_seconds") or 0.0) + max(0.0, float(duration_seconds)),
        3,
    )
    avg_runtime_seconds = round(total_runtime_seconds / max(1, runs_total), 3)
    success_rate = round(runs_success / max(1, runs_total), 4)
    paid_success_rate = round(paid_calls_success / max(1, paid_calls_total), 4) if paid_calls_total > 0 else 1.0

    updated = {
        "runs_total": runs_total,
        "runs_success": runs_success,
        "runs_failed": runs_failed,
        "success_rate": success_rate,
        "retries_total": retries_total,
        "paid_calls_total": paid_calls_total,
        "paid_calls_success": paid_calls_success,
        "paid_calls_failed": paid_calls_failed,
        "paid_retry_calls": paid_retry_calls,
        "paid_success_rate": paid_success_rate,
        "total_runtime_seconds": total_runtime_seconds,
        "avg_runtime_seconds": avg_runtime_seconds,
        "last_attempt": attempt,
        "last_status": attempt_status,
        "last_failure_class": failure_class if attempt_status != "completed" else "",
        "last_model": model,
        "last_tool": _tool_token(command),
        "updated_at": _utc_now_iso(),
    }
    _patch_task_context(
        client,
        task_id=task_id,
        context_patch={
            "runner_metrics": updated,
            "runner_last_result": {
                "attempt": attempt,
                "status": attempt_status,
                "failure_class": failure_class if attempt_status != "completed" else "",
                "duration_seconds": round(float(duration_seconds), 3),
                "paid_call": paid_call,
                "task_type": task_type,
                "model": model,
                "command_tool": _tool_token(command),
                "at": _utc_now_iso(),
            },
        },
    )
    return updated


def _schedule_retry_if_configured(
    client: httpx.Client,
    *,
    task_id: str,
    task_ctx: dict[str, Any],
    output: str,
    failure_class: str,
    attempt: int,
    duration_seconds: float,
) -> tuple[bool, str]:
    max_retries = max(0, _to_int(task_ctx.get("runner_retry_max"), 0))
    retry_delay_seconds = max(0, min(3600, _to_int(task_ctx.get("runner_retry_delay_seconds"), 8)))
    retries_used = max(0, attempt - 1)
    retries_remaining = max_retries - retries_used
    if retries_remaining <= 0:
        return False, ""

    live_snapshot = _safe_get_task_snapshot(client, task_id)
    live_ctx = _safe_get_task_context(live_snapshot)
    merged_ctx = dict(task_ctx)
    merged_ctx.update(live_ctx)
    retry_not_before = (datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)).isoformat()
    failure_entry = {
        "attempt": attempt,
        "failure_class": failure_class,
        "duration_seconds": round(float(duration_seconds), 3),
        "at": _utc_now_iso(),
        "output_tail": _tail_text(output, 600),
    }
    failure_history = _append_failure_history(merged_ctx.get("runner_failure_history"), failure_entry)
    context_patch = {
        "runner_retry_max": max_retries,
        "runner_retry_delay_seconds": retry_delay_seconds,
        "runner_retry_count": retries_used + 1,
        "runner_retry_remaining": retries_remaining - 1,
        "runner_state": "retry_pending",
        "retry_not_before": retry_not_before,
        "runner_last_failure": failure_entry,
        "runner_failure_history": failure_history,
    }
    message = (
        f"[runner-retry] attempt {attempt} failed ({failure_class}); "
        f"scheduled retry in {retry_delay_seconds}s ({retries_remaining - 1} retries remaining)."
    )
    try:
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={
                "status": "pending",
                "current_step": "retry scheduled",
                "output": f"{output[-3200:]}\n\n{message}"[-4000:],
                "context": context_patch,
            },
        )
    except Exception:
        return False, ""
    return True, message


def _sanitize_branch_name(raw: str, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-/]", "-", (raw or "").strip())
    slug = slug.strip("/").strip(".-")
    if not slug:
        return fallback
    return slug[:120]


def _extract_pr_branch(task_id: str, task_ctx: dict[str, Any], direction: str) -> str:
    explicit = (
        task_ctx.get("pr_branch")
        or task_ctx.get("git_branch")
        or task_ctx.get("branch")
        or f"codex/{task_id}"
    )
    prefix = str(task_ctx.get("pr_branch_prefix") or "").strip().strip("/")
    if prefix:
        explicit = f"{prefix}/{explicit}"
    return _sanitize_branch_name(f"{explicit}", f"codex/{_sanitize_branch_name(task_id, task_id[:8])}")


def _should_run_pr_flow(task: dict[str, Any]) -> bool:
    task_type = str(task.get("task_type") or "impl").strip().lower()
    if task_type != "impl":
        return False
    ctx = _safe_get_task_context(task)
    explicit = str((ctx.get("execution_mode") or "")).strip().lower()
    if explicit in {"pr", "thread", "codex_thread", "codex-thread", "codex"}:
        return True
    return any(
        _as_bool(ctx.get(flag))
        for flag in ("create_pr", "requires_pr", "system_change", "pr_workflow", "codex_thread", "run_with_pr")
    )


def _run_cmd(
    command: list[str] | str,
    *,
    cwd: str,
    timeout: int = 1200,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        shell=shell,
        timeout=timeout,
    )


def _run_git(
    *args: str,
    cwd: str,
    timeout: int = 1200,
) -> subprocess.CompletedProcess[str]:
    return _run_cmd(["git", *args], cwd=cwd, timeout=timeout)


def _pr_command_output(report: object, max_len: int = 3000) -> str:
    if isinstance(report, str):
        return report[:max_len]
    if isinstance(report, dict):
        return json.dumps(report, indent=2)[:max_len]
    try:
        return str(report)
    except Exception:
        return ""


def _json_or_text(payload: str) -> object:
    if not payload:
        return {}
    text = payload.strip()
    if not text:
        return {}
    if not text.startswith(("{", "[")):
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return decoded


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def _read_run_records() -> dict[str, Any]:
    if not os.path.exists(RUN_RECORDS_FILE):
        return {"runs": []}
    try:
        with open(RUN_RECORDS_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {"runs": []}
    if not isinstance(payload, dict):
        return {"runs": []}
    runs = payload.get("runs")
    if not isinstance(runs, list):
        payload["runs"] = []
    return payload


def _write_run_records(payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(RUN_RECORDS_FILE), exist_ok=True)
    tmp = f"{RUN_RECORDS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, RUN_RECORDS_FILE)


def _record_run_update(run_id: str, patch: dict[str, Any]) -> None:
    if not run_id:
        return
    with RUN_RECORDS_LOCK:
        payload = _read_run_records()
        runs = payload.get("runs")
        if not isinstance(runs, list):
            runs = []
        target: dict[str, Any] | None = None
        for rec in runs:
            if isinstance(rec, dict) and str(rec.get("run_id") or "") == run_id:
                target = rec
                break
        if target is None:
            target = {"run_id": run_id, "created_at": _utc_now_iso()}
            runs.append(target)
        target.update(patch)
        target["updated_at"] = _utc_now_iso()
        if len(runs) > MAX_RUN_RECORDS:
            runs = runs[-MAX_RUN_RECORDS:]
        payload["runs"] = runs
        _write_run_records(payload)


def _claim_run_lease(
    client: httpx.Client,
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    attempt: int,
    branch: str,
    repo_path: str,
    task_type: str,
    direction: str,
) -> bool:
    try:
        resp = client.post(
            f"{BASE}/api/agent/run-state/claim",
            json={
                "task_id": task_id,
                "run_id": run_id,
                "worker_id": worker_id,
                "lease_seconds": RUN_LEASE_SECONDS,
                "attempt": attempt,
                "branch": branch,
                "repo_path": repo_path,
                "metadata": {"task_type": task_type, "direction": direction[:500]},
            },
            timeout=HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            # Backward-compatible fallback when run-state API is unavailable.
            return True
        payload = resp.json() if resp.content else {}
        if not isinstance(payload, dict):
            return True
        claimed = payload.get("claimed")
        if claimed is False:
            detail = str(payload.get("detail") or "").strip()
            if detail == "lease_owned_by_other_worker":
                return False
        return True
    except Exception:
        # Best-effort: do not block task execution if lease service is down.
        return True


def _sync_run_state(
    client: httpx.Client,
    *,
    task_id: str,
    run_id: str,
    worker_id: str,
    patch: dict[str, Any],
    lease_seconds: int | None = None,
    require_owner: bool = True,
) -> None:
    _record_run_update(run_id, patch)
    try:
        client.post(
            f"{BASE}/api/agent/run-state/update",
            json={
                "task_id": task_id,
                "run_id": run_id,
                "worker_id": worker_id,
                "patch": patch,
                "lease_seconds": lease_seconds,
                "require_owner": require_owner,
            },
            timeout=HTTP_TIMEOUT,
        )
    except Exception:
        return


def _runner_heartbeat(
    client: httpx.Client,
    *,
    runner_id: str,
    status: str,
    active_task_id: str = "",
    active_run_id: str = "",
    last_error: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    lease_seconds = max(20, min(3600, RUN_HEARTBEAT_SECONDS * 3))
    payload = {
        "runner_id": runner_id,
        "status": str(status or "idle"),
        "lease_seconds": lease_seconds,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "version": os.environ.get("AGENT_RUNNER_VERSION", "agent_runner.py"),
        "active_task_id": active_task_id[:200],
        "active_run_id": active_run_id[:200],
        "last_error": last_error[:2000],
        "metadata": metadata or {},
    }
    try:
        client.post(f"{BASE}/api/agent/runners/heartbeat", json=payload, timeout=HTTP_TIMEOUT)
    except Exception:
        return


def _next_task_attempt(task_id: str) -> int:
    if not task_id:
        return 1
    with RUN_RECORDS_LOCK:
        payload = _read_run_records()
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return 1
    best = 0
    for rec in runs:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("task_id") or "") != task_id:
            continue
        best = max(best, _to_int(rec.get("attempt"), 0))
    return best + 1


def _current_head_sha(repo_path: str) -> str:
    head = _run_git("rev-parse", "HEAD", cwd=repo_path, timeout=60)
    if head.returncode != 0:
        return ""
    return (head.stdout or "").strip()[:80]


def _checkpoint_partial_progress(
    *,
    task_id: str,
    repo_path: str,
    branch: str,
    run_id: str,
    reason: str,
    log: logging.Logger,
) -> dict[str, Any]:
    status = _run_git("status", "--porcelain", cwd=repo_path, timeout=120)
    if status.returncode != 0:
        return {"ok": False, "reason": f"git status failed: {status.stderr.strip()[:500]}"}

    changed = bool((status.stdout or "").strip())
    if changed:
        add = _run_git("add", "-A", cwd=repo_path, timeout=120)
        if add.returncode != 0:
            return {"ok": False, "reason": f"git add failed: {add.stderr.strip()[:500]}"}
        message = f"[checkpoint] task {task_id} run {run_id}: {reason}"[:120]
        commit = _run_git("commit", "-m", message, cwd=repo_path, timeout=240)
        if commit.returncode != 0 and "nothing to commit" not in (commit.stderr or "").lower():
            return {"ok": False, "reason": f"git commit failed: {commit.stderr.strip()[:500]}"}

    push = _run_cmd(["git", "push", "-u", "origin", branch], cwd=repo_path, timeout=300)
    if push.returncode != 0:
        return {"ok": False, "reason": f"git push failed: {push.stderr.strip()[:500]}", "changed": changed}

    head_sha = _current_head_sha(repo_path)
    log.info("task=%s checkpoint pushed branch=%s sha=%s reason=%s", task_id, branch, head_sha, reason)
    return {"ok": True, "changed": changed, "checkpoint_sha": head_sha, "branch": branch}


_USAGE_LIMIT_MARKERS = (
    "usage limit",
    "rate limit",
    "quota exceeded",
    "insufficient_quota",
    "billing hard limit",
    "too many requests",
    "provider blocked",
)


def _detect_usage_limit(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _USAGE_LIMIT_MARKERS)


def _classify_failure(
    *,
    output: str,
    timed_out: bool,
    stopped_for_usage: bool,
    stopped_for_abort: bool,
    returncode: int,
) -> str:
    if stopped_for_abort:
        return "aborted_by_user"
    if stopped_for_usage or _detect_usage_limit(output):
        return "usage_limit"
    if timed_out:
        return "timeout"
    if returncode in {-9, 137, 143}:
        return "killed"
    return "command_failed"


def _post_runtime_event(
    client: httpx.Client,
    *,
    tool_name: str,
    status_code: int,
    runtime_ms: float,
    task_id: str,
    task_type: str,
    model: str,
    returncode: int,
    output_len: int,
    worker_id: str,
    executor: str,
    is_openai_codex: bool,
) -> None:
    if os.environ.get("PIPELINE_TOOL_TELEMETRY_ENABLED", "1").strip() in {"0", "false", "False"}:
        return
    payload = {
        "source": "worker",
        "endpoint": f"tool:{tool_name}",
        "method": "RUN",
        "status_code": int(status_code),
        "runtime_ms": max(0.1, float(runtime_ms)),
        "idea_id": "coherence-network-agent-pipeline",
        "metadata": {
            "task_id": task_id,
            "task_type": task_type,
            "model": model,
            "is_paid_provider": _model_is_paid(model),
            "returncode": int(returncode),
            "output_len": int(output_len),
            "worker_id": worker_id,
            "executor": executor,
            "agent_id": "openai-codex" if is_openai_codex else worker_id,
            "is_openai_codex": bool(is_openai_codex),
        },
    }
    try:
        client.post(f"{BASE}/api/runtime/events", json=payload, timeout=5.0)
    except Exception:
        # Telemetry should not affect task progression.
        pass


def _post_tool_failure_friction(
    client: httpx.Client,
    *,
    tool_name: str,
    task_id: str,
    task_type: str,
    model: str,
    duration_seconds: float,
    returncode: int,
    command: str,
) -> None:
    if os.environ.get("PIPELINE_TOOL_FAILURE_FRICTION_ENABLED", "1").strip() in {"0", "false", "False"}:
        return
    now = datetime.now(timezone.utc)
    energy_loss = round(max(0.0, float(duration_seconds)) * _time_cost_per_second(), 6)
    cmd_summary = _scrub_command(command)
    payload = {
        "id": f"fr_toolfail_{task_id}_{uuid.uuid4().hex[:8]}",
        "timestamp": now.isoformat(),
        "stage": "agent_runner",
        "block_type": "tool_failure",
        "severity": "high" if duration_seconds >= 120 or returncode != 0 else "medium",
        "owner": "automation",
        "unblock_condition": "Fix tool invocation/dependencies/auth; rerun task",
        "energy_loss_estimate": energy_loss,
        "cost_of_delay": energy_loss,
        "status": "resolved",
        "resolved_at": now.isoformat(),
        "time_open_hours": round(max(0.0, float(duration_seconds)) / 3600.0, 6),
        "resolution_action": "task_marked_failed",
        "notes": f"tool={tool_name} task_id={task_id} task_type={task_type} model={model} returncode={returncode} cmd={cmd_summary}",
    }
    try:
        client.post(f"{BASE}/api/friction/events", json=payload, timeout=5.0)
    except Exception:
        pass


def _setup_logging(verbose: bool = False) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "agent_runner.log")
    log = logging.getLogger("agent_runner")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not log.handlers:
        h = logging.FileHandler(log_file, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        if verbose:
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            log.addHandler(sh)
    return log


def _try_commit(task_id: str, task_type: str, log: logging.Logger) -> None:
    """Run commit_progress.py when PIPELINE_AUTO_COMMIT=1. Non-blocking; logs on failure."""
    import subprocess

    project_root = os.path.dirname(_api_dir)
    script = os.path.join(_api_dir, "scripts", "commit_progress.py")
    push = os.environ.get("PIPELINE_AUTO_PUSH") == "1"
    cmd = [sys.executable, script, "--task-id", task_id, "--task-type", task_type]
    if push:
        cmd.append("--push")
    try:
        r = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and r.stderr:
            log.warning("commit_progress failed: %s", r.stderr[:200])
    except Exception as e:
        log.warning("commit_progress error: %s", e)


def _uses_claude_cli(command: str) -> bool:
    """True if command uses Claude Code CLI (claude -p ...)."""
    return command.strip().startswith("claude ")


def _uses_anthropic_cloud(command: str) -> bool:
    """True if command uses Anthropic cloud (e.g. HEAL with claude-3-5-haiku), not Ollama."""
    if "ollama/" in command:
        return False
    return "claude-3-5" in command or "claude-4" in command


def _uses_cursor_cli(command: str) -> bool:
    """True if command uses Cursor CLI (agent '...'). Cursor uses its own auth."""
    return command.strip().startswith("agent ")


def _uses_gemini_cli(command: str) -> bool:
    """True if command uses Gemini CLI."""
    return command.strip().startswith("gemini ")


def _uses_openclaw_cli(command: str) -> bool:
    """True if command uses OpenClaw CLI."""
    stripped = command.strip()
    return stripped.startswith("openclaw ") or stripped.startswith("clawwork ")


def _uses_codex_cli(command: str) -> bool:
    return command.strip().startswith("codex ")


def _uses_openrouter_executor_command(command: str) -> bool:
    return command.strip().startswith("openrouter-exec ")


def _non_root_min_uid() -> int:
    try:
        value = int(os.getenv("AGENT_RUN_AS_MIN_UID", "1000"))
    except Exception:
        value = 1000
    return max(1, value)


def _non_root_auto_create_enabled() -> bool:
    return _as_bool(os.getenv("AGENT_RUN_AS_AUTO_CREATE", "1"))


def _auto_create_non_root_exec_user(*, min_uid: int, preferred_user: str = "") -> tuple[str, int, int, str]:
    try:
        if os.geteuid() != 0:
            return "", -1, -1, ""
    except Exception:
        return "", -1, -1, ""
    if not _non_root_auto_create_enabled():
        return "", -1, -1, ""

    configured = str(os.getenv("AGENT_RUN_AS_AUTO_CREATE_USER", "")).strip()
    user_name = configured or str(preferred_user or "").strip() or "runner"
    if not user_name:
        user_name = "runner"
    user_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", user_name).strip("-") or "runner"
    home_dir = str(os.getenv("AGENT_RUN_AS_AUTO_CREATE_HOME", f"/home/{user_name}")).strip() or f"/home/{user_name}"
    shell = str(os.getenv("AGENT_RUN_AS_AUTO_CREATE_SHELL", "/bin/sh")).strip() or "/bin/sh"
    try:
        requested_uid = int(os.getenv("AGENT_RUN_AS_AUTO_CREATE_UID", str(min_uid)))
    except Exception:
        requested_uid = min_uid
    requested_uid = max(min_uid, requested_uid)

    try:
        existing = pwd.getpwnam(user_name)
        if int(existing.pw_uid) >= min_uid:
            home = str(existing.pw_dir or "").strip()
            if home and os.path.isdir(home):
                return str(existing.pw_name), int(existing.pw_uid), int(existing.pw_gid), home
    except KeyError:
        pass
    except Exception:
        pass

    create_commands: list[list[str]] = []
    if shutil.which("useradd"):
        create_commands.extend(
            [
                ["useradd", "-m", "-d", home_dir, "-s", shell, "-u", str(requested_uid), user_name],
                ["useradd", "-m", "-d", home_dir, "-s", shell, user_name],
            ]
        )
    elif shutil.which("adduser"):
        create_commands.extend(
            [
                ["adduser", "-D", "-h", home_dir, "-s", shell, "-u", str(requested_uid), user_name],
                ["adduser", "-D", "-h", home_dir, "-s", shell, user_name],
            ]
        )
    else:
        return "", -1, -1, ""

    for argv in create_commands:
        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=20,
            )
        except Exception:
            continue
        output = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
        if proc.returncode == 0 or "already exists" in output:
            break
    else:
        return "", -1, -1, ""

    try:
        created = pwd.getpwnam(user_name)
    except Exception:
        return "", -1, -1, ""
    uid = int(created.pw_uid)
    gid = int(created.pw_gid)
    if uid < min_uid:
        return "", -1, -1, ""
    home = str(created.pw_dir or "").strip() or home_dir
    try:
        os.makedirs(home, exist_ok=True)
    except Exception:
        pass
    if not os.path.isdir(home):
        return "", -1, -1, ""
    try:
        os.chown(home, uid, gid)
    except Exception:
        pass
    return str(created.pw_name), uid, gid, home


def _resolve_non_root_exec_user(preferred_user: str) -> tuple[str, int, int, str]:
    min_uid = _non_root_min_uid()
    candidates: list[str] = []
    preferred = str(preferred_user or "").strip()
    if preferred:
        candidates.append(preferred)
    fallback_raw = str(os.getenv("AGENT_RUN_AS_USER_FALLBACKS", "agent,app,coder,runner,ubuntu")).strip()
    if fallback_raw:
        for raw in fallback_raw.split(","):
            candidate = str(raw or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

    for candidate in candidates:
        try:
            row = pwd.getpwnam(candidate)
        except KeyError:
            continue
        except Exception:
            continue
        if int(row.pw_uid) < min_uid:
            continue
        home = str(row.pw_dir or "").strip()
        if not home or not os.path.isdir(home):
            continue
        return str(row.pw_name), int(row.pw_uid), int(row.pw_gid), home

    if not _as_bool(os.getenv("AGENT_RUN_AS_AUTO_DISCOVER", "1")):
        return _auto_create_non_root_exec_user(min_uid=min_uid, preferred_user=preferred)

    try:
        for row in sorted(pwd.getpwall(), key=lambda item: int(item.pw_uid)):
            uid = int(row.pw_uid)
            if uid < min_uid:
                continue
            shell = str(row.pw_shell or "").strip().lower()
            if shell.endswith("nologin") or shell.endswith("false"):
                continue
            home = str(row.pw_dir or "").strip()
            if not home or not os.path.isdir(home):
                continue
            return str(row.pw_name), uid, int(row.pw_gid), home
    except Exception:
        return _auto_create_non_root_exec_user(min_uid=min_uid, preferred_user=preferred)

    created_user = _auto_create_non_root_exec_user(min_uid=min_uid, preferred_user=preferred)
    if created_user[0]:
        return created_user
    return "", -1, -1, ""


def _prepare_non_root_execution_for_command(
    *,
    command: str,
    env: dict[str, str],
) -> tuple[bool, str, Callable[[], None] | None]:
    if "--dangerously-skip-permissions" not in str(command or ""):
        return True, "", None
    try:
        if os.geteuid() != 0:
            return True, "", None
    except Exception:
        return True, "", None

    preferred = str(os.getenv("AGENT_RUN_AS_USER", "")).strip()
    user_name, uid, gid, home = _resolve_non_root_exec_user(preferred)
    if not user_name or uid <= 0:
        return False, "runner_non_root_user_unavailable", None

    env["HOME"] = home
    env["USER"] = user_name
    env["LOGNAME"] = user_name
    local_bin = os.path.join(home, ".local", "bin")
    current_path = str(env.get("PATH", ""))
    filtered_parts = [part for part in current_path.split(os.pathsep) if part and not part.startswith("/root/")]
    current_path = os.pathsep.join(filtered_parts)
    if local_bin and not current_path.startswith(local_bin):
        env["PATH"] = f"{local_bin}{os.pathsep}{current_path}" if current_path else local_bin

    def _demote() -> None:
        os.setgid(gid)
        try:
            os.initgroups(user_name, gid)
        except Exception:
            pass
        os.setuid(uid)

    return True, f"runner_non_root_exec_user:{user_name}:{uid}:{gid}", _demote


def _cli_auto_install_enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") and not _as_bool(os.getenv("AGENT_RUNNER_AUTO_INSTALL_CLI_IN_TESTS", "0")):
        return False
    return _as_bool(os.getenv("AGENT_RUNNER_AUTO_INSTALL_CLI", "1"))


def _cli_install_timeout_seconds() -> int:
    try:
        value = int(os.getenv("AGENT_RUNNER_INSTALL_TIMEOUT_SECONDS", "300"))
    except Exception:
        value = 300
    return max(30, min(value, 900))


def _cli_install_provider_for_command(command: str) -> str:
    if _uses_cursor_cli(command):
        return "cursor"
    if _uses_claude_cli(command):
        return "claude"
    if _uses_gemini_cli(command):
        return "gemini"
    if _uses_codex_cli(command):
        return "codex"
    return ""


def _cli_binary_for_provider(provider: str) -> str:
    mapping = {
        "cursor": "agent",
        "claude": "claude",
        "gemini": "gemini",
        "codex": "codex",
    }
    return mapping.get(provider, "")


def _cli_install_commands(provider: str) -> list[str]:
    def _package_bootstrap(packages: list[str]) -> str:
        joined = " ".join(packages)
        return (
            "if command -v apt-get >/dev/null 2>&1; then "
            "apt-get update && DEBIAN_FRONTEND=noninteractive "
            f"apt-get install -y --no-install-recommends {joined}; "
            "elif command -v apk >/dev/null 2>&1; then "
            f"apk add --no-cache {joined}; "
            "elif command -v dnf >/dev/null 2>&1; then "
            f"dnf install -y {joined}; "
            "elif command -v yum >/dev/null 2>&1; then "
            f"yum install -y {joined}; "
            "else echo 'no_supported_pkg_manager'; exit 1; fi"
        )

    ensure_curl_cmd = (
        "if ! command -v curl >/dev/null 2>&1; then "
        f"{_package_bootstrap(['curl'])}; "
        "fi"
    )
    ensure_node_cmd = (
        "if ! command -v npm >/dev/null 2>&1; then "
        f"{_package_bootstrap(['nodejs', 'npm'])}; "
        "fi"
    )

    env_overrides = {
        "cursor": "AGENT_RUNNER_CURSOR_INSTALL_COMMANDS",
        "claude": "AGENT_RUNNER_CLAUDE_INSTALL_COMMANDS",
        "gemini": "AGENT_RUNNER_GEMINI_INSTALL_COMMANDS",
        "codex": "AGENT_RUNNER_CODEX_INSTALL_COMMANDS",
    }
    default_commands = {
        "cursor": [
            ensure_curl_cmd,
            "curl -fsSL https://cursor.com/install | bash",
        ],
        "claude": [
            ensure_curl_cmd,
            ensure_node_cmd,
            "curl -fsSL https://claude.ai/install.sh | bash",
            "npm install -g @anthropic-ai/claude-code",
        ],
        "gemini": [
            ensure_node_cmd,
            "npm install -g @google/gemini-cli",
        ],
        "codex": [
            ensure_node_cmd,
            "npm install -g @openai/codex",
        ],
    }

    override_key = env_overrides.get(provider, "")
    override_raw = str(os.getenv(override_key, "")).strip() if override_key else ""
    if override_raw:
        return [item.strip() for item in override_raw.split("||") if item.strip()]
    return list(default_commands.get(provider, []))


def _candidate_cli_paths(binary: str, env: dict[str, str]) -> list[str]:
    home = str(env.get("HOME", "")).strip() or str(Path.home())
    candidates = [
        os.path.join(home, ".local", "bin", binary),
        os.path.join(home, ".cursor", "bin", binary),
        os.path.join(home, ".cursor", "agent", "bin", binary),
        os.path.join(home, ".npm-global", "bin", binary),
        os.path.join(home, "bin", binary),
        f"/usr/local/bin/{binary}",
        f"/usr/bin/{binary}",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _abs_expanded_path(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _promote_binary_to_shared_path(binary: str, source_path: str) -> str:
    for target in (f"/usr/local/bin/{binary}", f"/usr/bin/{binary}"):
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source_path, target)
            os.chmod(target, 0o755)
            return target
        except Exception:
            continue
    return ""


def _resolve_cli_binary(binary: str, env: dict[str, str]) -> str:
    discovered = shutil.which(binary, path=str(env.get("PATH", "")))
    if discovered:
        return discovered
    for candidate in _candidate_cli_paths(binary, env):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _cursor_binary_runtime_layout(binary_path: str) -> tuple[bool, str]:
    normalized = _abs_expanded_path(binary_path)
    if not normalized:
        return False, "cursor_binary_path_missing"
    if not os.path.isfile(normalized) or not os.access(normalized, os.X_OK):
        return False, "cursor_binary_missing_or_not_executable"
    real_binary = _abs_expanded_path(os.path.realpath(normalized)) or normalized
    runtime_dir = os.path.dirname(real_binary)
    index_js = os.path.join(runtime_dir, "index.js")
    node_bin = os.path.join(runtime_dir, "node")
    if os.path.isfile(index_js) and os.path.isfile(node_bin) and os.access(node_bin, os.X_OK):
        return True, f"cursor_runtime_layout_ok:{runtime_dir}"
    return False, f"cursor_runtime_layout_missing:{runtime_dir}"


def _resolve_cursor_cli_binary(binary: str, env: dict[str, str]) -> tuple[str, bool, str]:
    candidates = _candidate_cli_paths(binary, env)
    discovered = shutil.which(binary, path=str(env.get("PATH", "")))
    if discovered:
        discovered_normalized = _abs_expanded_path(discovered)
        if discovered_normalized and discovered_normalized not in candidates:
            candidates.append(discovered_normalized)

    fallback = ""
    fallback_detail = "cursor_binary_missing"
    for candidate in candidates:
        normalized = _abs_expanded_path(candidate)
        if not normalized:
            continue
        if not os.path.isfile(normalized) or not os.access(normalized, os.X_OK):
            continue
        if not fallback:
            fallback = normalized
        layout_ok, layout_detail = _cursor_binary_runtime_layout(normalized)
        if layout_ok:
            return normalized, True, layout_detail
        fallback_detail = layout_detail

    if fallback:
        return fallback, False, fallback_detail
    if discovered:
        normalized = _abs_expanded_path(discovered)
        if normalized:
            layout_ok, layout_detail = _cursor_binary_runtime_layout(normalized)
            return normalized, bool(layout_ok), layout_detail
    return "", False, "cursor_binary_missing"


def _prepend_cli_path(binary_path: str, env: dict[str, str]) -> None:
    directory = os.path.dirname(binary_path)
    if not directory:
        return
    current = str(env.get("PATH", ""))
    parts = [item for item in current.split(os.pathsep) if item]
    if directory not in parts:
        env["PATH"] = directory + (os.pathsep + current if current else "")
    process_current = str(os.environ.get("PATH", ""))
    process_parts = [item for item in process_current.split(os.pathsep) if item]
    if directory not in process_parts:
        os.environ["PATH"] = directory + (os.pathsep + process_current if process_current else "")


def _resolve_node_binary(env: dict[str, str]) -> str:
    def _is_node_shim(path: str) -> bool:
        lowered = str(path or "").lower()
        return "/mise/shims/" in lowered or "/.asdf/shims/" in lowered

    def _resolve_node_shim_target(path: str) -> str:
        lowered = str(path or "").lower()
        commands: list[list[str]] = []
        if "/mise/shims/" in lowered:
            commands.extend(
                [
                    ["mise", "which", "node"],
                    ["/mise/bin/mise", "which", "node"],
                ]
            )
        elif "/.asdf/shims/" in lowered:
            commands.extend(
                [
                    ["asdf", "which", "nodejs"],
                    ["asdf", "which", "node"],
                ]
            )
        for argv in commands:
            try:
                completed = subprocess.run(
                    argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    text=True,
                    timeout=6,
                    env=env,
                )
            except Exception:
                continue
            if completed.returncode != 0:
                continue
            candidate = _abs_expanded_path(str(completed.stdout or "").strip())
            if not candidate:
                continue
            if candidate == path:
                continue
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return ""

    def _usable_binary(path: str, *, allow_shim: bool = False) -> str:
        normalized = _abs_expanded_path(path)
        if not normalized:
            return ""
        if not os.path.isfile(normalized) or not os.access(normalized, os.X_OK):
            return ""
        resolved = _abs_expanded_path(os.path.realpath(normalized))
        active_path = resolved or normalized
        if _is_node_shim(active_path):
            concrete = _resolve_node_shim_target(active_path)
            if concrete:
                return concrete
            if not allow_shim:
                return ""
        return normalized

    for candidate in ("/usr/bin/node", "/bin/node", "/opt/homebrew/bin/node", "/usr/local/bin/node"):
        normalized = _abs_expanded_path(candidate)
        usable = _usable_binary(normalized)
        if usable:
            return usable
    discovered = shutil.which("node", path=str(env.get("PATH", "")))
    if discovered:
        normalized = _abs_expanded_path(discovered)
        usable = _usable_binary(normalized)
        if usable:
            return usable
        usable_shim = _usable_binary(normalized, allow_shim=True)
        if usable_shim:
            return usable_shim
    return ""


def _cursor_node_shim_path(*, cursor_binary: str = "") -> str:
    configured = _abs_expanded_path(str(os.getenv("AGENT_RUNNER_CURSOR_NODE_SHIM_PATH", "")).strip())
    if configured:
        return configured
    cursor_path = _abs_expanded_path(cursor_binary)
    if cursor_path:
        resolved_cursor_path = _abs_expanded_path(os.path.realpath(cursor_path)) or cursor_path
        cursor_dir = os.path.dirname(resolved_cursor_path)
        if cursor_dir:
            return os.path.join(cursor_dir, "node")
    return "/usr/local/bin/node"


def _node_binary_accepts_use_system_ca(node_binary: str, *, env: dict[str, str]) -> bool:
    binary = _abs_expanded_path(node_binary)
    if not binary:
        return False
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        return False
    try:
        completed = subprocess.run(
            [binary, "--use-system-ca", "-e", "process.exit(0)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=8,
            env=env,
        )
    except Exception:
        return False
    return completed.returncode == 0


def _write_cursor_node_compat_wrapper(*, shim_path: str, node_binary: str) -> None:
    quoted_binary = shlex.quote(node_binary)
    content = (
        "#!/bin/sh\n"
        "set -eu\n"
        "while [ \"${1-}\" = \"--use-system-ca\" ]; do\n"
        "  shift\n"
        "done\n"
        f"exec {quoted_binary} \"$@\"\n"
    )
    with open(shim_path, "w", encoding="utf-8") as file:
        file.write(content)
    os.chmod(shim_path, 0o755)


def _ensure_cursor_node_shim(*, env: dict[str, str], cursor_binary: str = "") -> tuple[bool, str]:
    shim_path = _cursor_node_shim_path(cursor_binary=cursor_binary)
    shim_exists = os.path.lexists(shim_path)
    if os.path.isfile(shim_path) and os.access(shim_path, os.X_OK):
        if _node_binary_accepts_use_system_ca(shim_path, env=env):
            return True, f"cursor_node_shim_present:{shim_path}"
        shim_exists = True
    node_binary = _resolve_node_binary(env)
    if not node_binary:
        return False, "cursor_node_missing"
    supports_use_system_ca = _node_binary_accepts_use_system_ca(node_binary, env=env)
    try:
        shim_dir = os.path.dirname(shim_path) or "."
        os.makedirs(shim_dir, exist_ok=True)
        if os.path.lexists(shim_path):
            os.remove(shim_path)
        if supports_use_system_ca:
            os.symlink(node_binary, shim_path)
        else:
            _write_cursor_node_compat_wrapper(shim_path=shim_path, node_binary=node_binary)
    except Exception as exc:
        return False, f"cursor_node_shim_failed:{type(exc).__name__}"
    if not _node_binary_accepts_use_system_ca(shim_path, env=env):
        return False, "cursor_node_shim_failed:unsupported_use_system_ca"
    if supports_use_system_ca:
        event = "cursor_node_shim_repaired" if shim_exists else "cursor_node_shim_created"
    else:
        event = "cursor_node_shim_repaired_compat" if shim_exists else "cursor_node_shim_created_compat"
    return True, f"{event}:{shim_path}->{node_binary}"


def _run_cli_install_command(command: str, *, env: dict[str, str], timeout_seconds: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["/bin/sh", "-lc", command],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return False, str(exc)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    combined = stdout if stdout else stderr
    if not combined:
        combined = f"exit_code={result.returncode}"
    return result.returncode == 0, combined[:400]


def _ensure_cli_for_command(
    *,
    command: str,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
) -> tuple[bool, str]:
    provider = _cli_install_provider_for_command(command)
    if not provider:
        return True, ""
    binary = _cli_binary_for_provider(provider)
    if not binary:
        return True, ""

    preinstall_notes: list[str] = []
    cursor_layout_ok = True
    cursor_layout_detail = ""
    if provider == "cursor":
        existing, cursor_layout_ok, cursor_layout_detail = _resolve_cursor_cli_binary(binary, env)
    else:
        existing = _resolve_cli_binary(binary, env)
    if existing:
        try:
            if os.geteuid() == 0 and provider != "cursor":
                promoted = _promote_binary_to_shared_path(binary, existing)
                if promoted:
                    existing = promoted
        except Exception:
            pass
        _prepend_cli_path(existing, env)
        if provider == "cursor":
            shim_ok, shim_detail = _ensure_cursor_node_shim(env=env, cursor_binary=existing)
            runtime_unhealthy_detail = ""
            if not shim_ok:
                runtime_unhealthy_detail = shim_detail
            elif not cursor_layout_ok:
                runtime_unhealthy_detail = cursor_layout_detail
            if not runtime_unhealthy_detail:
                return True, f"runner_cli_present:{provider}:{binary}:{existing}:{shim_detail}:{cursor_layout_detail}"
            if not _cli_auto_install_enabled():
                return False, (
                    f"runner_cli_present_but_runtime_unhealthy:{provider}:{binary}:{runtime_unhealthy_detail}"
                )
            preinstall_notes.append(f"cursor_runtime:{runtime_unhealthy_detail}")
        else:
            return True, f"runner_cli_present:{provider}:{binary}:{existing}"

    if not _cli_auto_install_enabled():
        return False, f"runner_cli_missing_auto_install_disabled:{provider}:{binary}"

    commands = _cli_install_commands(provider)
    if not commands:
        return False, f"runner_cli_missing_no_install_commands:{provider}:{binary}"

    timeout_seconds = _cli_install_timeout_seconds()
    notes: list[str] = list(preinstall_notes)
    for index, install_command in enumerate(commands, start=1):
        ok, detail = _run_cli_install_command(install_command, env=env, timeout_seconds=timeout_seconds)
        notes.append(f"cmd{index}:{'ok' if ok else 'fail'}:{detail}")
        if not ok:
            continue
        if provider == "cursor":
            resolved, resolved_layout_ok, resolved_layout_detail = _resolve_cursor_cli_binary(binary, env)
        else:
            resolved = _resolve_cli_binary(binary, env)
            resolved_layout_ok = True
            resolved_layout_detail = ""
        if resolved:
            try:
                if os.geteuid() == 0 and provider != "cursor":
                    promoted = _promote_binary_to_shared_path(binary, resolved)
                    if promoted:
                        resolved = promoted
            except Exception:
                pass
            _prepend_cli_path(resolved, env)
            if provider == "cursor":
                shim_ok, shim_detail = _ensure_cursor_node_shim(env=env, cursor_binary=resolved)
                if not shim_ok:
                    notes.append(f"cursor_runtime:{shim_detail}")
                    continue
                if not resolved_layout_ok:
                    notes.append(f"cursor_runtime:{resolved_layout_detail}")
                    continue
                return True, (
                    f"runner_cli_install_ok:{provider}:{binary}:{resolved}:{shim_detail}:{resolved_layout_detail}"
                )
            return True, f"runner_cli_install_ok:{provider}:{binary}:{resolved}"

    log.warning("task=%s cli install failed provider=%s notes=%s", task_id, provider, "; ".join(notes)[:500])
    return False, f"runner_cli_install_failed:{provider}:{binary}:{'; '.join(notes)[:500]}"


def _prepare_cli_command_for_exec(command: str) -> tuple[str | list[str], bool, str]:
    """Run supported CLI commands via argv to avoid shell expansion in prompt text."""
    cmd = str(command or "")
    if not (
        _uses_codex_cli(cmd)
        or _uses_cursor_cli(cmd)
        or _uses_gemini_cli(cmd)
        or _uses_openclaw_cli(cmd)
        or _uses_claude_cli(cmd)
    ):
        return cmd, True, "shell"
    try:
        argv = shlex.split(cmd, posix=True)
    except ValueError:
        return cmd, True, "shell_parse_error"
    if not argv:
        return cmd, True, "shell_empty_argv"
    if argv[0] in {"sh", "bash", "/bin/sh", "/bin/bash"}:
        return cmd, True, "shell_wrapper"
    return argv, False, "argv"


def _normalize_oauth_only_auth_mode(raw: Any, *, default: str = "oauth", allowed: set[str] | None = None) -> str:
    mode = str(raw or "").strip().lower()
    allowed_modes = allowed or {"oauth"}
    if mode in allowed_modes:
        return mode
    return default


def _normalize_codex_auth_mode(raw: Any, *, default: str = "oauth") -> str:
    mode = str(raw or "").strip().lower()
    if mode in CODEX_AUTH_MODE_VALUES:
        return mode
    return default


def _codex_auth_mode(override: str | None = None) -> str:
    raw = override if str(override or "").strip() else os.environ.get("AGENT_CODEX_AUTH_MODE", "oauth")
    if raw in CODEX_AUTH_MODE_VALUES:
        return str(raw).strip().lower()
    return _normalize_codex_auth_mode(raw, default="oauth")


def _abs_expanded_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    return os.path.abspath(os.path.expanduser(value))


def _set_env_if_blank(env: dict[str, str], key: str, value: str) -> None:
    if not str(value or "").strip():
        return
    if str(env.get(key, "")).strip():
        return
    env[key] = value


def _codex_oauth_session_target_path(env: dict[str, str]) -> str:
    explicit_session_file = str(env.get("AGENT_CODEX_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CODEX_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        return _abs_expanded_path(explicit_session_file)

    codex_home = str(env.get("AGENT_CODEX_HOME", "")).strip() or str(os.environ.get("AGENT_CODEX_HOME", "")).strip()
    if not codex_home:
        codex_home = str(env.get("CODEX_HOME", "")).strip() or str(os.environ.get("CODEX_HOME", "")).strip()
    if codex_home:
        return _abs_expanded_path(os.path.join(codex_home, "auth.json"))

    home = str(env.get("HOME", "")).strip() or str(os.environ.get("HOME", "")).strip()
    if home:
        return _abs_expanded_path(os.path.join(home, ".codex", "auth.json"))
    return ""


def _find_nested_token_value(node: Any, token_key: str) -> str:
    if isinstance(node, dict):
        direct = node.get(token_key)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        for value in node.values():
            found = _find_nested_token_value(value, token_key)
            if found:
                return found
        return ""
    if isinstance(node, list):
        for item in node:
            found = _find_nested_token_value(item, token_key)
            if found:
                return found
    return ""


def _find_first_nested_token_value(node: Any, token_keys: tuple[str, ...]) -> str:
    for token_key in token_keys:
        found = _find_nested_token_value(node, token_key)
        if found:
            return found
    return ""


def _extract_codex_oauth_tokens(payload: Any) -> tuple[str, str]:
    access_token = _find_nested_token_value(payload, "access_token")
    refresh_token = _find_nested_token_value(payload, "refresh_token")
    return access_token, refresh_token


def _read_json_object_file(path: str) -> dict[str, Any]:
    candidate = _abs_expanded_path(path)
    if not candidate:
        return {}
    try:
        with open(candidate, encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _bootstrap_codex_oauth_session_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_codex_oauth_session_b64",
        env=env,
        env_key="AGENT_CODEX_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, ""
    target_path = _codex_oauth_session_target_path(env)
    if not target_path:
        return False, "oauth_session_target_missing"

    existing_payload = _read_json_object_file(target_path)
    existing_access_token, existing_refresh_token = _extract_codex_oauth_tokens(existing_payload)
    if existing_access_token or existing_refresh_token:
        if overwrite_existing:
            log.info("task=%s replacing existing codex oauth session at %s", task_id, target_path)
        else:
            env["AGENT_CODEX_OAUTH_SESSION_FILE"] = target_path
            return False, f"oauth_session_preserved_existing:{target_path}"
    existing_had_tokens = bool(existing_access_token or existing_refresh_token)
    if existing_had_tokens and overwrite_existing:
        env["AGENT_CODEX_OAUTH_SESSION_FILE"] = target_path

    compact = "".join(encoded.split())
    if not compact:
        return False, "oauth_session_b64_empty"
    padded = compact + ("=" * ((4 - (len(compact) % 4)) % 4))

    decoded_text = ""
    decode_errors: list[str] = []
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            decoded_text = decoder(padded.encode("utf-8")).decode("utf-8")
            if decoded_text:
                break
        except Exception as exc:
            decode_errors.append(type(exc).__name__)
    if not decoded_text:
        detail = "/".join(decode_errors) if decode_errors else "unknown"
        log.warning("task=%s failed to decode AGENT_CODEX_OAUTH_SESSION_B64 detail=%s", task_id, detail)
        return False, f"oauth_session_b64_decode_failed:{detail[:80]}"

    try:
        payload = json.loads(decoded_text)
    except Exception as exc:
        return False, f"oauth_session_json_invalid:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return False, "oauth_session_json_not_object"

    access_token, refresh_token = _extract_codex_oauth_tokens(payload)
    if not refresh_token and not access_token:
        return False, "oauth_session_missing_tokens"

    if access_token:
        payload["access_token"] = access_token
    if refresh_token:
        payload["refresh_token"] = refresh_token
    payload.setdefault("auth_mode", "oauth")

    try:
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        os.chmod(target_path, 0o600)
    except Exception as exc:
        return False, f"oauth_session_write_failed:{type(exc).__name__}"

    env["AGENT_CODEX_OAUTH_SESSION_FILE"] = target_path
    if existing_had_tokens and overwrite_existing:
        return True, f"oauth_session_overwritten:{target_path}"
    return True, f"oauth_session_bootstrapped:{target_path}"


def _attempt_codex_oauth_session_refresh_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_codex_oauth_session_b64",
        env=env,
        env_key="AGENT_CODEX_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, "oauth_session_refresh_b64_missing"
    refreshed, detail = _bootstrap_codex_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
        overwrite_existing=True,
    )
    if refreshed:
        return True, detail or "oauth_session_refreshed"
    return False, detail or "oauth_session_refresh_failed"


def _codex_oauth_session_candidates(env: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(path: str) -> None:
        candidate = _abs_expanded_path(path)
        if not candidate:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    explicit_session_file = str(env.get("AGENT_CODEX_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CODEX_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        _append(explicit_session_file)

    codex_home = str(env.get("AGENT_CODEX_HOME", "")).strip() or str(os.environ.get("AGENT_CODEX_HOME", "")).strip()
    if not codex_home:
        codex_home = str(env.get("CODEX_HOME", "")).strip() or str(os.environ.get("CODEX_HOME", "")).strip()
    if codex_home:
        _append(os.path.join(codex_home, "auth.json"))
        _append(os.path.join(codex_home, "oauth.json"))
        _append(os.path.join(codex_home, "credentials.json"))

    home = str(env.get("HOME", "")).strip() or str(os.environ.get("HOME", "")).strip()
    if home:
        _append(os.path.join(home, ".codex", "auth.json"))
        _append(os.path.join(home, ".codex", "oauth.json"))
        _append(os.path.join(home, ".codex", "credentials.json"))
        _append(os.path.join(home, ".config", "codex", "auth.json"))
        _append(os.path.join(home, ".config", "codex", "oauth.json"))

    return candidates


def _codex_oauth_session_status(env: dict[str, str]) -> tuple[bool, str]:
    candidates = _codex_oauth_session_candidates(env)
    for candidate in candidates:
        try:
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return True, f"session_file:{candidate}"
        except OSError:
            continue

    status_commands = (
        (["codex", "login", "status"], "codex_login_status"),
        (["codex", "auth", "status"], "codex_auth_status"),
    )
    success_markers = ("logged in", "authenticated", "oauth")
    for argv, source in status_commands:
        try:
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=8,
                env=env,
            )
        except Exception:
            continue
        if completed.returncode != 0:
            continue
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
        if any(marker in output for marker in success_markers):
            return True, source

    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_codex_oauth_session"


def _ensure_codex_api_key_isolated_home(env: dict[str, str], *, task_id: str) -> str:
    """Force Codex API-key mode to ignore stale oauth sessions from the default home."""
    slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", str(task_id or "task")).strip("-") or "task"
    current_home = str(env.get("HOME") or os.path.expanduser("~")).strip() or os.path.expanduser("~")
    default_root = os.path.join(current_home, ".agent-runner-codex-api-key")
    home_root = str(os.environ.get("AGENT_CODEX_API_KEY_HOME_ROOT", default_root)).strip() or default_root
    base_home = os.path.join(home_root, slug)
    codex_home = os.path.join(base_home, ".codex")
    try:
        os.makedirs(codex_home, exist_ok=True)
    except OSError:
        # Last-resort fallback keeps runs alive even when preferred home root is not writable.
        base_home = os.path.join("/tmp", "agent-runner-codex-api-key", slug)
        codex_home = os.path.join(base_home, ".codex")
        os.makedirs(codex_home, exist_ok=True)
    env["HOME"] = base_home
    env["CODEX_HOME"] = codex_home
    return codex_home


def _configure_codex_cli_environment(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_mode_raw = str((task_ctx or {}).get("runner_codex_auth_mode") or "").strip().lower()
    requested_mode = _codex_auth_mode(requested_mode_raw or None)
    codex_home_override = str(os.environ.get("AGENT_CODEX_HOME", "")).strip()
    if codex_home_override:
        env["CODEX_HOME"] = _abs_expanded_path(codex_home_override)

    oauth_session_bootstrapped = False
    oauth_session_bootstrap_detail = ""
    effective_mode = "oauth"
    if requested_mode_raw and requested_mode_raw != "oauth":
        log.info(
            "task=%s forcing codex auth mode to oauth; ignoring requested=%s",
            task_id,
            requested_mode_raw,
        )

    oauth_session_bootstrapped, oauth_session_bootstrap_detail = _bootstrap_codex_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
    )
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_ADMIN_API_KEY", None)
    env.pop("OPENAI_API_BASE", None)
    env.pop("OPENAI_BASE_URL", None)

    oauth_available, oauth_source = _codex_oauth_session_status(env)
    oauth_missing = bool(not oauth_available)
    auth_state = {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "oauth_session": bool(oauth_available),
        "oauth_source": oauth_source,
        "api_key_present": False,
        "oauth_fallback_allowed": False,
        "oauth_missing": oauth_missing,
        "oauth_session_bootstrapped": bool(oauth_session_bootstrapped),
        "oauth_session_bootstrap_detail": oauth_session_bootstrap_detail,
        "api_key_login_bootstrapped": False,
        "api_key_login_source": "",
    }
    if oauth_missing:
        log.warning(
            "task=%s codex oauth mode requested but no session detected source=%s",
            task_id,
            oauth_source,
        )
    log.info(
        "task=%s using codex CLI auth requested=%s effective=%s oauth_session=%s source=%s oauth_bootstrap=%s",
        task_id,
        requested_mode,
        effective_mode,
        bool(oauth_available),
        oauth_source,
        oauth_session_bootstrap_detail or "none",
    )
    return auth_state


def _oauth_session_b64_from_task_or_env(
    *,
    task_ctx: dict[str, Any] | None,
    task_ctx_key: str,
    env: dict[str, str],
    env_key: str,
) -> str:
    task_value = str((task_ctx or {}).get(task_ctx_key) or "").strip()
    if task_value:
        return task_value
    env_value = str(env.get(env_key, "")).strip()
    if env_value:
        return env_value
    return str(os.environ.get(env_key, "")).strip()


def _decode_oauth_session_b64_payload(
    *,
    encoded: str,
    task_id: str,
    log: logging.Logger,
    env_key: str,
) -> tuple[dict[str, Any], str]:
    compact = "".join(encoded.split())
    if not compact:
        return {}, "oauth_session_b64_empty"
    padded = compact + ("=" * ((4 - (len(compact) % 4)) % 4))

    decoded_text = ""
    decode_errors: list[str] = []
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            decoded_text = decoder(padded.encode("utf-8")).decode("utf-8")
            if decoded_text:
                break
        except Exception as exc:
            decode_errors.append(type(exc).__name__)
    if not decoded_text:
        detail = "/".join(decode_errors) if decode_errors else "unknown"
        log.warning("task=%s failed to decode %s detail=%s", task_id, env_key, detail)
        return {}, f"oauth_session_b64_decode_failed:{detail[:80]}"

    try:
        payload = json.loads(decoded_text)
    except Exception as exc:
        return {}, f"oauth_session_json_invalid:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, "oauth_session_json_not_object"
    return payload, ""


def _cursor_oauth_session_target_path(env: dict[str, str]) -> str:
    explicit_session_file = str(env.get("AGENT_CURSOR_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CURSOR_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        return _abs_expanded_path(explicit_session_file)

    config_dir = str(env.get("CURSOR_CONFIG_DIR", "")).strip() or str(os.environ.get("CURSOR_CONFIG_DIR", "")).strip()
    if config_dir:
        return _abs_expanded_path(os.path.join(config_dir, "auth.json"))

    home = str(env.get("HOME", "")).strip() or str(os.environ.get("HOME", "")).strip()
    xdg_config_home = str(env.get("XDG_CONFIG_HOME", "")).strip() or str(os.environ.get("XDG_CONFIG_HOME", "")).strip()
    if not xdg_config_home and home:
        xdg_config_home = os.path.join(home, ".config")

    names_raw = (
        str(env.get("AGENT_CURSOR_OAUTH_NAMES", "")).strip()
        or str(os.environ.get("AGENT_CURSOR_OAUTH_NAMES", "")).strip()
        or "cagent,cursor"
    )
    names = [item.strip() for item in names_raw.split(",") if item.strip()]
    if not names:
        names = ["cagent", "cursor"]

    candidates: list[str] = []
    for name in names:
        if xdg_config_home:
            candidates.append(os.path.join(xdg_config_home, name, "auth.json"))
        if home:
            candidates.append(os.path.join(home, f".{name}", "auth.json"))

    for candidate in candidates:
        normalized = _abs_expanded_path(candidate)
        if normalized and os.path.isfile(normalized):
            return normalized
    if candidates:
        return _abs_expanded_path(candidates[0])
    return ""


def _extract_cursor_oauth_tokens(payload: Any) -> tuple[str, str]:
    access_token = _find_first_nested_token_value(payload, ("accessToken", "access_token"))
    refresh_token = _find_first_nested_token_value(payload, ("refreshToken", "refresh_token"))
    return access_token, refresh_token


def _cursor_oauth_session_candidates(env: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(path: str) -> None:
        candidate = _abs_expanded_path(path)
        if not candidate:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    explicit_session_file = str(env.get("AGENT_CURSOR_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CURSOR_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        _append(explicit_session_file)

    config_dir = str(env.get("CURSOR_CONFIG_DIR", "")).strip() or str(os.environ.get("CURSOR_CONFIG_DIR", "")).strip()
    if config_dir:
        _append(os.path.join(config_dir, "auth.json"))

    target = _cursor_oauth_session_target_path(env)
    if target:
        _append(target)
    return candidates


def _cursor_oauth_session_status(env: dict[str, str]) -> tuple[bool, str]:
    candidates = _cursor_oauth_session_candidates(env)
    for candidate in candidates:
        payload = _read_json_object_file(candidate)
        if not payload:
            continue
        access_token, refresh_token = _extract_cursor_oauth_tokens(payload)
        if refresh_token or access_token:
            return True, f"session_file:{candidate}"
    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_cursor_oauth_session"


def _bootstrap_cursor_oauth_session_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_cursor_oauth_session_b64",
        env=env,
        env_key="AGENT_CURSOR_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, ""
    target_path = _cursor_oauth_session_target_path(env)
    if not target_path:
        return False, "oauth_session_target_missing"

    existing_payload = _read_json_object_file(target_path)
    existing_access_token, existing_refresh_token = _extract_cursor_oauth_tokens(existing_payload)
    if existing_refresh_token or existing_access_token:
        if overwrite_existing:
            log.info("task=%s replacing existing cursor oauth session at %s", task_id, target_path)
        else:
            env["AGENT_CURSOR_OAUTH_SESSION_FILE"] = target_path
            env["CURSOR_CONFIG_DIR"] = os.path.dirname(target_path) or "."
            return False, f"oauth_session_preserved_existing:{target_path}"

    payload, decode_detail = _decode_oauth_session_b64_payload(
        encoded=encoded,
        task_id=task_id,
        log=log,
        env_key="AGENT_CURSOR_OAUTH_SESSION_B64",
    )
    if not payload:
        return False, decode_detail or "oauth_session_b64_decode_failed"

    access_token, refresh_token = _extract_cursor_oauth_tokens(payload)
    if not refresh_token:
        return False, "oauth_session_missing_refresh_token"
    if access_token:
        payload["accessToken"] = access_token
    payload["refreshToken"] = refresh_token
    payload.pop("apiKey", None)
    payload.pop("api_key", None)

    try:
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        os.chmod(target_path, 0o600)
    except Exception as exc:
        return False, f"oauth_session_write_failed:{type(exc).__name__}"

    env["AGENT_CURSOR_OAUTH_SESSION_FILE"] = target_path
    env["CURSOR_CONFIG_DIR"] = os.path.dirname(target_path) or "."
    if existing_refresh_token or existing_access_token:
        return True, f"oauth_session_overwritten:{target_path}"
    return True, f"oauth_session_bootstrapped:{target_path}"


def _attempt_cursor_oauth_session_refresh_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_cursor_oauth_session_b64",
        env=env,
        env_key="AGENT_CURSOR_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, "oauth_session_refresh_b64_missing"
    refreshed, detail = _bootstrap_cursor_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
        overwrite_existing=True,
    )
    if refreshed:
        return True, detail or "oauth_session_refreshed"
    return False, detail or "oauth_session_refresh_failed"


def _configure_cursor_cli_environment(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_mode_raw = str((task_ctx or {}).get("runner_cursor_auth_mode") or "").strip().lower()
    requested_mode = _normalize_oauth_only_auth_mode(
        requested_mode_raw or str(os.environ.get("AGENT_CURSOR_AUTH_MODE", "oauth")),
        default="oauth",
        allowed=CURSOR_AUTH_MODE_VALUES,
    )
    effective_mode = "oauth"
    if requested_mode_raw and requested_mode_raw != "oauth":
        log.info(
            "task=%s forcing cursor auth mode to oauth; ignoring requested=%s",
            task_id,
            requested_mode_raw,
        )

    oauth_session_bootstrapped, oauth_session_bootstrap_detail = _bootstrap_cursor_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
    )
    env.pop("CURSOR_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_ADMIN_API_KEY", None)
    env.pop("OPENAI_API_BASE", None)
    env.pop("OPENAI_BASE_URL", None)

    target_path = _cursor_oauth_session_target_path(env)
    if target_path:
        env["CURSOR_CONFIG_DIR"] = os.path.dirname(target_path) or "."

    oauth_available, oauth_source = _cursor_oauth_session_status(env)
    oauth_missing = bool(not oauth_available)
    auth_state = {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "oauth_session": bool(oauth_available),
        "oauth_source": oauth_source,
        "api_key_present": False,
        "oauth_missing": oauth_missing,
        "oauth_session_bootstrapped": bool(oauth_session_bootstrapped),
        "oauth_session_bootstrap_detail": oauth_session_bootstrap_detail,
    }
    if oauth_missing:
        log.warning(
            "task=%s cursor oauth mode requested but no session detected source=%s",
            task_id,
            oauth_source,
        )
    log.info(
        "task=%s using cursor CLI auth requested=%s effective=%s oauth_session=%s source=%s oauth_bootstrap=%s",
        task_id,
        requested_mode,
        effective_mode,
        bool(oauth_available),
        oauth_source,
        oauth_session_bootstrap_detail or "none",
    )
    return auth_state


def _configure_gemini_cli_environment(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_mode_raw = str((task_ctx or {}).get("runner_gemini_auth_mode") or "").strip().lower()
    requested_mode = _normalize_oauth_only_auth_mode(
        requested_mode_raw or str(os.environ.get("AGENT_GEMINI_AUTH_MODE", "oauth")),
        default="oauth",
        allowed=GEMINI_AUTH_MODE_VALUES,
    )
    effective_mode = "oauth"
    if requested_mode_raw and requested_mode_raw != "oauth":
        log.info(
            "task=%s forcing gemini auth mode to oauth; ignoring requested=%s",
            task_id,
            requested_mode_raw,
        )
    gemini_config_override = str(os.environ.get("AGENT_GEMINI_CONFIG_DIR", "")).strip()
    if gemini_config_override:
        env["AGENT_GEMINI_CONFIG_DIR"] = _abs_expanded_path(gemini_config_override)

    oauth_session_bootstrapped, oauth_session_bootstrap_detail = _bootstrap_gemini_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
    )
    settings_configured, settings_config_detail = _ensure_gemini_oauth_settings(
        env=env,
        task_id=task_id,
        log=log,
    )

    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    target_oauth_path = _gemini_oauth_creds_target_path(env)
    if target_oauth_path:
        env["AGENT_GEMINI_OAUTH_CREDS_FILE"] = target_oauth_path
    config_dir = _gemini_config_dir(env)
    if config_dir:
        env["AGENT_GEMINI_CONFIG_DIR"] = config_dir

    oauth_available, oauth_source = _gemini_oauth_session_status(env)
    oauth_missing = bool(not oauth_available)
    auth_state = {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "oauth_session": bool(oauth_available),
        "oauth_source": oauth_source,
        "api_key_present": False,
        "oauth_missing": oauth_missing,
        "oauth_session_bootstrapped": bool(oauth_session_bootstrapped),
        "oauth_session_bootstrap_detail": oauth_session_bootstrap_detail,
        "oauth_settings_configured": bool(settings_configured),
        "oauth_settings_config_detail": settings_config_detail,
    }
    if oauth_missing:
        log.warning(
            "task=%s gemini oauth mode requested but no session detected source=%s",
            task_id,
            oauth_source,
        )
    log.info(
        "task=%s using gemini CLI auth requested=%s effective=%s oauth_session=%s source=%s oauth_bootstrap=%s settings=%s",
        task_id,
        requested_mode,
        effective_mode,
        bool(oauth_available),
        oauth_source,
        oauth_session_bootstrap_detail or "none",
        settings_config_detail or "none",
    )
    return auth_state


def _gemini_config_dir(env: dict[str, str]) -> str:
    config_dir = (
        str(env.get("AGENT_GEMINI_CONFIG_DIR", "")).strip()
        or str(os.environ.get("AGENT_GEMINI_CONFIG_DIR", "")).strip()
        or str(env.get("GEMINI_CONFIG_DIR", "")).strip()
        or str(os.environ.get("GEMINI_CONFIG_DIR", "")).strip()
    )
    if config_dir:
        return _abs_expanded_path(config_dir)
    home = str(env.get("HOME", "")).strip() or str(os.environ.get("HOME", "")).strip()
    if home:
        return _abs_expanded_path(os.path.join(home, ".gemini"))
    return ""


def _gemini_oauth_creds_target_path(env: dict[str, str]) -> str:
    explicit = str(env.get("AGENT_GEMINI_OAUTH_CREDS_FILE", "")).strip()
    if not explicit:
        explicit = str(os.environ.get("AGENT_GEMINI_OAUTH_CREDS_FILE", "")).strip()
    if explicit:
        return _abs_expanded_path(explicit)
    config_dir = _gemini_config_dir(env)
    if config_dir:
        return _abs_expanded_path(os.path.join(config_dir, "oauth_creds.json"))
    return ""


def _gemini_settings_target_path(env: dict[str, str]) -> str:
    explicit = str(env.get("AGENT_GEMINI_SETTINGS_FILE", "")).strip()
    if not explicit:
        explicit = str(os.environ.get("AGENT_GEMINI_SETTINGS_FILE", "")).strip()
    if explicit:
        return _abs_expanded_path(explicit)
    config_dir = _gemini_config_dir(env)
    if config_dir:
        return _abs_expanded_path(os.path.join(config_dir, "settings.json"))
    return ""


def _extract_gemini_oauth_tokens(payload: Any) -> tuple[str, str]:
    access_token = _find_first_nested_token_value(payload, ("accessToken", "access_token", "oauth_token"))
    refresh_token = _find_first_nested_token_value(payload, ("refreshToken", "refresh_token"))
    return access_token, refresh_token


def _gemini_oauth_session_status(env: dict[str, str]) -> tuple[bool, str]:
    target = _gemini_oauth_creds_target_path(env)
    if not target:
        return False, "missing_gemini_oauth_session"
    payload = _read_json_object_file(target)
    if payload:
        access_token, refresh_token = _extract_gemini_oauth_tokens(payload)
        if refresh_token or access_token:
            return True, f"session_file:{target}"
    return False, f"missing_session_file:{target}"


def _bootstrap_gemini_oauth_session_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_gemini_oauth_session_b64",
        env=env,
        env_key="AGENT_GEMINI_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, ""
    target_path = _gemini_oauth_creds_target_path(env)
    if not target_path:
        return False, "oauth_session_target_missing"

    existing_payload = _read_json_object_file(target_path)
    existing_access_token, existing_refresh_token = _extract_gemini_oauth_tokens(existing_payload)
    if existing_refresh_token or existing_access_token:
        if overwrite_existing:
            log.info("task=%s replacing existing gemini oauth session at %s", task_id, target_path)
        else:
            env["AGENT_GEMINI_OAUTH_CREDS_FILE"] = target_path
            return False, f"oauth_session_preserved_existing:{target_path}"

    payload, decode_detail = _decode_oauth_session_b64_payload(
        encoded=encoded,
        task_id=task_id,
        log=log,
        env_key="AGENT_GEMINI_OAUTH_SESSION_B64",
    )
    if not payload:
        return False, decode_detail or "oauth_session_b64_decode_failed"

    access_token, refresh_token = _extract_gemini_oauth_tokens(payload)
    if not refresh_token:
        return False, "oauth_session_missing_refresh_token"
    if access_token:
        payload["access_token"] = access_token
    payload["refresh_token"] = refresh_token
    payload.pop("apiKey", None)
    payload.pop("api_key", None)

    try:
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        os.chmod(target_path, 0o600)
    except Exception as exc:
        return False, f"oauth_session_write_failed:{type(exc).__name__}"

    env["AGENT_GEMINI_OAUTH_CREDS_FILE"] = target_path
    if existing_refresh_token or existing_access_token:
        return True, f"oauth_session_overwritten:{target_path}"
    return True, f"oauth_session_bootstrapped:{target_path}"


def _attempt_gemini_oauth_session_refresh_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_gemini_oauth_session_b64",
        env=env,
        env_key="AGENT_GEMINI_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, "oauth_session_refresh_b64_missing"
    refreshed, detail = _bootstrap_gemini_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
        overwrite_existing=True,
    )
    if refreshed:
        return True, detail or "oauth_session_refreshed"
    return False, detail or "oauth_session_refresh_failed"


def _ensure_gemini_oauth_settings(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
) -> tuple[bool, str]:
    settings_path = _gemini_settings_target_path(env)
    if not settings_path:
        return False, "oauth_settings_target_missing"
    payload = _read_json_object_file(settings_path)
    if not payload:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    security = payload.get("security")
    if not isinstance(security, dict):
        security = {}
    auth = security.get("auth")
    if not isinstance(auth, dict):
        auth = {}

    selected = str(auth.get("selectedType") or "").strip().lower()
    enforced = str(auth.get("enforcedType") or "").strip().lower()
    desired = "oauth-personal"
    if selected == desired and enforced == desired:
        env["AGENT_GEMINI_SETTINGS_FILE"] = settings_path
        return False, f"oauth_settings_preserved_existing:{settings_path}"

    auth["selectedType"] = desired
    auth["enforcedType"] = desired
    security["auth"] = auth
    payload["security"] = security

    try:
        os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        os.chmod(settings_path, 0o600)
    except Exception as exc:
        log.warning("task=%s failed to configure gemini oauth settings detail=%s", task_id, type(exc).__name__)
        return False, f"oauth_settings_write_failed:{type(exc).__name__}"

    env["AGENT_GEMINI_SETTINGS_FILE"] = settings_path
    return True, f"oauth_settings_bootstrapped:{settings_path}"


def _claude_oauth_session_target_path(env: dict[str, str]) -> str:
    explicit_session_file = str(env.get("AGENT_CLAUDE_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CLAUDE_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        return _abs_expanded_path(explicit_session_file)

    config_dir = (
        str(env.get("AGENT_CLAUDE_CONFIG_DIR", "")).strip()
        or str(os.environ.get("AGENT_CLAUDE_CONFIG_DIR", "")).strip()
        or str(env.get("CLAUDE_CONFIG_DIR", "")).strip()
        or str(os.environ.get("CLAUDE_CONFIG_DIR", "")).strip()
    )
    if config_dir:
        return _abs_expanded_path(os.path.join(config_dir, ".credentials.json"))

    home = str(env.get("HOME", "")).strip() or str(os.environ.get("HOME", "")).strip()
    if home:
        return _abs_expanded_path(os.path.join(home, ".claude", ".credentials.json"))
    return ""


def _extract_claude_oauth_tokens(payload: Any) -> tuple[str, str]:
    access_token = _find_first_nested_token_value(payload, ("accessToken", "access_token", "oauth_token"))
    refresh_token = _find_first_nested_token_value(payload, ("refreshToken", "refresh_token"))
    return access_token, refresh_token


def _claude_oauth_session_candidates(env: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(path: str) -> None:
        candidate = _abs_expanded_path(path)
        if not candidate:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    explicit_session_file = str(env.get("AGENT_CLAUDE_OAUTH_SESSION_FILE", "")).strip()
    if not explicit_session_file:
        explicit_session_file = str(os.environ.get("AGENT_CLAUDE_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        _append(explicit_session_file)

    config_dir = (
        str(env.get("AGENT_CLAUDE_CONFIG_DIR", "")).strip()
        or str(os.environ.get("AGENT_CLAUDE_CONFIG_DIR", "")).strip()
        or str(env.get("CLAUDE_CONFIG_DIR", "")).strip()
        or str(os.environ.get("CLAUDE_CONFIG_DIR", "")).strip()
    )
    if config_dir:
        _append(os.path.join(config_dir, ".credentials.json"))

    target = _claude_oauth_session_target_path(env)
    if target:
        _append(target)
    return candidates


def _claude_oauth_session_status(env: dict[str, str]) -> tuple[bool, str]:
    candidates = _claude_oauth_session_candidates(env)
    for candidate in candidates:
        payload = _read_json_object_file(candidate)
        if not payload:
            continue
        access_token, refresh_token = _extract_claude_oauth_tokens(payload)
        if refresh_token or access_token:
            return True, f"session_file:{candidate}"

    if not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            completed = subprocess.run(
                ["claude", "auth", "status", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=8,
                env={**env, "CLAUDECODE": ""},
            )
            if completed.returncode == 0:
                payload = json.loads(str(completed.stdout or "{}").strip())
                if isinstance(payload, dict) and bool(payload.get("loggedIn")):
                    return True, "claude_cli_auth_status"
        except Exception:
            pass

    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_claude_oauth_session"


def _bootstrap_claude_oauth_session_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
    overwrite_existing: bool = False,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_claude_oauth_session_b64",
        env=env,
        env_key="AGENT_CLAUDE_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, ""
    target_path = _claude_oauth_session_target_path(env)
    if not target_path:
        return False, "oauth_session_target_missing"

    existing_payload = _read_json_object_file(target_path)
    existing_access_token, existing_refresh_token = _extract_claude_oauth_tokens(existing_payload)
    if existing_refresh_token or existing_access_token:
        if overwrite_existing:
            log.info("task=%s replacing existing claude oauth session at %s", task_id, target_path)
        else:
            env["AGENT_CLAUDE_OAUTH_SESSION_FILE"] = target_path
            env["CLAUDE_CONFIG_DIR"] = os.path.dirname(target_path) or "."
            return False, f"oauth_session_preserved_existing:{target_path}"

    payload, decode_detail = _decode_oauth_session_b64_payload(
        encoded=encoded,
        task_id=task_id,
        log=log,
        env_key="AGENT_CLAUDE_OAUTH_SESSION_B64",
    )
    if not payload:
        return False, decode_detail or "oauth_session_b64_decode_failed"

    access_token, refresh_token = _extract_claude_oauth_tokens(payload)
    if not refresh_token:
        return False, "oauth_session_missing_refresh_token"
    if access_token:
        payload["accessToken"] = access_token
    payload["refreshToken"] = refresh_token
    payload.pop("apiKey", None)
    payload.pop("api_key", None)

    try:
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
        os.chmod(target_path, 0o600)
    except Exception as exc:
        return False, f"oauth_session_write_failed:{type(exc).__name__}"

    env["AGENT_CLAUDE_OAUTH_SESSION_FILE"] = target_path
    env["CLAUDE_CONFIG_DIR"] = os.path.dirname(target_path) or "."
    if existing_refresh_token or existing_access_token:
        return True, f"oauth_session_overwritten:{target_path}"
    return True, f"oauth_session_bootstrapped:{target_path}"


def _attempt_claude_oauth_session_refresh_from_env(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    encoded = _oauth_session_b64_from_task_or_env(
        task_ctx=task_ctx,
        task_ctx_key="runner_claude_oauth_session_b64",
        env=env,
        env_key="AGENT_CLAUDE_OAUTH_SESSION_B64",
    )
    if not encoded:
        return False, "oauth_session_refresh_b64_missing"
    refreshed, detail = _bootstrap_claude_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
        overwrite_existing=True,
    )
    if refreshed:
        return True, detail or "oauth_session_refreshed"
    return False, detail or "oauth_session_refresh_failed"


def _configure_claude_cli_environment(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
    task_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requested_mode_raw = str((task_ctx or {}).get("runner_claude_auth_mode") or "").strip().lower()
    requested_mode = _normalize_oauth_only_auth_mode(
        requested_mode_raw or str(os.environ.get("AGENT_CLAUDE_AUTH_MODE", "oauth")),
        default="oauth",
        allowed=CLAUDE_AUTH_MODE_VALUES,
    )
    effective_mode = "oauth"
    if requested_mode_raw and requested_mode_raw != "oauth":
        log.info(
            "task=%s forcing claude auth mode to oauth; ignoring requested=%s",
            task_id,
            requested_mode_raw,
        )

    claude_config_override = str(os.environ.get("AGENT_CLAUDE_CONFIG_DIR", "")).strip()
    if claude_config_override:
        env["CLAUDE_CONFIG_DIR"] = _abs_expanded_path(claude_config_override)

    oauth_session_bootstrapped, oauth_session_bootstrap_detail = _bootstrap_claude_oauth_session_from_env(
        env=env,
        task_id=task_id,
        log=log,
        task_ctx=task_ctx,
    )
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("ANTHROPIC_BASE_URL", None)
    env.pop("CLAUDE_API_KEY", None)
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)

    target_path = _claude_oauth_session_target_path(env)
    if target_path:
        env["CLAUDE_CONFIG_DIR"] = os.path.dirname(target_path) or "."

    oauth_available, oauth_source = _claude_oauth_session_status(env)
    oauth_missing = bool(not oauth_available)
    auth_state = {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "oauth_session": bool(oauth_available),
        "oauth_source": oauth_source,
        "api_key_present": False,
        "oauth_missing": oauth_missing,
        "oauth_session_bootstrapped": bool(oauth_session_bootstrapped),
        "oauth_session_bootstrap_detail": oauth_session_bootstrap_detail,
    }
    if oauth_missing:
        log.warning(
            "task=%s claude oauth mode requested but no session detected source=%s",
            task_id,
            oauth_source,
        )
    log.info(
        "task=%s using claude CLI auth requested=%s effective=%s oauth_session=%s source=%s oauth_bootstrap=%s",
        task_id,
        requested_mode,
        effective_mode,
        bool(oauth_available),
        oauth_source,
        oauth_session_bootstrap_detail or "none",
    )
    return auth_state


def _codex_oauth_auto_relogin_enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") and not _as_bool(
        os.getenv("AGENT_RUNNER_CODEX_OAUTH_AUTO_RELOGIN_IN_TESTS", "0")
    ):
        return False
    return _as_bool(os.getenv("AGENT_RUNNER_CODEX_OAUTH_AUTO_RELOGIN", "1"))


def _attempt_codex_oauth_relogin(
    *,
    env: dict[str, str],
    task_id: str,
    log: logging.Logger,
) -> tuple[bool, str]:
    if not _codex_oauth_auto_relogin_enabled():
        return False, "oauth_relogin_disabled"

    codex_binary = _resolve_cli_binary("codex", env) or ""
    if not codex_binary:
        return False, "oauth_relogin_codex_missing"

    login_commands = (
        ([codex_binary, "login", "--device-auth"], "codex_login_device_auth"),
        ([codex_binary, "auth", "login", "--device-auth"], "codex_auth_login_device_auth"),
    )
    last_error = "oauth_relogin_command_failed"
    for argv, source in login_commands:
        try:
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=45,
                env=env,
            )
        except Exception as exc:
            last_error = f"{source}_exception:{type(exc).__name__}"
            continue
        if completed.returncode == 0:
            session_ok, session_source = _codex_oauth_session_status(env)
            if session_ok:
                return True, f"{source}:{session_source}"
            return True, source
        stderr = str(completed.stderr or "").strip()
        stdout = str(completed.stdout or "").strip()
        detail = (stderr or stdout or "unknown_error")[:180]
        last_error = f"{source}_rc{completed.returncode}:{detail}"

    log.warning("task=%s codex oauth relogin failed detail=%s", task_id, last_error)
    return False, last_error


def _parse_codex_model_alias_map(raw: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for pair in str(raw or "").split(","):
        item = pair.strip()
        if not item or ":" not in item:
            continue
        source, target = item.split(":", 1)
        source_key = source.strip().lower()
        target_value = target.strip()
        if source_key and target_value:
            aliases[source_key] = target_value
    return aliases


def _codex_model_alias_map() -> dict[str, str]:
    aliases = _parse_codex_model_alias_map(DEFAULT_CODEX_MODEL_ALIAS_MAP)
    raw = os.environ.get("AGENT_CODEX_MODEL_ALIAS_MAP", "")
    if raw:
        aliases.update(_parse_codex_model_alias_map(str(raw)))
    return aliases


def _codex_model_not_found_fallback_map() -> dict[str, str]:
    aliases = _parse_codex_model_alias_map(DEFAULT_CODEX_MODEL_NOT_FOUND_FALLBACK_MAP)
    raw = os.environ.get("AGENT_CODEX_MODEL_NOT_FOUND_FALLBACK_MAP", "")
    if raw:
        aliases.update(_parse_codex_model_alias_map(str(raw)))
    return aliases


def _codex_command_model(command: str) -> str:
    if not _uses_codex_cli(command):
        return ""
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return ""
    return match.group("model").strip()


def _apply_codex_model_alias(command: str) -> tuple[str, dict[str, str] | None]:
    requested_model = _codex_command_model(command)
    if not requested_model:
        return command, None
    requested_model_key = requested_model.lower()
    target_model = MANDATORY_CODEX_MODEL_ALIAS_MAP.get(requested_model_key, "").strip()
    if not target_model:
        target_model = _codex_model_alias_map().get(requested_model_key, "").strip()
    if not target_model or target_model.lower() == requested_model.lower():
        return command, None
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return command, None
    remapped = f"{command[:match.start('model')]}{target_model}{command[match.end('model'):]}"
    return remapped, {
        "requested_model": requested_model,
        "effective_model": target_model,
    }


def _claude_command_model(command: str) -> str:
    if not _uses_claude_cli(command):
        return ""
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return ""
    return match.group("model").strip()


def _apply_claude_model_alias(command: str) -> tuple[str, dict[str, str] | None]:
    requested_model = _claude_command_model(command)
    if not requested_model:
        return command, None
    target_model = requested_model
    if requested_model.lower().startswith("claude/"):
        target_model = requested_model.split("/", 1)[1].strip()
    if not target_model or target_model.lower() == requested_model.lower():
        return command, None
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return command, None
    remapped = f"{command[:match.start('model')]}{target_model}{command[match.end('model'):]}"
    return remapped, {
        "requested_model": requested_model,
        "effective_model": target_model,
    }


def _codex_model_not_found_or_access_error(output: str) -> bool:
    lowered = (output or "").lower()
    if not lowered:
        return False
    if "model_not_found" in lowered:
        return True
    if "does not exist or you do not have access" in lowered:
        return True
    if "do not have access to it" in lowered and "model" in lowered:
        return True
    if "model" in lowered and "does not exist" in lowered:
        return True
    return False


def _codex_oauth_refresh_token_reused_error(output: str) -> bool:
    lowered = (output or "").lower()
    if not lowered:
        return False
    if "refresh_token_reused" in lowered:
        return True
    if "refresh token has already been used" in lowered:
        return True
    if "access token could not be refreshed because your refresh token was already used" in lowered:
        return True
    if "failed to refresh token: 401 unauthorized" in lowered:
        return True
    return False


def _oauth_session_refresh_or_auth_error(output: str) -> bool:
    lowered = (output or "").lower()
    if not lowered:
        return False
    direct_markers = (
        "refresh_token_reused",
        "failed to refresh token",
        "refresh token has already been used",
        "invalid_grant",
        "grant_type=refresh_token",
        "reauthenticate",
        "login required",
        "not logged in",
        "authentication required",
    )
    if any(marker in lowered for marker in direct_markers):
        return True
    has_token_context = any(marker in lowered for marker in ("oauth", "token", "auth"))
    has_auth_error = any(marker in lowered for marker in ("unauthorized", "401", "forbidden", "invalid token"))
    return bool(has_token_context and has_auth_error)


def _codex_model_not_found_fallback(command: str, output: str) -> tuple[str, dict[str, str] | None]:
    if not _codex_model_not_found_or_access_error(output):
        return command, None
    requested_model = _codex_command_model(command)
    if not requested_model:
        return command, None
    target_model = _codex_model_not_found_fallback_map().get(requested_model.lower(), "").strip()
    if not target_model or target_model.lower() == requested_model.lower():
        return command, None
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return command, None
    remapped = f"{command[:match.start('model')]}{target_model}{command[match.end('model'):]}"
    return remapped, {
        "requested_model": requested_model,
        "effective_model": target_model,
        "trigger": "model_not_found_or_access",
    }


def _uses_codex_cli(command: str) -> bool:
    return command.strip().startswith("codex ")


def _infer_executor(command: str, model: str) -> str:
    model_value = (model or "").strip().lower()
    if _uses_cursor_cli(command) or model_value.startswith("cursor/"):
        return "cursor"
    if _uses_codex_cli(command):
        return "openai-codex"
    if _uses_openclaw_cli(command) or model_value.startswith("openclaw/"):
        return "openclaw"
    if _uses_claude_cli(command) or model_value.startswith("claude/"):
        return "claude"
    return "unknown"


def _is_openai_codex_worker(worker_id: str) -> bool:
    normalized = (worker_id or "").strip().lower()
    if not normalized:
        return False
    return normalized == "openai-codex" or normalized.startswith("openai-codex:")


def _repo_path_for_task(task_ctx: dict[str, Any]) -> str:
    repo_path = str(
        task_ctx.get("repo_path")
        or task_ctx.get("working_copy_path")
        or os.environ.get("AGENT_WORKTREE_PATH", REPO_PATH)
    ).strip()
    if not repo_path:
        return REPO_PATH
    return os.path.abspath(repo_path)


def _ensure_repo_checkout(repo_path: str, *, log: logging.Logger) -> bool:
    git_dir = os.path.join(repo_path, ".git")
    if os.path.isdir(git_dir):
        return True
    clone_url = REPO_GIT_URL
    if not clone_url:
        log.warning("repo checkout missing at %s and AGENT_REPO_GIT_URL is not set", repo_path)
        return False
    parent = os.path.dirname(repo_path.rstrip("/")) or "."
    os.makedirs(parent, exist_ok=True)
    clone = _run_cmd(["git", "clone", clone_url, repo_path], cwd=parent, timeout=1200)
    if clone.returncode != 0:
        log.warning("git clone failed repo_path=%s err=%s", repo_path, clone.stderr.strip())
        return False
    return os.path.isdir(git_dir)


def _prepare_pr_branch(task_id: str, repo_path: str, branch: str, *, log: logging.Logger) -> bool:
    base_branch = str(os.environ.get("AGENT_PR_BASE_BRANCH", DEFAULT_PR_BASE_BRANCH)).strip() or DEFAULT_PR_BASE_BRANCH
    try:
        if not _ensure_repo_checkout(repo_path, log=log):
            return False
        fetch = _run_git("fetch", "origin", "--prune", cwd=repo_path, timeout=120)
        if fetch.returncode != 0:
            log.warning("task=%s git fetch failed: %s", task_id, fetch.stderr.strip())
            return False
        remote_branch = _run_git("rev-parse", "--verify", f"origin/{branch}", cwd=repo_path, timeout=60)
        if remote_branch.returncode == 0:
            # Resume from previously pushed progress when available.
            checkout = _run_git("checkout", "-B", branch, f"origin/{branch}", cwd=repo_path, timeout=120)
            if checkout.returncode != 0:
                log.warning("task=%s branch resume failed: %s", task_id, checkout.stderr.strip())
                return False
            return True

        checkout = _run_git("checkout", "-B", branch, f"origin/{base_branch}", cwd=repo_path, timeout=120)
        if checkout.returncode != 0:
            checkout = _run_git("checkout", "-B", branch, base_branch, cwd=repo_path, timeout=120)
        if checkout.returncode != 0:
            checkout = _run_git("checkout", "-B", branch, cwd=repo_path, timeout=120)
        if checkout.returncode != 0:
            log.warning("task=%s branch setup failed: %s", task_id, checkout.stderr.strip())
            return False
        return True
    except Exception as e:
        log.warning("task=%s branch prep failed: %s", task_id, e)
        return False


def _run_local_pr_checks(
    branch: str,
    task_id: str,
    log: logging.Logger,
    *,
    repo_path: str,
) -> dict[str, object]:
    repo = str(os.environ.get("AGENT_GITHUB_REPO", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO
    args: list[str] = [
        sys.executable,
        os.path.join(_api_dir, "scripts", "validate_pr_to_public.py"),
        "--branch",
        branch,
        "--repo",
        repo,
        "--json",
    ]
    try:
        check = _run_cmd(args, cwd=repo_path, timeout=max(30, PR_GATE_POLL_SECONDS))
        if check.returncode not in {0, 2}:
            return {
                "result": "blocked",
                "reason": "validate_pr_to_public.py invocation failed",
                "error": check.stderr.strip()[:1200],
            }
        payload = _json_or_text(check.stdout)
        if isinstance(payload, dict):
            return payload
        return {
            "result": "blocked",
            "reason": "validate_pr_to_public.py returned non-dict payload",
            "payload": payload,
        }
    except Exception as e:
        log.warning("task=%s PR gate check failed: %s", task_id, e)
        return {
            "result": "blocked",
            "reason": "PR gate check raised exception",
            "error": str(e)[:1200],
        }


def _get_or_create_pr(
    *,
    task_id: str,
    task_ctx: dict[str, Any],
    repo: str,
    repo_path: str,
    branch: str,
    direction: str,
    log: logging.Logger,
) -> tuple[bool, str]:
    list_cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--head",
        branch,
        "--state",
        "open",
        "--json",
        "number,url,title",
    ]
    listed = _run_cmd(list_cmd, cwd=repo_path, timeout=120)
    if listed.returncode == 0:
        payload = _json_or_text(listed.stdout)
        if isinstance(payload, list):
            for pr in payload:
                if isinstance(pr, dict):
                    url = str(pr.get("url") or "").strip()
                    if url:
                        return True, url
    else:
        log.warning("task=%s PR list failed: %s", task_id, listed.stderr.strip())

    title = str(
        task_ctx.get("pr_title")
        or f"[{task_id}] {str(direction or '').strip()}".strip()
        or f"Coherence-Network task {task_id}"
    )
    title = title[:140]
    body = str(
        task_ctx.get("pr_body")
        or (
            "System task for Codex thread execution.\n\n"
            f"Task ID: {task_id}\n"
            f"Direction: {direction}\n"
            "Please review and merge when checks are green."
        )
    )[:4000]
    create_cmd = [
        "gh",
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        str(os.environ.get("AGENT_PR_BASE_BRANCH", DEFAULT_PR_BASE_BRANCH)).strip() or DEFAULT_PR_BASE_BRANCH,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
    ]
    created = _run_cmd(create_cmd, cwd=repo_path, timeout=1200)
    if created.returncode != 0:
        err = created.stderr.strip()[:1200]
        if "already exists" in err.lower() or "already exists" in created.stdout.lower():
            # Another actor created it between list and create. Retry lookup.
            listed = _run_cmd(list_cmd, cwd=repo_path, timeout=120)
            payload = _json_or_text(listed.stdout)
            if isinstance(payload, list):
                for pr in payload:
                    if isinstance(pr, dict):
                        url = str(pr.get("url") or "").strip()
                        if url:
                            return True, url
        return False, f"PR create failed: {err}"

    url = ""
    payload = _json_or_text(created.stdout)
    if isinstance(payload, dict):
        url = str(payload.get("url") or "").strip()
    if not url:
        parsed = created.stdout.strip().splitlines()
        for line in reversed(parsed):
            if line.strip().startswith("https://"):
                url = line.strip()
                break
    if url:
        return True, url
    return False, f"PR created but URL unknown. stdout={created.stdout[:500]}"


def _attempt_pr_merge(
    *,
    task_id: str,
    pr_url: str,
    repo_path: str,
    log: logging.Logger,
) -> tuple[bool, str]:
    method = str(os.environ.get("AGENT_PR_MERGE_METHOD", "squash")).strip().lower() or "squash"
    method_flag = f"--{method}" if method in {"squash", "merge", "rebase"} else "--squash"
    merge_cmd = [
        "gh",
        "pr",
        "merge",
        "--repo",
        str(os.environ.get("AGENT_GITHUB_REPO", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO,
        pr_url,
        "--auto",
        method_flag,
        "--delete-branch",
    ]
    merged = _run_cmd(merge_cmd, cwd=repo_path, timeout=1800)
    if merged.returncode != 0:
        return False, merged.stderr.strip()[:1200]
    return True, merged.stdout.strip()[:3000]


def _run_pr_delivery_flow(
    task_id: str,
    task: dict[str, Any],
    task_direction: str,
    command_status: str,
    command_output: str,
    log: logging.Logger,
) -> tuple[str, str]:
    if command_status != "completed":
        return "failed", "[pr-flow] Skipped PR delivery because execution failed."

    ctx = _safe_get_task_context(task)
    branch = _extract_pr_branch(task_id=task_id, task_ctx=ctx, direction=task_direction)
    repo_path = _repo_path_for_task(ctx)
    if not os.path.isdir(repo_path) and not _ensure_repo_checkout(repo_path, log=log):
        return "failed", f"[pr-flow] Repo path not found and clone failed: {repo_path}"
    if not os.path.isdir(repo_path):
        return "failed", f"[pr-flow] Repo path not found: {repo_path}"

    if not _prepare_pr_branch(task_id, repo_path, branch, log=log):
        return "failed", "[pr-flow] Unable to initialize codex task branch."

    if not _as_bool(ctx.get("skip_local_validation")):
        validation_cmd = str(os.environ.get("AGENT_PR_LOCAL_VALIDATION_CMD", DEFAULT_PR_LOCAL_CHECK_CMD)).strip()
        if validation_cmd:
            validation = _run_cmd(
                validation_cmd,
                cwd=repo_path,
                timeout=max(60, PR_GATE_POLL_SECONDS),
                shell=True,
            )
            if validation.returncode != 0:
                return (
                    "failed",
                    f"[pr-flow] Local validation command failed: {validation.stderr.strip()[:1200]}",
                )

    status_lines = _run_git("status", "--porcelain", cwd=repo_path, timeout=120)
    if status_lines.returncode != 0:
        return "failed", f"[pr-flow] Unable to inspect working tree: {status_lines.stderr.strip()[:1200]}"
    if not status_lines.stdout.strip():
        return "completed", f"[pr-flow] No file changes. Branch '{branch}' unchanged."

    commit_msg = str(
        ctx.get("pr_commit_message")
        or f"[coherence-bot] task {task_id}: {task_direction}".strip()
    )[:120]
    add = _run_git("add", "-A", cwd=repo_path, timeout=120)
    if add.returncode != 0:
        return "failed", f"[pr-flow] git add failed: {add.stderr.strip()[:1200]}"
    commit = _run_git("commit", "-m", commit_msg, cwd=repo_path, timeout=240)
    if commit.returncode != 0:
        if "nothing to commit" in commit.stderr.lower() and "changed" in commit.stderr.lower():
            return "completed", f"[pr-flow] No commit created for {branch}; no changes."
        return "failed", f"[pr-flow] git commit failed: {commit.stderr.strip()[:1200]}"

    push = _run_cmd(
        ["git", "push", "-u", "origin", branch],
        cwd=repo_path,
        timeout=300,
    )
    if push.returncode != 0:
        return "failed", f"[pr-flow] git push failed: {push.stderr.strip()[:1200]}"

    repo = str(os.environ.get("AGENT_GITHUB_REPO", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO
    pr_ok, pr_url_or_error = _get_or_create_pr(
        task_id=task_id,
        task_ctx=ctx,
        repo=repo,
        repo_path=repo_path,
        branch=branch,
        direction=task_direction,
        log=log,
    )
    if not pr_ok:
        return "failed", f"[pr-flow] PR create/update failed: {pr_url_or_error}"

    # Poll for checks. This handles transient check lag and flake.
    deadline = time.time() + PR_FLOW_TIMEOUT_SECONDS
    last_report = {}
    attempts_remaining = MAX_PR_GATE_ATTEMPTS
    while time.time() < deadline and attempts_remaining > 0:
        attempts_remaining -= 1
        last_report = _run_local_pr_checks(branch, task_id, log=log, repo_path=repo_path)
        result = str(last_report.get("result") or "").strip()
        if result in {"ready_for_merge", "public_validated"}:
            if _as_bool(ctx.get("auto_merge")) or _as_bool(ctx.get("auto_merge_pr")):
                merged, merge_msg = _attempt_pr_merge(
                    task_id=task_id,
                    pr_url=pr_url_or_error,
                    repo_path=repo_path,
                    log=log,
                )
                if not merged:
                    return (
                        "needs_decision",
                        f"[pr-flow] PR ready but merge failed: {merge_msg}\nPR: {pr_url_or_error}",
                    )
                merged_output = f"PR merged: {pr_url_or_error}"
                if _as_bool(ctx.get("wait_public")):
                    wait_public = _run_cmd(
                        [
                            sys.executable,
                            os.path.join(_api_dir, "scripts", "validate_pr_to_public.py"),
                            "--branch",
                            branch,
                            "--repo",
                            repo,
                            "--wait-public",
                            "--json",
                        ],
                        cwd=repo_path,
                        timeout=1800,
                    )
                    if wait_public.returncode != 0:
                        return (
                            "failed",
                            f"[pr-flow] PR merged but public validation command failed: {wait_public.stderr.strip()[:1200]}",
                        )
                return "completed", f"[pr-flow] {merged_output}. Branch={branch}"
            return "completed", f"[pr-flow] PR ready for merge: {pr_url_or_error}. Branch={branch}"
        if len(last_report) == 0:
            return "failed", "[pr-flow] PR checks did not return a valid report."
        if result not in {"blocked", "ready_for_merge", "public_validated"}:
            return "failed", f"[pr-flow] PR checks returned unknown result: {_pr_command_output(last_report, 600)}"
        time.sleep(PR_GATE_POLL_SECONDS)

    reason = str(last_report.get("reason") or "PR checks did not become green before timeout.")
    return "failed", f"[pr-flow] Timeout waiting for PR checks/mergeability. reason={reason}\nPR: {pr_url_or_error}"


def _handle_pr_failure_handoff(
    *,
    client: httpx.Client,
    task_id: str,
    task_ctx: dict[str, Any],
    repo_path: str,
    branch: str,
    failure_class: str,
    output: str,
    run_id: str,
    attempt: int,
    worker_id: str,
    log: logging.Logger,
) -> tuple[str, str]:
    reason = f"{failure_class} during codex execution"
    checkpoint = _checkpoint_partial_progress(
        task_id=task_id,
        repo_path=repo_path,
        branch=branch,
        run_id=run_id,
        reason=reason,
        log=log,
    )
    checkpoint_ok = _as_bool(checkpoint.get("ok"))
    checkpoint_sha = str(checkpoint.get("checkpoint_sha") or "").strip()
    resume_attempts = _to_int(task_ctx.get("resume_attempts"), 0)
    max_resume_attempts = max(0, _to_int(task_ctx.get("max_resume_attempts"), MAX_RESUME_ATTEMPTS))
    should_requeue = (
        checkpoint_ok
        and failure_class in {"usage_limit", "timeout"}
        and resume_attempts < max_resume_attempts
    )
    next_status = "pending" if should_requeue else "failed"
    next_action = "requeue_for_resume" if should_requeue else "needs_manual_attention"
    context_patch: dict[str, Any] = {
        "resume_branch": branch,
        "resume_checkpoint_sha": checkpoint_sha,
        "resume_ready": checkpoint_ok,
        "resume_reason": reason,
        "resume_from_run_id": run_id,
        "resume_attempts": resume_attempts + (1 if should_requeue else 0),
        "last_failure_class": failure_class,
        "last_attempt": attempt,
        "last_worker_id": worker_id,
        "repo_path": repo_path,
        "next_action": next_action,
    }
    if checkpoint_ok and checkpoint_sha:
        context_patch["resume_head_sha"] = checkpoint_sha

    summary = (
        f"[handoff] failure_class={failure_class}; "
        f"checkpoint_ok={checkpoint_ok}; branch={branch}; checkpoint_sha={checkpoint_sha or 'n/a'}; "
        f"next_status={next_status}; attempts={resume_attempts}/{max_resume_attempts}"
    )
    final_output = f"{output}\n\n{summary}"[-4000:]
    client.patch(
        f"{BASE}/api/agent/tasks/{task_id}",
        json={"status": next_status, "output": final_output, "context": context_patch},
    )
    _sync_run_state(
        client,
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch={
            "status": next_status,
            "failure_class": failure_class,
            "checkpoint_ok": checkpoint_ok,
            "checkpoint_sha": checkpoint_sha,
            "next_action": next_action,
            "completed_at": _utc_now_iso(),
        },
        lease_seconds=RUN_LEASE_SECONDS,
        require_owner=False,
    )
    return next_status, summary


def run_one_task(
    client: httpx.Client,
    task_id: str,
    command: str,
    log: logging.Logger,
    verbose: bool = False,
    task_type: str = "impl",
    model: str = "unknown",
    task_context: dict[str, Any] | None = None,
    task_direction: str = "",
) -> bool:
    """Execute task command, PATCH status. Returns True if completed/failed, False if needs_decision."""
    task_ctx = task_context or {}
    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    requested_executor = str(task_ctx.get("executor") or "").strip().lower()
    inferred_executor = _infer_executor(command, model)
    if requested_executor == "openrouter" or inferred_executor == "openrouter":
        return _dispatch_openrouter_server_executor(
            client=client,
            task_id=task_id,
            task_ctx=task_ctx,
            task_type=str(task_type or "impl"),
            worker_id=worker_id,
            log=log,
        )
    env = os.environ.copy()
    codex_model_alias: dict[str, str] | None = None
    claude_model_alias: dict[str, str] | None = None
    codex_auth_state: dict[str, Any] | None = None
    cursor_auth_state: dict[str, Any] | None = None
    gemini_auth_state: dict[str, Any] | None = None
    claude_auth_state: dict[str, Any] | None = None
    cli_bootstrap_ok = True
    cli_bootstrap_detail = ""
    cli_bootstrap_ok, cli_bootstrap_detail = _ensure_cli_for_command(
        command=command,
        env=env,
        task_id=task_id,
        log=log,
    )
    if cli_bootstrap_detail:
        if cli_bootstrap_ok:
            log.info("task=%s %s", task_id, cli_bootstrap_detail)
        else:
            log.warning("task=%s %s", task_id, cli_bootstrap_detail)
    popen_command: str | list[str] = command
    popen_shell = True
    popen_preexec_fn: Callable[[], None] | None = None
    command_exec_mode = "shell"
    if _uses_cursor_cli(command):
        # Cursor CLI uses Cursor app auth; ensure OpenAI-compatible env vars for OpenRouter
        env.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        env.setdefault("OPENAI_API_BASE", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        log.info("task=%s using Cursor CLI with OpenRouter", task_id)
    elif _uses_codex_cli(command):
        env.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        env.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"))
        env.setdefault("OPENAI_BASE_URL", env.get("OPENAI_API_BASE"))
        log.info("task=%s using codex CLI", task_id)
    elif _uses_openclaw_cli(command):
        env.setdefault("OPENCLAW_API_KEY", os.environ.get("OPENCLAW_API_KEY", ""))
        env.setdefault("OPENCLAW_BASE_URL", os.environ.get("OPENCLAW_BASE_URL", ""))
        log.info("task=%s using OpenClaw executor", task_id)
    elif _uses_claude_cli(command):
        # Claude Code CLI auth resolution order:
        #   1. ANTHROPIC_API_KEY  — explicit cloud key
        #   2. CLAUDE_CODE_OAUTH_TOKEN  — explicit OAuth env token
        #   3. Local CLI session (`claude login`) — inherited automatically; no env override needed
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
            env.pop("ANTHROPIC_BASE_URL", None)
            log.info("task=%s using Claude Code CLI (API key)", task_id)
        elif oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
            env.pop("ANTHROPIC_BASE_URL", None)
            log.info("task=%s using Claude Code CLI (OAuth token)", task_id)
        else:
            # No explicit auth env vars — let the CLI use its own session (from `claude login`).
            # Clear any Ollama overrides that would confuse the Claude Code CLI.
            env.pop("ANTHROPIC_AUTH_TOKEN", None)
            env.pop("ANTHROPIC_BASE_URL", None)
            env.pop("ANTHROPIC_API_KEY", None)
            log.info("task=%s using Claude Code CLI (inherited session)", task_id)
    elif _uses_anthropic_cloud(command):
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        env.pop("ANTHROPIC_API_KEY", None)
        log.warning(
            "task=%s anthropic cloud API-key auth disabled; use Claude CLI OAuth/session for paid Anthropic access",
            task_id,
        )
    else:
        env.setdefault("ANTHROPIC_AUTH_TOKEN", "ollama")
        env.setdefault("ANTHROPIC_BASE_URL", "http://localhost:11434")
        env.setdefault("ANTHROPIC_API_KEY", "")
    popen_command, popen_shell, command_exec_mode = _prepare_cli_command_for_exec(command)
    if _uses_codex_cli(command):
        log.info("task=%s codex execution mode=%s", task_id, command_exec_mode)
    # Suppress Claude Code requests to unsupported local-model endpoints (GitHub #13949)
    env.setdefault("DISABLE_TELEMETRY", "1")
    env.setdefault("DISABLE_ERROR_REPORTING", "1")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    non_root_ok, non_root_detail, non_root_preexec = _prepare_non_root_execution_for_command(
        command=command,
        env=env,
    )
    if non_root_detail:
        if non_root_ok:
            log.info("task=%s %s", task_id, non_root_detail)
            popen_preexec_fn = non_root_preexec
        else:
            log.warning("task=%s %s", task_id, non_root_detail)

    executor = _infer_executor(command, model)
    is_openai_codex = _is_openai_codex_worker(worker_id) or _uses_codex_cli(command)

    task_ctx = task_context or {}
    task_snapshot = {"task_type": task_type, "context": task_ctx}
    pr_mode = _should_run_pr_flow(task_snapshot)
    repo_path = _repo_path_for_task(task_ctx) if pr_mode else os.path.dirname(_api_dir)
    branch_name = _extract_pr_branch(task_id=task_id, task_ctx=task_ctx, direction=task_direction) if pr_mode else ""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    attempt = _next_task_attempt(task_id)
    if attempt > 1:
        retry_override_command = str(task_ctx.get("retry_override_command") or "").strip()
        if retry_override_command:
            log.info("task=%s applying retry_override_command for attempt=%s", task_id, attempt)
            command = retry_override_command
    _runner_heartbeat(
        client,
        runner_id=worker_id,
        status="running",
        active_task_id=task_id,
        active_run_id=run_id,
        metadata={"executor": executor, "task_type": task_type},
    )
    # Ensure the task runs from the target worktree in PR mode so file edits stay on a dedicated branch.
    if pr_mode:
        if not _prepare_pr_branch(task_id, repo_path, branch_name, log=log):
            _sync_run_state(
                client,
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                patch={
                    "task_id": task_id,
                    "attempt": attempt,
                    "status": "failed",
                    "worker_id": worker_id,
                    "task_type": task_type,
                    "direction": task_direction,
                    "branch": branch_name,
                    "repo_path": repo_path,
                    "failure_class": "branch_setup_failed",
                    "next_action": "needs_attention",
                    "completed_at": _utc_now_iso(),
                },
                lease_seconds=RUN_LEASE_SECONDS,
                require_owner=False,
            )
            if verbose:
                print(f"  -> pre-run branch setup failed for {task_id}")
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={"status": "failed", "output": f"[pr-flow] branch setup failed: {branch_name}"},
            )
            _runner_heartbeat(
                client,
                runner_id=worker_id,
                status="degraded",
                active_task_id="",
                active_run_id="",
                last_error="branch setup failed",
                metadata={"task_id": task_id, "task_type": task_type},
            )
            return True

    lease_ok = _claim_run_lease(
        client,
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        attempt=attempt,
        branch=branch_name,
        repo_path=repo_path,
        task_type=task_type,
        direction=task_direction,
    )
    if not lease_ok:
        log.info("task=%s lease claim rejected by run-state owner", task_id)
        try:
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={
                    "current_step": "waiting for lease",
                    "context": {
                        "retry_not_before": (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat(),
                    },
                },
            )
        except Exception:
            pass
        _sync_run_state(
            client,
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch={
                "status": "skipped",
                "failure_class": "lease_claim_rejected",
                "next_action": "skip",
                "completed_at": _utc_now_iso(),
            },
            lease_seconds=RUN_LEASE_SECONDS,
            require_owner=False,
        )
        _runner_heartbeat(
            client,
            runner_id=worker_id,
            status="idle",
            active_task_id="",
            active_run_id="",
            metadata={"last_task_id": task_id, "detail": "lease_claim_rejected"},
        )
        return True

    # PATCH to running
    running_context: dict[str, Any] = {
        "active_run_id": run_id,
        "active_worker_id": worker_id,
        "active_branch": branch_name if pr_mode else "",
        "last_attempt": attempt,
    }
    if cli_bootstrap_detail:
        running_context["runner_cli_bootstrap"] = {
            "ok": bool(cli_bootstrap_ok),
            "detail": cli_bootstrap_detail,
            "at": _utc_now_iso(),
        }
    if codex_auth_state:
        running_context["runner_codex_auth"] = {
            **codex_auth_state,
            "at": _utc_now_iso(),
        }
    if codex_model_alias or claude_model_alias:
        active_model_alias = codex_model_alias or claude_model_alias
        running_context["runner_model_alias"] = {
            **(active_model_alias or {}),
            "at": _utc_now_iso(),
        }
    if non_root_detail:
        running_context["runner_exec_user"] = {
            "ok": bool(non_root_ok),
            "detail": non_root_detail,
            "at": _utc_now_iso(),
        }
    r = client.patch(
        f"{BASE}/api/agent/tasks/{task_id}",
        json={
            "status": "running",
            "worker_id": worker_id,
            "context": {
                "active_run_id": run_id,
                "active_worker_id": worker_id,
                "active_branch": branch_name if pr_mode else "",
                "last_attempt": attempt,
            },
        },
    )
    if r.status_code != 200:
        _sync_run_state(
            client,
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch={
                "task_id": task_id,
                "attempt": attempt,
                "status": "skipped",
                "worker_id": worker_id,
                "task_type": task_type,
                "direction": task_direction,
                "branch": branch_name,
                "repo_path": repo_path,
                "failure_class": "claim_conflict" if r.status_code == 409 else "claim_failed",
                "next_action": "skip",
                "completed_at": _utc_now_iso(),
            },
            lease_seconds=RUN_LEASE_SECONDS,
            require_owner=False,
        )
        if r.status_code == 409:
            log.info("task=%s already claimed by another worker; skipping", task_id)
        else:
            log.error("task=%s PATCH running failed status=%s", task_id, r.status_code)
        _runner_heartbeat(
            client,
            runner_id=worker_id,
            status="idle",
            active_task_id="",
            active_run_id="",
            metadata={"last_task_id": task_id, "detail": "patch_running_failed"},
        )
        return True

    _sync_run_state(
        client,
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch={
            "task_id": task_id,
            "attempt": attempt,
            "status": "running",
            "worker_id": worker_id,
            "task_type": task_type,
            "direction": task_direction,
            "branch": branch_name,
            "repo_path": repo_path,
            "started_at": _utc_now_iso(),
            "last_heartbeat_at": _utc_now_iso(),
            "head_sha": _current_head_sha(repo_path) if pr_mode else "",
            "next_action": "execute_command",
        },
        lease_seconds=RUN_LEASE_SECONDS,
        require_owner=True,
    )

    start_time = time.monotonic()
    log.info("task=%s starting command=%s", task_id, command[:120])
    if verbose:
        print(f"Running: {command[:80]}...")

    out_file = os.path.join(LOG_DIR, f"task_{task_id}.log")
    output_lines: list[str] = []
    reader_done = threading.Event()
    auth_note = ""
    if codex_auth_state:
        auth_note = (
            "[runner-codex-auth] requested_mode="
            f"{codex_auth_state['requested_mode']} effective_mode={codex_auth_state['effective_mode']} "
            f"oauth_session={'true' if codex_auth_state['oauth_session'] else 'false'} "
            f"oauth_source={codex_auth_state['oauth_source']} "
            f"api_key_present={'true' if codex_auth_state['api_key_present'] else 'false'} "
            f"oauth_missing={'true' if codex_auth_state['oauth_missing'] else 'false'}\n"
        )
    alias_note = ""
    effective_model_alias = codex_model_alias or claude_model_alias
    if effective_model_alias:
        alias_note = (
            "[runner-model-alias] requested_model="
            f"{effective_model_alias['requested_model']} effective_model={effective_model_alias['effective_model']}\n"
        )
    exec_mode_note = ""
    if _uses_codex_cli(command):
        exec_mode_note = f"[runner-command-exec] mode={command_exec_mode}\n"

    def _stream_reader(proc: subprocess.Popen) -> None:
        """Read process stdout line-by-line, write to log file + collect output."""
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(f"# task_id={task_id} status=running\n")
                f.write(f"# command={command}\n")
                f.write("---\n")
                if auth_note:
                    f.write(auth_note)
                    output_lines.append(auth_note)
                if alias_note:
                    f.write(alias_note)
                    output_lines.append(alias_note)
                if exec_mode_note:
                    f.write(exec_mode_note)
                    output_lines.append(exec_mode_note)
                f.flush()
                for line in iter(proc.stdout.readline, ""):
                    f.write(line)
                    f.flush()
                    output_lines.append(line)
        except Exception as e:
            output_lines.append(f"\n[stream error: {e}]\n")
        finally:
            reader_done.set()

    try:
        if not non_root_ok:
            failure_output = (
                "[runner-exec-user] root execution blocked for --dangerously-skip-permissions: "
                f"{non_root_detail}. Configure AGENT_RUN_AS_USER to an existing non-root account."
            )
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={"status": "failed", "output": failure_output},
            )
            _sync_run_state(
                client,
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                patch={
                    "task_id": task_id,
                    "attempt": attempt,
                    "status": "failed",
                    "worker_id": worker_id,
                    "task_type": task_type,
                    "direction": task_direction,
                    "branch": branch_name,
                    "repo_path": repo_path,
                    "failure_class": "runner_exec_user_unavailable",
                    "next_action": "needs_attention",
                    "completed_at": _utc_now_iso(),
                },
                lease_seconds=RUN_LEASE_SECONDS,
                require_owner=False,
            )
            _runner_heartbeat(
                client,
                runner_id=worker_id,
                status="degraded",
                active_task_id="",
                active_run_id="",
                last_error="runner_exec_user_unavailable",
                metadata={"task_id": task_id, "task_type": task_type},
            )
            return True

        process = subprocess.Popen(
            popen_command,
            shell=popen_shell,
            env=env,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        reader = threading.Thread(target=_stream_reader, args=(process,), daemon=False)
        reader.start()

        requested_runtime = _to_int(task_ctx.get("max_runtime_seconds"), TASK_TIMEOUT)
        max_runtime_seconds = max(30, min(TASK_TIMEOUT, requested_runtime))
        timed_out = False
        stopped_for_usage = False
        stopped_for_abort = False
        abort_reason = ""
        diagnostic_completed_id = str(task_ctx.get("diagnostic_last_completed_id") or "").strip()
        if hasattr(process, "poll"):
            deadline = start_time + float(max_runtime_seconds)
            next_heartbeat = time.monotonic() + RUN_HEARTBEAT_SECONDS
            next_control_poll = time.monotonic() + CONTROL_POLL_SECONDS
            next_progress_patch = time.monotonic() + max(2, min(RUN_HEARTBEAT_SECONDS, CONTROL_POLL_SECONDS))
            next_checkpoint = (
                time.monotonic() + PERIODIC_CHECKPOINT_SECONDS
                if pr_mode and PERIODIC_CHECKPOINT_SECONDS > 0
                else float("inf")
            )
            while process.poll() is None:
                now = time.monotonic()
                if now >= deadline:
                    timed_out = True
                    output_lines.append(f"\n[Timeout {max_runtime_seconds}s]\n")
                    break
                if now >= next_heartbeat:
                    elapsed = max(0.0, now - start_time)
                    approx_progress = min(95, max(1, int((elapsed / max_runtime_seconds) * 90)))
                    tail = _tail_output_lines(output_lines)
                    _patch_task_progress(
                        client,
                        task_id=task_id,
                        progress_pct=approx_progress,
                        current_step="running command",
                        context_patch={
                            "runner_id": worker_id,
                            "runner_run_id": run_id,
                            "runner_last_seen_at": _utc_now_iso(),
                            "runner_pid": getattr(process, "pid", None),
                            "runner_log_tail": tail,
                        },
                    )
                    _sync_run_state(
                        client,
                        task_id=task_id,
                        run_id=run_id,
                        worker_id=worker_id,
                        patch={
                            "status": "running",
                            "last_heartbeat_at": _utc_now_iso(),
                            "next_action": "execute_command",
                        },
                        lease_seconds=RUN_LEASE_SECONDS,
                        require_owner=True,
                    )
                    _runner_heartbeat(
                        client,
                        runner_id=worker_id,
                        status="running",
                        active_task_id=task_id,
                        active_run_id=run_id,
                        metadata={"executor": executor, "task_type": task_type},
                    )
                    next_heartbeat = now + RUN_HEARTBEAT_SECONDS
                if now >= next_control_poll:
                    task_snapshot_live = _safe_get_task_snapshot(client, task_id)
                    abort_requested, requested_abort_reason, diagnostic_request = _extract_control_signals(task_snapshot_live)
                    if diagnostic_request:
                        request_id = _diagnostic_request_id(diagnostic_request)
                        if request_id and request_id != diagnostic_completed_id:
                            diagnostic_result = _run_diagnostic_request(
                                diagnostic_request,
                                cwd=repo_path,
                                env=env,
                            )
                            diagnostic_completed_id = request_id
                            _patch_task_progress(
                                client,
                                task_id=task_id,
                                progress_pct=min(95, max(1, int(((now - start_time) / max_runtime_seconds) * 90))),
                                current_step="running diagnostic",
                                context_patch={
                                    "diagnostic_last_completed_id": request_id,
                                    "diagnostic_last_result": diagnostic_result,
                                    "runner_last_seen_at": _utc_now_iso(),
                                },
                            )
                            output_lines.append(
                                "\n[Diagnostic] "
                                f"id={request_id} status={diagnostic_result.get('status')} "
                                f"exit={diagnostic_result.get('exit_code')}\n"
                            )
                    if abort_requested:
                        stopped_for_abort = True
                        abort_reason = requested_abort_reason or "abort requested from API"
                        output_lines.append(f"\n[Abort] {abort_reason}\n")
                        _sync_run_state(
                            client,
                            task_id=task_id,
                            run_id=run_id,
                            worker_id=worker_id,
                            patch={
                                "status": "running",
                                "last_heartbeat_at": _utc_now_iso(),
                                "next_action": "abort_requested",
                                "failure_class": "aborted_by_user",
                            },
                            lease_seconds=RUN_LEASE_SECONDS,
                            require_owner=True,
                        )
                        break
                    next_control_poll = now + CONTROL_POLL_SECONDS
                if now >= next_progress_patch:
                    elapsed = max(0.0, now - start_time)
                    approx_progress = min(95, max(1, int((elapsed / max_runtime_seconds) * 90)))
                    _patch_task_progress(
                        client,
                        task_id=task_id,
                        progress_pct=approx_progress,
                        current_step="running command",
                        context_patch={
                            "runner_id": worker_id,
                            "runner_run_id": run_id,
                            "runner_last_seen_at": _utc_now_iso(),
                            "runner_log_tail": _tail_output_lines(output_lines),
                        },
                    )
                    next_progress_patch = now + max(2, min(RUN_HEARTBEAT_SECONDS, CONTROL_POLL_SECONDS))
                if now >= next_checkpoint:
                    checkpoint = _checkpoint_partial_progress(
                        task_id=task_id,
                        repo_path=repo_path,
                        branch=branch_name,
                        run_id=run_id,
                        reason="periodic checkpoint",
                        log=log,
                    )
                    checkpoint_sha = str(checkpoint.get("checkpoint_sha") or "").strip()
                    if _as_bool(checkpoint.get("ok")):
                        _sync_run_state(
                            client,
                            task_id=task_id,
                            run_id=run_id,
                            worker_id=worker_id,
                            patch={
                                "checkpoint_sha": checkpoint_sha,
                                "head_sha": checkpoint_sha,
                                "next_action": "execute_command",
                            },
                            lease_seconds=RUN_LEASE_SECONDS,
                            require_owner=True,
                        )
                    else:
                        log.warning(
                            "task=%s periodic checkpoint failed: %s",
                            task_id,
                            str(checkpoint.get("reason") or "unknown"),
                        )
                    next_checkpoint = now + PERIODIC_CHECKPOINT_SECONDS
                tail = "".join(output_lines[-120:])
                if _detect_usage_limit(tail):
                    stopped_for_usage = True
                    output_lines.append("\n[Usage guard] Stopping execution due to usage/quota signal.\n")
                    break
                time.sleep(1)
        else:
            # Legacy/mocked process objects may only support wait(timeout=...).
            try:
                process.wait(timeout=max_runtime_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                output_lines.append(f"\n[Timeout {max_runtime_seconds}s]\n")

        if timed_out or stopped_for_usage or stopped_for_abort:
            try:
                process.terminate()
                process.wait(timeout=10)
            except Exception:
                process.kill()
                process.wait()

        reader_done.wait(timeout=5)
        reader.join(timeout=2)

        output = "".join(output_lines)
        returncode = process.returncode if process.returncode is not None else -9
        duration_sec = round(time.monotonic() - start_time, 1)
        tool_name = _tool_token(command)

        # Zero/short output on exit 0 is suspicious: likely capture failure or silent crash
        MIN_OUTPUT_CHARS = 10
        output_stripped = (output or "").strip()
        if returncode == 0 and len(output_stripped) < MIN_OUTPUT_CHARS:
            status = "failed"
            output = (
                output
                + f"\n[Pipeline] Marked failed: completed with {len(output_stripped)} chars output (expected >{MIN_OUTPUT_CHARS}). Possible capture failure or silent crash."
            )
        else:
            status = "completed" if returncode == 0 else "failed"
        if stopped_for_abort:
            status = "failed"
            output = f"{output}\n[Runner] Task aborted by request: {abort_reason or 'abort requested'}"
        failure_class = _classify_failure(
            output=output,
            timed_out=timed_out,
            stopped_for_usage=stopped_for_usage,
            stopped_for_abort=stopped_for_abort,
            returncode=returncode,
        )

        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"\n# duration_seconds={duration_sec} exit={returncode} status={status}\n")

        # Record tool execution telemetry (cost even when failing).
        sc = 200 if status == "completed" else 500
        _post_runtime_event(
            client,
            tool_name=tool_name,
            status_code=sc,
            runtime_ms=duration_sec * 1000.0,
            task_id=task_id,
            task_type=task_type,
            model=model,
            returncode=returncode,
            output_len=len(output or ""),
            worker_id=worker_id,
            executor=executor,
            is_openai_codex=is_openai_codex,
        )
        if status != "completed":
            _post_tool_failure_friction(
                client,
                tool_name=tool_name,
                task_id=task_id,
                task_type=task_type,
                model=model,
                duration_seconds=duration_sec,
                returncode=returncode,
                command=command,
            )

        _update_task_run_metrics(
            client,
            task_id=task_id,
            task_type=task_type,
            model=model,
            command=command,
            attempt=attempt,
            duration_seconds=duration_sec,
            attempt_status=status,
            failure_class=failure_class,
        )

        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": status, "output": output[:4000]},
        )
        _sync_run_state(
            client,
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch={
                "status": status,
                "duration_seconds": duration_sec,
                "returncode": returncode,
                "failure_class": failure_class if status != "completed" else "",
                "last_heartbeat_at": _utc_now_iso(),
                "head_sha": _current_head_sha(repo_path) if pr_mode else "",
                "next_action": "pr_delivery" if pr_mode and status == "completed" else "finalize",
            },
            lease_seconds=RUN_LEASE_SECONDS,
            require_owner=True,
        )

        final_status = status
        if pr_mode and status == "completed":
            final_status, pr_output = _run_pr_delivery_flow(
                task_id=task_id,
                task=task_snapshot,
                task_direction=task_direction,
                command_status=status,
                command_output=output,
                log=log,
            )
            status = final_status
            if pr_output:
                output = f"{output}\n\n{pr_output}"
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={"status": final_status, "output": output[-4000:]},
            )
            _sync_run_state(
                client,
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                patch={
                    "status": final_status,
                    "head_sha": _current_head_sha(repo_path),
                    "next_action": "done" if final_status == "completed" else "needs_attention",
                    "completed_at": _utc_now_iso(),
                },
                lease_seconds=RUN_LEASE_SECONDS,
                require_owner=True,
            )
        elif pr_mode and status != "completed":
            final_status, handoff_summary = _handle_pr_failure_handoff(
                client=client,
                task_id=task_id,
                task_ctx=task_ctx,
                repo_path=repo_path,
                branch=branch_name,
                failure_class=failure_class,
                output=output,
                run_id=run_id,
                attempt=attempt,
                worker_id=worker_id,
                log=log,
            )
            status = final_status
            output = f"{output}\n\n{handoff_summary}" if handoff_summary else output
        elif (not pr_mode) and status != "completed":
            retry_scheduled, retry_message = _schedule_retry_if_configured(
                client,
                task_id=task_id,
                task_ctx=task_ctx,
                output=output,
                failure_class=failure_class,
                attempt=attempt,
                duration_seconds=duration_sec,
            )
            if retry_scheduled:
                status = "pending"
                output = f"{output}\n\n{retry_message}"
                _sync_run_state(
                    client,
                    task_id=task_id,
                    run_id=run_id,
                    worker_id=worker_id,
                    patch={
                        "status": "failed",
                        "failure_class": failure_class,
                        "next_action": "retry_scheduled",
                        "completed_at": _utc_now_iso(),
                    },
                    lease_seconds=RUN_LEASE_SECONDS,
                    require_owner=True,
                )
            else:
                _sync_run_state(
                    client,
                    task_id=task_id,
                    run_id=run_id,
                    worker_id=worker_id,
                    patch={
                        "status": status,
                        "next_action": "needs_attention",
                        "completed_at": _utc_now_iso(),
                    },
                    lease_seconds=RUN_LEASE_SECONDS,
                    require_owner=True,
                )
        else:
            _sync_run_state(
                client,
                task_id=task_id,
                run_id=run_id,
                worker_id=worker_id,
                patch={
                    "status": status,
                    "next_action": "done" if status == "completed" else "needs_attention",
                    "completed_at": _utc_now_iso(),
                },
                lease_seconds=RUN_LEASE_SECONDS,
                require_owner=True,
            )
        log.info("task=%s %s exit=%s duration=%.1fs output_len=%d out_file=%s", task_id, status, returncode, duration_sec, len(output), out_file)
        if verbose:
            print(f"  -> {status} (exit {returncode})")
        _runner_heartbeat(
            client,
            runner_id=worker_id,
            status="idle",
            active_task_id="",
            active_run_id="",
            metadata={"last_task_id": task_id, "last_status": status},
        )

        # Auto-commit progress (spec 030) when PIPELINE_AUTO_COMMIT=1
        if status == "completed" and task_type != "heal" and os.environ.get("PIPELINE_AUTO_COMMIT") == "1":
            _try_commit(task_id, task_type, log)

        if status == "failed" and ROLLBACK_ON_TASK_FAILURE:
            _maybe_trigger_runner_rollback(
                client,
                log,
                reason="task_failed",
                task_id=task_id,
                failure_class=failure_class,
            )

        return True
    except Exception as e:
        duration_sec = round(time.monotonic() - start_time, 1)  # start_time set before try
        tool_name = _tool_token(command)
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"\n# duration_seconds={duration_sec} exit=-1 status=failed error={e}\n")
        _post_runtime_event(
            client,
            tool_name=tool_name,
            status_code=500,
            runtime_ms=duration_sec * 1000.0,
            task_id=task_id,
            task_type=task_type,
            model=model,
            returncode=-1,
            output_len=len(str(e)),
            worker_id=worker_id,
            executor=executor,
            is_openai_codex=is_openai_codex,
        )
        _post_tool_failure_friction(
            client,
            tool_name=tool_name,
            task_id=task_id,
            task_type=task_type,
            model=model,
            duration_seconds=duration_sec,
            returncode=-1,
            command=command,
        )
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": str(e)},
        )
        _sync_run_state(
            client,
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch={
                "status": "failed",
                "failure_class": "runner_exception",
                "error": str(e)[:1200],
                "next_action": "needs_attention",
                "completed_at": _utc_now_iso(),
            },
            lease_seconds=RUN_LEASE_SECONDS,
            require_owner=False,
        )
        _runner_heartbeat(
            client,
            runner_id=worker_id,
            status="degraded",
            active_task_id="",
            active_run_id="",
            last_error=str(e),
            metadata={"last_task_id": task_id, "task_type": task_type},
        )
        log.exception("task=%s error: %s", task_id, e)
        return True


def _task_status_count(client: httpx.Client, log: logging.Logger, status: str) -> int | None:
    response = _http_with_retry(
        client,
        "GET",
        f"{BASE}/api/agent/tasks",
        log,
        params={"status": status, "limit": 1},
    )
    if response is None or response.status_code != 200:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    total_raw = payload.get("total")
    if isinstance(total_raw, bool):
        return None
    try:
        return int(total_raw or 0)
    except (TypeError, ValueError):
        return None


def _has_open_tasks(client: httpx.Client, log: logging.Logger) -> bool:
    for status in ("pending", "running", "needs_decision"):
        total = _task_status_count(client, log, status)
        if total is None:
            # Fail safe: avoid creating duplicate tasks when API state is uncertain.
            return True
        if total > 0:
            return True
    return False


def _extract_idle_generated_count(payload: object) -> int:
    if not isinstance(payload, dict):
        return 0

    created_raw = payload.get("created_count")
    if not isinstance(created_raw, bool):
        try:
            created_count = int(created_raw or 0)
            if created_count > 0:
                return created_count
        except (TypeError, ValueError):
            pass

    created_task = payload.get("created_task")
    if isinstance(created_task, dict):
        task_id = str(created_task.get("id") or "").strip()
        if task_id:
            return 1

    created_tasks = payload.get("created_tasks")
    if isinstance(created_tasks, list):
        count = 0
        for row in created_tasks:
            if not isinstance(row, dict):
                continue
            task_id = str(row.get("task_id") or row.get("id") or "").strip()
            if task_id:
                count += 1
        return count

    return 0


def _request_idle_task_generation(
    client: httpx.Client,
    log: logging.Logger,
    *,
    endpoint: str,
    params: dict[str, object],
) -> int:
    response = _http_with_retry(client, "POST", f"{BASE}{endpoint}", log, params=params)
    if response is None or response.status_code != 200:
        return 0
    try:
        payload = response.json()
    except Exception:
        return 0
    return _extract_idle_generated_count(payload)


def _auto_generate_tasks_when_idle(client: httpx.Client, log: logging.Logger) -> int:
    global _last_idle_task_generation_ts
    if not AUTO_GENERATE_IDLE_TASKS:
        return 0

    now = time.monotonic()
    if AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS > 0:
        elapsed = now - _last_idle_task_generation_ts
        if elapsed < AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS:
            return 0

    if _has_open_tasks(client, log):
        return 0

    _last_idle_task_generation_ts = now
    created_count = _request_idle_task_generation(
        client,
        log,
        endpoint="/api/inventory/specs/sync-implementation-tasks",
        params={
            "create_task": True,
            "limit": AUTO_GENERATE_IDLE_TASK_LIMIT,
        },
    )
    if created_count > 0:
        log.info(
            "Idle queue detected: created %d task(s) from spec implementation gaps",
            created_count,
        )
        return created_count

    fallback_created = _request_idle_task_generation(
        client,
        log,
        endpoint="/api/inventory/flow/next-unblock-task",
        params={"create_task": True},
    )
    if fallback_created > 0:
        log.info(
            "Idle queue detected: created %d task(s) from unblock flow fallback",
            fallback_created,
        )
        return fallback_created

    return 0


def poll_and_run(
    client: httpx.Client,
    once: bool = False,
    interval: int = 10,
    workers: int = 1,
    log: logging.Logger = None,
    verbose: bool = False,
) -> None:
    """Poll for pending tasks and run up to workers in parallel (Cursor supports multiple concurrent agent invocations)."""
    log = log or logging.getLogger("agent_runner")
    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    while True:
        _runner_heartbeat(
            client,
            runner_id=worker_id,
            status="idle",
            active_task_id="",
            active_run_id="",
            metadata={"mode": "polling"},
        )
        r = _http_with_retry(
            client,
            "GET",
            f"{BASE}/api/agent/tasks",
            log,
            params={"status": "pending", "limit": fetch_limit},
        )
        if r is None:
            if once:
                break
            time.sleep(interval)
            continue
        if r.status_code != 200:
            log.warning("GET tasks failed: %s", r.status_code)
            if once:
                break
            time.sleep(interval)
            continue

        data = r.json()
        tasks = data.get("tasks") or []
        if not tasks:
            created_count = _auto_generate_tasks_when_idle(client, log)
            if created_count > 0:
                if verbose:
                    print(f"Auto-generated {created_count} task(s) while idle")
                continue
            if once:
                print("No pending tasks")
                break
            time.sleep(interval)
            continue

        # Fetch full task (including command) for each
        to_run: list[tuple[str, str, str, str, dict[str, Any], str]] = []
        for task in tasks:
            task_id = task["id"]
            r2 = _http_with_retry(client, "GET", f"{BASE}/api/agent/tasks/{task_id}", log)
            if r2 is None or r2.status_code != 200:
                log.warning("GET task %s failed: %s", task_id, r2.status_code if r2 else "None")
                continue
            full = r2.json()
            command = full.get("command")
            if not command:
                client.patch(
                    f"{BASE}/api/agent/tasks/{task_id}",
                    json={"status": "failed", "output": "No command"},
                )
                continue
            task_type = str(full.get("task_type", "impl"))
            model = str(full.get("model", "unknown"))
            context = _safe_get_task_context(full)
            retry_not_before = _parse_iso_utc(context.get("retry_not_before"))
            if retry_not_before is not None and retry_not_before > datetime.now(timezone.utc):
                continue
            direction = str(full.get("direction", "") or "")
            to_run.append((task_id, command, task_type, model, context, direction))

        if not to_run:
            if once:
                break
            time.sleep(interval)
            continue

        # PR-flow tasks should stay serial to avoid shared worktree race conditions.
        pr_tasks: list[tuple[str, str, str, str, dict[str, Any], str]] = []
        direct_tasks: list[tuple[str, str, str, str, dict[str, Any], str]] = []
        for item in to_run:
            _, _, task_type, _, ctx, _ = item
            if _should_run_pr_flow({"task_type": task_type, "context": ctx}):
                pr_tasks.append(item)
            else:
                direct_tasks.append(item)

        if pr_tasks:
            for tid, cmd, tt, m, ctx, direction in pr_tasks:
                run_one_task(
                    client,
                    tid,
                    cmd,
                    log=log,
                    verbose=verbose,
                    task_type=tt,
                    model=m,
                    task_context=ctx,
                    task_direction=direction,
                )

        if not direct_tasks:
            if once:
                break
            time.sleep(interval)
            continue

        if workers == 1:
            tid, cmd, tt, m, ctx, direction = direct_tasks[0]
            run_one_task(
                client,
                tid,
                cmd,
                log=log,
                verbose=verbose,
                task_type=tt,
                model=m,
                task_context=ctx,
                task_direction=direction,
            )
        else:
            with ThreadPoolExecutor(max_workers=max(1, len(direct_tasks))) as ex:
                futures = {
                    ex.submit(
                        run_one_task,
                        client,
                        tid,
                        cmd,
                        log,
                        verbose,
                        tt,
                        m,
                        ctx,
                        direction,
                    ): (tid, cmd)
                    for tid, cmd, tt, m, ctx, direction in direct_tasks
                }
                for future in as_completed(futures):
                    tid, _, has_measured_value = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        log.exception("task=%s worker error: %s", tid, e)
                    _record_scheduler_execution(has_measured_value)
            _maybe_trigger_runner_self_update(client, log)

        if once:
            break


def _check_api(client: httpx.Client) -> bool:
    """Verify API is reachable. Returns True if OK."""
    try:
        r = client.get(f"{BASE}/api/health")
        return r.status_code == 200
    except Exception:
        return False


def _http_with_retry(client: httpx.Client, method: str, url: str, log: logging.Logger, **kwargs) -> Optional[httpx.Response]:
    """Make HTTP request with retries for transient connection errors. Returns None on final failure."""
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method.upper() == "GET":
                return client.get(url, timeout=HTTP_TIMEOUT, **kwargs)
            if method.upper() == "PATCH":
                return client.patch(url, timeout=HTTP_TIMEOUT, **kwargs)
            if method.upper() == "POST":
                return client.post(url, timeout=HTTP_TIMEOUT, **kwargs)
            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                log.warning("API %s %s failed (attempt %d/%d): %s — retrying in %ds", method, url, attempt, MAX_RETRIES, e, RETRY_BACKOFF)
                time.sleep(RETRY_BACKOFF)
    log.error("API %s %s failed after %d retries: %s", method, url, MAX_RETRIES, last_exc)
    return None


def main():
    global REPO_PATH
    ap = argparse.ArgumentParser(description="Agent runner: poll and execute pending tasks")
    ap.add_argument("--interval", type=int, default=10, help="Poll interval (seconds)")
    ap.add_argument("--once", action="store_true", help="Run one task and exit")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print progress to stdout")
    ap.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help="Max parallel tasks (default 1). With Cursor executor, use 2+ to run multiple tasks concurrently.",
    )
    ap.add_argument(
        "--repo-path",
        default=os.environ.get("AGENT_WORKTREE_PATH", REPO_PATH),
        help="Path to the local git checkout used by PR workflow and command execution.",
    )
    args = ap.parse_args()

    workers = max(1, args.workers)
    REPO_PATH = os.path.abspath(args.repo_path)
    log = _setup_logging(verbose=args.verbose)
    log.info("Agent runner started API=%s interval=%s timeout=%ds workers=%d", BASE, args.interval, TASK_TIMEOUT, workers)

    with httpx.Client(timeout=float(HTTP_TIMEOUT)) as client:
        if not _check_api(client):
            msg = f"API not reachable at {BASE}/api/health — start the API first"
            log.error(msg)
            print(msg)
            if ROLLBACK_ON_START_FAILURE:
                _maybe_trigger_runner_rollback(client, log, reason="startup_api_unreachable")
            sys.exit(1)
        if args.verbose:
            print(f"Agent runner | API: {BASE} | interval: {args.interval}s | workers: {workers}")
            print(f"  Log: {LOG_FILE}")
            print("  Polling for pending tasks...\n")

        try:
            poll_and_run(
                client, once=args.once, interval=args.interval, workers=workers, log=log, verbose=args.verbose
            )
        except Exception:
            if ROLLBACK_ON_START_FAILURE:
                _maybe_trigger_runner_rollback(client, log, reason="startup_runner_crash")
            raise


if __name__ == "__main__":
    main()
