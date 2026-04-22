#!/usr/bin/env python3
"""Move presences to their honest node types.

The resolver's HOST_HINTS inference assigns ``contributor`` to any
URL that isn't on a known community/festival host. That worked fine
for artists but left festivals, organizations, platforms, and
physical venues all sharing the ``contributor`` bucket — making the
/people directory read as if Unison Festival, Boulder Theater, and
Actualize Earth are all humans.

This pass walks known-misclassified nodes by id + name and moves
them to the right type:

  · scene        — physical places, venues, sanctuaries, resorts
  · community    — gathering collectives (festivals, dance series,
                   recurring event groups)
  · network-org  — organizations, platforms, promoter brands, NGOs
  · contributor  — only humans (and named artist projects for humans)

Idempotent: running twice is a no-op. Safe to run against any env.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.services.graph_service import session  # noqa: E402
from app.models.graph import Node  # noqa: E402


# Canonical retyping map. Each key is a name-substring or id-substring
# match; value is the target type. We match against both so the pass
# works across environments where auto-generated ids differ slightly.
RETYPE_RULES: list[tuple[str, str]] = [
    # Scenes / physical places
    ("Boulder Theater", "scene"),
    ("Avalon Ballroom", "scene"),
    ("Tico Time", "scene"),
    ("Vali Soul Sanctuary", "scene"),
    ("The Yoga Barn", "scene"),
    ("Pyramids of Chi", "scene"),
    ("Heart Space Bali", "scene"),
    ("Udara Bali", "scene"),

    # Communities — gathering collectives, festivals, dance series
    ("Unison Festival", "community"),
    ("BaliSpirit Festival", "community"),
    ("PORTAL", "community"),
    ("Pagan Ritual", "community"),
    ("Boulder Ecstatic Dance", "community"),
    ("Ecstatic Dance", "community"),
    ("E.M.T.", "community"),
    ("Ecstatic Movement Tribe", "community"),
    ("Ministry of Movement", "community"),
    ("Rhythm Sanctuary", "community"),
    ("OneBody Dance", "community"),
    ("Reciprocity Music", "community"),

    # Network-orgs — organizations, platforms, promoter brands, NGOs
    ("Actualize Earth", "network-org"),
    ("Conscious Roots", "network-org"),
    ("Next Level Soul", "network-org"),
    ("MAPS", "network-org"),
    ("Multidisciplinary Association for Psychedelic Studies", "network-org"),
    ("Only One", "network-org"),
    ("Ubud Raw", "network-org"),
]


# Only retype from these source types — events stay events, assets
# stay assets. A "Boulder Theater"-named event shouldn't become a
# scene just because its title contains the venue's name.
RETYPEABLE_FROM = {"contributor", "community", "network-org", "scene"}


def reclassify(dry_run: bool = False) -> dict[str, int]:
    """Walk the graph and retype nodes whose full name matches the
    rules. Uses whole-name equality (case-insensitive) so "Boulder
    Theater" doesn't catch "Ocean Bloom at Boulder Theater". Only
    retypes from the presence-type buckets — events, assets,
    concepts, and practices stay where they are."""
    counts: dict[str, int] = {}
    with session() as s:
        nodes = s.query(Node).all()
        for node in nodes:
            if not node.name:
                continue
            if node.type not in RETYPEABLE_FROM:
                continue
            node_name_lower = node.name.lower().strip()
            for needle, target_type in RETYPE_RULES:
                if needle.lower() != node_name_lower:
                    continue
                if node.type == target_type:
                    break  # already right
                print(f"  {node.name:45s} {node.type:12s} → {target_type}")
                if not dry_run:
                    node.type = target_type
                counts[target_type] = counts.get(target_type, 0) + 1
                break
        if not dry_run:
            s.commit()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "WRITING"
    print(f"=== Reclassifying presence types ({mode}) ===\n")

    counts = reclassify(dry_run=args.dry_run)

    print(f"\nRetyped {sum(counts.values())} nodes:")
    for t, n in counts.items():
        print(f"  {t:12s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
