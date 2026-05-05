#!/usr/bin/env python3
"""Auto-import creations into the graph from external sources.

Walks one presence (`--id`) or every presence (`--all`), fetches
the creations from each registered source plugin (Bandcamp,
YouTube, Substack, Goodreads, generic RSS), and writes them as
asset nodes with `contributes-to` edges from the presence.

Usage:
    python3 scripts/import_creations.py --id contributor:foo
    python3 scripts/import_creations.py --all
    python3 scripts/import_creations.py --all --source bandcamp
    python3 scripts/import_creations.py --all --limit 5 --dry-run

Dry-run prints what would be imported without writing to the graph.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_app_path() -> None:
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if not api_dir.exists():
        return
    sys_path = str(api_dir)
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)


def _summarise(report: dict) -> str:
    parts = [
        f"node_id={report.get('node_id')}",
        f"urls={len(report.get('source_urls') or [])}",
        f"imported={report.get('creations_imported', 0)}",
        f"deduped={report.get('creations_skipped_dedupe', 0)}",
    ]
    invalid = report.get("creations_skipped_invalid_kind") or 0
    if invalid:
        parts.append(f"invalid_kind={invalid}")
    errors = report.get("errors") or []
    if errors:
        parts.append(f"errors={len(errors)}")
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--id",
        dest="node_id",
        help="Run against a single presence node id (e.g. contributor:foo)",
    )
    target.add_argument(
        "--all",
        action="store_true",
        help="Run against every presence node in the graph",
    )
    parser.add_argument(
        "--source",
        choices=["bandcamp", "youtube", "substack", "rss", "goodreads"],
        help="Restrict the source plugins to one named source",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on presences walked (only with --all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the import plan without persisting nodes/edges",
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit the full JSON report instead of one-line summaries",
    )
    args = parser.parse_args(argv)

    _ensure_app_path()
    from app.services import creations_importer  # noqa: WPS433 — defer import until path set

    if args.node_id:
        report = creations_importer.import_for_presence(
            args.node_id,
            only_source=args.source,
            dry_run=args.dry_run,
        )
        if args.emit_json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(_summarise(report))
        return 0

    reports = creations_importer.import_all(
        only_source=args.source,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    if args.emit_json:
        print(json.dumps(reports, indent=2, default=str))
    else:
        for report in reports:
            print(_summarise(report))
        total_imported = sum(r.get("creations_imported", 0) for r in reports)
        total_deduped = sum(r.get("creations_skipped_dedupe", 0) for r in reports)
        print(
            f"--- {len(reports)} presences | "
            f"{total_imported} imported | {total_deduped} deduped"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
