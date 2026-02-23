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
STAGE_SUBMIT_ATTEMPTS = int(os.environ.get("SELF_IMPROVE_STAGE_SUBMIT_ATTEMPTS", "4"))
STAGE_SUBMIT_RETRY_BASE_SECONDS = float(os.environ.get("SELF_IMPROVE_STAGE_SUBMIT_RETRY_BASE_SECONDS", "2.0"))
CHECKPOINT_FILE = Path(".cache/self_improve_cycle_checkpoint.json")
CHECKPOINT_MAX_AGE_SECONDS = int(os.environ.get("SELF_IMPROVE_CHECKPOINT_MAX_AGE_SECONDS", "172800"))
INFRA_PREFLIGHT_SLEEP_SECONDS = int(os.environ.get("SELF_IMPROVE_INFRA_PREFLIGHT_SLEEP_SECONDS", "20"))
AGENT_TASK_DIRECTION_MAX_CHARS = int(os.environ.get("SELF_IMPROVE_AGENT_TASK_DIRECTION_MAX_CHARS", "5000"))
AGENT_TASK_DIRECTION_SAFE_CHARS = max(400, AGENT_TASK_DIRECTION_MAX_CHARS - 300)
AGENT_TASK_DIRECTION_422_RETRY_CHARS = max(300, AGENT_TASK_DIRECTION_SAFE_CHARS - 600)
TASK_DIRECTION_TRUNCATION_NOTE = "[truncated to fit task direction limit]"
SELF_IMPROVE_RUNNER_CODEX_AUTH_MODE = str(
    os.environ.get("SELF_IMPROVE_RUNNER_CODEX_AUTH_MODE", "api_key")
).strip().lower() or "api_key"

STAGE_SPECS = {
    "plan": {"task_type": "spec", "model": PLAN_MODEL},
    "execute": {"task_type": "impl", "model": EXECUTE_MODEL},
    "review": {"task_type": "review", "model": REVIEW_MODEL},
}


def _is_infra_error(message: str) -> bool:
    lowered = (message or "").lower()
    return (
        "read operation timed out" in lowered
        or "timed out" in lowered
        or "status=none" in lowered
        or "connection" in lowered
    )


def _maybe_blocked_report(failed_stage: str, exc: Exception, bundle: dict[str, Any]) -> dict[str, Any]:
    msg = str(exc)
    if _is_infra_error(msg):
        return {
            "status": "infra_blocked",
            "failed_stage": failed_stage,
            "failure_error": msg,
            "stages": [],
            "data_quality_mode": bundle.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(bundle),
            "input_bundle_before": bundle,
            "input_bundle_after": bundle,
            "delta_summary": _build_delta_summary(bundle, bundle, "infra_blocked"),
        }
    raise


def _awareness_reflection(
    *,
    status: str,
    failed_stage: str | None,
    failure_error: str | None,
    data_quality_mode: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "failed_stage": failed_stage or "",
        "failure_error": failure_error or "",
        "data_quality_mode": data_quality_mode or "",
        "questions": [
            "What was I not aware of that contributed to this failure?",
            "What should I be aware of next time and why?",
            "How will I verify that this mistake is less likely to repeat?",
        ],
    }


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


def _fit_task_direction(direction: str, *, max_chars: int = AGENT_TASK_DIRECTION_SAFE_CHARS) -> str:
    text = str(direction or "")
    safe_max = max(120, max_chars)
    if len(text) <= safe_max:
        return text
    suffix = f"\n\n{TASK_DIRECTION_TRUNCATION_NOTE}"
    keep = max(1, safe_max - len(suffix))
    return text[:keep] + suffix


def _is_http_status_error(exc: Exception, status_code: int) -> bool:
    message = str(exc or "").lower()
    return f"status={status_code}" in message or f"http {status_code}" in message


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
        "7. Intent first: state what is being optimized for (trust, clarity, reuse), not only completion.\n"
        "8. System-level lens: explain expected behavior change in the running system, not just file deltas.\n"
        "9. Option thinking: include 2-3 approaches, pick one, and justify long-term tradeoff.\n"
        "10. Failure anticipation: include how the solution could degrade in two weeks and what guardrails detect it.\n"
        "11. Proof of meaning: define why this is better for humans/operators, not only that commands passed.\n"
        "12. Maintainability guidance: use quality-awareness signals (hotspots + recommendations) to reduce code drift.\n"
        "Output only the plan content, no preamble."
    )


