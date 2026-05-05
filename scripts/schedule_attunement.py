#!/usr/bin/env python3
"""Re-attune every presence so newly added concepts get picked up.

Designed for weekly cron / scheduled task. Walks every presence-type
node in the graph and re-runs the attune step (the same operation
fired by ``POST /api/presences/{id}/resonances/attune``). Idempotent:
existing edges stay, new ones get added, stale ones get pruned.

Usage:
    python3 scripts/schedule_attunement.py
    python3 scripts/schedule_attunement.py --limit 50
    python3 scripts/schedule_attunement.py --dry-run
    python3 scripts/schedule_attunement.py --dry-run --limit 3 --json

Persists the run summary to ``api/output/last_attunement_run.json``
so subsequent observers can answer "when did this last run?" by
reading one file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add api/ to sys.path so ``app.services.*`` imports resolve when this
# script is invoked directly (matches the pattern other scripts use).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def _print_table(summary: dict) -> None:
    """Human-readable summary — what an operator wants to see at a glance."""
    print(f"Attunement scheduler run")
    print(f"  started:  {summary['started_at']}")
    print(f"  finished: {summary['finished_at']}")
    print(f"  duration: {summary['duration_seconds']}s")
    print(f"  dry_run:  {summary['dry_run']}")
    print()
    print(f"  total_scanned:        {summary['total_scanned']}")
    print(f"  total_with_new_edges: {summary['total_with_new_edges']}")
    print(f"  total_unchanged:      {summary['total_unchanged']}")
    print(f"  total_errors:         {summary['total_errors']}")

    if summary.get("errors"):
        print()
        print("  Errors:")
        for err in summary["errors"][:10]:
            print(f"    - {err['node_id']}: {err['error']}")
        if len(summary["errors"]) > 10:
            print(f"    ... and {len(summary['errors']) - 10} more")

    details = summary.get("details") or []
    if details:
        print()
        print("  Top changes:")
        for d in details[:10]:
            gained = d.get("gained_count", 0)
            written = len(d.get("written") or [])
            existed = len(d.get("existed") or [])
            pruned = len(d.get("pruned") or [])
            print(
                f"    - {d['node_id']}: gained={gained} "
                f"written={written} existed={existed} pruned={pruned}"
            )

    if summary.get("summary_path"):
        print()
        print(f"  summary written to: {summary['summary_path']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-attune every presence to current Living Collective concepts."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N presences (useful for smoke tests).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute would-write counts without modifying any edges.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit the full summary as JSON (machine-readable).",
    )
    args = parser.parse_args(argv)

    # Imported here so --help works even if app modules fail to import
    # under a partial dev setup.
    from app.services import attunement_scheduler

    summary = attunement_scheduler.run_all(
        limit=args.limit,
        dry_run=args.dry_run,
    )

    if args.as_json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        _print_table(summary)

    # Non-zero exit when any presence errored — useful for cron alerting.
    return 1 if summary["total_errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
