#!/usr/bin/env python3
"""Validate public Railway + Vercel deployment contract against main SHA."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.services import release_gate_service as gates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate public deployment contract (Railway API + Vercel web)."
    )
    parser.add_argument("--repo", default="seeker71/Coherence-Network")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--api-base", default="https://coherence-network-production.up.railway.app")
    parser.add_argument("--web-base", default="https://coherence-network.vercel.app")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    report = gates.evaluate_public_deploy_contract_report(
        repository=args.repo,
        branch=args.branch,
        api_base=args.api_base,
        web_base=args.web_base,
        expected_sha=args.expected_sha.strip() or None,
        timeout=max(1.0, args.timeout),
        github_token=token,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _emit(report)
    if str(report.get("result")) == "public_contract_passed":
        return
    sys.exit(2)


def _emit(report: dict[str, object]) -> None:
    print(f"Repository: {report.get('repository')}")
    print(f"Branch: {report.get('branch')}")
    print(f"Expected SHA: {report.get('expected_sha')}")
    print(f"Result: {report.get('result')}")
    if report.get("reason"):
        print(f"Reason: {report.get('reason')}")
    checks = report.get("checks", [])
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict):
                continue
            print(
                f"- {item.get('name')}: ok={item.get('ok')} "
                f"status={item.get('status_code')} url={item.get('url')}"
            )
            if item.get("observed_sha") is not None:
                print(f"  observed_sha={item.get('observed_sha')} sha_match={item.get('sha_match')}")
            if item.get("web_updated_at") is not None:
                print(
                    "  web_updated_at="
                    f"{item.get('web_updated_at')} sha_match={item.get('sha_match')} "
                    f"api_status={item.get('api_status')}"
                )


if __name__ == "__main__":
    main()