def build_execute_direction(plan_output: str) -> str:
    return (
        "Execute the plan below exactly and keep output deterministic.\n"
        "You are a cheap, fast executor: follow instructions literally, keep edits minimal, and provide proof for each step.\n"
        "If proof is missing for any step, retry that step until proof exists or you record a concrete blocker with unblock attempts.\n"
        "Keep intent/system/options/failure/meaning/maintainability commitments from the plan explicit in the RESULT section.\n"
        "\n"
        "Plan to execute:\n"
        f"{_clip(plan_output, max_chars=3200)}\n"
        "\n"
        "Required output format (exact sections): PLAN, PATCH, RUN, RESULT.\n"
        "Under RUN and RESULT, include concrete proof artifacts for every completed step."
    )


def build_review_direction(plan_output: str, execute_output: str) -> str:
    return (
        "Review whether execution followed the plan and proof contract.\n"
        "Reject any step without concrete proof and require retry guidance.\n"
        "Confirm intent, system behavior change, options rationale, failure guardrails, proof-of-meaning, "
        "and maintainability drift guidance are present.\n"
        "\n"
        "Original plan:\n"
        f"{_clip(plan_output, max_chars=1800)}\n"
        "\n"
        "Execution output:\n"
        f"{_clip(execute_output, max_chars=1800)}\n"
        "\n"
        "Return verdict with sections: PASS_FAIL, FINDINGS, REQUIRED_RETRIES, UNBLOCK_GUIDANCE.\n"
        "In UNBLOCK_GUIDANCE, include common issue playbooks (tests/lint/secrets/rebase/flaky network/dependencies)."
    )


def build_task_payload(*, direction: str, task_type: str, model_override: str) -> dict[str, Any]:
    bounded_direction = _fit_task_direction(direction, max_chars=AGENT_TASK_DIRECTION_SAFE_CHARS)
    return {
        "direction": bounded_direction,
        "task_type": task_type,
        "context": {
            "executor": "codex",
            "model_override": model_override,
            "force_paid_providers": True,
            "runner_codex_auth_mode": "api_key",
            "source": "self_improve_cycle",
            "runner_codex_auth_mode": SELF_IMPROVE_RUNNER_CODEX_AUTH_MODE,
        },
    }


def _safe_get(
    client: Any,
    url: str,
    *,
    timeout: float = INPUT_ENDPOINT_TIMEOUT_SECONDS,
    attempts: int = HTTP_RETRY_ATTEMPTS,
    headers: dict[str, str] | None = None,
) -> tuple[bool, Any, str | None, int | None]:
    response: Any | None = None
    status_code: int | None = None
    last_error: str | None = None
    for _ in range(max(1, attempts)):
        try:
            if headers:
                response = client.get(url, timeout=timeout, headers=headers)
            else:
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


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "records", "items", "results", "data", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        payload = _coerce_dict(raw)
        updated_at = str(payload.get("updated_at") or "")
        if updated_at:
            dt = _parse_timestamp(updated_at)
            if dt is not None:
                age = (datetime.now(timezone.utc) - dt).total_seconds()
                if age > CHECKPOINT_MAX_AGE_SECONDS:
                    return {}
        return payload
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _stage_checkpoint_view(stage: dict[str, Any]) -> dict[str, Any]:
    task = stage.get("task") if isinstance(stage.get("task"), dict) else {}
    return {
        "stage": str(stage.get("stage") or ""),
        "task_id": str(stage.get("task_id") or ""),
        "status": str(stage.get("status") or ""),
        "executor": str(stage.get("executor") or ""),
        "model": str(stage.get("model") or ""),
        "output": str(stage.get("output") or ""),
        "task": task,
        "resumed": bool(stage.get("resumed", False)),
        "resume_source": str(stage.get("resume_source") or ""),
    }


