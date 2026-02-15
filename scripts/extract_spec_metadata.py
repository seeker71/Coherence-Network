#!/usr/bin/env python3
"""Extract spec metadata used by automated lineage generation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

IDEA_PATTERNS = [
    re.compile(r"\*\*Idea\*\*:\s*`([a-z0-9-]+)`", re.IGNORECASE),
    re.compile(r"\*\*Idea\s+ID\*\*:\s*`?([a-z0-9-]+)`?", re.IGNORECASE),
    re.compile(r"^Idea:\s*`?([a-z0-9-]+)`?$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"Related to (?:idea|concept):\s*`?([a-z0-9-]+)`?", re.IGNORECASE),
]

COST_PATTERNS = [
    re.compile(r"Estimated\s+cost:\s*(\d+(?:\.\d+)?)\s*hours?", re.IGNORECASE),
    re.compile(r"^Cost:\s*(\d+(?:\.\d+)?)\s*hours?", re.MULTILINE | re.IGNORECASE),
    re.compile(r"Effort:\s*(\d+(?:\.\d+)?)\s*hours?", re.IGNORECASE),
]


def extract_spec_id(spec_path: str) -> str:
    return Path(spec_path).stem


def _read_text(spec_path: str) -> str:
    return Path(spec_path).read_text(encoding="utf-8")


def extract_idea_id_from_content(spec_path: str) -> str | None:
    try:
        content = _read_text(spec_path)
    except OSError as exc:
        print(f"Warning: Could not read spec file: {exc}", file=sys.stderr)
        return None
    for pattern in IDEA_PATTERNS:
        match = pattern.search(content)
        if match:
            return match.group(1)
    return None


def extract_estimated_cost(spec_path: str) -> float | None:
    try:
        content = _read_text(spec_path)
    except OSError as exc:
        print(f"Warning: Could not read spec file: {exc}", file=sys.stderr)
        return None
    for pattern in COST_PATTERNS:
        match = pattern.search(content)
        if match:
            return float(match.group(1))
    return None


def _build_metadata(spec_path: str) -> dict[str, str | float | None]:
    return {
        "spec_id": extract_spec_id(spec_path),
        "idea_id": extract_idea_id_from_content(spec_path),
        "estimated_cost": extract_estimated_cost(spec_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract metadata from spec file")
    parser.add_argument("spec_path", help="Path to spec file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    metadata = _build_metadata(args.spec_path)
    if args.json:
        print(json.dumps(metadata, indent=2))
    else:
        print(f"Spec ID: {metadata['spec_id']}")
        print(f"Idea ID: {metadata['idea_id'] or 'NOT FOUND'}")
        print(f"Estimated Cost: {metadata['estimated_cost'] or 'NOT FOUND'}")
    return 0 if metadata["idea_id"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
