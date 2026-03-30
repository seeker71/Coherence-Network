#!/usr/bin/env python3
"""Run maintainability audit (architecture drift + runtime placeholder debt)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_api_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_api_dir))
os.chdir(str(_api_dir.parent))

from app.services import maintainability_audit_service


def _default_baseline_path() -> Path:
    return _api_dir.parent / "docs" / "system_audit" / "maintainability_baseline.json"


def _print_human_summary(report: dict) -> None:
    summary = report.get("summary", {})
    print("Maintainability Audit")
    print("====================")
    print(f"severity: {summary.get('severity', 'unknown')}")
    print(f"risk_score: {summary.get('risk_score', 0)}")
    print(
        "counts: "
        f"layer_violations={summary.get('layer_violation_count', 0)}, "
        f"large_modules={summary.get('large_module_count', 0)}, "
        f"very_large_modules={summary.get('very_large_module_count', 0)}, "
        f"long_functions={summary.get('long_function_count', 0)}, "
        f"placeholders={summary.get('placeholder_count', 0)}"
    )
    if summary.get("regression"):
        print("regression: yes")
        for reason in summary.get("regression_reasons", []):
            print(f"  - {reason}")
    else:
        print("regression: no")

    tasks = report.get("recommended_tasks") or []
    if tasks:
        print("recommended_tasks:")
        for task in tasks[:3]:
            print(
                f"  - {task.get('task_id')}: roi={task.get('roi_estimate')} "
                f"cost_h={task.get('estimated_cost_hours')} value={task.get('value_to_whole')}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run maintainability architecture + placeholder audit")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--output", type=str, default="", help="Write full report JSON to path")
    parser.add_argument(
        "--baseline",
        type=str,
        default=str(_default_baseline_path()),
        help="Baseline JSON path for regression check",
    )
    parser.add_argument("--write-baseline", action="store_true", help="Write baseline file from current report")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit 1 when regression vs baseline is detected")
    parser.add_argument("--fail-on-blocking", action="store_true", help="Exit 1 when severity is high")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    baseline = maintainability_audit_service.load_baseline(baseline_path)

    report = maintainability_audit_service.build_maintainability_audit(baseline=baseline)
    summary = report.get("summary", {})

    if args.write_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        payload = maintainability_audit_service.baseline_from_summary(summary)
        baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human_summary(report)

    if args.fail_on_regression and bool(summary.get("regression")):
        return 1
    if args.fail_on_blocking and bool(summary.get("blocking_gap")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
