#!/usr/bin/env python3
"""Import gatherings from event-source URLs onto presence nodes.

A presence carries the events where it happens. Most presences point
at Bandsintown, an iCal feed, an Eventbrite organizer profile, or a
generic events page — none of which flowed into the graph until now.
This script walks those URLs and plants the missing event nodes plus
``contributes-to`` edges with role="primary".

Usage:
    python3 scripts/import_gatherings.py --id contributor:abc123
    python3 scripts/import_gatherings.py --all
    python3 scripts/import_gatherings.py --all --limit 25 --dry-run
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Ensure api/ is on the path when run from the repo root.
ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))


def _print_report(report: dict) -> None:
    """One-presence summary."""
    nid = report["node_id"]
    imp = report["events_imported"]
    dup = report["events_skipped_dedupe"]
    matched = report.get("source_urls") or []
    errors = report.get("errors") or []
    skipped = report.get("skipped") or []

    line = f"{nid}: imported={imp} deduped={dup}"
    if matched:
        sources = ", ".join(f"{m.get('source')}({m.get('fetched',0)})" for m in matched)
        line += f"  via {sources}"
    if errors:
        line += f"  errors={len(errors)}"
    if skipped:
        skip_summary = ", ".join(s.get("reason", "?") for s in skipped)
        line += f"  skipped={skip_summary}"
    print(line)


def _print_aggregate(reports: list[dict]) -> None:
    """Per-source totals + grand total at the end of an --all run."""
    by_source: Counter[str] = Counter()
    total_imp = 0
    total_dup = 0
    total_err = 0
    for r in reports:
        total_imp += r.get("events_imported", 0)
        total_dup += r.get("events_skipped_dedupe", 0)
        total_err += len(r.get("errors") or [])
        for m in r.get("source_urls") or []:
            by_source[m.get("source", "unknown")] += int(m.get("fetched", 0) or 0)

    print()
    print(f"presences scanned: {len(reports)}")
    if by_source:
        print("per-source totals (events fetched):")
        for src, n in by_source.most_common():
            print(f"  {src}: {n}")
    print(f"events imported: {total_imp}")
    print(f"events skipped (dedupe): {total_dup}")
    if total_err:
        print(f"errors: {total_err}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import gatherings from event sources onto presence nodes",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--id",
        help="Single presence node id (e.g. contributor:abc123)",
    )
    target.add_argument(
        "--all",
        action="store_true",
        help="Walk every presence node that carries at least one URL",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of presences processed in --all mode",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip node + edge writes; only report what would be imported",
    )
    args = parser.parse_args()

    # Imported lazily so --help doesn't trigger DB connection setup.
    from app.services import gatherings_importer

    if args.id:
        report = gatherings_importer.import_for_presence(args.id, dry_run=args.dry_run)
        _print_report(report)
        if report.get("errors") and not report.get("source_urls"):
            return 1
        return 0

    reports = gatherings_importer.import_all(limit=args.limit, dry_run=args.dry_run)
    for r in reports:
        _print_report(r)
    _print_aggregate(reports)
    return 0


if __name__ == "__main__":
    sys.exit(main())