def _restore_stage_from_checkpoint(checkpoint: dict[str, Any], stage_name: str) -> dict[str, Any] | None:
    stages = checkpoint.get("stages")
    if not isinstance(stages, list):
        return None
    for row in stages:
        if not isinstance(row, dict):
            continue
        if str(row.get("stage") or "").strip().lower() != stage_name:
            continue
        status = str(row.get("status") or "").strip().lower()
        output = str(row.get("output") or "")
        if status != "completed":
            continue
        if stage_name in {"plan", "execute"} and not output:
            continue
        model = str(row.get("model") or "")
        expected_model = STAGE_SPECS[stage_name]["model"]
        if model and model != expected_model:
            continue
        restored = dict(row)
        restored["resumed"] = True
        restored["resume_source"] = "checkpoint"
        return restored
    return None


def _infer_stage_name(task: dict[str, Any]) -> str | None:
    task_type = str(task.get("task_type") or "").strip().lower()
    model = str(task.get("model") or "")
    context = _coerce_dict(task.get("context"), {})
    if not model:
        model = str(context.get("model_override") or "")

    if task_type == "spec" and model == PLAN_MODEL:
        return "plan"
    if task_type == "impl" and model == EXECUTE_MODEL:
        return "execute"
    if task_type == "review" and model == REVIEW_MODEL:
        return "review"
    return None


