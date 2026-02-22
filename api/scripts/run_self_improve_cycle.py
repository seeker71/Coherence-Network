#!/usr/bin/env python3
"""Run a model-pinned self-improvement cycle (plan -> execute -> review)."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PLAN_MODEL = "gpt-5.3-codex"
EXECUTE_MODEL = "gpt-5.3-codex-spark"
REVIEW_MODEL = "gpt-5.3-codex"
DEFAULT_LIMIT_THRESHOLD_RATIO = 0.15
USAGE_CACHE_FILE = Path(".cache/self_improve_usage_snapshot.json")
USAGE_CACHE_TTL_SECONDS = int(os.environ.get("SELF_IMPROVE_USAGE_CACHE_TTL_SECONDS", "21600"))
INPUT_ENDPOINT_TIMEOUT_SECONDS = float(os.environ.get("SELF_IMPROVE_INPUT_TIMEOUT_SECONDS", "12.0"))
HTTP_RETRY_ATTEMPTS = int(os.environ.get("SELF_IMPROVE_HTTP_RETRY_ATTEMPTS", "3"))
HTTP_RETRY_BASE_SECONDS = float(os.environ.get("SELF_IMPROVE_HTTP_RETRY_BASE_SECONDS", "0.75"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("SELF_IMPROVE_HTTP_TIMEOUT_SECONDS", "20.0"))


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _clip(text: str, max_chars: int = 12000) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "\n\n[truncated]"


def build_plan_direction() -> str:
    return (
        "You are planning a self-improvement task for this repository.\n"
        "Assume the execution model is cheap and fast, and may miss constraints unless they are explicit.\n"
        "Produce a strict, verification-first execution plan with exactly these sections: PLAN, PATCH, RUN, RESULT.\n"
        "Requirements:\n"
        "1. Every step must define concrete proof artifacts (file path, command output, or API response fields).\n"
        "2. If proof is missing or weak, require retry until proof is present or a blocker is documented.\n"
        "3. Include unblock guidance for common blockers: lint/test failures, missing env vars/secrets, stale branch/rebase conflicts,"
        " flaky CI/network errors, and missing tool dependencies.\n"
        "4. For each common blocker, provide exact unblock commands and acceptance proof.\n"
        "5. Keep scope small and deterministic; no speculative refactors.\n"
        "6. Explicitly require the executor to show proof for each completed step before moving on.\n"
        "Output only the plan content, no preamble."
    )


def build_execute_direction(plan_output: str) -> str:
    return (
        "Execute the plan below exactly and keep output deterministic.\n"
        "You are a cheap, fast executor: follow instructions literally, keep edits minimal, and provide proof for each step.\n"
        "If proof is missing for any step, retry that step until proof exists or you record a concrete blocker with unblock attempts.\n"
        "\n"
        "Plan to execute:\n"
        f"{_clip(plan_output)}\n"
        "\n"
        "Required output format (exact sections): PLAN, PATCH, RUN, RESULT.\n"
        "Under RUN and RESULT, include concrete proof artifacts for every completed step."
    )


def build_review_direction(plan_output: str, execute_output: str) -> str:
    return (
        "Review whether execution followed the plan and proof contract.\n"
        "Reject any step without concrete proof and require retry guidance.\n"
        "\n"
        "Original plan:\n"
        f"{_clip(plan_output, max_chars=8000)}\n"
        "\n"
        "Execution output:\n"
        f"{_clip(execute_output, max_chars=12000)}\n"
        "\n"
        "Return verdict with sections: PASS_FAIL, FINDINGS, REQUIRED_RETRIES, UNBLOCK_GUIDANCE.\n"
        "In UNBLOCK_GUIDANCE, include common issue playbooks (tests/lint/secrets/rebase/flaky network/dependencies)."
    )


def build_task_payload(*, direction: str, task_type: str, model_override: str) -> dict[str, Any]:
    return {
        "direction": direction,
        "task_type": task_type,
        "context": {
            "executor": "codex",
            "model_override": model_override,
            "force_paid_providers": True,
            "source": "self_improve_cycle",
        },
    }


def _safe_get(
    client: Any,
    url: str,
    *,
    timeout: float = INPUT_ENDPOINT_TIMEOUT_SECONDS,
    attempts: int = HTTP_RETRY_ATTEMPTS,
) -> tuple[bool, Any, str | None, int | None]:
    response: Any | None = None
    status_code: int | None = None
    last_error: str | None = None
    for _ in range(max(1, attempts)):
        try:
            response = client.get(url, timeout=timeout)
            status_code = response.status_code
            if status_code >= 400:
                return False, None, f"HTTP {status_code}", status_code
            return True, response.json(), None, status_code
        except Exception as exc:
            last_error = str(exc)
            time.sleep(HTTP_RETRY_BASE_SECONDS)
            response = None
    return False, None, last_error, status_code


def _safe_post(
    client: Any,
    url: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = HTTP_TIMEOUT_SECONDS,
    attempts: int = HTTP_RETRY_ATTEMPTS,
) -> tuple[bool, Any, str | None, int | None]:
    response: Any | None = None
    status_code: int | None = None
    last_error: str | None = None
    for _ in range(max(1, attempts)):
        try:
            response = client.post(url, json=json, headers=headers, timeout=timeout)
            status_code = response.status_code
            if status_code >= 400:
                return False, None, f"HTTP {status_code}", status_code
            return True, response.json(), None, status_code
        except Exception as exc:
            last_error = str(exc)
            time.sleep(HTTP_RETRY_BASE_SECONDS)
            response = None
    return False, None, last_error, status_code


def _coerce_list(value: Any, default: list[Any] | None = None) -> list[Any]:
    return list(value) if isinstance(value, list) else (list(default) if default is not None else [])


def _coerce_dict(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else (dict(default) if default is not None else {})


def _safe_cache_is_fresh(collected_at: str) -> bool:
    dt = _parse_timestamp(collected_at)
    if dt is None:
        return False
    return (datetime.now(timezone.utc) - dt).total_seconds() <= USAGE_CACHE_TTL_SECONDS


def _load_cached_usage_payload(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        if not path.exists():
            return False, {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        payload = _coerce_dict(raw)
        collected_at = str(payload.get("collected_at") or "")
        cached_payload = payload.get("payload")
        if not collected_at or not isinstance(cached_payload, dict):
            return False, {}
        if not _safe_cache_is_fresh(collected_at):
            return False, {}
        return True, _coerce_dict(cached_payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return False, {}


def _save_cached_usage_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"collected_at": _utcnow(), "payload": payload}, indent=2),
        encoding="utf-8",
    )


def _status_for_records(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "unknown").strip().lower()
        counts[status] = counts.get(status, 0) + 1
    return counts


def _collect_input_bundle(
    client: Any,
    *,
    base_url: str,
    threshold_ratio: float,
    usage_cache_path: Path,
) -> dict[str, Any]:
    usage_ok, usage_payload_raw, usage_error, usage_status_code = _safe_get(
        client,
        f"{base_url}/api/automation/usage/alerts?threshold_ratio={threshold_ratio}&force_refresh=true",
    )
    usage_payload = _coerce_dict(usage_payload_raw, {})
    usage_source = "live"

    if not usage_ok:
        cache_ok, cache_payload = _load_cached_usage_payload(usage_cache_path)
        if cache_ok:
            usage_payload = cache_payload
            usage_source = "cached"
            usage_ok = True
        else:
            usage_source = "missing"
            usage_payload = {"threshold_ratio": threshold_ratio, "alerts": []}

    if usage_source == "live" and usage_ok and usage_status_code == 200:
        _save_cached_usage_payload(usage_cache_path, usage_payload)

    task_ok, tasks_payload_raw, task_error, task_status_code = _safe_get(
        client,
        f"{base_url}/api/agent/tasks?limit=40",
    )
    task_records = _coerce_list(tasks_payload_raw, [])

    needs_decision_ok, needs_decision_payload_raw, needs_decision_error, needs_decision_status_code = _safe_get(
        client,
        f"{base_url}/api/agent/tasks?status=needs_decision&limit=20",
    )
    needs_decision_records = _coerce_list(needs_decision_payload_raw, [])

    friction_ok, friction_payload_raw, friction_error, friction_status_code = _safe_get(
        client,
        f"{base_url}/api/friction/events?status=open&limit=50",
    )
    friction_records = _coerce_list(friction_payload_raw, [])

    runtime_ok, runtime_payload_raw, runtime_error, runtime_status_code = _safe_get(
        client,
        f"{base_url}/api/runtime/endpoints/summary?limit=25",
    )
    runtime_payload = _coerce_dict(runtime_payload_raw, {})

    usage_alerts = _coerce_list(usage_payload.get("alerts"), [])
    blocking_alerts: list[dict[str, Any]] = []
    target_providers = {"openai", "openrouter", "coherence-internal"}
    for row in usage_alerts:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").strip().lower()
        remaining_ratio = row.get("remaining_ratio")
        if provider not in target_providers or remaining_ratio is None:
            continue
        try:
            ratio = float(remaining_ratio)
        except (TypeError, ValueError):
            continue
        if ratio <= threshold_ratio:
            blocking_alerts.append(
                {
                    "provider": provider,
                    "metric_id": str(row.get("metric_id") or ""),
                    "severity": str(row.get("severity") or ""),
                    "remaining_ratio": round(ratio, 6),
                    "message": str(row.get("message") or ""),
                }
            )

    data_quality_mode = "full"
    if usage_source in {"cached", "missing"}:
        data_quality_mode = "degraded_usage"
    if not task_ok or not needs_decision_ok or not friction_ok or not runtime_ok:
        data_quality_mode = "degraded_partial"

    return {
        "collected_at": _utcnow(),
        "summary": {
            "task_count": len(task_records),
            "needs_decision_count": len(needs_decision_records),
            "friction_open_count": len(friction_records),
            "runtime_endpoint_count": len(_coerce_list(runtime_payload.get("summary"), [])),
            "blocking_usage_alert_count": len(blocking_alerts),
        },
        "usage": {
            "ok": usage_ok,
            "source": usage_source,
            "payload": usage_payload,
            "error": usage_error,
            "status_code": usage_status_code,
            "threshold_ratio": threshold_ratio,
            "blocking_alerts": blocking_alerts,
            "counts": {
                "alerts_total": len(usage_alerts),
                "blocking": len(blocking_alerts),
            },
        },
        "tasks": {
            "ok": task_ok,
            "error": task_error,
            "status_code": task_status_code,
            "records": task_records[:20],
            "count": len(task_records),
            "status_counts": _status_for_records(task_records),
        },
        "needs_decision": {
            "ok": needs_decision_ok,
            "error": needs_decision_error,
            "status_code": needs_decision_status_code,
            "records": needs_decision_records,
            "count": len(needs_decision_records),
        },
        "friction": {
            "ok": friction_ok,
            "error": friction_error,
            "status_code": friction_status_code,
            "records": friction_records,
            "count": len(friction_records),
        },
        "runtime": {
            "ok": runtime_ok,
            "error": runtime_error,
            "status_code": runtime_status_code,
            "payload": runtime_payload,
        },
        "data_quality_mode": data_quality_mode,
    }


def _input_bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "data_quality_mode": bundle.get("data_quality_mode", "degraded_usage"),
        "usage_source": _coerce_dict(bundle.get("usage", {})).get("source", "missing"),
        "usage_alert_count": _coerce_dict(bundle.get("usage", {})).get("counts", {}).get("alerts_total", 0),
        "blocking_usage_alert_count": _coerce_dict(bundle.get("usage", {})).get("counts", {}).get("blocking", 0),
        "task_count": _coerce_dict(bundle.get("summary", {})).get("task_count", 0),
        "needs_decision_count": _coerce_dict(bundle.get("summary", {})).get("needs_decision_count", 0),
        "friction_open_count": _coerce_dict(bundle.get("summary", {})).get("friction_open_count", 0),
    }


def _usage_limit_precheck(bundle: dict[str, Any], threshold_ratio: float) -> dict[str, Any]:
    usage = _coerce_dict(bundle.get("usage", {}))
    blocking_alerts = _coerce_list(usage.get("blocking_alerts"), [])
    if not blocking_alerts:
        return {
            "allowed": True,
            "threshold_ratio": threshold_ratio,
            "blocking_alerts": [],
            "usage_limit_data": {
                "bundle": bundle,
                "data_quality_mode": bundle.get("data_quality_mode"),
            },
        }

    summary = "; ".join(
        f"{row['provider']}:{row['metric_id']} remaining_ratio={row['remaining_ratio']}<=threshold={threshold_ratio}"
        for row in blocking_alerts
    )
    return {
        "allowed": False,
        "threshold_ratio": threshold_ratio,
        "skip_reason": f"Usage limit precheck blocked self-improve cycle: {summary}",
        "blocking_alerts": blocking_alerts,
        "usage_limit_data": {
            "bundle": bundle,
            "data_quality_mode": bundle.get("data_quality_mode"),
        },
    }


def _build_delta_summary(
    before: dict[str, Any],
    after: dict[str, Any],
    result_status: str,
) -> dict[str, Any]:
    before_summary = _coerce_dict(before.get("summary"), {})
    after_summary = _coerce_dict(after.get("summary"), {})
    return {
        "status": result_status,
        "data_quality_mode": {
            "before": before.get("data_quality_mode", "degraded_usage"),
            "after": after.get("data_quality_mode", "degraded_usage"),
        },
        "problem": (
            f"usage_blocking={before_summary.get('blocking_usage_alert_count', 0)}; "
            f"tasks={before_summary.get('task_count', 0)}; "
            f"needs_decision={before_summary.get('needs_decision_count', 0)}; "
            f"friction={before_summary.get('friction_open_count', 0)}"
        ),
        "action": "Captured fresh runtime/task/friction bundle before and after cycle execution.",
        "proof": {
            "status": result_status,
            "before_counts": {
                "task_count": before_summary.get("task_count", 0),
                "needs_decision_count": before_summary.get("needs_decision_count", 0),
                "friction_open_count": before_summary.get("friction_open_count", 0),
            },
            "after_counts": {
                "task_count": after_summary.get("task_count", 0),
                "needs_decision_count": after_summary.get("needs_decision_count", 0),
                "friction_open_count": after_summary.get("friction_open_count", 0),
            },
        },
        "before_metrics": before_summary,
        "after_metrics": after_summary,
    }


def _submit_task(client: Any, base_url: str, payload: dict[str, Any]) -> str:
    ok, data, error, status_code = _safe_post(
        client,
        f"{base_url}/api/agent/tasks",
        json=payload,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if not ok:
        raise RuntimeError(f"task submit failed (status={status_code}) {error}")
    assert data is not None
    task_id = str(data.get("id") or "").strip()
    if not task_id:
        raise RuntimeError("Task create response missing id")
    return task_id


def _request_execute(client: Any, base_url: str, task_id: str, execute_token: str) -> None:
    headers = {}
    if execute_token:
        headers["X-Agent-Execute-Token"] = execute_token
    ok, _, error, status_code = _safe_post(
        client,
        f"{base_url}/api/agent/tasks/{task_id}/execute",
        headers=headers,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    if not ok:
        raise RuntimeError(f"execute request failed for {task_id} (status={status_code}) {error}")


def _wait_for_terminal(
    client: Any,
    *,
    base_url: str,
    task_id: str,
    poll_interval_seconds: int,
    timeout_seconds: int,
    execute_pending: bool,
    execute_token: str,
) -> dict[str, Any]:
    started = time.time()
    execute_attempted = False
    while True:
        ok, task_payload, error, status_code = _safe_get(
            client,
            f"{base_url}/api/agent/tasks/{task_id}",
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        if not ok:
            if int(time.time() - started) >= timeout_seconds:
                raise TimeoutError(
                    f"Timed out waiting for task {task_id}; last status=unknown, "
                    f"last_http_status={status_code}, error={error}"
                )
            time.sleep(max(0, poll_interval_seconds))
            continue

        task = _coerce_dict(task_payload, {})
        status = str(task.get("status") or "").strip().lower()
        if status in {"completed", "failed", "needs_decision"}:
            return task

        elapsed = int(time.time() - started)
        if execute_pending and status == "pending" and not execute_attempted:
            _request_execute(client, base_url, task_id, execute_token)
            execute_attempted = True

        if elapsed >= timeout_seconds:
            raise TimeoutError(f"Timed out waiting for task {task_id}; last status={status or 'unknown'}")
        time.sleep(max(0, poll_interval_seconds))


def _run_stage(
    *,
    client: Any,
    base_url: str,
    poll_interval_seconds: int,
    timeout_seconds: int,
    execute_pending: bool,
    execute_token: str,
    stage_name: str,
    direction: str,
    task_type: str,
    model_override: str,
) -> dict[str, Any]:
    payload = build_task_payload(
        direction=direction,
        task_type=task_type,
        model_override=model_override,
    )
    task_id = _submit_task(client, base_url, payload)
    task = _wait_for_terminal(
        client,
        base_url=base_url,
        task_id=task_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        execute_pending=execute_pending,
        execute_token=execute_token,
    )
    task_ctx = task.get("context") if isinstance(task.get("context"), dict) else {}
    return {
        "stage": stage_name,
        "task_id": task_id,
        "status": str(task.get("status") or ""),
        "executor": str(task_ctx.get("executor") or ""),
        "model": str(task.get("model") or ""),
        "task": task,
        "output": str(task.get("output") or ""),
    }


def run_cycle(
    *,
    client: Any,
    base_url: str,
    poll_interval_seconds: int,
    timeout_seconds: int,
    execute_pending: bool,
    execute_token: str,
    usage_threshold_ratio: float,
    usage_cache_path: str = str(USAGE_CACHE_FILE),
) -> dict[str, Any]:
    threshold_ratio = max(0.0, min(1.0, float(usage_threshold_ratio)))
    input_bundle_before = _collect_input_bundle(
        client,
        base_url=base_url,
        threshold_ratio=threshold_ratio,
        usage_cache_path=Path(usage_cache_path),
    )

    precheck = _usage_limit_precheck(input_bundle_before, threshold_ratio=threshold_ratio)
    if not precheck.get("allowed"):
        return {
            "status": "skipped",
            "skip_reason": precheck.get("skip_reason"),
            "usage_limit_precheck": precheck,
            "data_quality_mode": input_bundle_before.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_before),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_before,
            "stages": [],
            "delta_summary": _build_delta_summary(
                input_bundle_before,
                input_bundle_before,
                "skipped",
            ),
        }

    stages: list[dict[str, Any]] = []

    try:
        plan_stage = _run_stage(
            client=client,
            base_url=base_url,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            execute_pending=execute_pending,
            execute_token=execute_token,
            stage_name="plan",
            direction=build_plan_direction(),
            task_type="spec",
            model_override=PLAN_MODEL,
        )
    except Exception as exc:
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "plan_submit_or_wait",
            "failure_error": str(exc),
            "stages": stages,
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }
    stages.append(plan_stage)
    plan_output = str(plan_stage.get("output") or "")
    plan_task = plan_stage["task"]
    if plan_task.get("status") != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "plan",
            "stages": stages,
            "task": plan_task,
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }

    try:
        execute_stage = _run_stage(
            client=client,
            base_url=base_url,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            execute_pending=execute_pending,
            execute_token=execute_token,
            stage_name="execute",
            direction=build_execute_direction(plan_stage.get("output", "")),
            task_type="impl",
            model_override=EXECUTE_MODEL,
        )
    except Exception as exc:
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "execute_submit_or_wait",
            "stages": stages,
            "failure_error": str(exc),
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }
    stages.append(execute_stage)
    execute_output = str(execute_stage.get("output") or "")
    execute_task = execute_stage["task"]
    if execute_stage.get("status") != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "execute",
            "stages": stages,
            "task": execute_task,
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }

    try:
        review_stage = _run_stage(
            client=client,
            base_url=base_url,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            execute_pending=execute_pending,
            execute_token=execute_token,
            stage_name="review",
            direction=build_review_direction(plan_stage["output"], execute_stage["output"]),
            task_type="review",
            model_override=REVIEW_MODEL,
        )
    except Exception as exc:
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "review_submit_or_wait",
            "stages": stages,
            "failure_error": str(exc),
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }
    stages.append(review_stage)
    review_output = str(review_stage.get("output") or "")
    review_task = review_stage["task"]
    if review_task.get("status") != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        return {
            "status": "failed",
            "failed_stage": "review",
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
            "stages": stages,
            "task": review_task,
        }

    input_bundle_after = _collect_input_bundle(
        client,
        base_url=base_url,
        threshold_ratio=threshold_ratio,
        usage_cache_path=Path(usage_cache_path),
    )
    return {
        "status": "completed",
        "usage_limit_precheck": precheck,
        "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
        "input_bundle": _input_bundle_summary(input_bundle_after),
        "input_bundle_before": input_bundle_before,
        "input_bundle_after": input_bundle_after,
        "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "completed"),
        "stages": stages,
        "outputs": {
            "plan": _clip(plan_output, max_chars=2000),
            "execute": _clip(execute_output, max_chars=2000),
            "review": _clip(review_output, max_chars=2000),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scheduled self-improve cycle")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SELF_IMPROVE_API_URL") or os.environ.get("API_URL") or "http://127.0.0.1:8000",
        help="Agent API base URL",
    )
    parser.add_argument("--poll-interval-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--execute-pending", action="store_true", help="Call /execute when a task remains pending")
    parser.add_argument("--execute-token", default=os.environ.get("AGENT_EXECUTE_TOKEN", ""))
    parser.add_argument(
        "--usage-threshold-ratio",
        type=float,
        default=float(os.environ.get("SELF_IMPROVE_USAGE_THRESHOLD_RATIO", DEFAULT_LIMIT_THRESHOLD_RATIO)),
        help="Skip the run when provider remaining_ratio is <= threshold for usage-limit alerts",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--usage-cache-file",
        default=str(USAGE_CACHE_FILE),
        help="Path to local usage snapshot cache file",
    )
    parser.add_argument(
        "--infra-preflight-attempts",
        type=int,
        default=int(os.environ.get("SELF_IMPROVE_INFRA_PREFLIGHT_ATTEMPTS", "5")),
        help="Legacy option retained for workflow compatibility",
    )
    parser.add_argument(
        "--infra-preflight-consecutive-successes",
        type=int,
        default=int(os.environ.get("SELF_IMPROVE_INFRA_PREFLIGHT_CONSECUTIVE_SUCCESSES", "2")),
        help="Legacy option retained for workflow compatibility",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        report = run_cycle(
            client=client,
            base_url=base_url,
            poll_interval_seconds=max(0, args.poll_interval_seconds),
            timeout_seconds=max(10, args.timeout_seconds),
            execute_pending=args.execute_pending,
            execute_token=args.execute_token,
            usage_threshold_ratio=args.usage_threshold_ratio,
            usage_cache_path=args.usage_cache_file,
        )

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"status={report.get('status')}")
        for row in report.get("stages", []):
            print(f"- {row.get('stage')}: task={row.get('task_id')} status={row.get('status')}")

    return 0 if report.get("status") in {"completed", "skipped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
