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
        f"{api_base.rstrip('/')}/api/gates/main-head",
        f"{web_base.rstrip('/')}/gates",
        f"{web_base.rstrip('/')}/api-health",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate merged change contract: checks, collective review, and public deployment."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--sha", required=True, help="Merged commit SHA on main")
    parser.add_argument("--api-base", default="https://coherence-network-production.up.railway.app")
    parser.add_argument("--web-base", default="https://coherence-web-production.up.railway.app")
    parser.add_argument("--endpoint", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--min-approvals", type=int, default=1)
    parser.add_argument("--min-unique-approvers", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    endpoints = args.endpoint or _default_endpoints(args.api_base, args.web_base)
    report = gates.evaluate_merged_change_contract_report(
        repository=args.repo,
        sha=args.sha,
        api_base=args.api_base,
        web_base=args.web_base,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        endpoint_urls=endpoints,
        min_approvals=args.min_approvals,
        min_unique_approvers=args.min_unique_approvers,
        github_token=token,
    )
    _emit(report, as_json=args.json)
    if str(report.get("result")) == "contract_passed":
        return
    sys.exit(2)


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
