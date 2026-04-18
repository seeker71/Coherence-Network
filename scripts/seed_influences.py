#!/usr/bin/env python3
"""Seed personal influences into the Coherence Network graph.

Reads a YAML file describing the people, communities, network-orgs, and
works that influenced one contributor, and creates the corresponding
graph nodes and edges.

The script is idempotent — running it twice produces no new nodes or
edges. Each placeholder node is claimable later by the real person or
collective it names; nothing is asked of them by this import.

Usage:
  python scripts/seed_influences.py                          # local API, default seed file
  python scripts/seed_influences.py --api-url https://...    # remote API
  python scripts/seed_influences.py --seed path/to/file.yaml
  python scripts/seed_influences.py --dry-run                # print what would happen
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

DEFAULT_API = os.environ.get("COHERENCE_API_URL", "http://localhost:8000")
DEFAULT_SEED = Path(__file__).parent / "influences_seed.yaml"

NODE_TYPE_PREFIX = {
    "contributor": "contributor",
    "community": "community",
    "network-org": "network-org",
    "asset": "asset",
}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "unnamed"


def _node_id(node_type: str, entry_id: str) -> str:
    prefix = NODE_TYPE_PREFIX.get(node_type, node_type)
    if entry_id.startswith(f"{prefix}:"):
        return entry_id
    return f"{prefix}:{entry_id}"


@dataclass
class Stats:
    nodes_created: int = 0
    nodes_existing: int = 0
    edges_created: int = 0
    edges_existing: int = 0
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class Seeder:
    def __init__(self, client: httpx.Client, api: str, source_id: str, *, dry_run: bool = False):
        self.client = client
        self.api = api.rstrip("/")
        self.source_id = source_id
        self.dry_run = dry_run
        self.stats = Stats()

    # ── Node / edge primitives ─────────────────────────────────────────
    def _node_exists(self, node_id: str) -> bool:
        if self.dry_run:
            return False
        r = self.client.get(f"{self.api}/api/graph/nodes/{node_id}")
        return r.status_code == 200

    def create_node(
        self,
        *,
        node_id: str,
        node_type: str,
        name: str,
        description: str = "",
        properties: dict[str, Any] | None = None,
        phase: str | None = None,
    ) -> None:
        if self._node_exists(node_id):
            self.stats.nodes_existing += 1
            print(f"  · node exists: {node_id}")
            return
        payload: dict[str, Any] = {
            "id": node_id,
            "type": node_type,
            "name": name,
            "description": description,
            "properties": properties or {},
        }
        if phase is not None:
            payload["phase"] = phase
        if self.dry_run:
            print(f"  + would create node: {node_id} ({node_type})")
            self.stats.nodes_created += 1
            return
        r = self.client.post(f"{self.api}/api/graph/nodes", json=payload)
        if r.status_code >= 400:
            msg = f"node {node_id}: {r.status_code} {r.text[:200]}"
            self.stats.errors.append(msg)
            print(f"  ! {msg}")
            return
        self.stats.nodes_created += 1
        print(f"  + created node: {node_id} ({node_type})")

    def create_edge(
        self,
        *,
        from_id: str,
        to_id: str,
        edge_type: str,
        strength: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "type": edge_type,
            "strength": strength,
            "properties": properties or {},
            "created_by": "seed_influences",
        }
        if self.dry_run:
            print(f"  + would create edge: {from_id} --[{edge_type}]--> {to_id}")
            self.stats.edges_created += 1
            return
        r = self.client.post(f"{self.api}/api/edges", json=payload)
        if r.status_code == 409:
            self.stats.edges_existing += 1
            print(f"  · edge exists: {from_id} --[{edge_type}]--> {to_id}")
            return
        if r.status_code >= 400:
            msg = f"edge {from_id}->{to_id} ({edge_type}): {r.status_code} {r.text[:200]}"
            self.stats.errors.append(msg)
            print(f"  ! {msg}")
            return
        self.stats.edges_created += 1
        print(f"  + created edge: {from_id} --[{edge_type}]--> {to_id}")

    # ── High-level operations ──────────────────────────────────────────
    def ensure_source_contributor(self, display_name: str) -> None:
        """Create the source contributor as a soft-identity node if missing."""
        node_id = self.source_id if self.source_id.startswith("contributor:") else f"contributor:{self.source_id}"
        if self._node_exists(node_id):
            print(f"Source contributor exists: {node_id}")
            self.source_id = node_id
            return
        print(f"Creating source contributor: {node_id}")
        self.create_node(
            node_id=node_id,
            node_type="contributor",
            name=_slug(display_name) or "friend",
            description=f"HUMAN contributor — {display_name}",
            properties={
                "contributor_type": "HUMAN",
                "email": f"{_slug(display_name)}@unclaimed.coherence.network",
                "author_display_name": display_name,
                "claimable": True,
                "seeded_by": "seed_influences",
            },
            phase="water",
        )
        self.source_id = node_id

    def seed_entry(self, entry: dict[str, Any]) -> None:
        entry_id = entry["id"]
        node_type = entry["node_type"]
        name = entry["name"]
        description = entry.get("description", "")
        tagline = entry.get("tagline")
        category = entry.get("category")
        themes = entry.get("themes") or []
        sub_groups = entry.get("sub_groups") or []
        people = entry.get("people") or []
        works = entry.get("works") or []

        top_id = _node_id(node_type, entry_id)
        print(f"\n→ {name} ({node_type}) — {top_id}")

        properties: dict[str, Any] = {
            "category": category,
            "tagline": tagline,
            "themes": themes or None,
            "sub_groups": sub_groups or None,
            "claimable": True,
            "seeded_by": "seed_influences",
        }
        # Contributor nodes need a display name + placeholder email so
        # the /api/contributors endpoint can render them.
        if node_type == "contributor":
            properties.update({
                "contributor_type": "HUMAN",
                "email": f"{entry_id}@unclaimed.coherence.network",
                "author_display_name": name,
            })
        # Drop keys whose value is None so the stored properties stay clean.
        properties = {k: v for k, v in properties.items() if v is not None}

        self.create_node(
            node_id=top_id,
            node_type=node_type,
            name=name,
            description=description,
            properties=properties,
        )

        # Associated people → contributor nodes + contributes-to edges
        for person in people:
            person_id = _node_id("contributor", person["id"])
            self.create_node(
                node_id=person_id,
                node_type="contributor",
                name=person["name"],
                description=person.get("notes", f"HUMAN contributor — {person['name']}"),
                properties={
                    "contributor_type": "HUMAN",
                    "email": f"{person['id']}@unclaimed.coherence.network",
                    "author_display_name": person["name"],
                    "role": person.get("role"),
                    "claimable": True,
                    "seeded_by": "seed_influences",
                },
            )
            self.create_edge(
                from_id=person_id,
                to_id=top_id,
                edge_type="contributes-to",
                properties={"role": person.get("role")} if person.get("role") else {},
            )

        # Notable works → asset nodes + contributes-to edges
        for work in works:
            work_id = _node_id("asset", work["id"])
            self.create_node(
                node_id=work_id,
                node_type="asset",
                name=work["name"],
                description=work.get("description") or f"Notable work by {name}",
                properties={
                    "asset_type": work.get("asset_type", "CONTENT"),
                    "total_cost": "0",
                    "claimable": True,
                    "seeded_by": "seed_influences",
                },
                phase="ice",
            )
            self.create_edge(
                from_id=top_id,
                to_id=work_id,
                edge_type="contributes-to",
            )

        # Source → entry: inspired-by
        self.create_edge(
            from_id=self.source_id,
            to_id=top_id,
            edge_type="inspired-by",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api-url", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    ap.add_argument("--seed", default=str(DEFAULT_SEED), help="Path to YAML seed file")
    ap.add_argument("--source", default=None, help="Override source contributor id")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    ap.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    args = ap.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.exists():
        print(f"Seed file not found: {seed_path}", file=sys.stderr)
        return 2
    data = yaml.safe_load(seed_path.read_text())
    if not isinstance(data, dict) or "entries" not in data:
        print("Seed file must have a top-level 'entries' list", file=sys.stderr)
        return 2

    source = data.get("source") or {}
    source_id = args.source or source.get("id") or "friend"
    source_display = source.get("display_name") or source_id

    print(f"API:     {args.api_url}")
    print(f"Seed:    {seed_path}")
    print(f"Source:  {source_id} ({source_display})")
    if args.dry_run:
        print("Mode:    DRY RUN — no writes")
    print()

    with httpx.Client(timeout=args.timeout) as client:
        seeder = Seeder(client, args.api_url, source_id, dry_run=args.dry_run)
        seeder.ensure_source_contributor(source_display)
        for entry in data["entries"]:
            try:
                seeder.seed_entry(entry)
            except Exception as exc:  # noqa: BLE001
                msg = f"entry {entry.get('id', '?')}: {exc}"
                seeder.stats.errors.append(msg)
                print(f"  ! {msg}")

    s = seeder.stats
    print(
        f"\nDone. Nodes: {s.nodes_created} created, {s.nodes_existing} existing. "
        f"Edges: {s.edges_created} created, {s.edges_existing} existing. "
        f"Errors: {len(s.errors)}"
    )
    if s.errors:
        for e in s.errors:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
