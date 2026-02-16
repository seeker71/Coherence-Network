#!/usr/bin/env python3
"""Run provider validation probes and verify config+usage+execution contract."""

from __future__ import annotations

import argparse
import json
import sys

import httpx


DEFAULT_REQUIRED = "coherence-internal,openai-codex,github,railway,claude"


def _parse_required(raw: str) -> str:
    rows = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return ",".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run provider validation e2e contract")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--required-providers", default=DEFAULT_REQUIRED)
    parser.add_argument("--runtime-window-seconds", type=int, default=86400)
    parser.add_argument("--min-execution-events", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    required = _parse_required(args.required_providers)
    base_url = args.base_url.rstrip("/")

    with httpx.Client(timeout=20.0) as client:
        run_response = client.post(
            f"{base_url}/api/automation/usage/provider-validation/run",
            params={"required_providers": required},
        )
        run_response.raise_for_status()
        run_payload = run_response.json()

        report_response = client.get(
            f"{base_url}/api/automation/usage/provider-validation",
            params={
                "required_providers": required,
                "runtime_window_seconds": args.runtime_window_seconds,
                "min_execution_events": args.min_execution_events,
                "force_refresh": True,
            },
        )
        report_response.raise_for_status()
        report_payload = report_response.json()

    output = {"run": run_payload, "report": report_payload}
    if args.json:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"required_providers={required}")
        print(f"all_required_validated={report_payload.get('all_required_validated')}")
        print(f"blocking_issues={len(report_payload.get('blocking_issues', []))}")
        for issue in report_payload.get("blocking_issues", []):
            print(f"- {issue}")

    return 0 if report_payload.get("all_required_validated") else 2


if __name__ == "__main__":
    raise SystemExit(main())
