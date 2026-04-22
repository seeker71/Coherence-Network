#!/usr/bin/env python3
"""Export the graph's presence lineage into a durable JSON manifest.

Presences, gatherings, and inspired-by edges currently live only in
the sqlite DB they were resolved into — on a dev machine, that means
the lineage vanishes every time the DB is reset or the environment
changes. This script walks the local graph, captures enough of the
structure to rebuild it via the public resolver API, and writes the
result as a versioned manifest under ``docs/lineage/``.

Rebuild is the job of the companion ``import_lineage.py`` — it POSTs
each entry through ``/api/inspired-by`` (URL resolves), ``/api/graph/nodes``
(manual placeholders), and ``/api/presences/{id}/gatherings``
(events). The resolver's auto-enrichment, cross-reference scan, and
resonance attunement all fire on the target side, so re-running
against a fresh prod DB rebuilds the full organism without any of
the derived edges hardcoded.

Usage:
    python scripts/export_lineage.py
    python scripts/export_lineage.py --api http://localhost:8000
    python scripts/export_lineage.py --out docs/lineage/seed-2026-04-21.json

The manifest format is intentionally small and obvious so it can be
edited by hand when a presence's canonical URL changes or a gathering
needs correcting.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API = "http://localhost:8000"
DEFAULT_OUT = REPO_ROOT / "docs" / "lineage" / f"seed-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"

# Skip nodes that are scaffolding rather than lineage.
SKIP_ID_MARKERS = (":wanderer-", ":test-", "gatherings_endpoint",)

# Presence-type nodes worth exporting.
PRESENCE_TYPES = (
    "contributor", "community", "network-org", "event", "asset",
    "scene", "practice", "skill",
)


def _is_skippable(node_id: str) -> bool:
    return any(marker in node_id for marker in SKIP_ID_MARKERS)


def _fetch(client: httpx.Client, path: str, **params: Any) -> dict[str, Any]:
    r = client.get(path, params=params)
    r.raise_for_status()
    return r.json()


def _node_signature(node: dict[str, Any]) -> dict[str, Any]:
    """Pick the shape an importer needs to recreate or re-resolve this
    node. URLs are the gold standard — the resolver handles
    enrichment + naming + presences from there. Placeholders carry
    their full property shape so the importer can create them as-is."""
    url = node.get("canonical_url") or ""
    # Prefer resolve-by-URL when the node was minted from a real
    # canonical source — this lets the target side re-enrich against
    # the live web rather than freezing a snapshot.
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return {
            "kind": "resolved",
            "url": url,
            "id_hint": node["id"],  # for cross-referencing in edges
            "name_hint": node.get("name"),
        }
    # Manual / placeholder nodes carry their body directly.
    props = dict(node.get("properties") or {})
    # Strip properties that are part of the node's top-level shape or
    # that would be re-derived on the target.
    for derived_key in (
        "created_at", "updated_at", "lifecycle_state", "phase",
        "canonical", "canonical_url", "provider", "provider_id",
        "image_url", "presences",
    ):
        props.pop(derived_key, None)
    for top_key in (
        "tagline", "canonical_url", "provider", "provider_id",
        "image_url", "presences", "claimed", "contributor_type", "email",
        "author_display_name", "also_known_as", "location", "geo",
        "when", "where", "starts_at", "ends_at", "url", "note",
        "added_by", "added_by_name", "added_at", "profession",
        "asset_type", "creation_kind", "total_cost", "claimable",
        "scope", "levels", "provisional",
    ):
        if top_key in node:
            props[top_key] = node[top_key]
    return {
        "kind": "manual",
        "id": node["id"],
        "type": node.get("type"),
        "name": node.get("name"),
        "description": node.get("description") or "",
        "properties": {k: v for k, v in props.items() if v not in (None, "", [], {})},
    }


def export_lineage(api_base: str, source_contributor_id: str = "contributor:presence-visitor") -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_source": api_base,
        "source_contributor_id": source_contributor_id,
        "presences": [],
        "gatherings": [],
        "inspired_by": [],
    }

    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        # The visitor's inspired-by chain drives what counts as the
        # "lineage" to export. Every presence the visitor carries.
        ib = _fetch(client, "/api/inspired-by", contributor_id=source_contributor_id)
        inspired_targets: list[dict[str, Any]] = []
        for item in ib.get("items", []):
            node = item.get("node") or {}
            nid = node.get("id")
            if not nid or _is_skippable(nid):
                continue
            inspired_targets.append({
                "id": nid,
                "weight": item.get("weight"),
            })

        # Walk every presence-type node (not only inspired-by targets)
        # so gathering hosts + performers that aren't in the visitor's
        # chain still get captured.
        seen: set[str] = set()
        presences_by_id: dict[str, dict[str, Any]] = {}
        for t in PRESENCE_TYPES:
            data = _fetch(client, "/api/graph/nodes", type=t, limit=500)
            for node in data.get("items", []):
                nid = node.get("id")
                if not nid or _is_skippable(nid):
                    continue
                if nid in seen:
                    continue
                seen.add(nid)
                sig = _node_signature(node)
                manifest["presences"].append(sig)
                presences_by_id[nid] = sig

        # Inspired-by edges — reference either a URL (for resolved
        # nodes) or an id (for manual). The importer maps back.
        for target in inspired_targets:
            sig = presences_by_id.get(target["id"])
            if not sig:
                continue
            manifest["inspired_by"].append({
                "target_ref": sig.get("url") or sig["id"],
                "weight": target.get("weight"),
            })

        # Gatherings — events + their role edges. For each event, the
        # importer re-creates it with the same host + co-lead + etc.
        # role edges.
        events = _fetch(client, "/api/graph/nodes", type="event", limit=500)
        for ev in events.get("items", []):
            eid = ev.get("id")
            if not eid or _is_skippable(eid):
                continue
            roster_raw = _fetch(client, "/api/edges", to_id=eid, type="contributes-to", limit=50)
            primary_id = None
            hosted_by_id = None
            co_leaders: list[str] = []
            performers: list[str] = []
            presenters: list[str] = []
            cacao_facilitators: list[str] = []
            videographers: list[str] = []
            partners: list[str] = []
            for edge in roster_raw.get("items", []):
                role = (edge.get("properties") or {}).get("role")
                from_id = edge.get("from_id")
                if not from_id or _is_skippable(from_id):
                    continue
                if role == "primary":
                    primary_id = from_id
                elif role == "hosting":
                    hosted_by_id = from_id
                elif role in ("co-leading", "co-creating"):
                    co_leaders.append(from_id)
                elif role == "performing":
                    performers.append(from_id)
                elif role == "presenting":
                    presenters.append(from_id)
                elif role == "cacao-facilitator":
                    cacao_facilitators.append(from_id)
                elif role == "videographer":
                    videographers.append(from_id)
                elif role == "partner":
                    partners.append(from_id)
            manifest["gatherings"].append({
                "title": ev.get("name"),
                "description": ev.get("description"),
                "when": ev.get("when"),
                "starts_at": ev.get("starts_at"),
                "ends_at": ev.get("ends_at"),
                "where": ev.get("where"),
                "url": ev.get("url"),
                "note": ev.get("note"),
                "primary_ref": _ref_for(presences_by_id, primary_id),
                "hosted_by_ref": _ref_for(presences_by_id, hosted_by_id),
                "co_leaders_ref": [_ref_for(presences_by_id, i) for i in co_leaders],
                "performers_ref": [_ref_for(presences_by_id, i) for i in performers],
                "presenters_ref": [_ref_for(presences_by_id, i) for i in presenters],
                "cacao_facilitators_ref": [_ref_for(presences_by_id, i) for i in cacao_facilitators],
                "videographers_ref": [_ref_for(presences_by_id, i) for i in videographers],
                "partners_ref": [_ref_for(presences_by_id, i) for i in partners],
            })

    return manifest


def _ref_for(presences_by_id: dict[str, dict[str, Any]], nid: str | None) -> str | None:
    if not nid:
        return None
    sig = presences_by_id.get(nid)
    if not sig:
        return None
    return sig.get("url") or sig["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--source", default="contributor:presence-visitor",
                        help="Contributor id whose inspired-by chain defines the lineage")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    args = parser.parse_args()

    manifest = export_lineage(args.api, args.source)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    counts = {
        "presences": len(manifest["presences"]),
        "gatherings": len(manifest["gatherings"]),
        "inspired_by": len(manifest["inspired_by"]),
    }
    print(f"Wrote {out_path}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
