#!/usr/bin/env python3
"""Detect, summarize, and optionally auto-rerun failing PR checks."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services import release_gate_service as gates  # noqa: E402
try:  # noqa: SIM105
    from app.services import telemetry_persistence_service  # type: ignore[attr-defined]  # noqa: E402
except Exception:  # pragma: no cover - best effort import only
    telemetry_persistence_service = None


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record_external_tool_usage(
    *,
    tool_name: str,
    provider: str,
    operation: str,
    resource: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> None:
    if telemetry_persistence_service is None:
        return
    try:
        telemetry_persistence_service.append_external_tool_usage_event(
            {
                "event_id": f"tool_{uuid.uuid4().hex}",
                "occurred_at": _now_utc(),
                "tool_name": tool_name,
                "provider": provider,
                "operation": operation,
                "resource": resource,
                "status": status,
                "payload": payload or {},
            }
        )
    except Exception:
        return


def _hint_for_check(name: str) -> str:
    value = name.lower()
    mapping: list[tuple[str, str]] = [
        (
            "validate commit evidence",
            "python3 scripts/validate_commit_evidence.py --base origin/main --head HEAD --require-changed-evidence",
        ),
        ("spec quality", "python3 scripts/validate_spec_quality.py --base origin/main --head HEAD"),
        ("workflow file references", "python3 scripts/validate_workflow_references.py"),
        (
            "maintainability",
            "python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression",
        ),
        ("test", "cd api && pytest -q"),
        ("build web", "cd web && npm ci && npm run build"),
        ("thread gates", "python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"),
        ("public deploy contract", "./scripts/verify_web_api_deploy.sh"),
        ("change contract", "python3 scripts/worktree_pr_guard.py --mode all --base-ref origin/main"),
    ]
    for key, command in mapping:
        if key in value:
            return command
    return "python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"


def _check_run_to_item(run: dict[str, Any]) -> dict[str, Any]:
    name = str(run.get("name") or "unknown")
    details_url = run.get("details_url")
    run_id = gates.extract_actions_run_id(details_url) if isinstance(details_url, str) else None
    return {
        "name": name,
        "status": str(run.get("status") or ""),
        "conclusion": str(run.get("conclusion") or ""),
        "details_url": details_url,
        "html_url": run.get("html_url"),
        "actions_run_id": run_id,
        "suggested_local_preflight": _hint_for_check(name),
    }


def _status_to_item(status: dict[str, Any]) -> dict[str, Any]:
    context = str(status.get("context") or "unknown")
    return {
        "context": context,
        "state": str(status.get("state") or "unknown"),
        "description": status.get("description"),
        "target_url": status.get("target_url"),
        "suggested_local_preflight": _hint_for_check(context),
    }


def _open_pr_payload(
    repo: str,
    base: str,
    head_prefix: str,
    token: str,
) -> list[dict[str, Any]]:
    pulls = gates.get_open_prs(repo, github_token=token)
    required_contexts = gates.get_required_contexts(repo, base, github_token=token) or []
    failed_conclusions = {"failure", "timed_out", "cancelled", "startup_failure", "action_required", "stale"}

    rows: list[dict[str, Any]] = []
    for pr in pulls:
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        branch = str(head.get("ref") or "")
        if head_prefix and not branch.startswith(head_prefix):
            continue
        sha = str(head.get("sha") or "")
        if not sha:
            continue
        commit_status = gates.get_commit_status(repo, sha, github_token=token)
        check_runs = gates.get_check_runs(repo, sha, github_token=token)
        eval_result = gates.evaluate_pr_gates(pr, commit_status, check_runs, required_contexts)

        failing_check_runs = []
        for run in check_runs:
            conclusion = str(run.get("conclusion") or "").lower()
            status = str(run.get("status") or "").lower()
            if status == "completed" and conclusion in failed_conclusions:
                failing_check_runs.append(_check_run_to_item(run))

        failing_status_contexts = []
        statuses = commit_status.get("statuses")
        if isinstance(statuses, list):
            for status in statuses:
                if not isinstance(status, dict):
                    continue
                state = str(status.get("state") or "").lower()
                if state not in {"success", "expected"}:
                    failing_status_contexts.append(_status_to_item(status))

        rows.append(
            {
                "pr_number": pr.get("number"),
                "pr_url": pr.get("html_url"),
                "title": pr.get("title"),
                "head_branch": branch,
                "head_sha": sha,
                "combined_status_state": commit_status.get("state"),
                "ready_to_merge": eval_result.get("ready_to_merge"),
                "missing_required_contexts": eval_result.get("missing_required_contexts"),
                "failing_required_contexts": eval_result.get("failing_required_contexts"),
                "failing_check_runs": failing_check_runs,
                "failing_status_contexts": failing_status_contexts,
            }
        )
    return rows


def _rerun_failed_actions(repo: str, rows: list[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen_run_ids: set[int] = set()
    for row in rows:
        checks = row.get("failing_check_runs")
        if not isinstance(checks, list):
            continue
        for check in checks:
            if not isinstance(check, dict):
                continue
            run_id = check.get("actions_run_id")
            if not isinstance(run_id, int) or run_id in seen_run_ids:
                continue
            seen_run_ids.add(run_id)
            result = gates.rerun_actions_failed_jobs(repo, run_id, token)
            actions.append(
                {
                    "run_id": run_id,
                    "accepted": bool(result.get("accepted")),
                    "status_code": result.get("status_code"),
                    "response_text": result.get("response_text"),
                    "check_name": check.get("name"),
                }
            )
    return actions


def _has_blocking_failures(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("failing_check_runs"):
            return True
        if row.get("failing_status_contexts"):
            return True
        if row.get("missing_required_contexts"):
            return True
        if row.get("failing_required_contexts"):
            return True
    return False


def _short_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No matching open PRs found."
    failures = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            row.get("failing_check_runs")
            or row.get("failing_status_contexts")
            or row.get("missing_required_contexts")
            or row.get("failing_required_contexts")
        ):
            failures += 1
    if failures == 0:
        return f"Checked {len(rows)} PR(s); no blocking failures."
    return f"Checked {len(rows)} PR(s); blocking failures in {failures} PR(s)."


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "report"


def _write_report(output_dir: Path, report: dict[str, Any], branch_filter: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"pr_failure_triage_{stamp}_{_safe_slug(branch_filter)}.json"
    path = output_dir / filename
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and triage open PR check failures.")
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--base", default="main")
    parser.add_argument("--head-prefix", default="codex/")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "docs" / "system_audit" / "pr_check_failures"))
    parser.add_argument("--fail-on-detected", action="store_true")
    parser.add_argument("--rerun-failed-actions", action="store_true")
    parser.add_argument("--rerun-settle-seconds", type=int, default=120)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        payload = {
            "generated_at": _now_utc(),
            "repo": args.repo,
            "base": args.base,
            "head_prefix": args.head_prefix,
            "status": "blocked_no_token",
            "summary": "Set GITHUB_TOKEN or GH_TOKEN.",
            "open_prs": [],
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(payload["summary"])
        return 2

    open_prs = _open_pr_payload(args.repo, args.base, args.head_prefix, token)
    report: dict[str, Any] = {
        "generated_at": _now_utc(),
        "tool": "scripts/pr_check_failure_triage.py",
        "repo": args.repo,
        "base": args.base,
        "head_prefix": args.head_prefix,
        "status": "ok",
        "open_prs": open_prs,
        "summary": _short_summary(open_prs),
        "auto_rerun_actions": [],
    }

    if args.rerun_failed_actions and _has_blocking_failures(open_prs):
        report["auto_rerun_actions"] = _rerun_failed_actions(args.repo, open_prs, token)
        deadline = time.time() + max(0, args.rerun_settle_seconds)
        while time.time() < deadline:
            refreshed = _open_pr_payload(args.repo, args.base, args.head_prefix, token)
            if not _has_blocking_failures(refreshed):
                open_prs = refreshed
                report["open_prs"] = refreshed
                break
            time.sleep(max(1, args.poll_seconds))
        report["summary_after_rerun"] = _short_summary(report["open_prs"])

    report["has_blocking_failures"] = _has_blocking_failures(report["open_prs"])
    _record_external_tool_usage(
        tool_name="pr-check-failure-triage",
        provider="github-actions",
        operation="run",
        resource=f"{args.repo}:{args.base}:{args.head_prefix}",
        status="error" if report["has_blocking_failures"] else "success",
        payload={
            "open_pr_count": len(report["open_prs"]),
            "has_blocking_failures": report["has_blocking_failures"],
            "rerun_requested": bool(args.rerun_failed_actions),
            "summary": report.get("summary"),
            "summary_after_rerun": report.get("summary_after_rerun"),
        },
    )
    report_path = _write_report(Path(args.output_dir), report, args.head_prefix)
    report["report_path"] = str(report_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"PR check triage report: {report_path}")
        print(report["summary"])
        if report.get("summary_after_rerun"):
            print(f"After auto-rerun: {report['summary_after_rerun']}")

    if args.fail_on_detected and report["has_blocking_failures"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
