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

TaskRunItem = tuple[str, str, str, str, dict[str, Any], str, bool]
DEFAULT_CODEX_MODEL_ALIAS_MAP = "gpt-5.3-codex-spark:gpt-5-codex,gpt-5.3-codex:gpt-5-codex"
CODEX_MODEL_ARG_RE = re.compile(r"(?P<prefix>--model\s+)(?P<model>[^\s]+)")


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
        primary_source_ref = source_refs[0] if source_refs else ""

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
    return command.strip().startswith("openclaw ")


def _uses_codex_cli(command: str) -> bool:
    return command.strip().startswith("codex ")


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
    raw = os.environ.get("AGENT_CODEX_MODEL_ALIAS_MAP", DEFAULT_CODEX_MODEL_ALIAS_MAP)
    return _parse_codex_model_alias_map(str(raw))


def _apply_codex_model_alias(command: str) -> tuple[str, dict[str, str] | None]:
    if not _uses_codex_cli(command):
        return command, None
    match = CODEX_MODEL_ARG_RE.search(command or "")
    if match is None:
        return command, None
    requested_model = match.group("model").strip()
    if not requested_model:
        return command, None
    target_model = _codex_model_alias_map().get(requested_model.lower(), "").strip()
    if not target_model or target_model.lower() == requested_model.lower():
        return command, None
    remapped = f"{command[:match.start('model')]}{target_model}{command[match.end('model'):]}"
    return remapped, {
        "requested_model": requested_model,
        "effective_model": target_model,
    }


def _infer_executor(command: str, model: str) -> str:
    s = (command or "").strip()
    model_value = (model or "").strip().lower()
    if _uses_cursor_cli(command) or model_value.startswith("cursor/"):
        return "cursor"
    if _uses_codex_cli(command):
        return "openai-codex"
    if _uses_openclaw_cli(command) or model_value.startswith("openclaw/"):
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
    env = os.environ.copy()
    codex_model_alias: dict[str, str] | None = None
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
    # Suppress Claude Code requests to unsupported local-model endpoints (GitHub #13949)
    env.setdefault("DISABLE_TELEMETRY", "1")
    env.setdefault("DISABLE_ERROR_REPORTING", "1")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    worker_id = os.environ.get("AGENT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
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

    start_time = time.monotonic()
    log.info("task=%s starting command=%s", task_id, command[:120])
    if verbose:
        print(f"Running: {command[:80]}...")

    out_file = os.path.join(LOG_DIR, f"task_{task_id}.log")
    output_lines: list[str] = []
    reader_done = threading.Event()
    alias_note = ""
    if codex_model_alias:
        alias_note = (
            "[runner-model-alias] requested_model="
            f"{codex_model_alias['requested_model']} effective_model={codex_model_alias['effective_model']}\n"
        )

    def _stream_reader(proc: subprocess.Popen) -> None:
        """Read process stdout line-by-line, write to log file + collect output."""
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(f"# task_id={task_id} status=running\n")
                f.write(f"# command={command}\n")
                f.write("---\n")
                if alias_note:
                    f.write(alias_note)
                    output_lines.append(alias_note)
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
            command,
            shell=True,
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
