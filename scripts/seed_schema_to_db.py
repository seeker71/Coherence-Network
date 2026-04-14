#!/usr/bin/env python3
"""One-time migration: load ontology schema (relationship types + axes) into DB.

Reads config/ontology/schema.json (compact format with defaults), expands
each entry, and POSTs to the graph API as nodes. Idempotent — skips
entries that already exist.

Usage:
    python scripts/seed_schema_to_db.py                          # production
    python scripts/seed_schema_to_db.py --api-url http://localhost:8000  # local
    python scripts/seed_schema_to_db.py --dry-run                # preview
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    import urllib.request
    httpx = None  # type: ignore

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "config" / "ontology" / "schema.json"
DEFAULT_API = "https://api.coherencycoin.com"


def load_schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def expand_items(items: list[dict], defaults: dict) -> list[dict]:
    """Merge defaults into each item (item values override defaults)."""
    return [{**defaults, **item} for item in items]


def post_node(api_url: str, node: dict, retries: int = 5) -> bool:
    """POST /api/graph/nodes — create a node. Returns True on success or 409 (already exists)."""
    url = f"{api_url}/api/graph/nodes"
    for attempt in range(retries):
        if httpx:
            resp = httpx.post(url, json=node, timeout=30)
            if resp.status_code in (200, 201):
                return True
            if resp.status_code == 409:
                return True  # already exists
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"    rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  ERROR {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False
        else:
            body = json.dumps(node).encode()
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.status in (200, 201)
            except Exception as e:
                if "409" in str(e):
                    return True
                if "429" in str(e):
                    time.sleep(2 ** attempt)
                    continue
                print(f"  ERROR: {e}", file=sys.stderr)
                return False
    print(f"  FAILED after {retries} retries: {node['id']}", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Seed ontology schema (rel types + axes) into DB")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    args = parser.parse_args()

    schema = load_schema()

    # --- Relationship types ---
    rel_defaults = schema.get("relationship_defaults", {})
    relationships = expand_items(schema.get("relationships", []), rel_defaults)
    print(f"Relationship types: {len(relationships)}")

    rel_ok = 0
    for rel in relationships:
        rel_id = rel["id"]
        # Store everything except id/name/description as JSONB properties
        first_class = {"id", "name", "description"}
        props = {k: v for k, v in rel.items() if k not in first_class}
        node = {
            "id": rel_id,
            "type": "relationship_type",
            "name": rel.get("name", rel_id),
            "description": rel.get("description", ""),
            "properties": props,
        }
        if args.dry_run:
            print(f"  [DRY RUN] POST {rel_id}: {rel.get('name')}")
            rel_ok += 1
        else:
            if post_node(args.api_url, node):
                rel_ok += 1
            time.sleep(0.5)  # avoid rate limiting

    # --- Axes ---
    axis_defaults = schema.get("axis_defaults", {})
    axes = expand_items(schema.get("axes", []), axis_defaults)
    print(f"Axes: {len(axes)}")

    ax_ok = 0
    for ax in axes:
        ax_id = ax["id"]
        first_class = {"id", "name", "description"}
        props = {k: v for k, v in ax.items() if k not in first_class}
        node = {
            "id": ax_id,
            "type": "axis",
            "name": ax.get("name", ax_id),
            "description": ax.get("description", ""),
            "properties": props,
        }
        if args.dry_run:
            print(f"  [DRY RUN] POST {ax_id}: {ax.get('name')}")
            ax_ok += 1
        else:
            if post_node(args.api_url, node):
                ax_ok += 1
            time.sleep(0.5)

    print(f"\nDone: {rel_ok}/{len(relationships)} rel types, {ax_ok}/{len(axes)} axes")


if __name__ == "__main__":
    main()
