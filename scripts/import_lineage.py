#!/usr/bin/env python3
"""Replay a lineage manifest against any target via the public API.

Pair to ``export_lineage.py``. Reads a JSON manifest (produced by
the exporter or edited by hand) and rebuilds the graph on the
target: resolved URLs go through /api/inspired-by (which triggers
auto-enrichment, cross-reference scanning, and resonance attune on
the target side); manual/placeholder nodes go through
/api/graph/nodes; gatherings go through
/api/presences/{id}/gatherings with the full role roster; explicit
edges go through /api/graph/edges after their endpoints exist.

Nothing is hardcoded — the target side does its own resolving, its
own attunement, its own cross-referencing. The manifest is the
minimum input needed to rebuild the lineage.

Usage:
    python scripts/import_lineage.py docs/lineage/seed-2026-04-21.json
    python scripts/import_lineage.py docs/lineage/seed.json \
        --api https://api.coherencycoin.com
    python scripts/import_lineage.py docs/lineage/seed.json \
        --source contributor:my-real-id
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def _resolve_url(client: httpx.Client, url: str, source_id: str) -> dict[str, Any] | None:
    """Re-resolve a URL via the public inspired-by endpoint. Returns
    the identity node dict on success, None on soft failure."""
    try:
        r = client.post(
            "/api/inspired-by",
            json={"name": url, "source_contributor_id": source_id},
            timeout=60.0,
        )
    except httpx.HTTPError as e:
        print(f"  ! {url}: {e}")
        return None
    if r.status_code == 422:
        # Unresolvable is a soft failure — skip, don't abort the run.
        print(f"  ! {url}: unresolved ({r.json().get('detail','')[:60]})")
        return None
    if not r.is_success:
        print(f"  ! {url}: HTTP {r.status_code}")
        return None
    return r.json().get("identity")


def _create_manual(client: httpx.Client, sig: dict[str, Any]) -> dict[str, Any] | None:
    payload = {
        "id": sig["id"],
        "type": sig["type"],
        "name": sig.get("name") or sig["id"],
        "description": sig.get("description") or "",
        "properties": sig.get("properties") or {},
    }
    try:
        r = client.post("/api/graph/nodes", json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        print(f"  ! {sig['id']}: {e}")
        return None
    if not r.is_success:
        print(f"  ! {sig['id']}: HTTP {r.status_code}")
        return None
    return r.json()


def _create_edge(
    client: httpx.Client,
    edge: dict[str, Any],
    ref_to_target_id: dict[str, str],
    source_id: str,
) -> dict[str, Any] | None:
    from_ref = edge.get("from_ref") or edge.get("from_id")
    to_ref = edge.get("to_ref") or edge.get("to_id")
    from_id = ref_to_target_id.get(from_ref, from_ref)
    to_id = ref_to_target_id.get(to_ref, to_ref)
    if not from_id or not to_id:
        print(f"  ? edge missing endpoint: {edge}")
        return None
    payload = {
        "from_id": from_id,
        "to_id": to_id,
        "type": edge["type"],
        "properties": edge.get("properties") or {},
        "strength": edge.get("strength", 1.0),
        "created_by": edge.get("created_by") or source_id,
    }
    try:
        r = client.post("/api/graph/edges", json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        print(f"  ! {from_id} -[{edge['type']}]-> {to_id}: {e}")
        return None
    if not r.is_success:
        print(f"  ! {from_id} -[{edge['type']}]-> {to_id}: HTTP {r.status_code}")
        return None
    return r.json()


def _ensure_source_contributor(client: httpx.Client, source_id: str) -> None:
    """Make sure the source contributor exists on the target. If not,
    create a minimal one — the importer writes inspired-by edges from
    this id, so it has to exist first."""
    try:
        r = client.get(f"/api/graph/nodes/{source_id}", timeout=15.0)
        if r.is_success:
            return
    except httpx.HTTPError:
        pass
    slug = source_id.split(":", 1)[-1]
    payload = {
        "id": source_id,
        "type": "contributor",
        "name": slug,
        "description": "Lineage import source",
        "properties": {
            "contributor_type": "HUMAN",
            "email": f"{slug}@lineage-import.local",
        },
    }
    r = client.post("/api/graph/nodes", json=payload, timeout=30.0)
    if r.is_success:
        print(f"Created source contributor {source_id} on target")


def replay(manifest_path: Path, api_base: str, source_id: str,
           dry_run: bool = False) -> dict[str, int]:
    manifest = json.loads(manifest_path.read_text())
    counts = {"resolved": 0, "manual": 0, "gatherings": 0, "edges": 0, "skipped": 0}

    # ref → target_id map built as we create nodes on the target.
    # A ref is either a URL (resolved entry) or the manual id string.
    ref_to_target_id: dict[str, str] = {}

    with httpx.Client(base_url=api_base) as client:
        if not dry_run:
            _ensure_source_contributor(client, source_id)

        # Pass 1 — create every presence on the target.
        presences = manifest.get("presences", [])
        gatherings = manifest.get("gatherings", [])
        edges = manifest.get("edges", [])

        print(f"\n[1/3] Creating {len(presences)} presences")
        for sig in presences:
            kind = sig.get("kind")
            label = sig.get("url") or sig.get("name") or sig.get("id")
            if dry_run:
                print(f"  [dry-run] {kind}: {label}")
                counts[kind] = counts.get(kind, 0) + 1
                continue
            if kind == "resolved":
                identity = _resolve_url(client, sig["url"], source_id)
                if identity:
                    ref_to_target_id[sig["url"]] = identity["id"]
                    counts["resolved"] += 1
                    print(f"  ✓ {sig['url']} → {identity['id']}")
                else:
                    counts["skipped"] += 1
                # Be polite to the target + give cross-ref scan time.
                time.sleep(0.3)
            elif kind == "manual":
                node = _create_manual(client, sig)
                if node:
                    ref_to_target_id[sig["id"]] = node["id"]
                    counts["manual"] += 1
                    print(f"  ✓ {sig['id']}")
                else:
                    counts["skipped"] += 1
            else:
                print(f"  ? unknown presence kind: {kind}")
                counts["skipped"] += 1

        # Pass 2 — gatherings, now that all hosts/performers exist on
        # the target with known ids.
        print(f"\n[2/3] Creating {len(gatherings)} gatherings")
        for ev in gatherings:
            primary_ref = ev.get("primary_ref")
            if not primary_ref:
                print(f"  ? skipping '{ev.get('title')}' — no primary")
                counts["skipped"] += 1
                continue
            primary_id = ref_to_target_id.get(primary_ref)
            if not primary_id:
                print(f"  ? '{ev.get('title')}' — primary not created")
                counts["skipped"] += 1
                continue
            if dry_run:
                print(f"  [dry-run] gathering: {ev.get('title')} under {primary_id}")
                counts["gatherings"] += 1
                continue

            def resolve_refs(refs: list[str | None]) -> list[str]:
                out = []
                for r in refs or []:
                    if not r:
                        continue
                    if r.startswith(("http://", "https://")):
                        # Pass URL directly to gatherings endpoint so
                        # it gets resolved on the target. Same shape
                        # the UI uses.
                        out.append(r)
                    else:
                        tid = ref_to_target_id.get(r)
                        if tid:
                            out.append(tid)
                return out

            hosted_by = ev.get("hosted_by_ref")
            if hosted_by and not hosted_by.startswith(("http://", "https://")):
                hosted_by = ref_to_target_id.get(hosted_by) or hosted_by

            payload = {
                "title": ev.get("title") or "Gathering",
                "when": ev.get("when"),
                "where": ev.get("where"),
                "url": ev.get("url"),
                "note": ev.get("note"),
                "added_by": source_id,
                "hosted_by": hosted_by,
                "co_led_with": resolve_refs(ev.get("co_leaders_ref")),
            }
            try:
                r = client.post(
                    f"/api/presences/{primary_id}/gatherings",
                    json=payload, timeout=60.0,
                )
                if r.is_success:
                    counts["gatherings"] += 1
                    print(f"  ✓ {ev.get('title')}")
                else:
                    print(f"  ! {ev.get('title')}: HTTP {r.status_code}")
                    counts["skipped"] += 1
            except httpx.HTTPError as e:
                print(f"  ! {ev.get('title')}: {e}")
                counts["skipped"] += 1
            time.sleep(0.3)

        print(f"\n[3/3] Creating {len(edges)} edges")
        for edge in edges:
            from_label = edge.get("from_ref") or edge.get("from_id")
            to_label = edge.get("to_ref") or edge.get("to_id")
            rel_type = edge.get("type")
            if dry_run:
                print(f"  [dry-run] edge: {from_label} -[{rel_type}]-> {to_label}")
                counts["edges"] += 1
                continue
            created = _create_edge(client, edge, ref_to_target_id, source_id)
            if created:
                counts["edges"] += 1
                print(f"  ✓ {from_label} -[{rel_type}]-> {to_label}")
            else:
                counts["skipped"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", help="Path to the lineage manifest JSON")
    parser.add_argument("--api", default="http://localhost:8000", help="Target API base URL")
    parser.add_argument("--source", default="contributor:presence-visitor",
                        help="Contributor id to thread inspired-by from on the target")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be sent without writing")
    args = parser.parse_args()

    path = Path(args.manifest)
    if not path.exists():
        print(f"manifest not found: {path}", file=sys.stderr)
        return 2

    print(f"Replaying {path} → {args.api} (source: {args.source})")
    if args.dry_run:
        print("DRY RUN — no writes\n")

    counts = replay(path, args.api, args.source, dry_run=args.dry_run)

    print("\nDone:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
