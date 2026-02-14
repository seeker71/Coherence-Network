#!/usr/bin/env python3
"""Check PR gates and optionally wait for public deployment validation."""

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
        f"{web_base.rstrip('/')}/api-health",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate PR merge gates, then optionally wait for public endpoints to become ready."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--branch", required=True, help="Head branch to inspect (e.g. codex/system-question-ledger)")
    parser.add_argument("--base", default="main", help="Base branch for required checks/protection")
    parser.add_argument("--api-base", default="https://coherence-network-production.up.railway.app")
    parser.add_argument("--web-base", default="https://coherence-network.vercel.app")
    parser.add_argument(
        "--endpoint",
        action="append",
        default=[],
        help="Explicit endpoint to validate (can be repeated). Overrides defaults when provided.",
    )
    parser.add_argument("--wait-public", action="store_true", help="Wait for public endpoints to be 200.")
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Output JSON only.")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    report: dict[str, object] = {
        "repo": args.repo,
        "branch": args.branch,
        "base": args.base,
    }

    prs = gates.get_open_prs(args.repo, head_branch=args.branch, github_token=token)
    report["open_pr_count"] = len(prs)
    if not prs:
        report["result"] = "blocked"
        report["reason"] = "No open PR found for branch"
        _emit(report, as_json=args.json)
        sys.exit(2)

    pr = prs[0]
    sha = pr.get("head", {}).get("sha")
    if not isinstance(sha, str):
        report["result"] = "blocked"
        report["reason"] = "PR has no head SHA"
        _emit(report, as_json=args.json)
        sys.exit(2)

    commit_status = gates.get_commit_status(args.repo, sha, github_token=token)
    check_runs = gates.get_check_runs(args.repo, sha, github_token=token)
    required = gates.get_required_contexts(args.repo, args.base, github_token=token)
    pr_gate = gates.evaluate_pr_gates(pr, commit_status, check_runs, required)
    report["pr_gate"] = pr_gate

    if not pr_gate.get("ready_to_merge"):
        report["result"] = "blocked"
        report["reason"] = "PR gates not fully green"
        _emit(report, as_json=args.json)
        sys.exit(2)

    if not args.wait_public:
        report["result"] = "ready_for_merge"
        _emit(report, as_json=args.json)
        return

    endpoints = args.endpoint or _default_endpoints(args.api_base, args.web_base)
    public = gates.wait_for_public_validation(
        endpoint_urls=endpoints,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_seconds,
    )
    report["public_validation"] = public
    report["result"] = "public_validated" if public.get("ready") else "blocked"
    _emit(report, as_json=args.json)
    sys.exit(0 if public.get("ready") else 2)


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"Repo: {payload.get('repo')}")
    print(f"Branch: {payload.get('branch')} -> {payload.get('base')}")
    print(f"Result: {payload.get('result')}")
    if payload.get("reason"):
        print(f"Reason: {payload.get('reason')}")
    gate = payload.get("pr_gate")
    if isinstance(gate, dict):
        print(
            "PR gate:"
            f" ready_to_merge={gate.get('ready_to_merge')}"
            f" draft={gate.get('draft')}"
            f" combined_status={gate.get('combined_status_state')}"
            f" missing_required={gate.get('missing_required_contexts')}"
            f" failing_required={gate.get('failing_required_contexts')}"
        )
    public = payload.get("public_validation")
    if isinstance(public, dict):
        print(
            f"Public validation: ready={public.get('ready')} "
            f"elapsed={public.get('elapsed_seconds')}s"
        )
        for check in public.get("checks", []):
            if isinstance(check, dict):
                print(f"  - {check.get('url')} -> {check.get('status_code')} ok={check.get('ok')}")


if __name__ == "__main__":
    main()
