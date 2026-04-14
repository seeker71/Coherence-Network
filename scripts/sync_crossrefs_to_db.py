#!/usr/bin/env python3
"""Sync cross-references from KB concept files into graph DB edges.

Reads the ## Cross-References section from each concept markdown file,
parses the `→ lc-xxx, lc-yyy` entries, and creates 'resonates-with'
edges in the graph DB via the API.

Also creates parent→child edges from the KB INDEX.md hierarchy.

Usage:
    python scripts/sync_crossrefs_to_db.py                            # production
    python scripts/sync_crossrefs_to_db.py --api-url http://localhost:8000
    python scripts/sync_crossrefs_to_db.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    import urllib.request
    httpx = None  # type: ignore

KB_DIR = Path(__file__).resolve().parent.parent / "docs" / "vision-kb" / "concepts"
INDEX_FILE = Path(__file__).resolve().parent.parent / "docs" / "vision-kb" / "INDEX.md"
DEFAULT_API = "https://api.coherencycoin.com"


def parse_crossrefs(filepath: Path) -> list[str]:
    """Extract cross-reference concept IDs from a markdown file."""
    text = filepath.read_text(encoding="utf-8")
    # Find ## Cross-References section
    match = re.search(r"^## Cross-References\s*\n(.*?)(?=\n## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    content = match.group(1).strip()
    # Parse → lc-xxx, lc-yyy format
    refs = re.findall(r"lc-[\w-]+", content)
    return refs


def parse_hierarchy_from_index() -> list[tuple[str, str]]:
    """Parse parent→child relationships from INDEX.md hierarchy.

    Returns list of (parent_id, child_id) tuples.
    """
    if not INDEX_FILE.exists():
        return []
    text = INDEX_FILE.read_text(encoding="utf-8")
    edges = []

    # Level 0 → Level 1 (pulse is parent of all L1 concepts)
    l1_ids = re.findall(r"\*\*\[.*?\]\(concepts/(lc-[^.]+)\.md\)\*\*", text)

    # The hierarchy is implicit in the INDEX structure
    # Level 0: lc-pulse
    # Level 1: lc-sensing, lc-attunement, lc-vitality, lc-nourishing, lc-resonating, lc-expressing, lc-spiraling, lc-field-sensing
    level1 = ["lc-sensing", "lc-attunement", "lc-vitality", "lc-nourishing", "lc-resonating", "lc-expressing", "lc-spiraling", "lc-field-sensing"]
    for child in level1:
        edges.append(("lc-pulse", child))

    return edges


def create_edge(api_url: str, from_id: str, to_id: str, edge_type: str = "resonates-with", retries: int = 3) -> bool:
    """POST /api/concepts/edges — create an edge. Returns True on success or conflict."""
    url = f"{api_url}/api/concepts/edges"
    body = {
        "from_id": from_id,
        "to_id": to_id,
        "type": edge_type,
        "created_by": "sync_crossrefs",
    }
    for attempt in range(retries):
        if httpx:
            resp = httpx.post(url, json=body, timeout=30)
            if resp.status_code in (200, 201):
                return True
            if resp.status_code == 409:
                return True  # already exists
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            # 404 means one of the nodes doesn't exist — skip silently
            if resp.status_code == 404:
                return False
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False
        else:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.status in (200, 201)
            except Exception as e:
                if "409" in str(e) or "404" in str(e):
                    return "409" in str(e)
                if "429" in str(e):
                    time.sleep(2 ** attempt)
                    continue
                print(f"  ERROR: {e}", file=sys.stderr)
                return False
    return False


def main():
    parser = argparse.ArgumentParser(description="Sync KB cross-references → graph DB edges")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()

    # Collect all cross-references
    all_edges: list[tuple[str, str, str]] = []  # (from, to, type)

    files = sorted(KB_DIR.glob("*.md"))
    for filepath in files:
        concept_id = filepath.stem
        refs = parse_crossrefs(filepath)
        for ref in refs:
            if ref != concept_id:  # no self-loops
                all_edges.append((concept_id, ref, "resonates-with"))

    # Add hierarchy edges
    hierarchy = parse_hierarchy_from_index()
    for parent, child in hierarchy:
        all_edges.append((parent, child, "emerges-from"))

    # Deduplicate (both directions count as same edge for symmetric types)
    seen = set()
    unique_edges = []
    for from_id, to_id, etype in all_edges:
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
