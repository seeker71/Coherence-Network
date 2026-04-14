#!/usr/bin/env python3
"""Sync cross-references from KB concept files into graph DB edges.

Reads the ## Connected Frequencies / ## Cross-References section from
each concept markdown file, parses the -> lc-xxx, lc-yyy entries, and
creates 'analogous-to' edges in the graph DB via the API.

Also creates parent->child edges from the KB INDEX.md hierarchy.

Usage:
    python scripts/sync_crossrefs_to_db.py                            # production
    python scripts/sync_crossrefs_to_db.py --api-url http://localhost:8000
    python scripts/sync_crossrefs_to_db.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import time

from kb_common import (
    KB_DIR, INDEX_FILE, DEFAULT_API,
    parse_crossrefs, api_post,
)


def parse_hierarchy_from_index() -> list[tuple[str, str]]:
    """Parse parent->child relationships from INDEX.md hierarchy.

    Extracts Level 1 concept IDs dynamically from the bold-linked entries
    in INDEX.md rather than hardcoding them.

    Returns list of (parent_id, child_id) tuples.
    """
    if not INDEX_FILE.exists():
        return []
    text = INDEX_FILE.read_text(encoding="utf-8")

    # Extract Level 1 IDs: bold-linked entries like **[Name](concepts/lc-xxx.md)**
    l1_ids = re.findall(r"\*\*\[.*?\]\(concepts/(lc-[^.]+)\.md\)\*\*", text)

    edges = []
    for child in l1_ids:
        edges.append(("lc-pulse", child))
    return edges


def create_edge(api_url: str, from_id: str, to_id: str, edge_type: str = "analogous-to") -> bool:
    """POST /api/graph/edges -- create an edge. Returns True on success or conflict."""
    body = {
        "from_id": from_id,
        "to_id": to_id,
        "type": edge_type,
        "created_by": "sync_crossrefs",
    }
    status = api_post(f"{api_url}/api/graph/edges", body)
    return status in (200, 201, 409)


def main():
    parser = argparse.ArgumentParser(description="Sync KB cross-references -> graph DB edges")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()

    # Collect all cross-references
    all_edges: list[tuple[str, str, str]] = []  # (from, to, type)

    files = sorted(KB_DIR.glob("*.md"))
    for filepath in files:
        concept_id = filepath.stem
        text = filepath.read_text(encoding="utf-8")
        refs = parse_crossrefs(text)
        for ref in refs:
            if ref != concept_id:  # no self-loops
                all_edges.append((concept_id, ref, "analogous-to"))

    # Add hierarchy edges (directional: parent -> child)
    hierarchy = parse_hierarchy_from_index()
    for parent, child in hierarchy:
        all_edges.append((parent, child, "parent-of"))

    # Deduplicate: symmetric dedup for analogous-to, directional dedup for parent-of
    seen: set[tuple[str, ...]] = set()
    unique_edges: list[tuple[str, str, str]] = []
    for from_id, to_id, etype in all_edges:
        if etype == "parent-of":
            # Directional — (A, B) != (B, A)
            key = (from_id, to_id, etype)
        else:
            # Symmetric — (A, B) == (B, A)
            key = tuple(sorted([from_id, to_id])) + (etype,)
        if key not in seen:
            seen.add(key)
            unique_edges.append((from_id, to_id, etype))

    print(f"Cross-reference edges: {len(unique_edges)} (from {len(files)} concept files)")

    ok = 0
    for from_id, to_id, etype in unique_edges:
        if args.dry_run:
            print(f"  [DRY RUN] {from_id} --{etype}--> {to_id}")
            ok += 1
        else:
            if create_edge(args.api_url, from_id, to_id, etype):
                ok += 1
            time.sleep(0.3)

    print(f"\nDone: {ok}/{len(unique_edges)} edges created/confirmed")


if __name__ == "__main__":
    main()
