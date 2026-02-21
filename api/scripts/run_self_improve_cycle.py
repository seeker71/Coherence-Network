#!/usr/bin/env python3
"""Run a model-pinned self-improvement cycle (plan -> execute -> review)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx

PLAN_MODEL = "gpt-5.3-codex"
EXECUTE_MODEL = "gpt-5.3-codex-spark"
REVIEW_MODEL = "gpt-5.3-codex"
DEFAULT_LIMIT_THRESHOLD_RATIO = 0.15


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


def _usage_limit_precheck(
    client: Any,
    *,
    base_url: str,
    threshold_ratio: float,
) -> dict[str, Any]:
    response = client.get(
        f"{base_url}/api/automation/usage/alerts?threshold_ratio={threshold_ratio}&force_refresh=true"
    )
    response.raise_for_status()
    payload = response.json() if isinstance(response.json(), dict) else {}
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    blocking: list[dict[str, Any]] = []
    target_providers = {"openai", "openrouter", "coherence-internal"}
    for row in alerts:
        if not isinstance(row, dict):
            continue
        provider = str(row.get("provider") or "").strip().lower()
        remaining_ratio = row.get("remaining_ratio")
        if provider not in target_providers:
            continue
        if remaining_ratio is None:
            continue
        try:
            numeric_ratio = float(remaining_ratio)
        except (TypeError, ValueError):
            continue
        if numeric_ratio <= threshold_ratio:
            blocking.append(
                {
                    "provider": provider,
                    "metric_id": str(row.get("metric_id") or ""),
                    "severity": str(row.get("severity") or ""),
                    "remaining_ratio": round(numeric_ratio, 6),
                    "message": str(row.get("message") or ""),
                }
            )

    if not blocking:
        return {"allowed": True, "threshold_ratio": threshold_ratio, "blocking_alerts": []}

    summary = "; ".join(
        f"{row['provider']}:{row['metric_id']} remaining_ratio={row['remaining_ratio']}<=threshold={threshold_ratio}"
        for row in blocking
    )
    return {
        "allowed": False,
        "threshold_ratio": threshold_ratio,
        "skip_reason": f"Usage limit precheck blocked self-improve cycle: {summary}",
        "blocking_alerts": blocking,
    }


def _submit_task(client: Any, base_url: str, payload: dict[str, Any]) -> str:
    response = client.post(f"{base_url}/api/agent/tasks", json=payload)
    response.raise_for_status()
    data = response.json()
    task_id = str(data.get("id") or "").strip()
    if not task_id:
        raise RuntimeError("Task create response missing id")
    return task_id


def _request_execute(client: Any, base_url: str, task_id: str, execute_token: str) -> None:
    headers = {}
    if execute_token:
        headers["X-Agent-Execute-Token"] = execute_token
    response = client.post(f"{base_url}/api/agent/tasks/{task_id}/execute", headers=headers)
    response.raise_for_status()


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
        response = client.get(f"{base_url}/api/agent/tasks/{task_id}")
        response.raise_for_status()
        task = response.json()
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


def run_cycle(
    *,
    client: Any,
    base_url: str,
    poll_interval_seconds: int,
    timeout_seconds: int,
    execute_pending: bool,
    execute_token: str,
    usage_threshold_ratio: float,
) -> dict[str, Any]:
    precheck = _usage_limit_precheck(
        client,
        base_url=base_url,
        threshold_ratio=max(0.0, min(1.0, float(usage_threshold_ratio))),
    )
    if not precheck.get("allowed"):
        return {
            "status": "skipped",
            "skip_reason": precheck.get("skip_reason"),
            "usage_limit_precheck": precheck,
            "stages": [],
        }

    stages: list[dict[str, Any]] = []

    plan_payload = build_task_payload(
        direction=build_plan_direction(),
        task_type="spec",
        model_override=PLAN_MODEL,
    )
    plan_task_id = _submit_task(client, base_url, plan_payload)
    plan_task = _wait_for_terminal(
        client,
        base_url=base_url,
        task_id=plan_task_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        execute_pending=execute_pending,
        execute_token=execute_token,
    )
    plan_ctx = plan_task.get("context") if isinstance(plan_task.get("context"), dict) else {}
    stages.append(
        {
            "stage": "plan",
            "task_id": plan_task_id,
            "status": plan_task.get("status"),
            "executor": str(plan_ctx.get("executor") or ""),
            "model": str(plan_task.get("model") or ""),
        }
    )
    if str(plan_task.get("status") or "").lower() != "completed":
        return {"status": "failed", "failed_stage": "plan", "stages": stages, "task": plan_task}

    plan_output = str(plan_task.get("output") or "")
    execute_payload = build_task_payload(
        direction=build_execute_direction(plan_output),
        task_type="impl",
        model_override=EXECUTE_MODEL,
    )
    execute_task_id = _submit_task(client, base_url, execute_payload)
    execute_task = _wait_for_terminal(
        client,
        base_url=base_url,
        task_id=execute_task_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        execute_pending=execute_pending,
        execute_token=execute_token,
    )
    execute_ctx = execute_task.get("context") if isinstance(execute_task.get("context"), dict) else {}
    stages.append(
        {
            "stage": "execute",
            "task_id": execute_task_id,
            "status": execute_task.get("status"),
            "executor": str(execute_ctx.get("executor") or ""),
            "model": str(execute_task.get("model") or ""),
        }
    )
    if str(execute_task.get("status") or "").lower() != "completed":
        return {"status": "failed", "failed_stage": "execute", "stages": stages, "task": execute_task}

    execute_output = str(execute_task.get("output") or "")
    review_payload = build_task_payload(
        direction=build_review_direction(plan_output, execute_output),
        task_type="review",
        model_override=REVIEW_MODEL,
    )
    review_task_id = _submit_task(client, base_url, review_payload)
    review_task = _wait_for_terminal(
        client,
        base_url=base_url,
        task_id=review_task_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        execute_pending=execute_pending,
        execute_token=execute_token,
    )
    review_ctx = review_task.get("context") if isinstance(review_task.get("context"), dict) else {}
    stages.append(
        {
            "stage": "review",
            "task_id": review_task_id,
            "status": review_task.get("status"),
            "executor": str(review_ctx.get("executor") or ""),
            "model": str(review_task.get("model") or ""),
        }
    )

    if str(review_task.get("status") or "").lower() != "completed":
        return {"status": "failed", "failed_stage": "review", "stages": stages, "task": review_task}

    return {
        "status": "completed",
        "usage_limit_precheck": precheck,
        "stages": stages,
        "outputs": {
            "plan": _clip(plan_output, max_chars=2000),
            "execute": _clip(execute_output, max_chars=2000),
            "review": _clip(str(review_task.get("output") or ""), max_chars=2000),
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
