#!/usr/bin/env python3
"""Connect Urs's contributor node to the Ubud cluster via inspired-by edges.

The body's named lineage (web/lib/named-lineage.ts) holds Ilena,
Vasudev Baba, Elios, Aly Constantine, and Steve Bjorg as cells in
active or foundational relation with the founder. Each has a
contributor graph node, but no inspired-by edge from `contributor:urs`
or `contributor:seeker71`. The /me 'Inspired by' rail therefore
ranks them silently — they never surface.

This script creates the missing edges idempotently. Runs against the
live API; re-running refreshes the weight rather than duplicating.

Weights reflect the body's felt-ground, not algorithmic ranking:
the Sunday-Wednesday Ubud rhythm is load-bearing for the present
cell, so those cells sit at 0.80-0.85 — equal to the heaviest
Audible/YouTube cells (Karl May 0.953, Terry Mancour 0.927).

Usage:
    python3 scripts/connect_ubud_cluster_inspired_by.py
    python3 scripts/connect_ubud_cluster_inspired_by.py --api https://api.coherencycoin.com
    python3 scripts/connect_ubud_cluster_inspired_by.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


DEFAULT_API = "https://api.coherencycoin.com"
SOURCE_CONTRIBUTOR = "contributor:seeker71"

# Cell, target_id in graph, weight
# Weights chosen to match the felt-ground of the present rhythm:
#   Ubud cluster (current sustained presence)  → 0.85
#   Aly Constantine (close Boulder relation)   → 0.80
#   Steve Bjorg (foundation collaborator)      → 0.75
CONNECTIONS: list[tuple[str, str, float]] = [
    ("Ilena (Ranakami host, Sunday rhythm)", "contributor:ilena", 0.85),
    ("Vasudev Baba (Wednesday Satsang)", "contributor:vasudev-baba", 0.85),
    ("Elios (Sunday chanting)", "contributor:elios", 0.80),
    ("Aly Constantine (Boulder ecstatic dance)", "contributor:aly-constantine", 0.80),
    ("Steve G. Bjorg (foundation collaborator, BML era)", "contributor:steve-bjorg", 0.75),
]


def post_inspired_by_manual(
    api: str, source: str, target: str, weight: float
) -> tuple[bool, str]:
    payload = json.dumps(
        {"source_contributor_id": source, "target_id": target, "weight": weight}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{api}/api/inspired-by/manual",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
            return True, body
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return False, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default=DEFAULT_API, help="API base URL")
    ap.add_argument(
        "--source",
        default=SOURCE_CONTRIBUTOR,
        help="Source contributor id (default contributor:seeker71)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be posted; do not actually create edges",
    )
    args = ap.parse_args()

    print(f"Source: {args.source}")
    print(f"API: {args.api}")
    print()

    ok = 0
    failed = 0
    for label, target, weight in CONNECTIONS:
        prefix = "[DRY] " if args.dry_run else ""
        print(f"{prefix}{label}")
        print(f"  → {target}  weight={weight}")
        if args.dry_run:
            ok += 1
            continue
        success, msg = post_inspired_by_manual(args.api, args.source, target, weight)
        if success:
            print("  ✓ edge created/refreshed")
            ok += 1
        else:
            print(f"  ✗ FAILED: {msg}")
            failed += 1
        print()

    print(f"Done. {ok} ok, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
