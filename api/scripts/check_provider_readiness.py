#!/usr/bin/env python3
"""Check provider configuration/readiness and emit machine-readable report."""

from __future__ import annotations

import argparse
import json
import sys

from app.services import automation_usage_service


def _parse_required(raw: str) -> list[str]:
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider readiness contract check")
    parser.add_argument("--required-providers", default="", help="Comma-separated required providers")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--fail-on-blocking", action="store_true", help="Exit non-zero when blocking issues exist")
    args = parser.parse_args()

    required = _parse_required(args.required_providers)
    report = automation_usage_service.provider_readiness_report(
        required_providers=required or None,
        force_refresh=True,
    )
    payload = report.model_dump(mode="json")

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"required={','.join(payload['required_providers'])}")
        print(f"all_required_ready={payload['all_required_ready']}")
        print(f"blocking_issues={len(payload['blocking_issues'])}")
        for issue in payload["blocking_issues"]:
            print(f"- {issue}")

    if args.fail_on_blocking and payload["blocking_issues"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
