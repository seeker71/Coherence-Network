#!/usr/bin/env python3
"""Sync structured presence content from JSON files into graph nodes.

Files at `docs/presence-content/{slug}.json` hold the body's authored
content for a /people/{slug} page in the same shape `PresenceContent`
defines (per-locale envelope with hero/facts/note_from_body/articles/
footer, each prose slot as markdown). This script reads them and
PATCHes the contributor graph node's `presence_content` property so
the dynamic [id] route renders the page through `PersonProfileTemplate`
— the same template the static directories use, with byte-identical
visual chrome.

This is the second sync pipeline alongside `sync_presences_to_db.py`:
that one writes the markdown body to `description` (PresencePage's
artist/musician card); this one writes structured content to
`presence_content` (PersonProfileTemplate's full long-form page).

Usage:
    python3 scripts/sync_presence_content.py portal
    python3 scripts/sync_presence_content.py portal urs mose
    python3 scripts/sync_presence_content.py --all
    python3 scripts/sync_presence_content.py portal --dry-run
    python3 scripts/sync_presence_content.py portal --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = REPO_ROOT / "docs" / "presence-content"
DEFAULT_API = "https://api.coherencycoin.com"


def find_node(api_url: str, slug: str) -> dict | None:
    """Look up the contributor node by slug.

    Tries `/api/graph/nodes/{slug}` first; if 404, tries
    `/api/graph/nodes/contributor:{slug}`. Returns the node dict on
    success, None when no match.
    """
    for candidate in (slug, f"contributor:{slug}"):
        url = f"{api_url.rstrip('/')}/api/graph/nodes/{_quote(candidate)}"
        req = urlrequest.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "coherence-sync/1.0"},
        )
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 404:
                continue
            raise
    return None


def patch_presence_content(
    api_url: str, node_id: str, presence_content: dict
) -> bool:
    """PATCH the graph node's `presence_content` property."""
    url = f"{api_url.rstrip('/')}/api/graph/nodes/{_quote(node_id)}"
    body = json.dumps({"properties": {"presence_content": presence_content}}).encode("utf-8")
    req = urlrequest.Request(
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
        with urlrequest.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except HTTPError as e:
        sys.stderr.write(f"PATCH {node_id} failed: {e.code} {e.reason}\n")
        return False


def _quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s, safe="")


def list_content_files() -> list[Path]:
    if not CONTENT_DIR.is_dir():
        return []
    return sorted(p for p in CONTENT_DIR.iterdir() if p.suffix == ".json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*", help="Slugs to sync (omit with --all)")
    parser.add_argument("--all", action="store_true", help="Sync every JSON in docs/presence-content/")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.all:
        slugs = [p.stem for p in list_content_files()]
    else:
        slugs = args.slugs

    if not slugs:
        parser.error("provide one or more slugs, or --all")

    print(f"Syncing {len(slugs)} cell(s) to {args.api_url}")
    succeeded = failed = 0

    for slug in slugs:
        path = CONTENT_DIR / f"{slug}.json"
        if not path.is_file():
            print(f"  ✗ {slug}: no JSON at {path.relative_to(REPO_ROOT)}")
            failed += 1
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  ✗ {slug}: invalid JSON ({e})")
            failed += 1
            continue

        node = find_node(args.api_url, slug)
        if not node:
            print(f"  ✗ {slug}: no contributor node found for slug")
            failed += 1
            continue

        node_id = node.get("id", f"contributor:{slug}")
        if args.dry_run:
            locales = list(payload.keys()) if isinstance(payload, dict) else []
            print(f"  · would set presence_content on {node_id} (locales: {locales})")
            succeeded += 1
            continue

        if patch_presence_content(args.api_url, node_id, payload):
            locales = list(payload.keys()) if isinstance(payload, dict) else []
            print(f"  → {slug}: synced {node_id} (locales: {locales})")
            succeeded += 1
        else:
            failed += 1

    print(f"\nResult: {succeeded}/{succeeded + failed} succeeded")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
