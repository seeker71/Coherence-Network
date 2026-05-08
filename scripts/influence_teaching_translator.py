#!/usr/bin/env python3
"""Print influence teaching translator shards for a field story."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.influence_teaching_translator_service import get_influence_teaching_translator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", default="urs-field-story")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    payload = get_influence_teaching_translator(args.slug, limit=args.limit)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
