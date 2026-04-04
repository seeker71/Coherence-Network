#!/usr/bin/env python3
"""Wire existing DB ideas into the fractal structure.

Reads scripts/idea_migration_map.yaml, then for each child idea in the DB:
  - sets parent_idea_id to its super-idea
  - sets idea_type = "child"
  - leaves is_curated = False

Super-ideas themselves are written by seed_curated_ideas() in seed_db.py.
This script only wires parents — nothing is deleted, nothing is hidden.

Idempotent. Safe to re-run.

Usage:
    python3 scripts/migrate_ideas_to_fractal.py           # apply migration
    python3 scripts/migrate_ideas_to_fractal.py --dry-run # show what would change
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))


def _load_yaml_map(path: Path) -> dict:
    """Minimal YAML loader for our mapping file — scalars and simple lists."""
    result: dict = {"super_ideas": [], "children": {}, "spec_leak_patterns": [], "stubs": [], "stubs_park_under": None, "default_park_under": None}
    lines = path.read_text().splitlines()

    section: str | None = None
    current_super: dict | None = None
    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        # Top-level keys
        if not line.startswith(" ") and not line.startswith("\t"):
            m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                section = key
                if val:
                    # Scalar value
                    result[key] = val.strip('"\'')
                current_super = None
            continue

        # super_ideas list items: "  - id: foo"
        if section == "super_ideas":
            m = re.match(r"^\s+-\s+id:\s*(.+)$", line)
            if m:
                current_super = {"id": m.group(1).strip()}
                result["super_ideas"].append(current_super)
                continue
            m = re.match(r"^\s+([a-z_]+):\s*(.+)$", line)
            if m and current_super is not None:
                current_super[m.group(1)] = m.group(2).strip()
                continue

        # children dict: "  key: value"
        if section == "children":
            m = re.match(r"^\s+([A-Za-z0-9_\-\?]+):\s*(.+)$", line)
            if m:
                result["children"][m.group(1)] = m.group(2).strip()

        # Strip inline comments (but only outside quoted strings) for list items
        line_for_list = line
        if section in ("spec_leak_patterns", "stubs"):
            # Find comment marker outside any quote
            in_quote = False
            quote_char = ""
            comment_at = -1
            for idx, ch in enumerate(line_for_list):
                if ch in ('"', "'") and not in_quote:
                    in_quote = True
                    quote_char = ch
                elif ch == quote_char and in_quote:
                    in_quote = False
                    quote_char = ""
                elif ch == "#" and not in_quote:
                    comment_at = idx
                    break
            if comment_at >= 0:
                line_for_list = line_for_list[:comment_at].rstrip()

        # spec_leak_patterns: "  - pattern"
        if section == "spec_leak_patterns":
            m = re.match(r'^\s+-\s+"?([^"]*)"?\s*$', line_for_list)
            if m:
                pattern = m.group(1).strip()
                if pattern:
                    result["spec_leak_patterns"].append(pattern)

        # stubs: "  - id"
        if section == "stubs":
            m = re.match(r"^\s+-\s+(.+)$", line_for_list)
            if m:
                result["stubs"].append(m.group(1).strip())

    return result


def _matches_any_pattern(idea_id: str, patterns: list[str]) -> bool:
    for p in patterns:
        try:
            if re.search(p, idea_id):
                return True
        except re.error:
            continue
    return False


def main(dry_run: bool = False) -> int:
    from app.services import graph_service

    mapping_path = ROOT / "scripts" / "idea_migration_map.yaml"
    if not mapping_path.exists():
        print(f"ERROR: mapping file not found: {mapping_path}")
        return 1

    mapping = _load_yaml_map(mapping_path)
    super_ids = {s["id"] for s in mapping["super_ideas"]}
    children_map: dict = mapping["children"]
    spec_leak_patterns: list = mapping["spec_leak_patterns"]
    stubs: list = mapping["stubs"]
    stubs_park = mapping.get("stubs_park_under")
    default_park = mapping.get("default_park_under")

    print(f"Loaded mapping: {len(super_ids)} super, {len(children_map)} child edges, "
          f"{len(spec_leak_patterns)} leak patterns, {len(stubs)} stubs, "
          f"default_park={default_park}")

    # Read all idea nodes directly from graph
    result = graph_service.list_nodes(type="idea", limit=10000, offset=0)
    nodes = result.get("items", [])
    print(f"DB has {len(nodes)} idea nodes")

    updated = 0
    skipped_super = 0
    skipped_leak = 0
    skipped_ok = 0
    parked_default = 0
    unmapped: list[str] = []

    for node in nodes:
        nid = node.get("id", "")
        if nid in super_ids:
            skipped_super += 1
            continue

        parent_id: str | None = None
        if nid in children_map:
            parent_id = children_map[nid]
        elif nid in stubs and stubs_park:
            parent_id = stubs_park
        elif _matches_any_pattern(nid, spec_leak_patterns):
            skipped_leak += 1
            continue
        elif default_park:
            parent_id = default_park
            parked_default += 1
            unmapped.append(nid)
        else:
            unmapped.append(nid)
            continue

        # Check current values
        current_parent = node.get("parent_idea_id")
        current_type = node.get("idea_type", "standalone")
        if current_parent == parent_id and current_type == "child":
            skipped_ok += 1
            continue

        if dry_run:
            print(f"  DRY: {nid} -> parent={parent_id}, type=child")
            updated += 1
            continue

        # Merge existing properties with new ones (preserve everything else)
        props = {k: v for k, v in node.items() if k not in ("id", "type", "name", "description", "phase", "created_at", "updated_at")}
        props["parent_idea_id"] = parent_id
        props["idea_type"] = "child"
        try:
            graph_service.update_node(
                nid,
                name=node.get("name", nid),
                description=node.get("description", ""),
                properties=props,
            )
            updated += 1
        except Exception as e:
            print(f"  FAIL {nid}: {e}")

    print(f"\n=== Migration summary ===")
    print(f"  Updated:            {updated}")
    print(f"  Skipped (super):    {skipped_super}")
    print(f"  Skipped (leak):     {skipped_leak}")
    print(f"  Skipped (okay):     {skipped_ok}")
    print(f"  Parked (default):   {parked_default}")
    if unmapped:
        print(f"  Auto-parked unmapped ideas (review later): {len(unmapped)}")
        print(f"  First 30: {unmapped[:30]}")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))
