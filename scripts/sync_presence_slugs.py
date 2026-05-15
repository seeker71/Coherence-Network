#!/usr/bin/env python3
"""Sync `/people/{slug}` presence pages back onto contributor nodes.

Stopgap. The body is moving from 90 hand-authored static `/people/{slug}/`
directories to a single dynamic `[id]` route that renders any contributor
from graph node properties. See
`docs/coherence-substrate/agents-tending-presence-pages.md` for the move
and how to migrate a cell.

While both paths coexist, `presence_slug` carries the override for the
rare case where a static directory sits at a different URL than the
contributor's own `slug` (e.g. `/people/urs` ↔ `slug=urs-muff`). The
/me tile uses `presence_slug` when set, the contributor's own `slug`
otherwise — so every contributor reaches a presence page regardless of
whether a static directory was authored for them.

When a static directory is composted, re-run this script and the
override clears: the contributor's own slug carries the tile, the
dynamic route renders the page from graph properties.

Idempotent. Safe to re-run after adding or composting presence pages.

Usage:
    python3 scripts/sync_presence_slugs.py                # against prod
    python3 scripts/sync_presence_slugs.py --dry-run      # show plan
    python3 scripts/sync_presence_slugs.py --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import urllib.error
import urllib.request
import json


DEFAULT_API = "https://api.coherencycoin.com"
PEOPLE_DIR = Path(__file__).resolve().parent.parent / "web" / "app" / "people"


def discover_presence_pages() -> list[tuple[str, str]]:
    """Walk `web/app/people/*/page.tsx`, return (slug, graphSlug) pairs.

    Skips dynamic [id] and edit-your-profile entries. A page with no
    `graphSlug=` is silently skipped — those are pages that don't claim
    a graph anchor and so can't be reverse-linked.
    """
    pairs: list[tuple[str, str]] = []
    if not PEOPLE_DIR.is_dir():
        return pairs
    for entry in sorted(PEOPLE_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("[") or entry.name == "edit-your-profile":
            continue
        page_file = entry / "page.tsx"
        if not page_file.is_file():
            continue
        text = page_file.read_text(encoding="utf-8")
        m = re.search(r'graphSlug\s*=\s*[\"\']([^\"\']+)[\"\']', text)
        if not m:
            continue
        pairs.append((entry.name, m.group(1)))
    return pairs


def fetch_node(api_url: str, node_id: str) -> Optional[dict]:
    """GET /api/graph/nodes/{id}. Returns the node dict or None on 404."""
    url = f"{api_url.rstrip('/')}/api/graph/nodes/{urllib_quote(node_id)}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "coherence-sync/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def patch_node(api_url: str, node_id: str, presence_slug: str) -> bool:
    """PATCH the node's properties with presence_slug. True on success."""
    url = f"{api_url.rstrip('/')}/api/graph/nodes/{urllib_quote(node_id)}"
    body = json.dumps({"properties": {"presence_slug": presence_slug}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "coherence-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"PATCH {node_id} failed: {e.code} {e.reason}\n")
        return False
    except urllib.error.URLError as e:
        sys.stderr.write(f"PATCH {node_id} unreachable: {e}\n")
        return False


def urllib_quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing.")
    args = parser.parse_args()

    pairs = discover_presence_pages()
    if not pairs:
        print("No presence pages with graphSlug found.")
        return 0

    print(f"Walked {len(pairs)} presence pages with graphSlug.")
    updated = 0
    skipped_non_contributor = 0
    skipped_already = 0
    skipped_aliased = 0
    missing = 0
    # Track contributor ids we've already written this run so that when
    # two presence pages alias to the same contributor (e.g. /people/ilena
    # and /people/ilena-young both → contributor:ilena), the first match
    # wins. Alphabetical order makes the choice deterministic; tend the
    # alias by hand if a different slug should be canonical.
    written_node_ids: set[str] = set()

    for slug, graph_slug in pairs:
        node = fetch_node(args.api_url, graph_slug)
        if node is None:
            print(f"  · {slug} → {graph_slug} (node not found)")
            missing += 1
            continue
        if node.get("type") != "contributor":
            skipped_non_contributor += 1
            continue
        node_id = node.get("id") or graph_slug
        if node_id in written_node_ids:
            print(f"  · skip alias: /people/{slug} also maps to {node_id}")
            skipped_aliased += 1
            continue
        current = (node.get("presence_slug") or "").strip()
        if current == slug:
            skipped_already += 1
            written_node_ids.add(node_id)
            continue
        if args.dry_run:
            print(f"  · would set presence_slug={slug!r} on {node_id} (was {current!r})")
            updated += 1
            written_node_ids.add(node_id)
            continue
        if patch_node(args.api_url, node_id, slug):
            print(f"  · set presence_slug={slug!r} on {node_id}")
            updated += 1
            written_node_ids.add(node_id)

    print(
        f"Summary: updated={updated}, "
        f"already_set={skipped_already}, "
        f"non_contributor={skipped_non_contributor}, "
        f"aliased={skipped_aliased}, "
        f"missing_nodes={missing}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
