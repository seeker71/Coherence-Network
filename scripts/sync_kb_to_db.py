#!/usr/bin/env python3
"""Sync KB markdown files -> Graph DB via API.

Reads concept files from docs/vision-kb/concepts/{id}.md, parses them
into structured properties, and PATCHes the graph node via the API.

This is the primary enrichment path: expand content in KB markdown,
then sync to DB. The ontology JSON is no longer the editing surface.

Usage:
    python scripts/sync_kb_to_db.py lc-space                    # sync one concept
    python scripts/sync_kb_to_db.py lc-space lc-nourishment     # sync multiple
    python scripts/sync_kb_to_db.py --all                       # sync all
    python scripts/sync_kb_to_db.py --all --min-status expanding # only expanding+
    python scripts/sync_kb_to_db.py lc-space --dry-run          # show what would change
    python scripts/sync_kb_to_db.py lc-space --api-url http://localhost:8000  # local API
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_common import (
    KB_DIR, DEFAULT_API, STATUS_ORDER,
    parse_concept_file, api_patch,
)


def patch_node(api_url: str, node_id: str, properties: dict) -> bool:
    """PATCH /api/graph/nodes/{id} with new properties."""
    return api_patch(f"{api_url}/api/graph/nodes/{node_id}", {"properties": properties})


def main():
    parser = argparse.ArgumentParser(description="Sync KB markdown -> Graph DB via API")
    parser.add_argument("concepts", nargs="*", help="Concept IDs to sync (e.g., lc-space)")
    parser.add_argument("--all", action="store_true", help="Sync all concept files")
    parser.add_argument("--min-status", default="seed", help="Minimum status to sync (seed|expanding|deepening|mature|complete)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    args = parser.parse_args()

    if not args.concepts and not args.all:
        parser.print_help()
        sys.exit(1)

    min_status_level = STATUS_ORDER.get(args.min_status, 0)

    # Collect files to sync
    files: list[Path] = []
    if args.all:
        files = sorted(KB_DIR.glob("*.md"))
    else:
        for cid in args.concepts:
            f = KB_DIR / f"{cid}.md"
            if f.exists():
                files.append(f)
            else:
                print(f"WARNING: {f} not found, skipping", file=sys.stderr)

    if not files:
        print("No concept files to sync.")
        sys.exit(0)

    synced = 0
    skipped = 0
    failed = 0

    for filepath in files:
        parsed = parse_concept_file(filepath)
        concept_id = parsed["id"]
        status = parsed["status"]
        props = parsed["properties"]

        status_level = STATUS_ORDER.get(status, 0)
        if status_level < min_status_level:
            skipped += 1
            continue

        if not props:
            print(f"  {concept_id}: no enrichment data to sync (status: {status})")
            skipped += 1
            continue

        field_summary = ", ".join(f"{k}({len(v) if isinstance(v, (list, dict)) else 'str'})" for k, v in props.items())
        print(f"  {concept_id}: {field_summary}")

        if args.dry_run:
            print(f"    [DRY RUN] would PATCH /api/graph/nodes/{concept_id}")
            synced += 1
            continue

        if patch_node(args.api_url, concept_id, props):
            print(f"    synced to DB")
            synced += 1
        else:
            print(f"    FAILED")
            failed += 1

    print(f"\nDone: {synced} synced, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
