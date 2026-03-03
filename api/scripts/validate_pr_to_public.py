#!/usr/bin/env python3
"""Check PR gates and optionally wait for public deployment validation."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from app.services import release_gate_service as gates

_N8N_V1_MIN = (1, 123, 17)
_N8N_V2_MIN = (2, 5, 2)


def _default_endpoints(api_base: str, web_base: str) -> list[str]:
    return [
        f"{api_base.rstrip('/')}/api/health",
        f"{api_base.rstrip('/')}/api/ideas",
        f"{api_base.rstrip('/')}/api/gates/main-head",
        f"{web_base.rstrip('/')}/gates",
        f"{web_base.rstrip('/')}/api-health",
    ]


def _format_semver(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def _parse_semver(raw: str) -> tuple[int, int, int] | None:
    text = raw.strip()
    if text.startswith("v"):
        text = text[1:]
    parts = text.split(".")
    if not parts:
        return None
    values: list[int] = []
    for idx in range(3):
        if idx >= len(parts):
            values.append(0)
            continue
        match = re.match(r"^(\d+)", parts[idx])
        if not match:
            return None
        values.append(int(match.group(1)))
    return (values[0], values[1], values[2])


def _evaluate_n8n_minimum(raw_version: str) -> dict[str, object]:
    parsed = _parse_semver(raw_version)
    if parsed is None:
        return {
            "input_version": raw_version,
            "ok": False,
            "reason": "invalid_n8n_version_format",
            "minimum": "unknown",
        }

    major = parsed[0]
    if major <= 1:
        minimum = _N8N_V1_MIN
    else:
        minimum = _N8N_V2_MIN
    ok = parsed >= minimum
    return {
        "input_version": raw_version,
        "parsed_version": _format_semver(parsed),
        "minimum": _format_semver(minimum),
        "ok": ok,
        "reason": "meets_minimum" if ok else "below minimum security floor",
    }


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
    parser.add_argument(
        "--n8n-version",
        default="",
        help=(
            "Optional deployed n8n version to validate against minimum security floor "
            "(v1>=1.123.17 or v2>=2.5.2). Can also be provided via N8N_VERSION."
        ),
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    n8n_version = args.n8n_version.strip() or os.getenv("N8N_VERSION", "").strip()
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
    if n8n_version:
        n8n_gate = _evaluate_n8n_minimum(n8n_version)
        report["n8n_gate"] = n8n_gate
        if not bool(n8n_gate.get("ok")):
            report["result"] = "blocked_n8n_version"
            report["reason"] = (
                "n8n security floor not met: "
                f"found {n8n_gate.get('input_version')} "
                f"minimum {n8n_gate.get('minimum')}"
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
    n8n_gate = payload.get("n8n_gate")
    if isinstance(n8n_gate, dict):
        print(
            "n8n gate:"
            f" ok={n8n_gate.get('ok')}"
            f" input={n8n_gate.get('input_version')}"
            f" minimum={n8n_gate.get('minimum')}"
            f" reason={n8n_gate.get('reason')}"
        )


if __name__ == "__main__":
    main()
