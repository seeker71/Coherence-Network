#!/usr/bin/env python3
"""Agent runner: polls pending tasks, runs commands, PATCHes status.

Usage:
  python scripts/agent_runner.py [--interval 10] [--once] [--verbose] [--workers N]

Requires API running. With Cursor executor, --workers N runs up to N tasks in parallel.
When task reaches needs_decision, runner stops for that task; user replies via /reply.

Debug: Logs to api/logs/agent_runner.log; full output in api/logs/task_{id}.log
"""

import argparse
import logging
import math
import os
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
from urllib.parse import quote

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
DEFAULT_GITHUB_REPO = os.environ.get("AGENT_GITHUB_REPO", "seeker71/Coherence-Network")
DEFAULT_PR_BASE_BRANCH = os.environ.get("AGENT_PR_BASE_BRANCH", "main")
DEFAULT_REPO_GIT_URL = f"https://github.com/{DEFAULT_GITHUB_REPO}.git"
REPO_GIT_URL = str(os.environ.get("AGENT_REPO_GIT_URL", DEFAULT_REPO_GIT_URL)).strip() or DEFAULT_REPO_GIT_URL
DEFAULT_REPO_FALLBACK_PATH = os.path.join("/tmp", DEFAULT_GITHUB_REPO.split("/")[-1] or "Coherence-Network")
REPO_FALLBACK_PATH = os.path.abspath(
    str(os.environ.get("AGENT_REPO_FALLBACK_PATH", DEFAULT_REPO_FALLBACK_PATH)).strip()
    or DEFAULT_REPO_FALLBACK_PATH
)
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
try:
    PENDING_TASK_FETCH_LIMIT = int(os.environ.get("AGENT_PENDING_TASK_FETCH_LIMIT", "20"))
except ValueError:
    PENDING_TASK_FETCH_LIMIT = 20
PENDING_TASK_FETCH_LIMIT = max(1, PENDING_TASK_FETCH_LIMIT)
try:
    MEASURED_VALUE_TARGET_SHARE = float(os.environ.get("AGENT_MEASURED_VALUE_TARGET_SHARE", "0.5"))
except ValueError:
    MEASURED_VALUE_TARGET_SHARE = 0.5
MEASURED_VALUE_TARGET_SHARE = max(0.0, min(1.0, MEASURED_VALUE_TARGET_SHARE))
try:
    IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS = int(
        os.environ.get("AGENT_IDEA_MEASURED_CACHE_TTL_SECONDS", "300")
    )
except ValueError:
    IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS = 300
IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS = max(30, IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS)
SCHEDULER_STATS_LOCK = threading.Lock()
SCHEDULER_EXECUTED_TOTAL = 0
SCHEDULER_EXECUTED_MEASURED = 0
IDEA_MEASURED_VALUE_CACHE_LOCK = threading.Lock()
IDEA_MEASURED_VALUE_CACHE: dict[str, tuple[float, bool]] = {}
SELF_UPDATE_ENABLED = str(os.environ.get("AGENT_RUNNER_SELF_UPDATE_ENABLED", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "enabled",
    "y",
}
SELF_UPDATE_REPO = (
    str(os.environ.get("AGENT_RUNNER_SELF_UPDATE_REPO", DEFAULT_GITHUB_REPO)).strip() or DEFAULT_GITHUB_REPO
)
SELF_UPDATE_BRANCH = (
    str(os.environ.get("AGENT_RUNNER_SELF_UPDATE_BRANCH", DEFAULT_PR_BASE_BRANCH)).strip()
    or DEFAULT_PR_BASE_BRANCH
)
try:
    SELF_UPDATE_MIN_INTERVAL_SECONDS = int(
        os.environ.get("AGENT_RUNNER_SELF_UPDATE_MIN_INTERVAL_SECONDS", "60")
    )
except ValueError:
    SELF_UPDATE_MIN_INTERVAL_SECONDS = 60
SELF_UPDATE_MIN_INTERVAL_SECONDS = max(5, SELF_UPDATE_MIN_INTERVAL_SECONDS)
SELF_UPDATE_LOCK = threading.Lock()
SELF_UPDATE_LAST_CHECK_AT = 0.0
SELF_UPDATE_LAST_TRIGGER_SHA = ""
ROLLBACK_ON_TASK_FAILURE = str(os.environ.get("AGENT_RUNNER_ROLLBACK_ON_TASK_FAILURE", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "enabled",
    "y",
}
ROLLBACK_ON_START_FAILURE = str(os.environ.get("AGENT_RUNNER_ROLLBACK_ON_START_FAILURE", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "enabled",
    "y",
}
try:
    ROLLBACK_MIN_INTERVAL_SECONDS = int(os.environ.get("AGENT_RUNNER_ROLLBACK_MIN_INTERVAL_SECONDS", "180"))
except ValueError:
    ROLLBACK_MIN_INTERVAL_SECONDS = 180
ROLLBACK_MIN_INTERVAL_SECONDS = max(10, ROLLBACK_MIN_INTERVAL_SECONDS)
ROLLBACK_LOCK = threading.Lock()
ROLLBACK_LAST_AT = 0.0
AGENT_MANIFESTS_DIR = os.path.abspath(
    os.environ.get("AGENT_MANIFESTS_DIR", os.path.join(LOG_DIR, "agent_manifests"))
)
AGENT_WEB_BASE_URL = str(os.environ.get("AGENT_WEB_BASE_URL", "")).strip().rstrip("/")
try:
    AGENT_MANIFEST_MAX_BLOCKS = int(os.environ.get("AGENT_MANIFEST_MAX_BLOCKS", "80"))
except ValueError:
    AGENT_MANIFEST_MAX_BLOCKS = 80
AGENT_MANIFEST_MAX_BLOCKS = max(1, AGENT_MANIFEST_MAX_BLOCKS)
try:
    AGENT_MANIFEST_CONTEXT_BLOCKS = int(os.environ.get("AGENT_MANIFEST_CONTEXT_BLOCKS", "20"))
except ValueError:
    AGENT_MANIFEST_CONTEXT_BLOCKS = 20
AGENT_MANIFEST_CONTEXT_BLOCKS = max(1, AGENT_MANIFEST_CONTEXT_BLOCKS)
AGENT_MANIFEST_ENABLED = str(os.environ.get("AGENT_MANIFEST_ENABLED", "1")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "enabled",
    "y",
}
AGENT_MANIFEST_WRITE_LOCK = threading.Lock()
DIFF_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
try:
    DEFAULT_OBSERVATION_WINDOW_SEC = int(os.environ.get("AGENT_OBSERVATION_WINDOW_SEC", "900"))
except ValueError:
    DEFAULT_OBSERVATION_WINDOW_SEC = 900
DEFAULT_OBSERVATION_WINDOW_SEC = max(30, min(DEFAULT_OBSERVATION_WINDOW_SEC, 7 * 24 * 60 * 60))
try:
    HOLD_PATTERN_SCORE_THRESHOLD_DEFAULT = float(
        os.environ.get("AGENT_HOLD_PATTERN_SCORE_THRESHOLD", "0.8")
    )
except ValueError:
    HOLD_PATTERN_SCORE_THRESHOLD_DEFAULT = 0.8
HOLD_PATTERN_SCORE_THRESHOLD_DEFAULT = max(0.0, HOLD_PATTERN_SCORE_THRESHOLD_DEFAULT)
try:
    HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS = int(
        os.environ.get("AGENT_HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS", "120")
    )
except ValueError:
    HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS = 120
HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS = max(10, min(HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS, 24 * 60 * 60))
HOLD_PATTERN_DIAGNOSTIC_COMMAND = str(
    os.environ.get(
        "AGENT_HOLD_PATTERN_DIAGNOSTIC_COMMAND",
        "git status --porcelain --branch && git log --oneline -n 5",
    )
).strip()
try:
    MIN_RETRY_DELAY_SECONDS = int(os.environ.get("AGENT_MIN_RETRY_DELAY_SECONDS", "15"))
except ValueError:
    MIN_RETRY_DELAY_SECONDS = 15
MIN_RETRY_DELAY_SECONDS = max(1, min(MIN_RETRY_DELAY_SECONDS, 3600))
try:
    DIAGNOSTIC_COOLDOWN_SECONDS = int(os.environ.get("AGENT_DIAGNOSTIC_COOLDOWN_SECONDS", "30"))
except ValueError:
    DIAGNOSTIC_COOLDOWN_SECONDS = 30
DIAGNOSTIC_COOLDOWN_SECONDS = max(0, min(DIAGNOSTIC_COOLDOWN_SECONDS, 3600))
try:
    MAX_INTERVENTIONS_PER_WINDOW = int(os.environ.get("AGENT_MAX_INTERVENTIONS_PER_WINDOW", "5"))
except ValueError:
    MAX_INTERVENTIONS_PER_WINDOW = 5
MAX_INTERVENTIONS_PER_WINDOW = max(1, min(MAX_INTERVENTIONS_PER_WINDOW, 100))
try:
    INTERVENTION_WINDOW_SECONDS = int(os.environ.get("AGENT_INTERVENTION_WINDOW_SECONDS", "900"))
except ValueError:
    INTERVENTION_WINDOW_SECONDS = 900
INTERVENTION_WINDOW_SECONDS = max(30, min(INTERVENTION_WINDOW_SECONDS, 24 * 60 * 60))
try:
    PAID_CALL_COST_UNITS = float(os.environ.get("AGENT_PAID_CALL_COST_UNITS", "1.0"))
except ValueError:
    PAID_CALL_COST_UNITS = 1.0
PAID_CALL_COST_UNITS = max(0.0, PAID_CALL_COST_UNITS)
AUTO_GENERATE_IDLE_TASKS = str(
    os.environ.get("AGENT_AUTO_GENERATE_IDLE_TASKS", "1")
).strip().lower() in {"1", "true", "yes", "on", "enabled", "y"}
try:
    AUTO_GENERATE_IDLE_TASK_LIMIT = int(os.environ.get("AGENT_AUTO_GENERATE_IDLE_TASK_LIMIT", "50"))
except ValueError:
    AUTO_GENERATE_IDLE_TASK_LIMIT = 50
AUTO_GENERATE_IDLE_TASK_LIMIT = max(1, min(AUTO_GENERATE_IDLE_TASK_LIMIT, 500))
try:
    AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS = int(
        os.environ.get("AGENT_AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS", "30")
    )
except ValueError:
    AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS = 30
AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS = max(0, AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS)
_last_idle_task_generation_ts = 0.0

TaskRunItem = tuple[str, str, str, str, dict[str, Any], str, bool]
DEFAULT_CODEX_MODEL_ALIAS_MAP = (
    "openrouter/free:gpt-5-codex,"
    "gpt-5.3-codex-spark:gpt-5.3-codex,"
    "gtp-5.3-codex-spark:gpt-5.3-codex,"
    "gtp-5.3-codex:gpt-5.3-codex"
)
DEFAULT_CODEX_MODEL_NOT_FOUND_FALLBACK_MAP = (
    "gpt-5.3-codex:gpt-5-codex,"
    "gpt-5.3-codex-spark:gpt-5-codex,"
    "gtp-5.3-codex:gpt-5-codex,"
    "gtp-5.3-codex-spark:gpt-5-codex"
)
CODEX_MODEL_ARG_RE = re.compile(r"(?P<prefix>--model\s+)(?P<model>[^\s]+)")
CODEX_AUTH_MODE_VALUES = {"api_key", "oauth", "auto"}


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


def _safe_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _context_first_float(context: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _safe_float(context.get(key))
        if value is not None:
            return value
    return None


def _estimated_roi_value(context: dict[str, Any]) -> float:
    value = _context_first_float(
        context,
        (
            "estimated_roi",
            "estimated_value",
            "potential_roi",
            "potential_value",
            "value_to_whole",
        ),
    )
    if value is None:
        value = _safe_float(context.get("awareness_estimated_roi_total"))
    return max(0.0, float(value or 0.0))


def _measured_roi_value(context: dict[str, Any]) -> float:
    value = _context_first_float(
        context,
        (
            "measured_roi",
            "actual_value",
            "measured_value",
            "measured_value_total",
            "measured_delta",
        ),
    )
    if value is None:
        value = _safe_float(context.get("awareness_measured_roi_total"))
    return max(0.0, float(value or 0.0))


def _estimated_transition_cost(duration_seconds: float, *, paid_call: bool) -> float:
    wall_time_cost = max(0.0, float(duration_seconds)) * _time_cost_per_second()
    paid_call_cost = PAID_CALL_COST_UNITS if paid_call else 0.0
    return round(max(0.0, wall_time_cost + paid_call_cost), 6)


def _normalize_evidence_terms(raw: object) -> list[str]:
    values = raw if isinstance(raw, list) else ([raw] if raw is not None else [])
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned[:240])
    return out


def _normalize_task_target_contract(
    task_ctx: dict[str, Any],
    *,
    task_type: str,
    task_direction: str,
) -> dict[str, Any]:
    target_state = str(task_ctx.get("target_state") or "").strip()
    if not target_state:
        direction_hint = " ".join(str(task_direction or "").split())[:200]
        base = f"{task_type} task reaches intended target state"
        target_state = f"{base}: {direction_hint}" if direction_hint else base

    success_evidence = _normalize_evidence_terms(task_ctx.get("success_evidence"))
    abort_evidence = _normalize_evidence_terms(task_ctx.get("abort_evidence"))

    raw_window = task_ctx.get("observation_window_sec")
    try:
        observation_window_sec = int(raw_window) if raw_window is not None else DEFAULT_OBSERVATION_WINDOW_SEC
    except Exception:
        observation_window_sec = DEFAULT_OBSERVATION_WINDOW_SEC
    observation_window_sec = max(30, min(observation_window_sec, 7 * 24 * 60 * 60))

    return {
        "target_state": target_state[:600],
        "success_evidence": success_evidence,
        "abort_evidence": abort_evidence,
        "observation_window_sec": observation_window_sec,
    }


def _observe_target_contract(
    *,
    contract: dict[str, Any],
    output: str,
    duration_seconds: float,
    attempt_status: str,
) -> dict[str, Any]:
    haystack = (output or "").lower()
    success_terms = _normalize_evidence_terms(contract.get("success_evidence"))
    abort_terms = _normalize_evidence_terms(contract.get("abort_evidence"))
    success_hits = [term for term in success_terms if term.lower() in haystack]
    abort_hits = [term for term in abort_terms if term.lower() in haystack]
    observation_window_sec = max(30, _to_int(contract.get("observation_window_sec"), DEFAULT_OBSERVATION_WINDOW_SEC))
    exceeded = float(duration_seconds) > float(observation_window_sec)
    return {
        "target_state": str(contract.get("target_state") or ""),
        "success_evidence": success_terms,
        "success_evidence_hits": success_hits,
        "success_evidence_met": bool(success_terms) and bool(success_hits),
        "abort_evidence": abort_terms,
        "abort_evidence_hits": abort_hits,
        "abort_evidence_met": bool(abort_hits),
        "observation_window_sec": observation_window_sec,
        "observation_window_exceeded": exceeded,
        "attempt_status": attempt_status,
        "observed_at": _utc_now_iso(),
    }


def _evaluate_hold_pattern_policy(task_ctx: dict[str, Any], *, attempt: int) -> dict[str, Any]:
    score = _safe_float(task_ctx.get("hold_pattern_score"))
    threshold = _safe_float(task_ctx.get("hold_pattern_score_threshold"))
    if threshold is None:
        threshold = HOLD_PATTERN_SCORE_THRESHOLD_DEFAULT
    threshold = max(0.0, threshold)
    high_hold = score is not None and score >= threshold
    return {
        "triggered": bool(high_hold),
        "score": score,
        "threshold": threshold,
        "attempt": max(1, int(attempt)),
        "action_rate": "reduced" if high_hold else "normal",
        "request_steering": bool(high_hold),
        "suppress_blind_retry": bool(high_hold),
    }


def _hold_pattern_diagnostic_command(task_ctx: dict[str, Any]) -> str:
    for key in (
        "hold_pattern_diagnostic_command",
        "high_signal_diagnostic_command",
        "runner_high_signal_diagnostic_command",
    ):
        value = str(task_ctx.get(key) or "").strip()
        if value:
            return value
    return HOLD_PATTERN_DIAGNOSTIC_COMMAND


def _apply_hold_pattern_policy(
    client: httpx.Client,
    *,
    task_id: str,
    task_ctx: dict[str, Any],
    attempt: int,
    failure_class: str,
    output: str,
    repo_path: str,
    env: dict[str, str],
    run_id: str,
    worker_id: str,
) -> tuple[bool, str]:
    policy = _evaluate_hold_pattern_policy(task_ctx, attempt=attempt)
    if not _as_bool(policy.get("triggered")):
        return False, ""

    intervention_allowed, cadence_patch, cadence_limits, window_load = _allow_intervention_frequency(
        task_ctx,
        kind="steering",
        hold_pattern_inc=1,
    )
    diagnostic_command = _hold_pattern_diagnostic_command(task_ctx)
    diagnostic_timeout = max(
        5,
        min(
            DIAGNOSTIC_TIMEOUT_SECONDS,
            _to_int(task_ctx.get("hold_pattern_diagnostic_timeout_seconds"), DIAGNOSTIC_TIMEOUT_SECONDS),
        ),
    )
    diagnostic_request_id = f"hold-pattern-{task_id[:24]}-attempt-{attempt}"
    diagnostic_result: dict[str, Any] | None = None
    if intervention_allowed and diagnostic_command:
        diagnostic_result = _run_diagnostic_request(
            {
                "id": diagnostic_request_id,
                "command": diagnostic_command,
                "timeout_seconds": diagnostic_timeout,
            },
            cwd=repo_path,
            env=env,
        )

    retry_not_before = (
        datetime.now(timezone.utc) + timedelta(seconds=HOLD_PATTERN_REDUCED_ACTION_DELAY_SECONDS)
    ).isoformat()
    score = policy.get("score")
    threshold = policy.get("threshold")
    if intervention_allowed:
        steering_message = (
            "[policy] High hold_pattern_score detected "
            f"(score={score if score is not None else 'n/a'}, threshold={threshold}); "
            "reduced action rate, ran one high-signal diagnostic, requested steering, and suppressed blind retries."
        )
    else:
        steering_message = (
            "[policy] High hold_pattern_score detected; steering requested. "
            f"Additional intervention suppressed by cadence limit "
            f"({window_load}/{cadence_limits.get('max_interventions_per_window')} in "
            f"{cadence_limits.get('intervention_window_sec')}s)."
        )
    context_patch: dict[str, Any] = dict(cadence_patch)
    context_patch.update(
        {
        "runner_state": "steering_required",
        "runner_action_rate": "reduced",
        "retry_not_before": retry_not_before,
        "next_action": "steering_required",
        "steering_requested": True,
        "hold_pattern_policy": {
            "triggered": True,
            "score": score,
            "threshold": threshold,
            "attempt": policy.get("attempt"),
            "action_rate": "reduced",
            "blind_retry_suppressed": True,
            "diagnostic_request_id": diagnostic_request_id,
            "diagnostic_command": _scrub_command(diagnostic_command),
            "intervention_allowed": intervention_allowed,
            "intervention_window_load": window_load,
            "intervention_window_limit": cadence_limits.get("max_interventions_per_window"),
            "triggered_at": _utc_now_iso(),
            "failure_class": failure_class,
        },
        "cadence_limits": cadence_limits,
    }
    )
    if not intervention_allowed:
        context_patch["runner_intervention_blocked"] = True
        context_patch["runner_intervention_block_reason"] = "max_interventions_per_window"
    if diagnostic_result is not None:
        context_patch["diagnostic_last_completed_id"] = diagnostic_request_id
        context_patch["diagnostic_last_result"] = diagnostic_result

    final_output = f"{output[-3200:]}\n\n{steering_message}"[-4000:]
    try:
        client.patch(
            f"{BASE}/api/agent/tasks/{task_id}",
            json={
                "status": "needs_decision",
                "current_step": "awaiting steering",
                "output": final_output,
                "context": context_patch,
            },
        )
    except Exception:
        return False, ""

    _sync_run_state(
        client,
        task_id=task_id,
        run_id=run_id,
        worker_id=worker_id,
        patch={
            "status": "needs_decision",
            "failure_class": failure_class,
            "next_action": "steering_required",
            "completed_at": _utc_now_iso(),
        },
        lease_seconds=RUN_LEASE_SECONDS,
        require_owner=True,
    )
    return True, steering_message


def _task_idea_id(context: dict[str, Any]) -> str:
    idea_id = str(context.get("idea_id") or "").strip()
    if idea_id:
        return idea_id
    idea_ids = context.get("idea_ids")
    if isinstance(idea_ids, list):
        for raw in idea_ids:
            candidate = str(raw or "").strip()
            if candidate:
                return candidate
    return ""


def _task_has_inline_measured_value(context: dict[str, Any]) -> bool:
    for key in ("measured_value_total", "measured_value", "actual_value", "measured_delta"):
        value = _safe_float(context.get(key))
        if value is not None and value > 0:
            return True
    return False


def _idea_has_measured_value(client: httpx.Client, *, idea_id: str, log: logging.Logger) -> bool:
    now = time.monotonic()
    with IDEA_MEASURED_VALUE_CACHE_LOCK:
        cached = IDEA_MEASURED_VALUE_CACHE.get(idea_id)
        if cached and cached[0] > now:
            return cached[1]

    has_measured = False
    ttl_seconds = IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS
    response = _http_with_retry(
        client,
        "GET",
        f"{BASE}/api/ideas/{quote(idea_id, safe='')}",
        log,
    )
    if response is not None and response.status_code == 200:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            actual_value = _safe_float(payload.get("actual_value"))
            measured_total = _safe_float(payload.get("measured_value_total"))
            has_measured = (actual_value is not None and actual_value > 0) or (
                measured_total is not None and measured_total > 0
            )
    else:
        ttl_seconds = min(60, IDEA_MEASURED_VALUE_CACHE_TTL_SECONDS)

    with IDEA_MEASURED_VALUE_CACHE_LOCK:
        IDEA_MEASURED_VALUE_CACHE[idea_id] = (now + ttl_seconds, has_measured)
    return has_measured


def _task_has_measured_value_signal(
    client: httpx.Client,
    *,
    context: dict[str, Any],
    log: logging.Logger,
) -> bool:
    if _task_has_inline_measured_value(context):
        return True
    idea_id = _task_idea_id(context)
    if not idea_id:
        return False
    return _idea_has_measured_value(client, idea_id=idea_id, log=log)


def _scheduler_stats_snapshot() -> tuple[int, int]:
    with SCHEDULER_STATS_LOCK:
        return SCHEDULER_EXECUTED_TOTAL, SCHEDULER_EXECUTED_MEASURED


def _record_scheduler_execution(has_measured_value: bool) -> None:
    global SCHEDULER_EXECUTED_TOTAL
    global SCHEDULER_EXECUTED_MEASURED
    with SCHEDULER_STATS_LOCK:
        SCHEDULER_EXECUTED_TOTAL += 1
        if has_measured_value:
            SCHEDULER_EXECUTED_MEASURED += 1


def _select_tasks_for_execution(
    candidates: list[TaskRunItem],
    *,
    max_tasks: int,
    log: logging.Logger,
) -> list[TaskRunItem]:
    if max_tasks <= 0 or not candidates:
        return []

    measured_pool = [item for item in candidates if item[6]]
    other_pool = [item for item in candidates if not item[6]]
    base_total, base_measured = _scheduler_stats_snapshot()

    selected: list[TaskRunItem] = []
    selected_measured = 0
    slots = min(max_tasks, len(candidates))
    for _ in range(slots):
        projected_total = base_total + len(selected) + 1
        required_measured = math.ceil(MEASURED_VALUE_TARGET_SHARE * projected_total)
        current_measured = base_measured + selected_measured
        must_pick_measured = current_measured < required_measured

        chosen: TaskRunItem | None = None
        if must_pick_measured and measured_pool:
            chosen = measured_pool.pop(0)
        elif other_pool:
            chosen = other_pool.pop(0)
        elif measured_pool:
            chosen = measured_pool.pop(0)

        if chosen is None:
            break
        selected.append(chosen)
        if chosen[6]:
            selected_measured += 1

    selected_count = len(selected)
    if selected_count > 0:
        selected_share = selected_measured / selected_count
        available_measured = len([item for item in candidates if item[6]])
        log.info(
            "scheduler selection measured=%s/%s (%.2f) available_measured=%s target=%.2f history=%s/%s",
            selected_measured,
            selected_count,
            selected_share,
            available_measured,
            MEASURED_VALUE_TARGET_SHARE,
            base_measured,
            base_total,
        )
    return selected


def _safe_get_task_context(task: object) -> dict[str, Any]:
    if isinstance(task, dict):
        context = task.get("context")
        if isinstance(context, dict):
            return context
    return {}


def _safe_agent_slug(value: str, default: str = "unknown-agent") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "-", (value or "").strip().lower())
    cleaned = cleaned.strip("-.")
    return cleaned or default


def _web_base_url() -> str:
    if AGENT_WEB_BASE_URL:
        return AGENT_WEB_BASE_URL
    base = BASE.rstrip("/")
    if base.endswith("/api"):
        return base[:-4]
    return base


def _task_source_references(context: dict[str, Any]) -> list[str]:
    refs: list[str] = []

    def _append_ref(raw: object) -> None:
        if not isinstance(raw, str):
            return
        text = raw.strip()
        if not text:
            return
        refs.append(text)

    for key in (
        "spec_ref",
        "spec_path",
        "doc_ref",
        "source_doc",
        "source_reference",
        "reference_doc",
    ):
        _append_ref(context.get(key))
    for key in ("doc_refs", "source_docs", "source_references", "reference_docs", "references"):
        values = context.get(key)
        if isinstance(values, list):
            for item in values:
                _append_ref(item)

    spec_id = str(context.get("spec_id") or "").strip()
    if spec_id:
        refs.append(f"/specs/{quote(spec_id, safe='')}")

    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        deduped.append(ref)
    return deduped


def _task_code_references(context: dict[str, Any]) -> list[dict[str, str]]:
    raw = context.get("code_references")
    if not isinstance(raw, list):
        return []

    references: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        url = ""
        license_name = ""
        note = ""
        if isinstance(item, str):
            url = item.strip()
        elif isinstance(item, dict):
            url = str(item.get("url") or item.get("source") or "").strip()
            license_name = str(item.get("license") or item.get("license_id") or "").strip()
            note = str(item.get("note") or item.get("repository") or item.get("match_reason") or "").strip()
        if not url:
            continue
        key = (url, license_name, note)
        if key in seen:
            continue
        seen.add(key)
        references.append({"url": url, "license": license_name, "note": note})
    return references


def _idea_links(idea_id: str) -> tuple[str, str]:
    if not idea_id:
        return "", ""
    encoded = quote(idea_id, safe="")
    web_base = _web_base_url().rstrip("/")
    api_base = BASE.rstrip("/")
    return f"{web_base}/ideas/{encoded}", f"{api_base}/api/ideas/{encoded}"


def _parse_diff_manifestation_blocks(
    diff_text: str,
    *,
    max_blocks: int,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not diff_text:
        return blocks

    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                current_file = ""
                continue
            if target.startswith("b/"):
                target = target[2:]
            current_file = target
            continue

        match = DIFF_HUNK_RE.match(line)
        if not match or not current_file:
            continue

        start = int(match.group(1))
        count_raw = match.group(2)
        count = int(count_raw) if count_raw is not None else 1
        count = max(1, count)
        end = start + count - 1
        read_range = f"{start}-{end}"
        blocks.append(
            {
                "file": current_file,
                "line": start,
                "file_line_ref": f"{current_file}:{start}",
                "read_range": read_range,
                "manifestation_range": f"L{start}-L{end}",
            }
        )
        if len(blocks) >= max_blocks:
            break

    return blocks


def _collect_manifestation_blocks(repo_path: str, *, max_blocks: int) -> list[dict[str, Any]]:
    git_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(git_dir):
        return []
    diff = _run_git("diff", "--unified=0", "--no-color", "--", cwd=repo_path, timeout=120)
    if diff.returncode != 0:
        return []
    return _parse_diff_manifestation_blocks(diff.stdout, max_blocks=max_blocks)


def _append_agent_manifest_entry(
    *,
    task_id: str,
    task_type: str,
    task_direction: str,
    task_ctx: dict[str, Any],
    repo_path: str,
    executor: str,
) -> dict[str, Any]:
    if not AGENT_MANIFEST_ENABLED:
        return {}
    try:
        blocks = _collect_manifestation_blocks(repo_path, max_blocks=AGENT_MANIFEST_MAX_BLOCKS)
        if not blocks:
            return {}

        agent_name = str(
            task_ctx.get("task_agent")
            or task_ctx.get("agent")
            or task_ctx.get("executor")
            or executor
            or task_type
            or "unknown-agent"
        ).strip()
        if not agent_name:
            agent_name = "unknown-agent"

        idea_id = _task_idea_id(task_ctx)
        idea_url, idea_api_url = _idea_links(idea_id)
        source_refs = _task_source_references(task_ctx)
        code_refs = _task_code_references(task_ctx)
        primary_source_ref = source_refs[0] if source_refs else ""
        primary_code_ref = code_refs[0]["url"] if code_refs else ""

        manifest_dir = os.path.join(AGENT_MANIFESTS_DIR, _safe_agent_slug(agent_name))
        manifest_path = os.path.join(manifest_dir, "AGENT.md")
        os.makedirs(manifest_dir, exist_ok=True)

        now_iso = _utc_now_iso()
        direction_preview = " ".join(str(task_direction or "").split())[:400]
        with AGENT_MANIFEST_WRITE_LOCK:
            exists = os.path.exists(manifest_path)
            with open(manifest_path, "a", encoding="utf-8") as handle:
                if not exists:
                    handle.write(f"# AGENT.md - {agent_name}\n\n")
                    handle.write("Append-only manifestation provenance written by `api/scripts/agent_runner.py`.\n\n")
                handle.write(f"## Task `{task_id}` ({now_iso})\n\n")
                handle.write(f"- Agent: `{agent_name}`\n")
                handle.write(f"- Task type: `{task_type}`\n")
                if direction_preview:
                    handle.write(f"- Decision prompt: `{direction_preview}`\n")
                if idea_id and idea_url:
                    handle.write(f"- Idea link: [{idea_id}]({idea_url})\n")
                if idea_id and idea_api_url:
                    handle.write(f"- Idea API: [{idea_api_url}]({idea_api_url})\n")
                if source_refs:
                    handle.write("- Source references:\n")
                    for ref in source_refs:
                        handle.write(f"  - [{ref}]({ref})\n")
                else:
                    handle.write("- Source references: none\n")
                if code_refs:
                    handle.write("- Code references:\n")
                    for ref in code_refs:
                        detail_parts: list[str] = []
                        if ref["license"]:
                            detail_parts.append(f"license `{ref['license']}`")
                        if ref["note"]:
                            detail_parts.append(ref["note"])
                        detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
                        handle.write(f"  - [{ref['url']}]({ref['url']}){detail}\n")
                else:
                    handle.write("- Code references: none\n")
                handle.write("- Manifestation blocks:\n")
                for block in blocks:
                    file_line_ref = str(block.get("file_line_ref") or "")
                    read_range = str(block.get("read_range") or "")
                    manifestation_range = str(block.get("manifestation_range") or "")
                    line = (
                        f"  - `{file_line_ref}` | read_range `{read_range}` | manifestation_range `{manifestation_range}`"
                    )
                    if idea_id and idea_url:
                        line += f" | idea [{idea_id}]({idea_url})"
                    if primary_source_ref:
                        line += f" | source [{primary_source_ref}]({primary_source_ref})"
                    if primary_code_ref:
                        line += f" | code_ref [{primary_code_ref}]({primary_code_ref})"
                    handle.write(line + "\n")
                handle.write("\n")

        context_blocks: list[dict[str, Any]] = []
        for block in blocks[:AGENT_MANIFEST_CONTEXT_BLOCKS]:
            payload = dict(block)
            if idea_id:
                payload["idea_id"] = idea_id
            if idea_url:
                payload["idea_url"] = idea_url
            if primary_source_ref:
                payload["source_ref"] = primary_source_ref
            context_blocks.append(payload)

        return {
            "agent_manifest": {
                "doc_path": manifest_path,
                "agent_name": agent_name,
                "updated_at": now_iso,
                "idea_id": idea_id or None,
                "idea_url": idea_url or None,
                "idea_api_url": idea_api_url or None,
                "source_refs": source_refs,
                "code_refs": code_refs,
                "manifestation_blocks": context_blocks,
                "manifestation_block_count": len(blocks),
            }
        }
    except Exception:
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


def _count_observer_context_snapshots(context: dict[str, Any]) -> int:
    raw = context.get("observer_context_snapshots")
    if not isinstance(raw, list):
        return 0
    count = 0
    for item in raw:
        if isinstance(item, dict):
            count += 1
    return count


def _awareness_quality_summary(
    *,
    events_total: int,
    interventions_total: int,
    blocks_total: int,
    snapshot_count: int,
    transition_total: int,
    successful_transition_total: int,
    hold_pattern_total: int,
    estimated_roi_total: float,
    measured_roi_total: float,
    transition_cost_total: float,
) -> dict[str, Any]:
    events_total = max(0, int(events_total))
    interventions_total = max(0, int(interventions_total))
    blocks_total = max(0, int(blocks_total))
    snapshot_count = max(0, int(snapshot_count))
    transition_total = max(0, int(transition_total))
    successful_transition_total = max(0, int(successful_transition_total))
    hold_pattern_total = max(0, int(hold_pattern_total))
    estimated_roi_total = max(0.0, float(estimated_roi_total))
    measured_roi_total = max(0.0, float(measured_roi_total))
    transition_cost_total = max(0.0, float(transition_cost_total))
    policy_discipline = max(0.0, 1.0 - (float(blocks_total) / float(max(1, events_total))))
    context_coverage = min(1.0, float(snapshot_count) / 5.0)
    state_transition_quality = (
        float(successful_transition_total) / float(max(1, transition_total))
        if transition_total > 0
        else 0.0
    )
    hold_pattern_rate = (
        float(hold_pattern_total) / float(max(1, transition_total))
        if transition_total > 0
        else 0.0
    )
    estimated_to_measured_roi_conversion = (
        float(measured_roi_total) / float(estimated_roi_total)
        if estimated_roi_total > 0
        else None
    )
    cost_per_successful_transition = (
        float(transition_cost_total) / float(max(1, successful_transition_total))
    )
    roi_component = (
        min(1.0, max(0.0, float(estimated_to_measured_roi_conversion)))
        if estimated_to_measured_roi_conversion is not None
        else 0.0
    )
    hold_component = max(0.0, 1.0 - min(1.0, hold_pattern_rate))
    cost_component = 1.0 / (1.0 + max(0.0, cost_per_successful_transition))
    score = round(
        max(
            0.0,
            min(
                1.0,
                (
                    (0.25 * policy_discipline)
                    + (0.15 * context_coverage)
                    + (0.20 * state_transition_quality)
                    + (0.15 * hold_component)
                    + (0.15 * roi_component)
                    + (0.10 * cost_component)
                ),
            ),
        ),
        4,
    )
    return {
        "score": score,
        "policy_discipline": round(policy_discipline, 4),
        "context_coverage": round(context_coverage, 4),
        "state_transition_quality": round(state_transition_quality, 4),
        "hold_pattern_rate": round(hold_pattern_rate, 4),
        "estimated_to_measured_roi_conversion": (
            round(float(estimated_to_measured_roi_conversion), 4)
            if estimated_to_measured_roi_conversion is not None
            else None
        ),
        "cost_per_successful_transition": round(cost_per_successful_transition, 6),
        "events_total": events_total,
        "interventions_total": interventions_total,
        "blocks_total": blocks_total,
        "snapshot_count": snapshot_count,
        "transition_total": transition_total,
        "successful_transition_total": successful_transition_total,
        "hold_pattern_total": hold_pattern_total,
        "estimated_roi_total": round(estimated_roi_total, 6),
        "measured_roi_total": round(measured_roi_total, 6),
        "transition_cost_total": round(transition_cost_total, 6),
        "updated_at": _utc_now_iso(),
    }


def _awareness_patch_from_context(
    context: dict[str, Any],
    *,
    event_inc: int = 0,
    intervention_inc: int = 0,
    block_inc: int = 0,
    transition_inc: int = 0,
    successful_transition_inc: int = 0,
    hold_pattern_inc: int = 0,
    transition_cost_inc: float = 0.0,
    snapshot_count_override: int | None = None,
) -> dict[str, Any]:
    events_total = max(0, _to_int(context.get("awareness_events_total"), 0)) + max(0, int(event_inc))
    interventions_total = max(0, _to_int(context.get("awareness_interventions_total"), 0)) + max(
        0,
        int(intervention_inc),
    )
    blocks_total = max(0, _to_int(context.get("awareness_blocks_total"), 0)) + max(0, int(block_inc))
    transition_total = max(0, _to_int(context.get("awareness_transition_total"), 0)) + max(0, int(transition_inc))
    successful_transition_total = max(0, _to_int(context.get("awareness_successful_transition_total"), 0)) + max(
        0,
        int(successful_transition_inc),
    )
    hold_pattern_total = max(0, _to_int(context.get("awareness_hold_pattern_total"), 0)) + max(0, int(hold_pattern_inc))
    transition_cost_total = max(0.0, float(_safe_float(context.get("awareness_transition_cost_total")) or 0.0)) + max(
        0.0,
        float(transition_cost_inc),
    )
    transition_cost_total = round(transition_cost_total, 6)
    snapshot_count = (
        max(0, int(snapshot_count_override))
        if snapshot_count_override is not None
        else _count_observer_context_snapshots(context)
    )
    estimated_roi_total = _estimated_roi_value(context)
    measured_roi_total = _measured_roi_value(context)
    quality = _awareness_quality_summary(
        events_total=events_total,
        interventions_total=interventions_total,
        blocks_total=blocks_total,
        snapshot_count=snapshot_count,
        transition_total=transition_total,
        successful_transition_total=successful_transition_total,
        hold_pattern_total=hold_pattern_total,
        estimated_roi_total=estimated_roi_total,
        measured_roi_total=measured_roi_total,
        transition_cost_total=transition_cost_total,
    )
    return {
        "awareness_events_total": events_total,
        "awareness_interventions_total": interventions_total,
        "awareness_blocks_total": blocks_total,
        "awareness_transition_total": transition_total,
        "awareness_successful_transition_total": successful_transition_total,
        "awareness_hold_pattern_total": hold_pattern_total,
        "awareness_transition_cost_total": transition_cost_total,
        "awareness_estimated_roi_total": round(estimated_roi_total, 6),
        "awareness_measured_roi_total": round(measured_roi_total, 6),
        "awareness_state_transition_quality": quality.get("state_transition_quality"),
        "awareness_hold_pattern_rate": quality.get("hold_pattern_rate"),
        "awareness_estimated_to_measured_roi_conversion": quality.get("estimated_to_measured_roi_conversion"),
        "awareness_cost_per_successful_transition": quality.get("cost_per_successful_transition"),
        "awareness_quality": quality,
    }


def _cadence_limits(context: dict[str, Any]) -> dict[str, int]:
    min_retry_delay_seconds = _to_int(
        context.get("runner_min_retry_delay_seconds"),
        _to_int(context.get("min_retry_delay_seconds"), MIN_RETRY_DELAY_SECONDS),
    )
    min_retry_delay_seconds = max(1, min(min_retry_delay_seconds, 3600))
    diagnostic_cooldown_seconds = _to_int(
        context.get("diagnostic_cooldown_seconds"),
        DIAGNOSTIC_COOLDOWN_SECONDS,
    )
    diagnostic_cooldown_seconds = max(0, min(diagnostic_cooldown_seconds, 3600))
    max_interventions_per_window = _to_int(
        context.get("max_interventions_per_window"),
        MAX_INTERVENTIONS_PER_WINDOW,
    )
    max_interventions_per_window = max(1, min(max_interventions_per_window, 100))
    intervention_window_sec = _to_int(
        context.get("intervention_window_sec"),
        INTERVENTION_WINDOW_SECONDS,
    )
    intervention_window_sec = max(30, min(intervention_window_sec, 24 * 60 * 60))
    return {
        "min_retry_delay_seconds": min_retry_delay_seconds,
        "diagnostic_cooldown_seconds": diagnostic_cooldown_seconds,
        "max_interventions_per_window": max_interventions_per_window,
        "intervention_window_sec": intervention_window_sec,
    }


def _recent_intervention_events(
    context: dict[str, Any],
    *,
    now: datetime,
    window_seconds: int,
) -> list[dict[str, Any]]:
    raw = context.get("runner_intervention_events")
    if not isinstance(raw, list):
        return []
    cutoff = now - timedelta(seconds=max(1, int(window_seconds)))
    events: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ts = _parse_iso_utc(item.get("at"))
        if ts is None or ts < cutoff:
            continue
        kind = str(item.get("kind") or "").strip()[:80]
        if not kind:
            continue
        events.append({"kind": kind, "at": ts.isoformat()})
    return events[-200:]


def _allow_intervention_frequency(
    context: dict[str, Any],
    *,
    kind: str,
    hold_pattern_inc: int = 0,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any], dict[str, int], int]:
    now_utc = now or datetime.now(timezone.utc)
    limits = _cadence_limits(context)
    recent = _recent_intervention_events(
        context,
        now=now_utc,
        window_seconds=limits["intervention_window_sec"],
    )
    window_load = len(recent)
    allowed = window_load < limits["max_interventions_per_window"]
    awareness_patch = _awareness_patch_from_context(
        context,
        event_inc=1,
        intervention_inc=1 if allowed else 0,
        block_inc=0 if allowed else 1,
        hold_pattern_inc=hold_pattern_inc,
    )
    patch = dict(awareness_patch)
    patch["cadence_limits"] = limits
    event = {"kind": str(kind or "unknown")[:80], "at": now_utc.isoformat()}
    if allowed:
        recent.append(event)
        patch["runner_intervention_events"] = recent[-100:]
        patch["cadence_last_intervention"] = {
            "kind": event["kind"],
            "at": event["at"],
            "window_load": window_load + 1,
            "window_limit": limits["max_interventions_per_window"],
            "window_seconds": limits["intervention_window_sec"],
        }
    else:
        patch["runner_intervention_events"] = recent[-100:]
        patch["cadence_last_block"] = {
            "kind": event["kind"],
            "at": event["at"],
            "reason": "max_interventions_per_window",
            "window_load": window_load,
            "window_limit": limits["max_interventions_per_window"],
            "window_seconds": limits["intervention_window_sec"],
        }
    return allowed, patch, limits, window_load


def _observer_context_compact_view(context: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "active_run_id",
        "active_worker_id",
        "active_branch",
        "last_attempt",
        "runner_state",
        "runner_retry_count",
        "runner_retry_remaining",
        "retry_not_before",
        "next_action",
        "last_failure_class",
        "resume_branch",
        "resume_checkpoint_sha",
        "resume_ready",
        "target_state",
        "observation_window_sec",
        "hold_pattern_score",
        "hold_pattern_score_threshold",
        "steering_requested",
        "abort_requested",
        "abort_reason",
    )
    compact: dict[str, Any] = {}
    for key in keys:
        if key in context:
            compact[key] = context.get(key)
    control = context.get("control")
    if isinstance(control, dict):
        control_view: dict[str, Any] = {}
        for key in ("action", "state", "abort", "reason"):
            if key in control:
                control_view[key] = control.get(key)
        if control_view:
            compact["control"] = control_view
    return compact


def _observer_context_delta(previous_state: object, current_state: dict[str, Any]) -> dict[str, Any]:
    prev = previous_state if isinstance(previous_state, dict) else {}
    sentinel = object()
    delta: dict[str, Any] = {}
    keys = set(prev.keys()) | set(current_state.keys())
    for key in sorted(keys):
        prev_value = prev.get(key, sentinel)
        curr_value = current_state.get(key, sentinel)
        if prev_value != curr_value:
            delta[key] = None if curr_value is sentinel else curr_value
    return delta


def _record_observer_context_snapshot(
    client: httpx.Client,
    *,
    task_id: str,
    transition: str,
    run_id: str,
    worker_id: str,
    status: str,
    current_step: str,
    failure_class: str = "",
    context_hint: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    snapshot = _safe_get_task_snapshot(client, task_id)
    context = _safe_get_task_context(snapshot)
    effective_context = dict(context)
    if isinstance(context_hint, dict):
        effective_context.update(context_hint)

    existing = context.get("observer_context_snapshots")
    history: list[dict[str, Any]] = []
    if isinstance(existing, list):
        for row in existing:
            if isinstance(row, dict):
                history.append(row)
    previous_entry = history[-1] if history else {}
    previous_state = previous_entry.get("state") if isinstance(previous_entry, dict) else {}
    state = _observer_context_compact_view(effective_context)
    state_delta = _observer_context_delta(previous_state, state)
    entry: dict[str, Any] = {
        "transition": str(transition or "unknown")[:80],
        "status": str(status or "")[:80],
        "current_step": str(current_step or "")[:200],
        "at": _utc_now_iso(),
        "run_id": str(run_id or "")[:120],
        "worker_id": str(worker_id or "")[:160],
        "failure_class": str(failure_class or "")[:120],
        "state": state,
        "delta": state_delta,
    }
    if isinstance(details, dict) and details:
        entry["details"] = details
    history.append(entry)
    history = history[-40:]
    transition_name = str(entry.get("transition") or "").strip().lower()
    transition_status = str(entry.get("status") or "").strip().lower()
    successful_transition = bool(state_delta) and transition_name != "abort" and (
        transition_status in {"claimed", "running", "pending", "completed", "needs_decision"}
    )
    awareness_patch = _awareness_patch_from_context(
        context,
        event_inc=1,
        transition_inc=1,
        successful_transition_inc=1 if successful_transition else 0,
        snapshot_count_override=len(history),
    )
    context_patch = {
        "observer_context_last_snapshot": entry,
        "observer_context_snapshots": history,
    }
    context_patch.update(awareness_patch)
    _patch_task_context(
        client,
        task_id=task_id,
        context_patch=context_patch,
    )


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
    transition_cost_inc = _estimated_transition_cost(duration_seconds, paid_call=paid_call)
    awareness_patch = _awareness_patch_from_context(
        context,
        transition_cost_inc=transition_cost_inc,
    )
    awareness = awareness_patch.get("awareness_quality")
    awareness_score = _safe_float(awareness.get("score")) if isinstance(awareness, dict) else None
    if awareness_score is None:
        awareness_score = _safe_float(context.get("awareness_quality_score"))
    if awareness_score is None:
        awareness_score = 0.0

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
        "awareness_quality_score": round(max(0.0, min(1.0, float(awareness_score))), 4),
        "state_transition_quality": _safe_float(awareness_patch.get("awareness_state_transition_quality")) or 0.0,
        "hold_pattern_rate": _safe_float(awareness_patch.get("awareness_hold_pattern_rate")) or 0.0,
        "estimated_to_measured_roi_conversion": awareness_patch.get("awareness_estimated_to_measured_roi_conversion"),
        "cost_per_successful_transition": (
            _safe_float(awareness_patch.get("awareness_cost_per_successful_transition")) or 0.0
        ),
        "awareness_events_total": max(0, _to_int(awareness_patch.get("awareness_events_total"), 0)),
        "awareness_interventions_total": max(0, _to_int(awareness_patch.get("awareness_interventions_total"), 0)),
        "awareness_blocks_total": max(0, _to_int(awareness_patch.get("awareness_blocks_total"), 0)),
        "awareness_transition_total": max(0, _to_int(awareness_patch.get("awareness_transition_total"), 0)),
        "awareness_successful_transition_total": max(
            0,
            _to_int(awareness_patch.get("awareness_successful_transition_total"), 0),
        ),
        "awareness_hold_pattern_total": max(0, _to_int(awareness_patch.get("awareness_hold_pattern_total"), 0)),
        "awareness_transition_cost_total": round(
            max(0.0, float(_safe_float(awareness_patch.get("awareness_transition_cost_total")) or 0.0)),
            6,
        ),
        "updated_at": _utc_now_iso(),
    }
    context_patch = dict(awareness_patch)
    context_patch.update(
        {
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
        }
    )
    _patch_task_context(
        client,
        task_id=task_id,
        context_patch=context_patch,
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
    extra_context_patch: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    max_retries = max(0, _to_int(task_ctx.get("runner_retry_max"), 0))
    requested_retry_delay_seconds = max(0, min(3600, _to_int(task_ctx.get("runner_retry_delay_seconds"), 8)))
    retries_used = max(0, attempt - 1)
    retries_remaining = max_retries - retries_used
    if retries_remaining <= 0:
        return False, ""

    live_snapshot = _safe_get_task_snapshot(client, task_id)
    live_ctx = _safe_get_task_context(live_snapshot)
    merged_ctx = dict(task_ctx)
    merged_ctx.update(live_ctx)
    cadence_limits = _cadence_limits(merged_ctx)
    retry_delay_seconds = max(cadence_limits["min_retry_delay_seconds"], requested_retry_delay_seconds)
    min_delay_enforced = retry_delay_seconds > requested_retry_delay_seconds
    intervention_allowed, cadence_patch, _, window_load = _allow_intervention_frequency(
        merged_ctx,
        kind="retry",
    )
    if not intervention_allowed:
        message = (
            "[cadence-steering] retry suppressed: intervention frequency limit reached "
            f"({window_load}/{cadence_limits['max_interventions_per_window']} in "
            f"{cadence_limits['intervention_window_sec']}s)."
        )
        context_patch: dict[str, Any] = dict(cadence_patch)
        context_patch.update(
            {
                "runner_state": "steering_required",
                "next_action": "steering_required",
                "steering_requested": True,
                "runner_retry_suppressed": "intervention_frequency_limit",
                "runner_retry_remaining": retries_remaining,
                "last_failure_class": failure_class,
            }
        )
        try:
            client.patch(
                f"{BASE}/api/agent/tasks/{task_id}",
                json={
                    "status": "needs_decision",
                    "current_step": "awaiting steering",
                    "output": f"{output[-3200:]}\n\n{message}"[-4000:],
                    "context": context_patch,
                },
            )
        except Exception:
            return False, ""
        return False, message
    retry_not_before = (datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)).isoformat()
    failure_entry = {
        "attempt": attempt,
        "failure_class": failure_class,
        "duration_seconds": round(float(duration_seconds), 3),
        "at": _utc_now_iso(),
        "output_tail": _tail_text(output, 600),
    }
    failure_history = _append_failure_history(merged_ctx.get("runner_failure_history"), failure_entry)
    context_patch = dict(cadence_patch)
    context_patch.update(
        {
        "runner_retry_max": max_retries,
        "runner_retry_delay_seconds": retry_delay_seconds,
        "runner_retry_delay_requested_seconds": requested_retry_delay_seconds,
        "runner_retry_delay_effective_seconds": retry_delay_seconds,
        "runner_min_retry_delay_seconds": cadence_limits["min_retry_delay_seconds"],
        "runner_retry_delay_enforced": min_delay_enforced,
        "runner_retry_count": retries_used + 1,
        "runner_retry_remaining": retries_remaining - 1,
        "runner_state": "retry_pending",
        "retry_not_before": retry_not_before,
        "runner_last_failure": failure_entry,
        "runner_failure_history": failure_history,
        "cadence_limits": cadence_limits,
    }
    )
    if extra_context_patch:
        context_patch.update(dict(extra_context_patch))
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


def _normalize_sha(value: object) -> str:
    text = str(value or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{7,64}", text):
        return text[:40]
    return ""


def _github_head_sha(client: httpx.Client, repo: str, branch: str, log: logging.Logger) -> str:
    repository = str(repo or "").strip()
    ref = str(branch or "").strip()
    if not repository or "/" not in repository:
        return ""
    if not ref:
        ref = "main"
    token = str(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "coherence-agent-runner",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repository}/commits/{ref}"
    response = _http_with_retry(client, "GET", url, log, headers=headers)
    if response is None:
        return ""
    if response.status_code != 200:
        log.warning(
            "runner self-update: GitHub head lookup failed repo=%s ref=%s status=%s",
            repository,
            ref,
            response.status_code,
        )
        return ""
    try:
        payload = response.json()
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return _normalize_sha(payload.get("sha"))


def _railway_runner_commit_sha(client: httpx.Client, log: logging.Logger) -> tuple[str, str]:
    token = str(os.environ.get("RAILWAY_TOKEN", "")).strip()
    env_id = str(os.environ.get("RAILWAY_ENVIRONMENT_ID") or os.environ.get("RAILWAY_ENVIRONMENT") or "").strip()
    service_id = str(os.environ.get("RAILWAY_SERVICE_ID") or os.environ.get("RAILWAY_SERVICE") or "").strip()
    if not token or not env_id or not service_id:
        env_commit = _normalize_sha(
            os.environ.get("RAILWAY_GIT_COMMIT_SHA")
            or os.environ.get("AGENT_RUNNER_BUILD_SHA")
            or os.environ.get("GIT_COMMIT_SHA")
        )
        return env_commit, ""
    try:
        uuid.UUID(env_id)
        uuid.UUID(service_id)
    except Exception:
        log.warning(
            "runner self-update: Railway IDs must be UUIDs (env=%r service=%r); skipping auto-redeploy check",
            env_id,
            service_id,
        )
        return "", ""

    railway_url = os.environ.get("RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2")
    query = {
        "query": (
            "query RunnerDeployment($environmentId:String!, $serviceId:String!) { "
            "serviceInstance(environmentId:$environmentId, serviceId:$serviceId) { "
            "latestDeployment { id meta } } }"
        ),
        "variables": {"environmentId": env_id, "serviceId": service_id},
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = client.post(railway_url, json=query, headers=headers, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        log.warning("runner self-update: Railway deployment lookup failed: %s", exc)
        return "", ""
    if response.status_code != 200:
        log.warning(
            "runner self-update: Railway deployment lookup status=%s",
            response.status_code,
        )
        return "", ""
    try:
        payload = response.json()
    except Exception:
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    if payload.get("errors"):
        log.warning("runner self-update: Railway deployment lookup errors=%s", str(payload.get("errors"))[:600])
        return "", ""
    service_instance = ((payload.get("data") or {}).get("serviceInstance") or {})
    latest_deployment = (service_instance.get("latestDeployment") or {})
    deployment_id = str(latest_deployment.get("id") or "").strip()
    meta = latest_deployment.get("meta")
    commit_sha = ""
    if isinstance(meta, dict):
        commit_sha = _normalize_sha(meta.get("commitHash"))
    if not commit_sha:
        commit_sha = _normalize_sha(
            os.environ.get("RAILWAY_GIT_COMMIT_SHA")
            or os.environ.get("AGENT_RUNNER_BUILD_SHA")
            or os.environ.get("GIT_COMMIT_SHA")
        )
    return commit_sha, deployment_id


def _trigger_railway_runner_redeploy(client: httpx.Client, log: logging.Logger) -> tuple[bool, str]:
    token = str(os.environ.get("RAILWAY_TOKEN", "")).strip()
    env_id = str(os.environ.get("RAILWAY_ENVIRONMENT_ID") or os.environ.get("RAILWAY_ENVIRONMENT") or "").strip()
    service_id = str(os.environ.get("RAILWAY_SERVICE_ID") or os.environ.get("RAILWAY_SERVICE") or "").strip()
    if not token or not env_id or not service_id:
        return False, "missing_railway_context"
    railway_url = os.environ.get("RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2")
    mutation = {
        "query": (
            "mutation RunnerRedeploy($environmentId:String!, $serviceId:String!) { "
            "serviceInstanceRedeploy(environmentId:$environmentId, serviceId:$serviceId) }"
        ),
        "variables": {"environmentId": env_id, "serviceId": service_id},
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = client.post(railway_url, json=mutation, headers=headers, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        return False, f"railway_request_failed:{exc}"
    if response.status_code != 200:
        return False, f"railway_status_{response.status_code}"
    try:
        payload = response.json()
    except Exception:
        return False, "railway_non_json_response"
    if not isinstance(payload, dict):
        return False, "railway_invalid_response"
    if payload.get("errors"):
        log.warning("runner self-update: Railway redeploy errors=%s", str(payload.get("errors"))[:800])
        return False, "railway_graphql_errors"
    data = payload.get("data") or {}
    if not bool(data.get("serviceInstanceRedeploy")):
        return False, "railway_redeploy_not_triggered"
    return True, "redeploy_triggered"


def _trigger_railway_runner_rollback(client: httpx.Client, log: logging.Logger) -> tuple[bool, str]:
    token = str(os.environ.get("RAILWAY_TOKEN", "")).strip()
    if not token:
        return False, "missing_railway_token"

    _, deployment_id = _railway_runner_commit_sha(client, log)
    if not deployment_id:
        return False, "missing_current_deployment_id"

    railway_url = os.environ.get("RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2")
    mutation = {
        "query": "mutation Rollback($id:String!) { deploymentRollback(id:$id) }",
        "variables": {"id": deployment_id},
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = client.post(railway_url, json=mutation, headers=headers, timeout=HTTP_TIMEOUT)
    except Exception as exc:
        return False, f"railway_request_failed:{exc}"
    if response.status_code != 200:
        return False, f"railway_status_{response.status_code}"
    try:
        payload = response.json()
    except Exception:
        return False, "railway_non_json_response"
    if not isinstance(payload, dict):
        return False, "railway_invalid_response"
    if payload.get("errors"):
        log.warning("runner rollback: Railway rollback errors=%s", str(payload.get("errors"))[:800])
        return False, "railway_graphql_errors"
    data = payload.get("data") or {}
    if not bool(data.get("deploymentRollback")):
        return False, "railway_rollback_not_triggered"
    return True, deployment_id


def _maybe_trigger_runner_rollback(
    client: httpx.Client,
    log: logging.Logger,
    *,
    reason: str,
    task_id: str = "",
    failure_class: str = "",
) -> None:
    now = time.monotonic()
    with ROLLBACK_LOCK:
        global ROLLBACK_LAST_AT
        if (now - ROLLBACK_LAST_AT) < float(ROLLBACK_MIN_INTERVAL_SECONDS):
            return
        ROLLBACK_LAST_AT = now

    ok, detail = _trigger_railway_runner_rollback(client, log)
    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    if not ok:
        log.warning(
            "runner rollback: failed reason=%s task=%s failure_class=%s detail=%s",
            reason,
            task_id or "-",
            failure_class or "-",
            detail,
        )
        return
    _runner_heartbeat(
        client,
        runner_id=worker_id,
        status="degraded",
        active_task_id="",
        active_run_id="",
        metadata={
            "rollback_triggered": True,
            "rollback_reason": reason,
            "rollback_task_id": task_id,
            "rollback_failure_class": failure_class,
            "rollback_source_deployment_id": detail,
        },
    )
    log.warning(
        "runner rollback: triggered reason=%s task=%s failure_class=%s source_deployment=%s",
        reason,
        task_id or "-",
        failure_class or "-",
        detail,
    )


def _maybe_trigger_runner_self_update(
    client: httpx.Client,
    log: logging.Logger,
    *,
    last_task_id: str = "",
) -> None:
    if not SELF_UPDATE_ENABLED:
        return
    now = time.monotonic()
    with SELF_UPDATE_LOCK:
        global SELF_UPDATE_LAST_CHECK_AT, SELF_UPDATE_LAST_TRIGGER_SHA
        if (now - SELF_UPDATE_LAST_CHECK_AT) < float(SELF_UPDATE_MIN_INTERVAL_SECONDS):
            return
        SELF_UPDATE_LAST_CHECK_AT = now

    latest_main_sha = _github_head_sha(client, SELF_UPDATE_REPO, SELF_UPDATE_BRANCH, log)
    if not latest_main_sha:
        return

    current_sha, deployment_id = _railway_runner_commit_sha(client, log)
    if not current_sha:
        log.info(
            "runner self-update: current deployment commit unavailable; "
            "set Railway context vars for commit-aware redeploy checks"
        )
        return

    if latest_main_sha.startswith(current_sha) or current_sha.startswith(latest_main_sha):
        return

    with SELF_UPDATE_LOCK:
        if SELF_UPDATE_LAST_TRIGGER_SHA == latest_main_sha:
            return

    ok, reason = _trigger_railway_runner_redeploy(client, log)
    if not ok:
        log.warning(
            "runner self-update: redeploy failed task=%s current=%s latest=%s reason=%s",
            last_task_id or "-",
            current_sha[:12],
            latest_main_sha[:12],
            reason,
        )
        return

    with SELF_UPDATE_LOCK:
        SELF_UPDATE_LAST_TRIGGER_SHA = latest_main_sha

    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    _runner_heartbeat(
        client,
        runner_id=worker_id,
        status="updating",
        active_task_id="",
        active_run_id="",
        metadata={
            "self_update_triggered": True,
            "self_update_task_id": last_task_id,
            "runner_commit": current_sha,
            "target_commit": latest_main_sha,
            "deployment_id": deployment_id,
            "reason": reason,
        },
    )
    log.warning(
        "runner self-update: triggered Railway redeploy task=%s current=%s latest=%s deployment=%s",
        last_task_id or "-",
        current_sha[:12],
        latest_main_sha[:12],
        deployment_id or "unknown",
    )


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


_USAGE_LIMIT_HARD_MARKERS = (
    "insufficient_quota",
    "quota exceeded",
    "billing hard limit",
    "provider blocked",
)

_USAGE_LIMIT_SOFT_MARKERS = (
    "usage limit",
    "rate limit",
    "too many requests",
)

_USAGE_LIMIT_ERROR_TOKENS = (
    "http 429",
    "status 429",
    " 429",
    "insufficient_quota",
    "quota exceeded",
    "billing hard limit",
    "too many requests",
    "rate limit reached",
    "provider blocked",
    "retry-after",
    "retry after",
)


def _detect_usage_limit(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    if any(marker in lowered for marker in _USAGE_LIMIT_HARD_MARKERS):
        return True
    for line in lowered.splitlines():
        if any(marker in line for marker in _USAGE_LIMIT_SOFT_MARKERS) and any(
            token in line for token in _USAGE_LIMIT_ERROR_TOKENS
        ):
            return True
    return False


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
    if _codex_model_not_found_or_access_error(output):
        return "model_not_found"
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


def _uses_anthropic_cloud(command: str) -> bool:
    """True if command uses Anthropic cloud (e.g. HEAL with claude-3-5-haiku), not Ollama."""
    if "ollama/" in command:
        return False
    return "claude-3-5" in command or "claude-4" in command


def _uses_cursor_cli(command: str) -> bool:
    """True if command uses Cursor CLI (agent '...'). Cursor uses its own auth."""
    return command.strip().startswith("agent ")


def _uses_openclaw_cli(command: str) -> bool:
    """True if command uses OpenClaw CLI."""
    stripped = command.strip()
    return stripped.startswith("openclaw ") or stripped.startswith("clawwork ")


def _uses_codex_cli(command: str) -> bool:
    return command.strip().startswith("codex ")


def _prepare_codex_command_for_exec(command: str) -> tuple[str | list[str], bool, str]:
    """Run codex commands via argv to avoid shell expansion of backticks in prompt text."""
    cmd = str(command or "")
    if not _uses_codex_cli(cmd):
        return cmd, True, "shell"
    try:
        argv = shlex.split(cmd, posix=True)
    except ValueError:
        return cmd, True, "shell_parse_error"
    if not argv:
        return cmd, True, "shell_empty_argv"
    return argv, False, "argv"


def _normalize_codex_auth_mode(raw: Any, *, default: str = "api_key") -> str:
    mode = str(raw or "").strip().lower()
    if mode in CODEX_AUTH_MODE_VALUES:
        return mode
    return default


def _codex_auth_mode(override: str | None = None) -> str:
    raw = override if str(override or "").strip() else os.environ.get("AGENT_CODEX_AUTH_MODE", "api_key")
    if raw in CODEX_AUTH_MODE_VALUES:
        return str(raw).strip().lower()
    return _normalize_codex_auth_mode(raw, default="api_key")


def _abs_expanded_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    return os.path.abspath(os.path.expanduser(value))


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

    codex_binary = shutil.which("codex")
    if codex_binary:
        try:
            completed = subprocess.run(
                ["codex", "auth", "status"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=8,
                env=env,
            )
            if completed.returncode == 0:
                return True, "codex_auth_status"
        except Exception:
            pass

    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_codex_oauth_session"


def _ensure_codex_api_key_isolated_home(env: dict[str, str], *, task_id: str) -> str:
    """Force Codex API-key mode to ignore stale oauth sessions from the default home."""
    slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", str(task_id or "task")).strip("-") or "task"
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
    task_auth_override = _normalize_codex_auth_mode(
        (task_ctx or {}).get("runner_codex_auth_mode"),
        default="",
    )
    requested_mode = _codex_auth_mode(task_auth_override or None)
    codex_home_override = str(os.environ.get("AGENT_CODEX_HOME", "")).strip()
    if codex_home_override:
        env["CODEX_HOME"] = _abs_expanded_path(codex_home_override)

    openai_api_key = str(os.environ.get("OPENAI_API_KEY", "")).strip()
    openai_admin_key = str(os.environ.get("OPENAI_ADMIN_API_KEY", "")).strip()
    openai_primary_key = openai_api_key or openai_admin_key
    api_key_present = bool(openai_primary_key)
    oauth_available_initial, oauth_source_initial = _codex_oauth_session_status(env)
    allow_oauth_fallback = _as_bool(os.environ.get("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", "1"))

    effective_mode = requested_mode
    if requested_mode == "auto":
        effective_mode = "api_key" if api_key_present else ("oauth" if oauth_available_initial else "api_key")

    if effective_mode == "oauth":
        if allow_oauth_fallback:
            env.setdefault("OPENAI_API_KEY", openai_primary_key)
            env.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"))
            env.setdefault("OPENAI_BASE_URL", env.get("OPENAI_API_BASE"))
        else:
            env.pop("OPENAI_API_KEY", None)
            env.pop("OPENAI_ADMIN_API_KEY", None)
            env.pop("OPENAI_API_BASE", None)
            env.pop("OPENAI_BASE_URL", None)
    else:
        if _as_bool(os.environ.get("AGENT_CODEX_API_KEY_ISOLATE_HOME", "1")):
            _ensure_codex_api_key_isolated_home(env, task_id=task_id)
            env["AGENT_CODEX_OAUTH_SESSION_FILE"] = ""
        env.setdefault("OPENAI_API_KEY", openai_primary_key)
        env.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1"))
        env.setdefault("OPENAI_BASE_URL", env.get("OPENAI_API_BASE"))

    oauth_available, oauth_source = _codex_oauth_session_status(env)
    oauth_missing = bool(effective_mode == "oauth" and not oauth_available and not allow_oauth_fallback)
    auth_state = {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "oauth_session": bool(oauth_available),
        "oauth_source": oauth_source,
        "api_key_present": bool(api_key_present),
        "oauth_fallback_allowed": bool(allow_oauth_fallback),
        "oauth_missing": oauth_missing,
    }
    if oauth_missing:
        log.warning(
            "task=%s codex oauth mode requested but no session detected source=%s",
            task_id,
            oauth_source,
        )
    log.info(
        "task=%s using codex CLI auth requested=%s effective=%s oauth_session=%s source=%s api_key_present=%s",
        task_id,
        requested_mode,
        effective_mode,
        bool(oauth_available),
        oauth_source,
        bool(api_key_present),
    )
    return auth_state


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
    target_model = _codex_model_alias_map().get(requested_model.lower(), "").strip()
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


def _infer_executor(command: str, model: str) -> str:
    s = (command or "").strip()
    model_value = (model or "").strip().lower()
    if _uses_cursor_cli(command) or model_value.startswith("cursor/"):
        return "cursor"
    if _uses_codex_cli(command):
        return "openai-codex"
    if _uses_openclaw_cli(command) or model_value.startswith(("openclaw/", "clawwork/")):
        return "openclaw"
    if s.startswith("aider "):
        return "aider"
    if s.startswith("claude "):
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


def _path_has_git_marker(repo_path: str) -> bool:
    git_marker = os.path.join(repo_path, ".git")
    return os.path.exists(git_marker)


def _directory_has_entries(path: str) -> bool:
    try:
        with os.scandir(path) as entries:
            for _ in entries:
                return True
    except OSError:
        return False
    return False


def _ensure_repo_checkout(repo_path: str, *, log: logging.Logger) -> bool:
    if _path_has_git_marker(repo_path):
        return True
    if os.path.isdir(repo_path) and _directory_has_entries(repo_path):
        log.warning(
            "repo checkout missing git metadata at %s; directory is non-empty and cannot be cloned in-place",
            repo_path,
        )
        return False
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
    return _path_has_git_marker(repo_path)


def _resolve_repo_path_for_execution(repo_path: str, *, log: logging.Logger) -> str:
    candidate = os.path.abspath(repo_path)
    if _path_has_git_marker(candidate):
        return candidate

    if os.path.isdir(candidate) and _directory_has_entries(candidate):
        fallback = os.path.abspath(REPO_FALLBACK_PATH)
        if fallback != candidate:
            log.warning(
                "repo path %s missing git metadata; switching execution checkout to %s",
                candidate,
                fallback,
            )
            candidate = fallback

    if os.path.abspath(candidate) == os.path.abspath(REPO_FALLBACK_PATH):
        if os.path.isdir(candidate) and _directory_has_entries(candidate) and not _path_has_git_marker(candidate):
            # The fallback directory is runner-managed scratch space. Reset it when stale.
            shutil.rmtree(candidate, ignore_errors=True)

    if not _path_has_git_marker(candidate):
        _ensure_repo_checkout(candidate, log=log)
    return candidate


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
    if should_requeue:
        _record_observer_context_snapshot(
            client,
            task_id=task_id,
            transition="retry",
            run_id=run_id,
            worker_id=worker_id,
            status="pending",
            current_step="resume checkpoint scheduled",
            failure_class=failure_class,
            context_hint={
                "runner_state": "retry_pending",
                "next_action": "requeue_for_resume",
                "resume_branch": branch,
                "resume_checkpoint_sha": checkpoint_sha,
                "last_failure_class": failure_class,
            },
            details={
                "checkpoint_ok": checkpoint_ok,
                "checkpoint_sha": checkpoint_sha,
                "resume_attempts": resume_attempts + 1,
                "max_resume_attempts": max_resume_attempts,
            },
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
    env = os.environ.copy()
    codex_model_alias: dict[str, str] | None = None
    codex_auth_state: dict[str, Any] | None = None
    popen_command: str | list[str] = command
    popen_shell = True
    command_exec_mode = "shell"
    if _uses_cursor_cli(command):
        # Cursor CLI uses Cursor app auth; ensure OpenAI-compatible env vars for OpenRouter
        env.setdefault("OPENAI_API_KEY", os.environ.get("OPENROUTER_API_KEY", ""))
        env.setdefault("OPENAI_API_BASE", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        log.info("task=%s using Cursor CLI with OpenRouter", task_id)
    elif _uses_codex_cli(command):
        codex_auth_state = _configure_codex_cli_environment(env=env, task_id=task_id, log=log, task_ctx=task_ctx)
        command, codex_model_alias = _apply_codex_model_alias(command)
        if codex_model_alias:
            log.warning(
                "task=%s remapped codex model %s -> %s",
                task_id,
                codex_model_alias["requested_model"],
                codex_model_alias["effective_model"],
            )
        if "--dangerously-bypass-approvals-and-sandbox" not in command:
            command = f"{command} --dangerously-bypass-approvals-and-sandbox"
        popen_command, popen_shell, command_exec_mode = _prepare_codex_command_for_exec(command)
    elif _uses_openclaw_cli(command):
        env.setdefault("OPENCLAW_API_KEY", os.environ.get("OPENCLAW_API_KEY", ""))
        env.setdefault("OPENCLAW_BASE_URL", os.environ.get("OPENCLAW_BASE_URL", ""))
        log.info("task=%s using OpenClaw executor", task_id)
    elif _uses_anthropic_cloud(command):
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        env.setdefault("ANTHROPIC_API_KEY", api_key)
        log.info("task=%s using Anthropic cloud has_key=%s", task_id, bool(api_key))
    else:
        env.setdefault("ANTHROPIC_AUTH_TOKEN", "ollama")
        env.setdefault("ANTHROPIC_BASE_URL", "http://localhost:11434")
        env.setdefault("ANTHROPIC_API_KEY", "")
    if _uses_codex_cli(command):
        log.info("task=%s codex execution mode=%s", task_id, command_exec_mode)
    # Suppress Claude Code requests to unsupported local-model endpoints (GitHub #13949)
    env.setdefault("DISABLE_TELEMETRY", "1")
    env.setdefault("DISABLE_ERROR_REPORTING", "1")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    executor = _infer_executor(command, model)
    is_openai_codex = _is_openai_codex_worker(worker_id) or _uses_codex_cli(command)

    target_contract = _normalize_task_target_contract(
        task_ctx,
        task_type=str(task_type or "impl"),
        task_direction=task_direction,
    )
    task_ctx.update(target_contract)
    task_snapshot = {"task_type": task_type, "context": task_ctx}
    pr_mode = _should_run_pr_flow(task_snapshot)
    repo_path = _repo_path_for_task(task_ctx)
    if not pr_mode:
        repo_path = _resolve_repo_path_for_execution(repo_path, log=log)
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

    _record_observer_context_snapshot(
        client,
        task_id=task_id,
        transition="claim",
        run_id=run_id,
        worker_id=worker_id,
        status="claimed",
        current_step="lease claimed",
        context_hint={
            "active_run_id": run_id,
            "active_worker_id": worker_id,
            "active_branch": branch_name if pr_mode else "",
            "last_attempt": attempt,
            "runner_state": "claimed",
        },
        details={
            "task_type": str(task_type or "")[:40],
            "direction": str(task_direction or "")[:200],
            "repo_path": repo_path if pr_mode else "",
        },
    )

    # PATCH to running
    running_context: dict[str, Any] = {
        "active_run_id": run_id,
        "active_worker_id": worker_id,
        "active_branch": branch_name if pr_mode else "",
        "last_attempt": attempt,
    }
    if codex_auth_state:
        running_context["runner_codex_auth"] = {
            **codex_auth_state,
            "at": _utc_now_iso(),
        }
    if codex_model_alias:
        running_context["runner_model_alias"] = {
            **codex_model_alias,
            "at": _utc_now_iso(),
        }
    r = client.patch(
        f"{BASE}/api/agent/tasks/{task_id}",
        json={
            "status": "running",
            "worker_id": worker_id,
            "context": running_context,
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
    _patch_task_context(
        client,
        task_id=task_id,
        context_patch={
            "target_state": target_contract.get("target_state"),
            "success_evidence": target_contract.get("success_evidence"),
            "abort_evidence": target_contract.get("abort_evidence"),
            "observation_window_sec": target_contract.get("observation_window_sec"),
            "target_state_contract": target_contract,
        },
    )
    _record_observer_context_snapshot(
        client,
        task_id=task_id,
        transition="start",
        run_id=run_id,
        worker_id=worker_id,
        status="running",
        current_step="command started",
        context_hint={
            "active_run_id": run_id,
            "active_worker_id": worker_id,
            "active_branch": branch_name if pr_mode else "",
            "last_attempt": attempt,
            "runner_state": "running",
            "next_action": "execute_command",
        },
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
    if codex_model_alias:
        alias_note = (
            "[runner-model-alias] requested_model="
            f"{codex_model_alias['requested_model']} effective_model={codex_model_alias['effective_model']}\n"
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
                    task_ctx_live = _safe_get_task_context(task_snapshot_live)
                    abort_requested, requested_abort_reason, diagnostic_request = _extract_control_signals(task_snapshot_live)
                    if diagnostic_request:
                        request_id = _diagnostic_request_id(diagnostic_request)
                        if request_id and request_id != diagnostic_completed_id:
                            cadence_limits = _cadence_limits(task_ctx_live)
                            cooldown_seconds = cadence_limits["diagnostic_cooldown_seconds"]
                            diag_now_utc = datetime.now(timezone.utc)
                            last_diag_at = _parse_iso_utc(task_ctx_live.get("diagnostic_last_ran_at"))
                            cooldown_remaining = 0
                            if last_diag_at is not None and cooldown_seconds > 0:
                                elapsed = (diag_now_utc - last_diag_at).total_seconds()
                                if elapsed < float(cooldown_seconds):
                                    cooldown_remaining = max(1, int(cooldown_seconds - elapsed))
                            if cooldown_remaining > 0:
                                diagnostic_completed_id = request_id
                                awareness_patch = _awareness_patch_from_context(
                                    task_ctx_live,
                                    event_inc=1,
                                    block_inc=1,
                                )
                                deferred_result = {
                                    "id": request_id,
                                    "status": "deferred_cooldown",
                                    "exit_code": None,
                                    "cooldown_seconds": cooldown_seconds,
                                    "retry_after_seconds": cooldown_remaining,
                                    "ran_at": _utc_now_iso(),
                                }
                                context_patch = dict(awareness_patch)
                                context_patch.update(
                                    {
                                        "diagnostic_last_completed_id": request_id,
                                        "diagnostic_last_result": deferred_result,
                                        "diagnostic_cooldown_seconds": cooldown_seconds,
                                        "runner_last_seen_at": _utc_now_iso(),
                                        "cadence_limits": cadence_limits,
                                    }
                                )
                                _patch_task_progress(
                                    client,
                                    task_id=task_id,
                                    progress_pct=min(95, max(1, int(((now - start_time) / max_runtime_seconds) * 90))),
                                    current_step="diagnostic cooldown active",
                                    context_patch=context_patch,
                                )
                                output_lines.append(
                                    "\n[Diagnostic] "
                                    f"id={request_id} status=deferred_cooldown retry_after={cooldown_remaining}s\n"
                                )
                            else:
                                intervention_allowed, cadence_patch, _, window_load = _allow_intervention_frequency(
                                    task_ctx_live,
                                    kind="diagnostic",
                                    now=diag_now_utc,
                                )
                                if not intervention_allowed:
                                    diagnostic_completed_id = request_id
                                    deferred_result = {
                                        "id": request_id,
                                        "status": "deferred_intervention_limit",
                                        "exit_code": None,
                                        "window_load": window_load,
                                        "window_limit": cadence_limits["max_interventions_per_window"],
                                        "window_seconds": cadence_limits["intervention_window_sec"],
                                        "ran_at": _utc_now_iso(),
                                    }
                                    context_patch = dict(cadence_patch)
                                    context_patch.update(
                                        {
                                            "diagnostic_last_completed_id": request_id,
                                            "diagnostic_last_result": deferred_result,
                                            "diagnostic_cooldown_seconds": cooldown_seconds,
                                            "runner_last_seen_at": _utc_now_iso(),
                                            "steering_requested": True,
                                            "next_action": "steering_required",
                                        }
                                    )
                                    _patch_task_progress(
                                        client,
                                        task_id=task_id,
                                        progress_pct=min(95, max(1, int(((now - start_time) / max_runtime_seconds) * 90))),
                                        current_step="diagnostic limited by cadence",
                                        context_patch=context_patch,
                                    )
                                    output_lines.append(
                                        "\n[Diagnostic] "
                                        f"id={request_id} status=deferred_intervention_limit "
                                        f"load={window_load}/{cadence_limits['max_interventions_per_window']}\n"
                                    )
                                else:
                                    diagnostic_result = _run_diagnostic_request(
                                        diagnostic_request,
                                        cwd=repo_path,
                                        env=env,
                                    )
                                    diagnostic_completed_id = request_id
                                    context_patch = dict(cadence_patch)
                                    context_patch.update(
                                        {
                                            "diagnostic_last_completed_id": request_id,
                                            "diagnostic_last_result": diagnostic_result,
                                            "diagnostic_last_ran_at": _utc_now_iso(),
                                            "diagnostic_cooldown_seconds": cooldown_seconds,
                                            "runner_last_seen_at": _utc_now_iso(),
                                            "cadence_limits": cadence_limits,
                                        }
                                    )
                                    _patch_task_progress(
                                        client,
                                        task_id=task_id,
                                        progress_pct=min(95, max(1, int(((now - start_time) / max_runtime_seconds) * 90))),
                                        current_step="running diagnostic",
                                        context_patch=context_patch,
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
                        _record_observer_context_snapshot(
                            client,
                            task_id=task_id,
                            transition="abort",
                            run_id=run_id,
                            worker_id=worker_id,
                            status="running",
                            current_step="abort requested",
                            failure_class="aborted_by_user",
                            context_hint={
                                "runner_state": "abort_requested",
                                "abort_requested": True,
                                "abort_reason": abort_reason,
                                "next_action": "abort_requested",
                            },
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
        contract_observation = _observe_target_contract(
            contract=target_contract,
            output=output,
            duration_seconds=duration_sec,
            attempt_status=status,
        )
        if _as_bool(contract_observation.get("abort_evidence_met")):
            status = "failed"
            hits = contract_observation.get("abort_evidence_hits") or []
            hit_preview = ", ".join(str(hit) for hit in hits[:3]) if isinstance(hits, list) else ""
            output = (
                f"{output}\n[Target Contract] Abort evidence observed; "
                f"marking task failed. hits={hit_preview or 'configured abort evidence matched'}"
            )
        failure_class = _classify_failure(
            output=output,
            timed_out=timed_out,
            stopped_for_usage=stopped_for_usage,
            stopped_for_abort=stopped_for_abort,
            returncode=returncode,
        )
        if _as_bool(contract_observation.get("abort_evidence_met")):
            failure_class = "abort_evidence_triggered"
        _patch_task_context(
            client,
            task_id=task_id,
            context_patch={
                "target_state_contract": target_contract,
                "target_state_observation": contract_observation,
                "target_state_last_observed_at": _utc_now_iso(),
            },
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
        if pr_mode:
            manifest_context_patch = _append_agent_manifest_entry(
                task_id=task_id,
                task_type=task_type,
                task_direction=task_direction,
                task_ctx=task_ctx,
                repo_path=repo_path,
                executor=executor,
            )
            if manifest_context_patch:
                _patch_task_context(client, task_id=task_id, context_patch=manifest_context_patch)

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

        hold_policy_applied = False
        hold_policy_message = ""
        if status != "completed":
            hold_policy_applied, hold_policy_message = _apply_hold_pattern_policy(
                client,
                task_id=task_id,
                task_ctx=task_ctx,
                attempt=attempt,
                failure_class=failure_class,
                output=output,
                repo_path=repo_path,
                env=env,
                run_id=run_id,
                worker_id=worker_id,
            )
            if hold_policy_applied:
                status = "needs_decision"
                output = f"{output}\n\n{hold_policy_message}" if hold_policy_message else output

        final_status = status
        if (not hold_policy_applied) and pr_mode and status == "completed":
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
        elif (not hold_policy_applied) and pr_mode and status != "completed":
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
        elif (not hold_policy_applied) and (not pr_mode) and status != "completed":
            retry_task_ctx = task_ctx
            retry_context_patch: dict[str, Any] | None = None
            if _uses_codex_cli(command):
                auth_fallback_already_attempted = _as_bool(task_ctx.get("runner_codex_auth_fallback_attempted"))
                oauth_retry_eligible = bool(
                    codex_auth_state
                    and codex_auth_state.get("effective_mode") == "oauth"
                    and codex_auth_state.get("api_key_present")
                )
                if oauth_retry_eligible and _codex_oauth_refresh_token_reused_error(output):
                    if not auth_fallback_already_attempted:
                        retry_task_ctx = dict(retry_task_ctx)
                        retry_task_ctx["runner_codex_auth_mode"] = "api_key"
                        retry_task_ctx["runner_codex_auth_fallback_attempted"] = True
                        retry_task_ctx["runner_retry_max"] = max(_to_int(task_ctx.get("runner_retry_max"), 0), attempt)
                        requested_delay = max(0, min(3600, _to_int(task_ctx.get("runner_retry_delay_seconds"), 8)))
                        retry_task_ctx["runner_retry_delay_seconds"] = min(3600, max(2, requested_delay))
                        retry_context_patch = (retry_context_patch or {}) | {
                            "runner_codex_auth_mode": "api_key",
                            "runner_codex_auth_fallback_attempted": True,
                            "runner_codex_auth_fallback": {
                                "trigger": "oauth_refresh_token_reused",
                                "from_mode": "oauth",
                                "to_mode": "api_key",
                                "at": _utc_now_iso(),
                            },
                        }
                        output = (
                            f"{output}\n[runner-codex-auth-fallback] oauth refresh token reuse detected; "
                            "retrying with api_key auth mode."
                        )
                    else:
                        output = (
                            f"{output}\n[runner-codex-auth-fallback] "
                            "oauth refresh-token fallback already attempted; not retrying auth fallback."
                        )
                if _codex_model_not_found_or_access_error(output):
                    fallback_already_attempted = _as_bool(task_ctx.get("runner_model_not_found_fallback_attempted"))
                    fallback_command, fallback_alias = _codex_model_not_found_fallback(command, output)
                    if fallback_alias and not fallback_already_attempted:
                        retry_task_ctx = dict(retry_task_ctx)
                        retry_task_ctx["retry_override_command"] = fallback_command
                        retry_task_ctx["runner_retry_max"] = max(_to_int(task_ctx.get("runner_retry_max"), 0), attempt)
                        requested_delay = max(0, min(3600, _to_int(task_ctx.get("runner_retry_delay_seconds"), 8)))
                        retry_task_ctx["runner_retry_delay_seconds"] = min(3600, max(2, requested_delay))
                        retry_context_patch = (retry_context_patch or {}) | {
                            "retry_override_command": fallback_command,
                            "runner_model_not_found_fallback_attempted": True,
                            "runner_model_not_found_fallback": {
                                **fallback_alias,
                                "at": _utc_now_iso(),
                            },
                        }
                        output = (
                            f"{output}\n[runner-model-fallback] model unavailable; "
                            f"retrying with --model {fallback_alias['effective_model']}."
                        )
                    elif fallback_already_attempted:
                        output = (
                            f"{output}\n[runner-model-fallback] "
                            "model unavailable after fallback attempt; not retrying fallback."
                        )
            retry_scheduled, retry_message = _schedule_retry_if_configured(
                client,
                task_id=task_id,
                task_ctx=retry_task_ctx,
                output=output,
                failure_class=failure_class,
                attempt=attempt,
                duration_seconds=duration_sec,
                extra_context_patch=retry_context_patch,
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
                _record_observer_context_snapshot(
                    client,
                    task_id=task_id,
                    transition="retry",
                    run_id=run_id,
                    worker_id=worker_id,
                    status="pending",
                    current_step="retry scheduled",
                    failure_class=failure_class,
                    context_hint={
                        "runner_state": "retry_pending",
                        "next_action": "retry_scheduled",
                        "last_failure_class": failure_class,
                    },
                )
            elif retry_message.startswith("[cadence-steering]"):
                status = "needs_decision"
                output = f"{output}\n\n{retry_message}"
                _sync_run_state(
                    client,
                    task_id=task_id,
                    run_id=run_id,
                    worker_id=worker_id,
                    patch={
                        "status": "needs_decision",
                        "failure_class": failure_class,
                        "next_action": "steering_required",
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
        elif not hold_policy_applied:
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
        _record_observer_context_snapshot(
            client,
            task_id=task_id,
            transition="complete",
            run_id=run_id,
            worker_id=worker_id,
            status=status,
            current_step="finalized",
            failure_class=failure_class if status != "completed" else "",
            context_hint={
                "runner_state": (
                    "idle"
                    if status == "completed"
                    else (
                        "retry_pending"
                        if status == "pending"
                        else ("steering_required" if status == "needs_decision" else "finished")
                    )
                ),
                "next_action": (
                    "done"
                    if status == "completed"
                    else (
                        "retry_scheduled"
                        if status == "pending"
                        else ("steering_required" if status == "needs_decision" else "needs_attention")
                    )
                ),
                "last_failure_class": failure_class if status != "completed" else "",
            },
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
        if ROLLBACK_ON_TASK_FAILURE:
            _maybe_trigger_runner_rollback(
                client,
                log,
                reason="runner_exception",
                task_id=task_id,
                failure_class="runner_exception",
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
        fetch_limit = max(workers, PENDING_TASK_FETCH_LIMIT)
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
        to_run: list[TaskRunItem] = []
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
            has_measured_value = _task_has_measured_value_signal(
                client,
                context=context,
                log=log,
            )
            to_run.append((task_id, command, task_type, model, context, direction, has_measured_value))

        if not to_run:
            if once:
                break
            time.sleep(interval)
            continue

        scheduled_tasks = _select_tasks_for_execution(
            to_run,
            max_tasks=max(1, workers),
            log=log,
        )
        if not scheduled_tasks:
            if once:
                break
            time.sleep(interval)
            continue

        # PR-flow tasks should stay serial to avoid shared worktree race conditions.
        pr_tasks: list[TaskRunItem] = []
        direct_tasks: list[TaskRunItem] = []
        for item in scheduled_tasks:
            _, _, task_type, _, ctx, _, _ = item
            if _should_run_pr_flow({"task_type": task_type, "context": ctx}):
                pr_tasks.append(item)
            else:
                direct_tasks.append(item)

        if pr_tasks:
            for tid, cmd, tt, m, ctx, direction, has_measured_value in pr_tasks:
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
                _record_scheduler_execution(has_measured_value)
                _maybe_trigger_runner_self_update(client, log, last_task_id=tid)

        if not direct_tasks:
            if once:
                break
            time.sleep(interval)
            continue

        if workers == 1:
            tid, cmd, tt, m, ctx, direction, has_measured_value = direct_tasks[0]
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
            _record_scheduler_execution(has_measured_value)
            _maybe_trigger_runner_self_update(client, log, last_task_id=tid)
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
                    ): (tid, cmd, has_measured_value)
                    for tid, cmd, tt, m, ctx, direction, has_measured_value in direct_tasks
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
