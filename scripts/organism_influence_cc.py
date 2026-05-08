#!/usr/bin/env python3
"""Print computed organism influence CC for a field story."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.organism_influence_cc_service import compute_organism_influence_cc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default="urs-field-story")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--cc-pool", type=float, default=1000.0)
    args = parser.parse_args()

    payload = compute_organism_influence_cc(
        args.slug,
        limit=args.limit,
        cc_pool=args.cc_pool,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
