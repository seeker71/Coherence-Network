#!/usr/bin/env python3
"""Run CLI executor task-flow validation matrix (local first, then remote).

Flow per executor/attempt:
1) spec  -> generate spec from idea with verification plan
2) impl  -> implement spec and provide verification evidence
3) review -> review against spec; require PASS_FAIL + PATCH_GUIDANCE contract
4) heal (optional) -> if review fails, apply concrete patch guidance
5) review (final) -> confirm PASS after heal

This script validates task-output contracts so failures remain patchable instead of
forcing a full restart from scratch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_EXECUTORS = ("codex", "claude", "cursor", "gemini")
DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_REMOTE_BASE_URL = "https://coherence-network-production.up.railway.app"
TERMINAL_STATUSES = {"completed", "failed", "needs_decision"}

PASS_FAIL_RE = re.compile(
    r"\bPASS_FAIL\b(?:\s*[:=]\s*|\s+|\\n+|\n+)(?:\*\*)?(PASS|FAIL)(?:\*\*)?(?:[^A-Za-z0-9]|$)",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clip(value: Any, max_chars: int = 1200) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _is_local_base_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0"}


def _oauth_only_context(executor: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "executor": executor,
        "runner_priority": "urgent",
        "runner_priority_reason": "cli_flow_matrix_validation",
    }
    if executor == "codex":
        base.update(
            {
                "runner_codex_auth_mode": "oauth",
                "runner_codex_oauth_allow_api_key_fallback": False,
            }
        )
    elif executor == "claude":
        base.update(
            {
                "runner_claude_auth_mode": "oauth",
            }
        )
    elif executor == "cursor":
        base.update(
            {
                "runner_cursor_auth_mode": "oauth",
            }
        )
    elif executor == "gemini":
        base.update(
            {
                "runner_gemini_auth_mode": "oauth",
            }
        )
    return base


def _slugify(value: str) -> str:
    lowered = str(value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:120].strip("-")


def _flow_idea_id(*, run_label: str, environment: str, executor: str, attempt: int) -> str:
    seed = f"{run_label}-{environment}-{executor}-attempt-{attempt}"
    slug = _slugify(seed)
    if not slug:
        slug = f"{environment}-{executor}-attempt-{attempt}"
    return f"runtime-idea-cli-flow-{slug}"


def _executor_model_override(executor: str, args: argparse.Namespace) -> str:
    if executor == "codex":
        return str(args.codex_model or "").strip()
    if executor == "claude":
        return str(args.claude_model or "").strip()
    if executor == "cursor":
        return str(args.cursor_model or "").strip()
    if executor == "gemini":
        return str(args.gemini_model or "").strip()
    return ""


def _stage_markers(stage_name: str) -> list[str]:
    if stage_name == "spec":
        return ["VERIFICATION_PLAN", "ACCEPTANCE_CRITERIA"]
    if stage_name == "impl":
        return ["VERIFICATION_EVIDENCE"]
    if stage_name == "review":
        return ["PASS_FAIL", "SPEC_VERIFICATION_STATUS", "PATCH_GUIDANCE"]
    if stage_name == "heal":
        return ["PATCH_APPLIED", "FILES_CHANGED", "VERIFICATION_EVIDENCE"]
    return []


def _missing_markers(output: str, markers: list[str]) -> list[str]:
    lowered = str(output or "").lower()
    missing: list[str] = []
    for marker in markers:
        if marker.lower() not in lowered:
            missing.append(marker)
    return missing


def _parse_pass_fail(output: str) -> str:
    text = str(output or "")
    match = PASS_FAIL_RE.search(text)
    if match:
        return str(match.group(1) or "").strip().lower()

    # Runner logs can capture JSON envelopes where model output lives in "result".
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        result_text = str(payload.get("result") or "")
        nested = PASS_FAIL_RE.search(result_text)
        if nested:
            return str(nested.group(1) or "").strip().lower()
    return "unknown"


def _task_get(client: httpx.Client, base_url: str, task_id: str) -> dict[str, Any]:
    response = client.get(f"{base_url.rstrip('/')}/api/agent/tasks/{task_id}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"task payload for {task_id} is not an object")
    return payload


def _task_create(
    client: httpx.Client,
    *,
    base_url: str,
    direction: str,
    task_type: str,
    context: dict[str, Any],
    force_paid_providers: bool,
) -> dict[str, Any]:
    payload = {
        "direction": direction,
        "task_type": task_type,
        "context": {
            **context,
            "force_paid_providers": bool(force_paid_providers),
        },
    }
    response = client.post(f"{base_url.rstrip('/')}/api/agent/tasks", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("create-task response is not an object")
    return data


def _task_execute(
    client: httpx.Client,
    *,
    base_url: str,
    task_id: str,
    force_paid_providers: bool,
    execute_token: str,
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if execute_token:
        headers["X-Agent-Execute-Token"] = execute_token
    if force_paid_providers:
        headers["X-Force-Paid-Providers"] = "1"
    response = client.post(
        f"{base_url.rstrip('/')}/api/agent/tasks/{task_id}/execute",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _wait_for_terminal_task(
    client: httpx.Client,
    *,
    base_url: str,
    task_id: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + max(1, int(timeout_seconds))
    last: dict[str, Any] = {}
    while time.time() < deadline:
        current = _task_get(client, base_url, task_id)
        last = current
        status = str(current.get("status") or "").strip().lower()
        if status in TERMINAL_STATUSES:
            return current
        time.sleep(max(0.2, float(poll_seconds)))
    timed_out = dict(last)
    timed_out.setdefault("id", task_id)
    timed_out["status"] = "timeout"
    timed_out.setdefault("output", "")
    return timed_out


def _spec_direction(*, run_label: str, executor: str, attempt: int, spec_path: str, impl_path: str, verify_path: str) -> str:
    return (
        "Generate a concrete spec from this idea and write it to the exact path below.\n"
        f"Idea: Create a deterministic slug utility for task-flow validation ({run_label}, {executor}, attempt {attempt}).\n\n"
        f"Required outputs:\n"
        f"- Spec file path: {spec_path}\n"
        f"- Planned implementation file: {impl_path}\n"
        f"- Planned verification script: {verify_path}\n\n"
        "Spec requirements:\n"
        "1. Define exact behavior for slug generation: lowercase, alphanumeric + hyphen only, collapse separators, trim hyphens.\n"
        "2. Include explicit acceptance criteria that can be verified automatically.\n"
        "3. Include a VERIFICATION_PLAN with executable commands and expected evidence.\n"
        f"4. VERIFICATION_PLAN must include: python3 {verify_path}\n"
        "5. Keep scope small and deterministic; no external dependencies.\n"
    )


def _impl_direction(*, spec_path: str, impl_path: str, verify_path: str) -> str:
    return (
        "Implement the spec exactly and do not expand scope.\n"
        f"Spec path: {spec_path}\n"
        f"Implementation path: {impl_path}\n"
        f"Verification script path: {verify_path}\n\n"
        "Implementation requirements:\n"
        "1. Implement a callable slug function and deterministic behavior defined in spec.\n"
        "2. Create a standalone verification script with multiple assertions and clear pass/fail output.\n"
        f"3. Execute: python3 {verify_path}\n"
        "4. Return VERIFICATION_EVIDENCE including command + output snippet.\n"
    )


def _review_direction(*, spec_path: str, impl_path: str, verify_path: str) -> str:
    return (
        "Review implementation against spec verification contract.\n"
        f"Spec path: {spec_path}\n"
        f"Implementation path: {impl_path}\n"
        f"Verification script path: {verify_path}\n\n"
        "Review requirements:\n"
        "1. Validate acceptance criteria coverage and correctness.\n"
        f"2. Re-run verification command: python3 {verify_path}\n"
        "3. Return PASS_FAIL, FINDINGS, SPEC_VERIFICATION_STATUS, PATCH_GUIDANCE.\n"
        "4. If FAIL, PATCH_GUIDANCE must contain exact file edits and re-verification commands.\n"
    )


def _heal_direction(*, spec_path: str, impl_path: str, verify_path: str, review_output: str) -> str:
    return (
        "Apply a minimal patch based on failed review guidance and recover to pass.\n"
        f"Spec path: {spec_path}\n"
        f"Implementation path: {impl_path}\n"
        f"Verification script path: {verify_path}\n\n"
        "Failed review output (for patch guidance):\n"
        f"{_clip(review_output, max_chars=2200)}\n\n"
        "Heal requirements:\n"
        "1. Apply concrete patch changes only for the identified failures.\n"
        f"2. Re-run: python3 {verify_path}\n"
        "3. Return PATCH_APPLIED, FILES_CHANGED, VERIFICATION_EVIDENCE.\n"
    )


def _effective_execute_mode(base_url: str, requested_mode: str) -> str:
    mode = str(requested_mode or "auto").strip().lower()
    if mode in {"api", "none", "runner"}:
        return mode
    return "runner" if _is_local_base_url(base_url) else "none"


def _run_stage(
    client: httpx.Client,
    *,
    base_url: str,
    execute_mode: str,
    execute_token: str,
    executor: str,
    task_type: str,
    stage_name: str,
    direction: str,
    model_override: str,
    timeout_seconds: int,
    poll_seconds: float,
    force_paid_providers: bool,
    idea_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = _oauth_only_context(executor)
    context["idea_id"] = idea_id
    if model_override:
        context["model_override"] = model_override
    task = _task_create(
        client,
        base_url=base_url,
        direction=direction,
        task_type=task_type,
        context=context,
        force_paid_providers=force_paid_providers,
    )
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        raise RuntimeError(f"{stage_name}: task id missing in create response")

    if execute_mode == "api":
        _task_execute(
            client,
            base_url=base_url,
            task_id=task_id,
            force_paid_providers=force_paid_providers,
            execute_token=execute_token,
        )

    terminal = _wait_for_terminal_task(
        client,
        base_url=base_url,
        task_id=task_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )

    output = str(terminal.get("output") or "")
    markers = _stage_markers(stage_name)
    missing = _missing_markers(output, markers)
    stage_result = {
        "stage": stage_name,
        "task_type": task_type,
        "task_id": task_id,
        "status": str(terminal.get("status") or "").strip().lower(),
        "markers_required": markers,
        "markers_missing": missing,
        "contract_ok": not missing,
        "pass_fail": _parse_pass_fail(output) if stage_name == "review" else "",
        "output_excerpt": _clip(output, max_chars=1800),
    }
    return stage_result, terminal


def _build_paths(*, run_id: str, environment: str, executor: str, attempt: int) -> tuple[str, str, str]:
    repo_root = _repo_root_from_script()
    root = repo_root / ".tmp" / "coherence-cli-flow" / run_id / environment / executor / f"attempt-{attempt}"
    spec_path = str(root / "spec.md")
    impl_path = str(root / "slug_impl.py")
    verify_path = str(root / "verify_slug.py")
    return spec_path, impl_path, verify_path


def _local_path_checks(*, spec_path: str, impl_path: str, verify_path: str) -> dict[str, bool]:
    return {
        "spec_exists": os.path.exists(spec_path),
        "impl_exists": os.path.exists(impl_path),
        "verify_exists": os.path.exists(verify_path),
    }


def _review_fallback_verification(
    *,
    verify_path: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if not os.path.exists(verify_path):
        return {
            "accepted": False,
            "reason": "verify_script_missing",
            "returncode": None,
            "output_excerpt": "",
        }
    try:
        completed = subprocess.run(
            ["python3", verify_path],
            capture_output=True,
            text=True,
            timeout=max(10, min(int(timeout_seconds), 300)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        combined = f"{exc.stdout or ''}\n{exc.stderr or ''}".strip()
        return {
            "accepted": False,
            "reason": "verify_timeout",
            "returncode": None,
            "output_excerpt": _clip(combined, max_chars=800),
        }
    except Exception as exc:  # pragma: no cover - defensive fallback
        return {
            "accepted": False,
            "reason": f"verify_exception:{type(exc).__name__}",
            "returncode": None,
            "output_excerpt": _clip(str(exc), max_chars=800),
        }

    combined = "\n".join(part for part in [(completed.stdout or "").strip(), (completed.stderr or "").strip()] if part)
    return {
        "accepted": int(completed.returncode or 0) == 0,
        "reason": "verify_exit_zero" if int(completed.returncode or 0) == 0 else "verify_nonzero_exit",
        "returncode": int(completed.returncode or 0),
        "output_excerpt": _clip(combined, max_chars=800),
    }


def _run_flow_for_executor(
    client: httpx.Client,
    *,
    base_url: str,
    run_label: str,
    environment: str,
    execute_mode: str,
    execute_token: str,
    executor: str,
    attempt: int,
    model_override: str,
    timeout_seconds: int,
    poll_seconds: float,
    force_paid_providers: bool,
) -> dict[str, Any]:
    spec_path, impl_path, verify_path = _build_paths(
        run_id=run_label,
        environment=environment,
        executor=executor,
        attempt=attempt,
    )
    for target_path in (spec_path, impl_path, verify_path):
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_file():
            target.unlink()

    flow: dict[str, Any] = {
        "executor": executor,
        "attempt": attempt,
        "model_override": model_override,
        "idea_id": _flow_idea_id(
            run_label=run_label,
            environment=environment,
            executor=executor,
            attempt=attempt,
        ),
        "paths": {
            "spec": spec_path,
            "impl": impl_path,
            "verify": verify_path,
        },
        "stages": [],
        "flow_success": False,
        "flow_blocked": False,
        "notes": [],
    }

    spec_stage, _spec_task = _run_stage(
        client,
        base_url=base_url,
        execute_mode=execute_mode,
        execute_token=execute_token,
        executor=executor,
        task_type="spec",
        stage_name="spec",
        direction=_spec_direction(
            run_label=run_label,
            executor=executor,
            attempt=attempt,
            spec_path=spec_path,
            impl_path=impl_path,
            verify_path=verify_path,
        ),
        model_override=model_override,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        force_paid_providers=force_paid_providers,
        idea_id=str(flow["idea_id"]),
    )
    flow["stages"].append(spec_stage)
    if spec_stage["status"] != "completed":
        flow["flow_blocked"] = True
        flow["notes"].append(f"spec stage ended with status={spec_stage['status']}")
        return flow

    impl_stage, _impl_task = _run_stage(
        client,
        base_url=base_url,
        execute_mode=execute_mode,
        execute_token=execute_token,
        executor=executor,
        task_type="impl",
        stage_name="impl",
        direction=_impl_direction(spec_path=spec_path, impl_path=impl_path, verify_path=verify_path),
        model_override=model_override,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        force_paid_providers=force_paid_providers,
        idea_id=str(flow["idea_id"]),
    )
    flow["stages"].append(impl_stage)
    if impl_stage["status"] != "completed":
        flow["flow_blocked"] = True
        flow["notes"].append(f"impl stage ended with status={impl_stage['status']}")
        return flow

    review_stage, review_task = _run_stage(
        client,
        base_url=base_url,
        execute_mode=execute_mode,
        execute_token=execute_token,
        executor=executor,
        task_type="review",
        stage_name="review",
        direction=_review_direction(spec_path=spec_path, impl_path=impl_path, verify_path=verify_path),
        model_override=model_override,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        force_paid_providers=force_paid_providers,
        idea_id=str(flow["idea_id"]),
    )
    flow["stages"].append(review_stage)
    if review_stage["status"] != "completed":
        flow["flow_blocked"] = True
        flow["notes"].append(f"review stage ended with status={review_stage['status']}")
        return flow

    review_pass_fail = str(review_stage.get("pass_fail") or "")
    review_output = str(review_task.get("output") or "")

    if review_pass_fail == "pass":
        flow["flow_success"] = True
        flow["notes"].append("initial review returned PASS")
    elif review_pass_fail == "fail":
        if "patch_guidance" not in review_output.lower():
            flow["notes"].append("review failed without PATCH_GUIDANCE marker")

        heal_stage, _heal_task = _run_stage(
            client,
            base_url=base_url,
            execute_mode=execute_mode,
            execute_token=execute_token,
            executor=executor,
            task_type="heal",
            stage_name="heal",
            direction=_heal_direction(
                spec_path=spec_path,
                impl_path=impl_path,
                verify_path=verify_path,
                review_output=review_output,
            ),
            model_override=model_override,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            force_paid_providers=force_paid_providers,
            idea_id=str(flow["idea_id"]),
        )
        flow["stages"].append(heal_stage)
        if heal_stage["status"] != "completed":
            flow["flow_blocked"] = True
            flow["notes"].append(f"heal stage ended with status={heal_stage['status']}")
            return flow

        final_review_stage, _final_review_task = _run_stage(
            client,
            base_url=base_url,
            execute_mode=execute_mode,
            execute_token=execute_token,
            executor=executor,
            task_type="review",
            stage_name="review",
            direction=_review_direction(spec_path=spec_path, impl_path=impl_path, verify_path=verify_path),
            model_override=model_override,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
            force_paid_providers=force_paid_providers,
            idea_id=str(flow["idea_id"]),
        )
        final_review_stage["stage"] = "review_final"
        flow["stages"].append(final_review_stage)
        flow["flow_success"] = (
            final_review_stage["status"] == "completed" and str(final_review_stage.get("pass_fail") or "") == "pass"
        )
        if not flow["flow_success"]:
            flow["notes"].append("final review did not return PASS")
    else:
        fallback = _review_fallback_verification(verify_path=verify_path)
        flow["review_fallback"] = fallback
        if bool(fallback.get("accepted")):
            flow["flow_success"] = True
            flow["notes"].append("review output missing parseable PASS_FAIL; accepted by verification fallback")
        else:
            flow["flow_blocked"] = True
            flow["notes"].append("review output missing parseable PASS_FAIL")
            flow["notes"].append(f"verification fallback failed: {fallback.get('reason')}")

    if _is_local_base_url(base_url):
        flow["local_paths"] = _local_path_checks(
            spec_path=spec_path,
            impl_path=impl_path,
            verify_path=verify_path,
        )

    return flow


def _executor_summary(flows: list[dict[str, Any]]) -> dict[str, Any]:
    by_executor: dict[str, dict[str, Any]] = {}
    for row in flows:
        executor = str(row.get("executor") or "").strip().lower()
        if not executor:
            continue
        slot = by_executor.setdefault(
            executor,
            {
                "attempts": 0,
                "flow_successes": 0,
                "flow_failures": 0,
                "stage_status_counts": {},
                "review_pass": 0,
                "review_fail": 0,
                "review_unknown": 0,
            },
        )
        slot["attempts"] += 1
        if bool(row.get("flow_success")):
            slot["flow_successes"] += 1
        else:
            slot["flow_failures"] += 1
        for stage in row.get("stages") or []:
            if not isinstance(stage, dict):
                continue
            status = str(stage.get("status") or "").strip().lower() or "unknown"
            counts = slot["stage_status_counts"]
            counts[status] = int(counts.get(status) or 0) + 1
            if str(stage.get("stage") or "").startswith("review"):
                pf = str(stage.get("pass_fail") or "").strip().lower()
                if pf == "pass":
                    slot["review_pass"] += 1
                elif pf == "fail":
                    slot["review_fail"] += 1
                else:
                    slot["review_unknown"] += 1

    for data in by_executor.values():
        attempts = max(1, int(data["attempts"]))
        data["flow_success_rate"] = round(float(data["flow_successes"]) / float(attempts), 4)
    return by_executor


def _run_environment(
    *,
    base_url: str,
    environment: str,
    execute_mode: str,
    execute_token: str,
    executors: list[str],
    attempts_per_executor: int,
    timeout_seconds: int,
    poll_seconds: float,
    force_paid_providers: bool,
    args: argparse.Namespace,
    run_id: str,
) -> dict[str, Any]:
    effective_mode = _effective_execute_mode(base_url, execute_mode)
    profile: dict[str, Any] = {
        "environment": environment,
        "base_url": base_url,
        "requested_execute_mode": execute_mode,
        "effective_execute_mode": effective_mode,
        "started_at": _utc_now_iso(),
        "flows": [],
        "errors": [],
    }

    with httpx.Client(timeout=60.0) as client:
        for executor in executors:
            model_override = _executor_model_override(executor, args)
            for attempt in range(1, max(1, attempts_per_executor) + 1):
                try:
                    flow = _run_flow_for_executor(
                        client,
                        base_url=base_url,
                        run_label=run_id,
                        environment=environment,
                        execute_mode=effective_mode,
                        execute_token=execute_token,
                        executor=executor,
                        attempt=attempt,
                        model_override=model_override,
                        timeout_seconds=timeout_seconds,
                        poll_seconds=poll_seconds,
                        force_paid_providers=force_paid_providers,
                    )
                    profile["flows"].append(flow)
                    print(
                        f"[{environment}] executor={executor} attempt={attempt} "
                        f"success={flow.get('flow_success')} blocked={flow.get('flow_blocked')}"
                    )
                except Exception as exc:
                    detail = f"executor={executor} attempt={attempt} error={type(exc).__name__}:{exc}"
                    profile["errors"].append(detail)
                    print(f"[{environment}] {detail}", file=sys.stderr)

    profile["ended_at"] = _utc_now_iso()
    profile["executor_summary"] = _executor_summary(profile["flows"])
    return profile


def _top_level_summary(environments: list[dict[str, Any]]) -> dict[str, Any]:
    total_flows = 0
    successful_flows = 0
    failed_flows = 0
    blocked_flows = 0
    terminal_status_counts: dict[str, int] = {}
    for env in environments:
        for flow in env.get("flows") or []:
            total_flows += 1
            if bool(flow.get("flow_success")):
                successful_flows += 1
            else:
                failed_flows += 1
            if bool(flow.get("flow_blocked")):
                blocked_flows += 1
            for stage in flow.get("stages") or []:
                if not isinstance(stage, dict):
                    continue
                status = str(stage.get("status") or "unknown").strip().lower()
                terminal_status_counts[status] = int(terminal_status_counts.get(status) or 0) + 1
    success_rate = round(float(successful_flows) / float(total_flows), 4) if total_flows else 0.0
    return {
        "total_flows": total_flows,
        "successful_flows": successful_flows,
        "failed_flows": failed_flows,
        "blocked_flows": blocked_flows,
        "flow_success_rate": success_rate,
        "stage_status_counts": terminal_status_counts,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CLI task flow matrix for codex/claude/cursor/gemini")
    parser.add_argument("--local-base-url", default=DEFAULT_LOCAL_BASE_URL)
    parser.add_argument("--remote-base-url", default=DEFAULT_REMOTE_BASE_URL)
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--include-remote", action="store_true")
    parser.add_argument("--local-execute-mode", choices=("auto", "api", "runner", "none"), default="auto")
    parser.add_argument("--remote-execute-mode", choices=("auto", "api", "runner", "none"), default="auto")
    parser.add_argument("--execute-token", default=os.getenv("AGENT_EXECUTE_TOKEN", ""))
    parser.add_argument("--executors", default=",".join(DEFAULT_EXECUTORS))
    parser.add_argument("--attempts-per-executor", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--force-paid-providers", action="store_true", default=True)
    parser.add_argument("--codex-model", default=os.getenv("CLI_FLOW_CODEX_MODEL", "gpt-5.3-codex"))
    parser.add_argument("--claude-model", default=os.getenv("CLI_FLOW_CLAUDE_MODEL", ""))
    parser.add_argument("--cursor-model", default=os.getenv("CLI_FLOW_CURSOR_MODEL", ""))
    parser.add_argument("--gemini-model", default=os.getenv("CLI_FLOW_GEMINI_MODEL", "gemini-3.1-pro-preview"))
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--spawn-local-runner",
        action="store_true",
        help="Start api/scripts/agent_runner.py automatically when local execute mode resolves to runner.",
    )
    parser.add_argument("--runner-workers", type=int, default=4, help="Worker count for spawned local runner")
    parser.add_argument("--runner-interval", type=int, default=2, help="Poll interval seconds for spawned local runner")
    parser.add_argument(
        "--runner-task-timeout",
        type=int,
        default=240,
        help="Per-task timeout (seconds) applied to spawned local runner.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any flow fails")
    return parser.parse_args()


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def _spawn_local_runner(
    *,
    run_id: str,
    api_base_url: str,
    workers: int,
    interval_seconds: int,
    task_timeout_seconds: int,
) -> tuple[subprocess.Popen[str], str, Any]:
    repo_root = _repo_root_from_script()
    api_dir = repo_root / "api"
    log_path = repo_root / "logs" / f"cli_task_flow_runner_{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", encoding="utf-8")
    runner_env = dict(os.environ)
    runner_env["AGENT_API_BASE"] = str(api_base_url).strip() or DEFAULT_LOCAL_BASE_URL
    runner_env["AGENT_AUTO_GENERATE_IDLE_TASKS"] = "0"
    runner_env["AGENT_TASK_TIMEOUT"] = str(max(30, int(task_timeout_seconds)))
    process = subprocess.Popen(
        [
            "python3",
            "scripts/agent_runner.py",
            "--interval",
            str(max(1, int(interval_seconds))),
            "--workers",
            str(max(1, int(workers))),
            "--repo-path",
            str(repo_root),
        ],
        cwd=str(api_dir),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=runner_env,
    )
    return process, str(log_path), log_file


def main() -> int:
    args = _parse_args()
    executors = _split_csv(args.executors)
    if not executors:
        raise SystemExit("No executors selected.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    report: dict[str, Any] = {
        "report_kind": "cli_task_flow_matrix",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "executors": executors,
        "attempts_per_executor": max(1, int(args.attempts_per_executor)),
        "timeout_seconds": int(args.timeout_seconds),
        "poll_seconds": float(args.poll_seconds),
        "force_paid_providers": bool(args.force_paid_providers),
        "environments": [],
    }

    runner_process: subprocess.Popen[str] | None = None
    runner_log_file: Any | None = None
    runner_log_path = ""
    try:
        if not args.skip_local:
            local_effective_mode = _effective_execute_mode(str(args.local_base_url), str(args.local_execute_mode))
            if local_effective_mode == "runner" and bool(args.spawn_local_runner):
                runner_process, runner_log_path, runner_log_file = _spawn_local_runner(
                    run_id=run_id,
                    api_base_url=str(args.local_base_url),
                    workers=max(1, int(args.runner_workers)),
                    interval_seconds=max(1, int(args.runner_interval)),
                    task_timeout_seconds=max(30, int(args.runner_task_timeout)),
                )
                # Give the runner a brief startup window before submitting tasks.
                time.sleep(2.0)
                report["local_runner"] = {
                    "spawned": True,
                    "pid": int(runner_process.pid),
                    "log_path": runner_log_path,
                }

            report["environments"].append(
                _run_environment(
                    base_url=str(args.local_base_url),
                    environment="local",
                    execute_mode=str(args.local_execute_mode),
                    execute_token=str(args.execute_token or ""),
                    executors=executors,
                    attempts_per_executor=max(1, int(args.attempts_per_executor)),
                    timeout_seconds=max(30, int(args.timeout_seconds)),
                    poll_seconds=max(0.2, float(args.poll_seconds)),
                    force_paid_providers=bool(args.force_paid_providers),
                    args=args,
                    run_id=run_id,
                )
            )

        if args.include_remote:
            report["environments"].append(
                _run_environment(
                    base_url=str(args.remote_base_url),
                    environment="remote",
                    execute_mode=str(args.remote_execute_mode),
                    execute_token=str(args.execute_token or ""),
                    executors=executors,
                    attempts_per_executor=max(1, int(args.attempts_per_executor)),
                    timeout_seconds=max(30, int(args.timeout_seconds)),
                    poll_seconds=max(0.2, float(args.poll_seconds)),
                    force_paid_providers=bool(args.force_paid_providers),
                    args=args,
                    run_id=run_id,
                )
            )
    finally:
        if runner_process is not None:
            try:
                runner_process.terminate()
                runner_process.wait(timeout=15)
            except Exception:
                try:
                    runner_process.kill()
                except Exception:
                    pass
        if runner_log_file is not None:
            try:
                runner_log_file.close()
            except Exception:
                pass

    report["summary"] = _top_level_summary(report["environments"])

    default_output = f"logs/cli_task_flow_matrix_{run_id}.json"
    output_path = str(args.output or default_output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print(json.dumps({"output": output_path, "summary": report["summary"]}, indent=2))

    if args.strict and int(report["summary"].get("failed_flows") or 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
