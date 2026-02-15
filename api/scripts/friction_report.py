#!/usr/bin/env python3
"""Summarize friction events and rank top energy-loss sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services import friction_service

def main() -> None:
    parser = argparse.ArgumentParser(description="Rank friction points by energy loss.")
    parser.add_argument(
        "--file",
        default="logs/friction_events.jsonl",
        help="Path to friction events JSONL file (default: logs/friction_events.jsonl)",
    )
    parser.add_argument("--window-days", type=int, default=7, help="Rolling window in days.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    path = Path(args.file)
    events, ignored = friction_service.load_events(path)
    report = friction_service.summarize(events, window_days=max(1, args.window_days))
    report["source_file"] = str(path)
    report["ignored_lines"] = ignored

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"Friction report: {path}")
    print(f"Window: last {report['window_days']} day(s)")
    print(f"Events: {report['total_events']} (open: {report['open_events']}, ignored lines: {ignored})")
    print(
        "Totals: "
        f"energy_loss={report['total_energy_loss']:.2f}, "
        f"cost_of_delay={report['total_cost_of_delay']:.2f}"
    )
    print("")
    print("Top block types by energy loss:")
    if report["top_block_types"]:
        for idx, item in enumerate(report["top_block_types"], start=1):
            print(
                f"{idx}. {item['key']} | count={item['count']} "
                f"| energy_loss={item['energy_loss']:.2f} | cost_of_delay={item['cost_of_delay']:.2f}"
            )
    else:
        print("No events in window.")


if __name__ == "__main__":
    main()
