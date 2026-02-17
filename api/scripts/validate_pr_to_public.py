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
        f"{api_base.rstrip('/')}/api/gates/main-head",
        f"{web_base.rstrip('/')}/gates",
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
    parser.add_argument("--web-base", default="https://coherence-web-production.up.railway.app")
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

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    endpoints = args.endpoint or _default_endpoints(args.api_base, args.web_base)
    report = gates.evaluate_pr_to_public_report(
        repository=args.repo,
        branch=args.branch,
        base=args.base,
        api_base=args.api_base,
        web_base=args.web_base,
        wait_public=args.wait_public,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        endpoint_urls=endpoints,
        github_token=token,
    )
    _emit(report, as_json=args.json)
    result = str(report.get("result"))
    if result in ("ready_for_merge", "public_validated"):
        sys.exit(0)
    sys.exit(2)


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
