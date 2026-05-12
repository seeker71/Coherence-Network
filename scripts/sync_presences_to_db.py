#!/usr/bin/env python3
"""Sync presence markdown files -> Graph DB via API.

Reads docs/presences/{slug}.md files, resolves each to a graph node
(by canonical_url or by name), and PATCHes the node so visitors
meet each presence in their own voice.

The markdown body (everything after the YAML frontmatter) becomes the
node's `description`. The frontmatter holds the identity:

    ---
    name: Anne Tucker               # canonical human name (overrides any
                                    # OG-title that was scraped earlier)
    canonical_url: https://...      # stable lookup key
    type: contributor               # node type
    contributor_type: HUMAN         # for contributor nodes
    create_if_missing: true         # optional; create the node if not found
    ---

The PATCH endpoint auto-re-attunes resonance edges when name or
description changes, so concept links stay aligned.

Usage:
    python3 scripts/sync_presences_to_db.py anne-tucker
    python3 scripts/sync_presences_to_db.py anne-tucker mose yaima
    python3 scripts/sync_presences_to_db.py --all
    python3 scripts/sync_presences_to_db.py anne-tucker --dry-run
    python3 scripts/sync_presences_to_db.py --all --api-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESENCES_DIR = REPO_ROOT / "docs" / "presences"
DEFAULT_API = os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com")
DEFAULT_API_KEY = os.environ.get("COHERENCE_API_KEY", "dev-key")


def _request(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urlrequest.Request(url, data=data, method=method)
    # Only set Content-Type when we're actually sending a body — Cloudflare
    # treats GET-with-Content-Type as suspicious and returns 403.
    if data is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "coherence-sync-presences/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        try:
            return e.code, json.loads(raw) if raw else None
        except Exception:
            return e.code, None


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_without_frontmatter)."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    fm_block = content[4:end]
    body = content[end + 5 :]
    fm: dict = {}
    for line in fm_block.splitlines():
        m = re.match(r"^([\w_-]+):\s*(.*)$", line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.lower() in ("true", "false"):
            fm[key] = val.lower() == "true"
        else:
            fm[key] = val.strip('"').strip("'")
    return fm, body.lstrip()


def find_node_by_url(api_url: str, canonical_url: str) -> dict | None:
    """Scan contributors list for one whose canonical_url matches."""
    # The list endpoint paginates; walk through pages until found or exhausted.
    offset = 0
    limit = 50
    while True:
        status, data = _request("GET", f"{api_url}/api/contributors?limit={limit}&offset={offset}")
        if status != 200 or not data:
            return None
        items = data.get("items", []) or []
        if not items:
            return None
        for c in items:
            if (c.get("canonical_url") or "").rstrip("/") == canonical_url.rstrip("/"):
                return c
        offset += limit
        if offset >= (data.get("total") or 0):
            return None


def find_node_by_name(api_url: str, name: str) -> dict | None:
    """Direct lookup by name."""
    from urllib.parse import quote
    status, data = _request("GET", f"{api_url}/api/contributors/{quote(name, safe='')}")
    return data if status == 200 else None


def _fetch_graph_node(api_url: str, node_id: str) -> dict | None:
    """Fetch a graph node by its stable id, or None if not found."""
    status, data = _request("GET", f"{api_url}/api/graph/nodes/{node_id}")
    return data if status == 200 and data else None


def sync_one(slug: str, api_url: str, api_key: str, dry_run: bool) -> bool:
    path = PRESENCES_DIR / f"{slug}.md"
    if not path.exists():
        print(f"  ✗ {slug}: file not found at {path}")
        return False
    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    name = fm.get("name")
    canonical_url = fm.get("canonical_url")
    create_if_missing = fm.get("create_if_missing", False)
    if not name:
        print(f"  ✗ {slug}: frontmatter missing `name`")
        return False

    # Resolve the node in priority order. The slug-derived stable id
    # is tried first because it is deterministic and unambiguous —
    # earlier versions fell back to a canonical_url match across all
    # contributors, which silently collided when two nodes both had
    # empty canonical_urls (the iterator's first-empty-match would
    # win and the PATCH would overwrite the wrong node). Slug-first
    # eliminates that class of bug.
    node: dict | None = None
    stable_id = f"contributor:{slug}"

    # 1. Try the slug-derived stable id directly.
    node = _fetch_graph_node(api_url, stable_id)

    # 2. Fall back to canonical_url match (only when we have a real URL).
    # Two presences can legitimately share a canonical_url (e.g. Ubbe
    # MacLean and Anchor the Light both anchored at anchorthelight.org).
    # When the URL match returns a node with a different name than ours,
    # that's a collision — fall through to create-if-missing rather than
    # silently overwriting the other person's node.
    if not node and canonical_url:
        candidate = find_node_by_url(api_url, canonical_url)
        if candidate:
            cand_name = (candidate.get("name") or "").strip()
            if cand_name == name:
                node = candidate
                # find_node_by_url returns the /api/contributors view, whose id is a
                # UUID. PATCH happens against /api/graph/nodes/{id}, which needs the
                # stable graph id (contributor:...). Resolve it via the graph-nodes
                # index.
                if node and not (node.get("id") or "").startswith("contributor:"):
                    status, list_data = _request("GET", f"{api_url}/api/graph/nodes?type=contributor&limit=500")
                    if status == 200 and list_data:
                        our_url = canonical_url.rstrip("/")
                        for n in list_data.get("items", []) or []:
                            if (n.get("canonical_url") or "").rstrip("/") == our_url and (n.get("name") or "").strip() == name:
                                node = n
                                break

    # 3. Last resort: name-based lookup. Only trust the result when
    # the API actually returned the contributor we asked for — the
    # /api/contributors/{name} endpoint has been observed returning
    # some other contributor record when the exact name isn't on
    # file (e.g. asking for "Boulder Ecstatic Dance" returned
    # Sayuri's node), so a stable-id-shape check alone is
    # insufficient. We require either:
    #   (a) the candidate's name matches ours exactly AND the id
    #       has the stable contributor:... shape, or
    #   (b) the candidate's canonical_url matches a non-empty URL
    #       we hold.
    # Anything else falls through to create-if-missing.
    if not node and name:
        candidate = find_node_by_name(api_url, name)
        if candidate:
            cand_id = candidate.get("id") or ""
            cand_name = (candidate.get("name") or "").strip()
            cand_url = (candidate.get("canonical_url") or "").rstrip("/")
            our_url = (canonical_url or "").rstrip("/")
            if cand_name == name and cand_id.startswith("contributor:"):
                # Same name AND stable graph id — trust it.
                node = candidate
            elif our_url and cand_url == our_url:
                # Name lookup returned a UUID, but canonical_url
                # matches: resolve via the graph-nodes index.
                status, list_data = _request("GET", f"{api_url}/api/graph/nodes?type=contributor&limit=500")
                if status == 200 and list_data:
                    for n in list_data.get("items", []) or []:
                        if (n.get("canonical_url") or "").rstrip("/") == our_url:
                            node = n
                            break
            # Otherwise (UUID id + empty/mismatched URL) we treat
            # this as "no safe match" and fall through to create.

    headers = {"X-API-Key": api_key} if api_key else {}

    if not node:
        if not create_if_missing:
            print(f"  ✗ {slug}: no matching node (slug={stable_id!r}, canonical_url={canonical_url!r}, name={name!r}); set create_if_missing: true to create")
            return False
        # Create a new node with the deterministic slug-derived id.
        payload = {
            "id": stable_id,
            "type": fm.get("type", "contributor"),
            "name": name,
            "description": body.strip(),
            "properties": {
                "contributor_type": fm.get("contributor_type", "HUMAN"),
                "author_display_name": name,
                "claimed": False,
                **({"canonical_url": canonical_url} if canonical_url else {}),
            },
        }
        if dry_run:
            print(f"  ⊕ {slug}: would CREATE {stable_id} (name={name!r}, url={canonical_url!r}, body={len(body)} chars)")
            return True
        status, result = _request("POST", f"{api_url}/api/graph/nodes", payload, headers=headers)
        if status in (200, 201):
            print(f"  ⊕ {slug}: created {stable_id}")
            return True
        print(f"  ✗ {slug}: create failed (HTTP {status}): {result}")
        return False

    # PATCH existing node.
    node_id = node.get("id")
    if not node_id:
        print(f"  ✗ {slug}: resolved node has no id: {node}")
        return False

    current_name = node.get("name", "")
    current_desc = node.get("description", "") or ""
    updates: dict = {}
    if current_name != name:
        updates["name"] = name
    new_desc = body.strip()
    if current_desc.strip() != new_desc:
        updates["description"] = new_desc
    # Ensure canonical_url is set to our frontmatter value.
    if canonical_url and (node.get("canonical_url") or "").rstrip("/") != canonical_url.rstrip("/"):
        updates.setdefault("properties", {})["canonical_url"] = canonical_url

    if not updates:
        print(f"  ≡ {slug}: already in sync ({node_id})")
        return True
    if dry_run:
        changes = list(updates.keys())
        print(f"  → {slug}: would PATCH {node_id} fields={changes}")
        if "name" in updates:
            print(f"      name: {current_name!r} → {name!r}")
        if "description" in updates:
            print(f"      description: {len(current_desc)} chars → {len(new_desc)} chars")
        return True

    status, result = _request("PATCH", f"{api_url}/api/graph/nodes/{node_id}", updates, headers=headers)
    if status == 200:
        print(f"  → {slug}: synced {node_id} ({', '.join(updates.keys())})")
        return True
    print(f"  ✗ {slug}: PATCH failed (HTTP {status}): {result}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="presence slugs to sync (e.g. anne-tucker)")
    ap.add_argument("--all", action="store_true", help="sync every .md file in docs/presences/ (except INDEX.md)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change without PATCHing")
    ap.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    ap.add_argument("--api-key", default=DEFAULT_API_KEY, help="X-API-Key for write auth (default: env COHERENCE_API_KEY or 'dev-key')")
    args = ap.parse_args()

    if args.all:
        slugs = sorted(
            p.stem for p in PRESENCES_DIR.glob("*.md") if p.stem.upper() != "INDEX"
        )
    else:
        slugs = list(args.slugs)

    if not slugs:
        ap.print_help()
        return 1

    print(f"Syncing {len(slugs)} presence(s) to {args.api_url} " + ("(DRY RUN)" if args.dry_run else ""))
    ok = 0
    for slug in slugs:
        if sync_one(slug, args.api_url, args.api_key, args.dry_run):
            ok += 1
    print(f"\nResult: {ok}/{len(slugs)} succeeded")
    return 0 if ok == len(slugs) else 1


if __name__ == "__main__":
    sys.exit(main())
