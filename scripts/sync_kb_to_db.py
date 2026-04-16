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
    python scripts/sync_kb_to_db.py lc-space --api-key dev-key  # explicit write auth
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kb_common import (
    KB_DIR, DEFAULT_API, STATUS_ORDER,
    parse_concept_file, parse_crossrefs, api_delete, api_get, api_patch, api_post,
)

DEFAULT_WRITE_API_KEY = "dev-key"

def _write_headers(api_key: str | None) -> dict[str, str]:
    return {"X-API-Key": api_key} if api_key else {}


def build_create_payload(parsed: dict) -> dict:
    properties = {
        "domains": ["living-collective"],
        "level": 2,
        "lifecycle_state": "gas",
    }
    if parsed.get("hz") is not None:
        properties["sacred_frequency"] = {"hz": parsed["hz"]}
    return {
        "id": parsed["id"],
        "type": "concept",
        "name": parsed.get("name") or parsed["id"],
        "description": parsed.get("description", ""),
        "phase": "gas",
        "properties": properties,
    }


def ensure_concept_node(api_url: str, parsed: dict, api_key: str | None) -> bool:
    concept_id = parsed["id"]
    try:
        api_get(f"{api_url}/api/concepts/{concept_id}")
        return True
    except Exception:
        pass

    status = api_post(
        f"{api_url}/api/graph/nodes",
        build_create_payload(parsed),
        headers=_write_headers(api_key),
    )
    if status in (200, 201):
        print("    created missing concept node")
        return True
    if status == 409:
        return True
    print(f"    create FAILED ({status})", file=sys.stderr)
    return False


def patch_node(api_url: str, node_id: str, properties: dict, api_key: str | None) -> bool:
    """PATCH /api/graph/nodes/{id} with new properties."""
    return api_patch(
        f"{api_url}/api/graph/nodes/{node_id}",
        {"properties": properties},
        headers=_write_headers(api_key),
    )


def load_crossref_map() -> dict[str, set[str]]:
    crossrefs: dict[str, set[str]] = {}
    for filepath in sorted(KB_DIR.glob("*.md")):
        concept_id = filepath.stem
        refs = set(parse_crossrefs(filepath.read_text(encoding="utf-8")))
        refs.discard(concept_id)
        crossrefs[concept_id] = refs
    return crossrefs


def fetch_concept_edges(api_url: str, concept_id: str) -> list[dict]:
    data = api_get(f"{api_url}/api/concepts/{concept_id}/edges")
    return data if isinstance(data, list) else []


def create_edge(api_url: str, from_id: str, to_id: str, edge_type: str, api_key: str | None) -> bool:
    status = api_post(
        f"{api_url}/api/graph/edges",
        {
            "from_id": from_id,
            "to_id": to_id,
            "type": edge_type,
            "created_by": "sync_kb_to_db",
        },
        headers=_write_headers(api_key),
    )
    return status in (200, 201, 409)


def delete_edge(api_url: str, edge_id: str, api_key: str | None) -> bool:
    status = api_delete(f"{api_url}/api/graph/edges/{edge_id}", headers=_write_headers(api_key))
    return status in (200, 404)


def sync_analogous_edges(
    concept_id: str,
    api_url: str,
    dry_run: bool,
    api_key: str | None,
    crossref_map: dict[str, set[str]],
) -> bool:
    desired_peers = set(crossref_map.get(concept_id, set()))
    desired_peers.update(other for other, refs in crossref_map.items() if concept_id in refs)

    if dry_run:
        print(f"    [DRY RUN] would reconcile analogous-to edges for {concept_id}: {sorted(desired_peers)}")
        return True

    try:
        edges = fetch_concept_edges(api_url, concept_id)
    except Exception as exc:
        print(f"    edge fetch FAILED ({exc})", file=sys.stderr)
        return False

    analogous_edges = [
        edge for edge in edges
        if edge.get("type") == "analogous-to"
        and (edge.get("from") == concept_id or edge.get("to") == concept_id)
    ]

    by_peer: dict[str, list[dict]] = {}
    for edge in analogous_edges:
        peer = edge["to"] if edge.get("from") == concept_id else edge["from"]
        by_peer.setdefault(peer, []).append(edge)

    ok = True

    for peer, peer_edges in by_peer.items():
        extras = peer_edges[1:]
        if peer not in desired_peers:
            extras = peer_edges
        for edge in extras:
            if not delete_edge(api_url, edge["id"], api_key):
                print(f"    delete FAILED ({edge['id']})", file=sys.stderr)
                ok = False

    for peer in sorted(desired_peers):
        if peer in by_peer:
            continue
        from_id, to_id = sorted([concept_id, peer])
        if not create_edge(api_url, from_id, to_id, "analogous-to", api_key):
            print(f"    edge create FAILED ({from_id} -> {to_id})", file=sys.stderr)
            ok = False

    return ok


def sync_concept(
    parsed: dict,
    api_url: str,
    dry_run: bool,
    api_key: str | None,
    crossref_map: dict[str, set[str]],
) -> bool:
    concept_id = parsed["id"]
    props = parsed["properties"]

    if dry_run:
        print(f"    [DRY RUN] would ensure + PATCH /api/graph/nodes/{concept_id}")
        return sync_analogous_edges(concept_id, api_url, dry_run, api_key, crossref_map)

    if not ensure_concept_node(api_url, parsed, api_key):
        return False
    if not patch_node(api_url, concept_id, props, api_key):
        return False
    return sync_analogous_edges(concept_id, api_url, dry_run, api_key, crossref_map)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync KB markdown -> Graph DB via API")
    parser.add_argument("concepts", nargs="*", help="Concept IDs to sync (e.g., lc-space)")
    parser.add_argument("--all", action="store_true", help="Sync all concept files")
    parser.add_argument("--min-status", default="seed", help="Minimum status to sync (seed|expanding|deepening|mature|complete)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--api-key", default=DEFAULT_WRITE_API_KEY, help="Write API key for POST/PATCH operations (default: dev-key)")
    args = parser.parse_args(argv)

    if not args.concepts and not args.all:
        parser.print_help()
        return 1

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
        return 0

    synced = 0
    skipped = 0
    failed = 0
    crossref_map = load_crossref_map()

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

        if sync_concept(parsed, args.api_url, args.dry_run, args.api_key, crossref_map):
            print(f"    synced to DB")
            synced += 1
        else:
            print(f"    FAILED")
            failed += 1

    print(f"\nDone: {synced} synced, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
