#!/usr/bin/env python3
"""Smart-contract style gate for merged changes: collective review + public validation."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.services import release_gate_service as gates


def _default_endpoints(api_base: str, web_base: str) -> list[str]:
    return [
        f"{api_base.rstrip('/')}/api/health",
        f"{api_base.rstrip('/')}/api/ideas",
        f"{web_base.rstrip('/')}/",
        f"{web_base.rstrip('/')}/api-health",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate merged change contract: checks, collective review, and public deployment."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--sha", required=True, help="Merged commit SHA on main")
    parser.add_argument("--api-base", default="https://coherence-network-production.up.railway.app")
    parser.add_argument("--web-base", default="https://coherence-network.vercel.app")
    parser.add_argument("--endpoint", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--min-approvals", type=int, default=1)
    parser.add_argument("--min-unique-approvers", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    report: dict[str, object] = {"repo": args.repo, "sha": args.sha}

    prs = gates.get_commit_pull_requests(args.repo, args.sha, github_token=token)
    merged_main_pr = None
    for pr in prs:
        if pr.get("merged_at") and str(pr.get("base", {}).get("ref", "")) == "main":
            merged_main_pr = pr
            break
    if merged_main_pr is None:
        report["result"] = "blocked"
        report["reason"] = "No merged PR to main associated with commit SHA"
        _emit(report, as_json=args.json)
        sys.exit(2)

    pr_number = int(merged_main_pr["number"])
    reviews = gates.get_pull_request_reviews(args.repo, pr_number, github_token=token)
    collective = gates.evaluate_collective_review_gates(
        merged_main_pr,
        reviews,
        min_approvals=max(0, args.min_approvals),
        min_unique_approvers=max(0, args.min_unique_approvers),
    )
    report["pr"] = {
        "number": pr_number,
        "url": merged_main_pr.get("html_url"),
        "author": ((merged_main_pr.get("user") or {}).get("login")),
        "merged_by": ((merged_main_pr.get("merged_by") or {}).get("login")),
    }
    report["collective_review"] = collective
    if not collective.get("collective_review_passed"):
        report["result"] = "blocked"
        report["reason"] = "Collective review gate failed"
        _emit(report, as_json=args.json)
        sys.exit(2)

    commit_status = gates.get_commit_status(args.repo, args.sha, github_token=token)
    check_runs = gates.get_check_runs(args.repo, args.sha, github_token=token)
    required = gates.get_required_contexts(args.repo, "main", github_token=token)
    # pseudo-pr for evaluate_pr_gates shape; merge readiness not checked, checks green is what we need post-merge
    pseudo_pr = {
        "number": pr_number,
        "head": {"sha": args.sha},
        "draft": False,
        "mergeable_state": "clean",
    }
    checks_gate = gates.evaluate_pr_gates(pseudo_pr, commit_status, check_runs, required)
    report["checks_gate"] = checks_gate
    if checks_gate.get("combined_status_state") != "success":
        report["result"] = "blocked"
        report["reason"] = "Commit checks are not green on main"
        _emit(report, as_json=args.json)
        sys.exit(2)

    endpoints = args.endpoint or _default_endpoints(args.api_base, args.web_base)
    public = gates.wait_for_public_validation(
        endpoint_urls=endpoints,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_seconds,
    )
    report["public_validation"] = public
    if not public.get("ready"):
        report["result"] = "blocked"
        report["reason"] = "Public validation timed out or failed"
        _emit(report, as_json=args.json)
        sys.exit(2)

    report["contributor_ack"] = {
        "eligible": True,
        "rule": "acknowledge only when checks + collective review + public validation pass",
        "contributor": report["pr"]["author"] if isinstance(report.get("pr"), dict) else None,
    }
    report["result"] = "contract_passed"
    _emit(report, as_json=args.json)


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"Repo: {payload.get('repo')}")
    print(f"SHA: {payload.get('sha')}")
    print(f"Result: {payload.get('result')}")
    if payload.get("reason"):
        print(f"Reason: {payload.get('reason')}")
    pr = payload.get("pr")
    if isinstance(pr, dict):
        print(f"PR: #{pr.get('number')} {pr.get('url')}")
    collective = payload.get("collective_review")
    if isinstance(collective, dict):
        print(
            "Collective review:"
            f" passed={collective.get('collective_review_passed')}"
            f" approvals={collective.get('approval_events')}"
            f" unique_approvers={collective.get('unique_approvers')}"
        )
    public = payload.get("public_validation")
    if isinstance(public, dict):
        print(f"Public validation: ready={public.get('ready')} elapsed={public.get('elapsed_seconds')}s")
        for check in public.get("checks", []):
            if isinstance(check, dict):
                print(f"  - {check.get('url')} -> {check.get('status_code')} ok={check.get('ok')}")
    ack = payload.get("contributor_ack")
    if isinstance(ack, dict):
        print(f"Contributor acknowledgment: eligible={ack.get('eligible')} contributor={ack.get('contributor')}")


if __name__ == "__main__":
    main()
