#!/usr/bin/env python3
"""Run daily asset modularity audit and optional task sync."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_api_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_api_dir))
os.chdir(str(_api_dir.parent))

from app.services import inventory_service


def _print_human_summary(report: dict) -> None:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    print("Asset Modularity Audit")
    print("======================")
    print(f"status: {report.get('status', 'unknown')}")
    print(f"blocking_assets: {summary.get('blocking_assets', 0)}")
    print(
        "scanned: "
        f"ideas={summary.get('ideas_scanned', 0)}, "
        f"specs={summary.get('specs_scanned', 0)}, "
        f"implementation_files={summary.get('implementation_files_scanned', 0)}"
    )
    by_category = summary.get("by_category") if isinstance(summary.get("by_category"), dict) else {}
    if by_category:
        print("by_category:")
        for key in sorted(by_category):
            print(f"  - {key}: {by_category[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run asset modularity drift audit")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--output", type=str, default="", help="Write report JSON to path")
    parser.add_argument("--runtime-window-seconds", type=int, default=86400)
    parser.add_argument("--max-implementation-files", type=int, default=5000)
    parser.add_argument("--create-tasks", action="store_true", help="Create deduped modularity split tasks")
    parser.add_argument("--max-tasks", type=int, default=50)
    parser.add_argument("--fail-on-blocking", action="store_true", help="Exit non-zero when blockers exist")
    args = parser.parse_args()

    report = inventory_service.evaluate_asset_modularity(
        runtime_window_seconds=max(60, int(args.runtime_window_seconds)),
        max_implementation_files=max(100, int(args.max_implementation_files)),
    )

    if args.create_tasks:
        sync = inventory_service.sync_asset_modularity_tasks(
            runtime_window_seconds=max(60, int(args.runtime_window_seconds)),
            max_tasks=max(1, int(args.max_tasks)),
        )
        report["task_sync"] = sync

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human_summary(report)

    blocking = int((report.get("summary") or {}).get("blocking_assets") or 0)
    if args.fail_on_blocking and blocking > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