def _restore_stage_from_input_bundle(bundle: dict[str, Any], stage_name: str) -> dict[str, Any] | None:
    task_rows = _extract_records(_coerce_dict(bundle.get("tasks"), {}).get("records"))
    for task in task_rows:
        if _infer_stage_name(task) != stage_name:
            continue
        context = _coerce_dict(task.get("context"), {})
        if str(context.get("source") or "") != "self_improve_cycle":
            continue
        status = str(task.get("status") or "").strip().lower()
        output = str(task.get("output") or "")
        if status != "completed":
            continue
        if stage_name in {"plan", "execute"} and not output:
            continue
        restored = {
            "stage": stage_name,
            "task_id": str(task.get("id") or ""),
            "status": str(task.get("status") or ""),
            "executor": str(context.get("executor") or "codex"),
            "model": str(task.get("model") or context.get("model_override") or ""),
            "task": task,
            "output": output,
            "resumed": True,
            "resume_source": "recent_tasks",
        }
        return restored
    return None


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
    task_records = _extract_records(tasks_payload_raw)

    needs_decision_ok, needs_decision_payload_raw, needs_decision_error, needs_decision_status_code = _safe_get(
        client,
        f"{base_url}/api/agent/tasks?status=needs_decision&limit=20",
    )
    needs_decision_records = _extract_records(needs_decision_payload_raw)

    friction_ok, friction_payload_raw, friction_error, friction_status_code = _safe_get(
        client,
        f"{base_url}/api/friction/events?status=open&limit=50",
    )
    friction_records = _extract_records(friction_payload_raw)

    runtime_ok, runtime_payload_raw, runtime_error, runtime_status_code = _safe_get(
        client,
        f"{base_url}/api/runtime/endpoints/summary?limit=25",
    )
    runtime_payload = _coerce_dict(runtime_payload_raw, {})
    if isinstance(runtime_payload_raw, list):
        runtime_payload = {"summary": runtime_payload_raw}
    daily_summary_ok, daily_summary_payload_raw, daily_summary_error, daily_summary_status_code = _safe_get(
        client,
        f"{base_url}/api/automation/usage/daily-summary?window_hours=24&top_n=5",
    )
    daily_summary_payload = _coerce_dict(daily_summary_payload_raw, {})
    quality_awareness = _coerce_dict(daily_summary_payload.get("quality_awareness"), {})
    quality_summary = _coerce_dict(quality_awareness.get("summary"), {})
    quality_hotspots = _coerce_list(quality_awareness.get("hotspots"), [])
    quality_guidance = _coerce_list(quality_awareness.get("guidance"), [])

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
    if not task_ok or not needs_decision_ok or not friction_ok or not runtime_ok or not daily_summary_ok:
        data_quality_mode = "degraded_partial"

    return {
        "collected_at": _utcnow(),
        "summary": {
            "task_count": len(task_records),
            "needs_decision_count": len(needs_decision_records),
            "friction_open_count": len(friction_records),
            "runtime_endpoint_count": len(_coerce_list(runtime_payload.get("summary"), [])),
            "blocking_usage_alert_count": len(blocking_alerts),
            "quality_hotspot_count": len(quality_hotspots),
            "quality_guidance_count": len(quality_guidance),
            "quality_severity": str(quality_summary.get("severity") or "unknown"),
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
        "daily_summary": {
            "ok": daily_summary_ok,
            "error": daily_summary_error,
            "status_code": daily_summary_status_code,
            "payload": daily_summary_payload,
        },
        "quality_awareness": {
            "status": str(quality_awareness.get("status") or "unavailable"),
            "summary": quality_summary,
            "hotspots": quality_hotspots[:10],
            "guidance": quality_guidance[:8],
            "recommended_tasks": _coerce_list(quality_awareness.get("recommended_tasks"), [])[:5],
        },
        "data_quality_mode": data_quality_mode,
    }


def _input_bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    summary = _coerce_dict(bundle.get("summary", {}))
    return {
        "data_quality_mode": bundle.get("data_quality_mode", "degraded_usage"),
        "usage_source": _coerce_dict(bundle.get("usage", {})).get("source", "missing"),
        "usage_alert_count": _coerce_dict(bundle.get("usage", {})).get("counts", {}).get("alerts_total", 0),
        "blocking_usage_alert_count": _coerce_dict(bundle.get("usage", {})).get("counts", {}).get("blocking", 0),
        "task_count": summary.get("task_count", 0),
        "needs_decision_count": summary.get("needs_decision_count", 0),
        "friction_open_count": summary.get("friction_open_count", 0),
        "quality_hotspot_count": summary.get("quality_hotspot_count", 0),
        "quality_guidance_count": summary.get("quality_guidance_count", 0),
        "quality_severity": summary.get("quality_severity", "unknown"),
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
            f"friction={before_summary.get('friction_open_count', 0)}; "
            f"quality_hotspots={before_summary.get('quality_hotspot_count', 0)}"
        ),
        "action": "Captured fresh runtime/task/friction bundle before and after cycle execution.",
        "proof": {
            "status": result_status,
            "before_counts": {
                "task_count": before_summary.get("task_count", 0),
                "needs_decision_count": before_summary.get("needs_decision_count", 0),
                "friction_open_count": before_summary.get("friction_open_count", 0),
                "quality_hotspot_count": before_summary.get("quality_hotspot_count", 0),
            },
            "after_counts": {
                "task_count": after_summary.get("task_count", 0),
                "needs_decision_count": after_summary.get("needs_decision_count", 0),
                "friction_open_count": after_summary.get("friction_open_count", 0),
                "quality_hotspot_count": after_summary.get("quality_hotspot_count", 0),
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


def _submit_task_with_retry(
    client: Any,
    *,
    base_url: str,
    payload: dict[str, Any],
    attempts: int = STAGE_SUBMIT_ATTEMPTS,
) -> str:
    safe_attempts = max(1, attempts)
    last_error: Exception | None = None
    for attempt in range(1, safe_attempts + 1):
        try:
            return _submit_task(client, base_url, payload)
        except Exception as exc:
            last_error = exc
            if attempt >= safe_attempts or not _is_infra_error(str(exc)):
                raise
            time.sleep(STAGE_SUBMIT_RETRY_BASE_SECONDS * attempt)
    if last_error is not None:
        raise RuntimeError(f"task submit failed after {safe_attempts} attempts: {last_error}")
    raise RuntimeError(f"task submit failed after {safe_attempts} attempts")


def _request_execute(client: Any, base_url: str, task_id: str, execute_token: str) -> bool:
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
        # In hosted production, tasks can auto-execute without this endpoint.
        # Treat auth/conflict responses as non-fatal to avoid false infra failures.
        if status_code in {401, 403, 409}:
            return False
        raise RuntimeError(f"execute request failed for {task_id} (status={status_code}) {error}")
    return True


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
    submit_payload = payload
    try:
        task_id = _submit_task_with_retry(client, base_url=base_url, payload=submit_payload)
    except Exception as exc:
        if not _is_http_status_error(exc, 422):
            raise
        compacted_payload = dict(submit_payload)
        compacted_payload["direction"] = _fit_task_direction(
            str(submit_payload.get("direction") or ""),
            max_chars=AGENT_TASK_DIRECTION_422_RETRY_CHARS,
        )
        task_id = _submit_task_with_retry(client, base_url=base_url, payload=compacted_payload)
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


def _check_active_public_deploy(client: Any) -> tuple[bool, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY", "seeker71/Coherence-Network")
    if not token:
        return False, "token_missing"
    ok, payload, error, _ = _safe_get(
        client,
        f"https://api.github.com/repos/{repo}/actions/workflows/public-deploy-contract.yml/runs?per_page=5",
        timeout=10.0,
        attempts=1,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if not ok:
        return False, f"github_api_error:{error}"
    runs = _extract_records(_coerce_dict(payload).get("workflow_runs"))
    active = [row for row in runs if str(row.get("status") or "").lower() in {"queued", "in_progress"}]
    if not active:
        return False, "none"
    urls = [str(row.get("html_url") or "") for row in active][:2]
    return True, ";".join([u for u in urls if u])


def _infra_preflight(
    *,
    client: Any,
    base_url: str,
    usage_threshold_ratio: float,
    usage_cache_path: Path,
    attempts: int,
    consecutive_successes: int,
) -> dict[str, Any]:
    safe_attempts = max(1, attempts)
    required_streak = max(1, consecutive_successes)
    streak = 0
    history: list[dict[str, Any]] = []
    last_bundle: dict[str, Any] | None = None
    for attempt in range(1, safe_attempts + 1):
        deploy_active, deploy_detail = _check_active_public_deploy(client)
        health_ok, _, health_error, health_status = _safe_get(
            client,
            f"{base_url}/api/health",
            timeout=10.0,
            attempts=1,
        )
        gate_ok, _, gate_error, gate_status = _safe_get(
            client,
            f"{base_url}/api/gates/main-head",
            timeout=10.0,
            attempts=1,
        )
        tasks_ok, _, tasks_error, tasks_status = _safe_get(
            client,
            f"{base_url}/api/agent/tasks?limit=1",
            timeout=8.0,
            attempts=1,
        )
        runtime_ok, _, runtime_error, runtime_status = _safe_get(
            client,
            f"{base_url}/api/runtime/endpoints/summary?limit=1",
            timeout=8.0,
            attempts=1,
        )
        bundle = {
            "data_quality_mode": "full" if tasks_ok and runtime_ok else "degraded_partial",
            "summary": {
                "task_count": 0,
                "needs_decision_count": 0,
                "friction_open_count": 0,
                "runtime_endpoint_count": 0,
                "blocking_usage_alert_count": 0,
            },
            "usage": {"source": "missing", "counts": {"alerts_total": 0, "blocking": 0}},
            "tasks": {
                "ok": tasks_ok,
                "error": tasks_error,
                "status_code": tasks_status,
                "records": [],
                "count": 0,
                "status_counts": {},
            },
            "runtime": {
                "ok": runtime_ok,
                "error": runtime_error,
                "status_code": runtime_status,
                "payload": {},
            },
            "needs_decision": {"ok": False, "error": "", "status_code": None, "records": [], "count": 0},
            "friction": {"ok": False, "error": "", "status_code": None, "records": [], "count": 0},
        }
        last_bundle = bundle
        # Only block preflight on deploy/core health instability.
        ready = bool(health_ok and gate_ok and not deploy_active)
        if ready:
            streak += 1
        else:
            streak = 0

        history.append(
            {
                "attempt": attempt,
                "ok": ready,
                "streak": streak,
                "deploy_active": deploy_active,
                "deploy_detail": deploy_detail,
                "health_ok": health_ok,
                "health_status": health_status,
                "health_error": health_error or "",
                "gates_ok": gate_ok,
                "gates_status": gate_status,
                "gates_error": gate_error or "",
                "tasks_ok": tasks_ok,
                "tasks_status": tasks_status,
                "tasks_error": tasks_error or "",
                "runtime_ok": runtime_ok,
                "runtime_status": runtime_status,
                "runtime_error": runtime_error or "",
                "data_quality_mode": str(bundle.get("data_quality_mode") or ""),
            }
        )
        if streak >= required_streak:
            return {
                "allowed": True,
                "history": history,
                "required_consecutive_successes": required_streak,
                "attempts": safe_attempts,
                "last_bundle": bundle,
            }

        if attempt < safe_attempts:
            sleep_seconds = max(5, INFRA_PREFLIGHT_SLEEP_SECONDS)
            if deploy_active:
                sleep_seconds = max(sleep_seconds, 30)
            time.sleep(sleep_seconds)

    preflight_error = "infra_not_settled_or_deploy_active"
    if history and all(not bool(row.get("deploy_active")) for row in history):
        preflight_error = "infra_core_health_unstable"
    return {
        "allowed": False,
        "history": history,
        "required_consecutive_successes": required_streak,
        "attempts": safe_attempts,
        "preflight_error": preflight_error,
        "last_bundle": last_bundle or {},
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
    checkpoint_path: str | None = None,
) -> dict[str, Any]:
    threshold_ratio = max(0.0, min(1.0, float(usage_threshold_ratio)))
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else None
    checkpoint_state = _load_checkpoint(checkpoint_file) if checkpoint_file else {}
    input_bundle_before = _collect_input_bundle(
        client,
        base_url=base_url,
        threshold_ratio=threshold_ratio,
        usage_cache_path=Path(usage_cache_path),
    )

    def persist_state(*, status: str, stages: list[dict[str, Any]], failure_error: str = "") -> None:
        if checkpoint_file is None:
            return
        checkpoint_payload = {
            "updated_at": _utcnow(),
            "status": status,
            "base_url": base_url,
            "failure_error": failure_error,
            "stages": [_stage_checkpoint_view(stage) for stage in stages],
        }
        _save_checkpoint(checkpoint_file, checkpoint_payload)

    precheck = _usage_limit_precheck(input_bundle_before, threshold_ratio=threshold_ratio)
    if not precheck.get("allowed"):
        report = {
            "status": "skipped",
            "skip_reason": precheck.get("skip_reason"),
            "usage_limit_precheck": precheck,
            "data_quality_mode": input_bundle_before.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_before),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_before,
            "stages": [],
            "awareness_reflection": _awareness_reflection(
                status="skipped",
                failed_stage="usage_limit_precheck",
                failure_error=str(precheck.get("skip_reason") or ""),
                data_quality_mode=str(input_bundle_before.get("data_quality_mode") or ""),
            ),
            "delta_summary": _build_delta_summary(
                input_bundle_before,
                input_bundle_before,
                "skipped",
            ),
        }
        persist_state(status="skipped", stages=[], failure_error=str(report.get("skip_reason") or ""))
        return report

    stages: list[dict[str, Any]] = []

    plan_stage = _restore_stage_from_checkpoint(checkpoint_state, "plan")
    if plan_stage is None:
        plan_stage = _restore_stage_from_input_bundle(input_bundle_before, "plan")
    if plan_stage is None:
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
            if _is_infra_error(str(exc)):
                report = {
                    "status": "infra_blocked",
                    "failed_stage": "plan_submit_or_wait",
                    "failure_error": str(exc),
                    "stages": stages,
                    "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                    "input_bundle": _input_bundle_summary(input_bundle_after),
                    "input_bundle_before": input_bundle_before,
                    "input_bundle_after": input_bundle_after,
                    "awareness_reflection": _awareness_reflection(
                        status="infra_blocked",
                        failed_stage="plan_submit_or_wait",
                        failure_error=str(exc),
                        data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                    ),
                    "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "infra_blocked"),
                }
                persist_state(status="infra_blocked", stages=stages, failure_error=str(exc))
                return report
            report = {
                "status": "failed",
                "failed_stage": "plan_submit_or_wait",
                "failure_error": str(exc),
                "stages": stages,
                "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                "input_bundle": _input_bundle_summary(input_bundle_after),
                "input_bundle_before": input_bundle_before,
                "input_bundle_after": input_bundle_after,
                "awareness_reflection": _awareness_reflection(
                    status="failed",
                    failed_stage="plan_submit_or_wait",
                    failure_error=str(exc),
                    data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                ),
                "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
            }
            persist_state(status="failed", stages=stages, failure_error=str(exc))
            return report

    stages.append(plan_stage)
    persist_state(status="running", stages=stages)
    plan_output = str(plan_stage.get("output") or "")
    plan_task = plan_stage["task"]
    if str(plan_task.get("status") or "").lower() != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        report = {
            "status": "failed",
            "failed_stage": "plan",
            "stages": stages,
            "task": plan_task,
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "awareness_reflection": _awareness_reflection(
                status="failed",
                failed_stage="plan",
                failure_error="plan task did not complete",
                data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
            ),
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }
        persist_state(status="failed", stages=stages, failure_error="plan task did not complete")
        return report

    execute_stage = _restore_stage_from_checkpoint(checkpoint_state, "execute")
    if execute_stage is None:
        execute_stage = _restore_stage_from_input_bundle(input_bundle_before, "execute")
    if execute_stage is None:
        try:
            execute_stage = _run_stage(
                client=client,
                base_url=base_url,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
                execute_pending=execute_pending,
                execute_token=execute_token,
                stage_name="execute",
                direction=build_execute_direction(plan_output),
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
            if _is_infra_error(str(exc)):
                report = {
                    "status": "infra_blocked",
                    "failed_stage": "execute_submit_or_wait",
                    "stages": stages,
                    "failure_error": str(exc),
                    "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                    "input_bundle": _input_bundle_summary(input_bundle_after),
                    "input_bundle_before": input_bundle_before,
                    "input_bundle_after": input_bundle_after,
                    "awareness_reflection": _awareness_reflection(
                        status="infra_blocked",
                        failed_stage="execute_submit_or_wait",
                        failure_error=str(exc),
                        data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                    ),
                    "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "infra_blocked"),
                }
                persist_state(status="infra_blocked", stages=stages, failure_error=str(exc))
                return report
            report = {
                "status": "failed",
                "failed_stage": "execute_submit_or_wait",
                "stages": stages,
                "failure_error": str(exc),
                "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                "input_bundle": _input_bundle_summary(input_bundle_after),
                "input_bundle_before": input_bundle_before,
                "input_bundle_after": input_bundle_after,
                "awareness_reflection": _awareness_reflection(
                    status="failed",
                    failed_stage="execute_submit_or_wait",
                    failure_error=str(exc),
                    data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                ),
                "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
            }
            persist_state(status="failed", stages=stages, failure_error=str(exc))
            return report

    stages.append(execute_stage)
    persist_state(status="running", stages=stages)
    execute_output = str(execute_stage.get("output") or "")
    execute_task = execute_stage["task"]
    if str(execute_stage.get("status") or "").lower() != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        report = {
            "status": "failed",
            "failed_stage": "execute",
            "stages": stages,
            "task": execute_task,
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "awareness_reflection": _awareness_reflection(
                status="failed",
                failed_stage="execute",
                failure_error="execute task did not complete",
                data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
            ),
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
        }
        persist_state(status="failed", stages=stages, failure_error="execute task did not complete")
        return report

    review_stage = _restore_stage_from_checkpoint(checkpoint_state, "review")
    if review_stage is None:
        review_stage = _restore_stage_from_input_bundle(input_bundle_before, "review")
    if review_stage is None:
        try:
            review_stage = _run_stage(
                client=client,
                base_url=base_url,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
                execute_pending=execute_pending,
                execute_token=execute_token,
                stage_name="review",
                direction=build_review_direction(plan_output, execute_output),
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
            if _is_infra_error(str(exc)):
                report = {
                    "status": "infra_blocked",
                    "failed_stage": "review_submit_or_wait",
                    "stages": stages,
                    "failure_error": str(exc),
                    "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                    "input_bundle": _input_bundle_summary(input_bundle_after),
                    "input_bundle_before": input_bundle_before,
                    "input_bundle_after": input_bundle_after,
                    "awareness_reflection": _awareness_reflection(
                        status="infra_blocked",
                        failed_stage="review_submit_or_wait",
                        failure_error=str(exc),
                        data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                    ),
                    "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "infra_blocked"),
                }
                persist_state(status="infra_blocked", stages=stages, failure_error=str(exc))
                return report
            report = {
                "status": "failed",
                "failed_stage": "review_submit_or_wait",
                "stages": stages,
                "failure_error": str(exc),
                "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
                "input_bundle": _input_bundle_summary(input_bundle_after),
                "input_bundle_before": input_bundle_before,
                "input_bundle_after": input_bundle_after,
                "awareness_reflection": _awareness_reflection(
                    status="failed",
                    failed_stage="review_submit_or_wait",
                    failure_error=str(exc),
                    data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
                ),
                "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
            }
            persist_state(status="failed", stages=stages, failure_error=str(exc))
            return report

    stages.append(review_stage)
    persist_state(status="running", stages=stages)
    review_output = str(review_stage.get("output") or "")
    review_task = review_stage["task"]
    if str(review_task.get("status") or "").lower() != "completed":
        input_bundle_after = _collect_input_bundle(
            client,
            base_url=base_url,
            threshold_ratio=threshold_ratio,
            usage_cache_path=Path(usage_cache_path),
        )
        report = {
            "status": "failed",
            "failed_stage": "review",
            "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
            "input_bundle": _input_bundle_summary(input_bundle_after),
            "input_bundle_before": input_bundle_before,
            "input_bundle_after": input_bundle_after,
            "awareness_reflection": _awareness_reflection(
                status="failed",
                failed_stage="review",
                failure_error="review task did not complete",
                data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
            ),
            "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "failed"),
            "stages": stages,
            "task": review_task,
        }
        persist_state(status="failed", stages=stages, failure_error="review task did not complete")
        return report

    input_bundle_after = _collect_input_bundle(
        client,
        base_url=base_url,
        threshold_ratio=threshold_ratio,
        usage_cache_path=Path(usage_cache_path),
    )
    report = {
        "status": "completed",
        "usage_limit_precheck": precheck,
        "data_quality_mode": input_bundle_after.get("data_quality_mode", "degraded_usage"),
        "input_bundle": _input_bundle_summary(input_bundle_after),
        "input_bundle_before": input_bundle_before,
        "input_bundle_after": input_bundle_after,
        "awareness_reflection": _awareness_reflection(
            status="completed",
            failed_stage="",
            failure_error="",
            data_quality_mode=str(input_bundle_after.get("data_quality_mode") or ""),
        ),
        "delta_summary": _build_delta_summary(input_bundle_before, input_bundle_after, "completed"),
        "stages": stages,
        "outputs": {
            "plan": _clip(plan_output, max_chars=2000),
            "execute": _clip(execute_output, max_chars=2000),
            "review": _clip(review_output, max_chars=2000),
        },
    }
    persist_state(status="completed", stages=stages)
    return report


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
        "--checkpoint-file",
        default=str(CHECKPOINT_FILE),
        help="Path to self-improve checkpoint file used for stage resume",
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
        preflight = _infra_preflight(
            client=client,
            base_url=base_url,
            usage_threshold_ratio=args.usage_threshold_ratio,
            usage_cache_path=Path(args.usage_cache_file),
            attempts=max(1, args.infra_preflight_attempts),
            consecutive_successes=max(1, args.infra_preflight_consecutive_successes),
        )
        if not preflight.get("allowed"):
            preflight_bundle = _coerce_dict(preflight.get("last_bundle"), {})
            report = {
                "status": "infra_blocked",
                "failed_stage": "infra_preflight",
                "skip_reason": "Deployment unsettled or API health was intermittent during preflight checks.",
                "failure_error": str(preflight.get("preflight_error") or "infra_preflight_failed"),
                "infra_preflight": preflight,
                "data_quality_mode": preflight_bundle.get("data_quality_mode", "degraded_partial"),
                "input_bundle": _input_bundle_summary(preflight_bundle),
                "input_bundle_before": preflight_bundle,
                "input_bundle_after": preflight_bundle,
                "stages": [],
                "awareness_reflection": _awareness_reflection(
                    status="infra_blocked",
                    failed_stage="infra_preflight",
                    failure_error=str(preflight.get("preflight_error") or ""),
                    data_quality_mode=str(preflight_bundle.get("data_quality_mode") or ""),
                ),
                "delta_summary": _build_delta_summary(preflight_bundle, preflight_bundle, "infra_blocked"),
            }
        else:
            report = run_cycle(
                client=client,
                base_url=base_url,
                poll_interval_seconds=max(0, args.poll_interval_seconds),
                timeout_seconds=max(10, args.timeout_seconds),
                execute_pending=args.execute_pending,
                execute_token=args.execute_token,
                usage_threshold_ratio=args.usage_threshold_ratio,
                usage_cache_path=args.usage_cache_file,
                checkpoint_path=args.checkpoint_file,
            )
            report["infra_preflight"] = preflight

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"status={report.get('status')}")
        for row in report.get("stages", []):
            print(f"- {row.get('stage')}: task={row.get('task_id')} status={row.get('status')}")

    return 0 if report.get("status") in {"completed", "skipped", "infra_blocked"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
