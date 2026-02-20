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
    parser.add_argument("--runtime-window-seconds", type=int, default=86400, help="Validation runtime evidence window")
    parser.add_argument("--min-execution-events", type=int, default=1, help="Minimum successful execution events per required provider")
    parser.add_argument("--run-probes", action="store_true", help="Run live provider execution probes before validation")
    parser.add_argument("--run-auto-heal", action="store_true", help="Run provider auto-heal attempts before validation")
    parser.add_argument("--heal-rounds", type=int, default=2, help="Auto-heal rounds per provider (max 6)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--fail-on-blocking", action="store_true", help="Exit non-zero when blocking issues exist")
    args = parser.parse_args()

    required = _parse_required(args.required_providers)
    auto_heal_payload = {}
    if args.run_auto_heal:
        auto_heal_payload = automation_usage_service.run_provider_auto_heal(
            required_providers=required or None,
            max_rounds=args.heal_rounds,
            runtime_window_seconds=args.runtime_window_seconds,
            min_execution_events=args.min_execution_events,
        )
    readiness_report = automation_usage_service.provider_readiness_report(
        required_providers=required or None,
        force_refresh=True,
    )
    probe_payload = {}
    if args.run_probes:
        probe_payload = automation_usage_service.run_provider_validation_probes(required_providers=required or None)
    validation_report = automation_usage_service.provider_validation_report(
        required_providers=required or None,
        runtime_window_seconds=args.runtime_window_seconds,
        min_execution_events=args.min_execution_events,
        force_refresh=True,
    )
    payload = {
        "readiness": readiness_report.model_dump(mode="json"),
        "validation": validation_report.model_dump(mode="json"),
        "probe_run": probe_payload,
        "auto_heal": auto_heal_payload,
    }

    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"required={','.join(payload['validation']['required_providers'])}")
        print(f"all_required_ready={payload['readiness']['all_required_ready']}")
        print(f"all_required_validated={payload['validation']['all_required_validated']}")
        print(f"blocking_issues={len(payload['validation']['blocking_issues'])}")
        for issue in payload["validation"]["blocking_issues"]:
            print(f"- {issue}")

    if args.fail_on_blocking and payload["validation"]["blocking_issues"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
