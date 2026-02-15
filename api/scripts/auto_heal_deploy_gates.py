#!/usr/bin/env python3
"""Detect and heal failed required checks that block deployment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from app.services import release_gate_service as gates


def _build_gate(
    sha: str,
    commit_status: dict[str, Any],
    check_runs: list[dict[str, Any]],
    required_contexts: list[str],
) -> dict[str, Any]:
    pseudo_pr: dict[str, Any] = {
        "number": 0,
        "draft": False,
        "mergeable_state": "clean",
        "head": {"sha": sha},
    }
    return gates.evaluate_pr_gates(pseudo_pr, commit_status, check_runs, required_contexts)


def _failed_actions_runs(check_runs: list[dict[str, Any]]) -> list[int]:
    return gates.collect_rerunnable_actions_run_ids([], check_runs)


def _actions_run_states(check_runs: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    states: dict[int, dict[str, str]] = {}
    for run in check_runs:
        details_url = run.get("details_url")
        if not isinstance(details_url, str):
            continue
        app = run.get("app")
        app_slug = app.get("slug") if isinstance(app, dict) else None
        if app_slug != "github-actions":
            continue
        run_id = gates.extract_actions_run_id(details_url)
        if run_id is None:
            continue
        states[run_id] = {
            "status": str(run.get("status") or ""),
            "conclusion": str(run.get("conclusion") or ""),
        }
    return states


def _rerun_state_summary(
    check_runs: list[dict[str, Any]],
    rerun_ids: list[int],
) -> tuple[bool, list[int], list[int], dict[int, dict[str, str]]]:
    if not rerun_ids:
        return True, [], [], {}
    state_map = _actions_run_states(check_runs)
    pending: list[int] = []
    failed: list[int] = []
    for run_id in rerun_ids:
        state = state_map.get(run_id)
        if not state:
            pending.append(run_id)
            continue
        status = state.get("status", "")
        conclusion = state.get("conclusion", "")
        if status != "completed":
            pending.append(run_id)
            continue
        if conclusion != "success":
            failed.append(run_id)
    ok = not pending and not failed
    return ok, pending, failed, state_map


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"Repo: {payload.get('repo')}")
    print(f"SHA: {payload.get('sha')}")
    print(f"Result: {payload.get('result')}")
    if payload.get("reason"):
        print(f"Reason: {payload.get('reason')}")
    initial = payload.get("initial_gate")
    if isinstance(initial, dict):
        print(
            "Initial gate:"
            f" combined={initial.get('combined_status_state')}"
            f" missing={initial.get('missing_required_contexts')}"
            f" failing={initial.get('failing_required_contexts')}"
        )
    failed_actions = payload.get("failed_actions_runs")
    if isinstance(failed_actions, list):
        print(f"Initial failed actions runs: {failed_actions}")
    actions = payload.get("actions")
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict):
                print(f"Action: run_id={action.get('run_id')} accepted={action.get('accepted')}")
    rerun_pending = payload.get("rerun_pending_runs")
    if isinstance(rerun_pending, list):
        print(f"Rerun pending runs: {rerun_pending}")
    rerun_failed = payload.get("rerun_failed_runs")
    if isinstance(rerun_failed, list):
        print(f"Rerun failed runs: {rerun_failed}")
    final = payload.get("final_gate")
    if isinstance(final, dict):
        print(
            "Final gate:"
            f" ready_to_merge={final.get('ready_to_merge')}"
            f" combined={final.get('combined_status_state')}"
            f" missing={final.get('missing_required_contexts')}"
            f" failing={final.get('failing_required_contexts')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-heal required check failures that block Railway deployment."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--base", default="main")
    parser.add_argument("--sha", default="")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        out = {"result": "blocked", "reason": "GITHUB_TOKEN is required"}
        _emit(out, as_json=args.json)
        sys.exit(2)

    sha = args.sha.strip() or gates.get_branch_head_sha(args.repo, args.branch, github_token=token)
    if not sha:
        out = {"result": "blocked", "reason": f"Unable to resolve head SHA for branch {args.branch}"}
        _emit(out, as_json=args.json)
        sys.exit(2)

    required_contexts = gates.get_required_contexts(args.repo, args.base, github_token=token) or []
    commit_status = gates.get_commit_status(args.repo, sha, github_token=token)
    check_runs = gates.get_check_runs(args.repo, sha, github_token=token)
    initial_gate = _build_gate(sha, commit_status, check_runs, required_contexts)

    report: dict[str, Any] = {
        "repo": args.repo,
        "sha": sha,
        "base": args.base,
        "required_contexts": required_contexts,
        "initial_gate": initial_gate,
        "failed_actions_runs": _failed_actions_runs(check_runs),
        "actions": [],
    }

    if initial_gate.get("ready_to_merge") and not report["failed_actions_runs"]:
        report["result"] = "already_green"
        report["final_gate"] = initial_gate
        _emit(report, as_json=args.json)
        sys.exit(0)

    failing_required = initial_gate.get("failing_required_contexts", [])
    failing_required = failing_required if isinstance(failing_required, list) else []
    run_ids = gates.collect_rerunnable_actions_run_ids(failing_required, check_runs)
    if not run_ids:
        run_ids = _failed_actions_runs(check_runs)
    for run_id in run_ids:
        action = gates.rerun_actions_failed_jobs(args.repo, run_id, token)
        report["actions"].append(action)

    started = time.time()
    final_gate = initial_gate
    while True:
        commit_status = gates.get_commit_status(args.repo, sha, github_token=token)
        check_runs = gates.get_check_runs(args.repo, sha, github_token=token)
        final_gate = _build_gate(sha, commit_status, check_runs, required_contexts)
        final_failed_actions = _failed_actions_runs(check_runs)
        rerun_ok, rerun_pending, rerun_failed, rerun_states = _rerun_state_summary(
            check_runs,
            run_ids,
        )
        report["rerun_pending_runs"] = rerun_pending
        report["rerun_failed_runs"] = rerun_failed
        report["rerun_states"] = rerun_states
        if final_gate.get("ready_to_merge") and not final_failed_actions and rerun_ok:
            report["result"] = "healed" if run_ids else "green_without_rerun"
            report["final_gate"] = final_gate
            report["final_failed_actions_runs"] = final_failed_actions
            _emit(report, as_json=args.json)
            sys.exit(0)
        if time.time() - started >= args.timeout_seconds:
            report["final_failed_actions_runs"] = final_failed_actions
            break
        time.sleep(max(1, args.poll_seconds))

    report["result"] = "blocked"
    if not run_ids:
        report["reason"] = "No rerunnable failed checks were found"
    elif report.get("rerun_failed_runs"):
        report["reason"] = "Retry completed but one or more checks still failed"
    elif report.get("rerun_pending_runs"):
        report["reason"] = "Retry did not settle before timeout"
    else:
        report["reason"] = "Checks remained non-green after retry window"
    report["final_gate"] = final_gate
    _emit(report, as_json=args.json)
    sys.exit(2)


if __name__ == "__main__":
    main()
