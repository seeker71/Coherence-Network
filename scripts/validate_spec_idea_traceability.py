#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _load_known_idea_ids(repo_root: Path) -> set[str]:
    out: set[str] = set()
    idea_service = repo_root / "api" / "app" / "services" / "idea_service.py"
    text = idea_service.read_text(encoding="utf-8")

    for match in re.findall(r'"id":\s*"([a-z0-9][a-z0-9-]*)"', text):
        out.add(match)
    for match in re.findall(r'^\s*"([a-z0-9][a-z0-9-]*)"\s*:\s*\{', text, flags=re.MULTILINE):
        out.add(match)

    system_audit = repo_root / "docs" / "system_audit"
    for path in sorted(system_audit.glob("commit_evidence_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ids = payload.get("idea_ids")
        if not isinstance(ids, list):
            continue
        for value in ids:
            if isinstance(value, str) and value.strip():
                out.add(value.strip())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all specs map to a known idea_id.")
    parser.add_argument(
        "--file",
        default="docs/SPEC-IDEA-TRACEABILITY.json",
        help="Traceability mapping file path.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    mapping_path = (repo_root / args.file).resolve()
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))

    rows = payload.get("mappings")
    if not isinstance(rows, list):
        print("ERROR: mappings must be a list")
        return 1

    spec_paths = sorted(
        str(p.relative_to(repo_root)).replace("\\", "/")
        for p in (repo_root / "specs").glob("*.md")
    )
    mapped_paths: list[str] = []
    mapped_ideas: dict[str, str] = {}

    for row in rows:
        if not isinstance(row, dict):
            print("ERROR: each mapping row must be an object")
            return 1
        spec_path = str(row.get("spec_path") or "").strip()
        idea_id = str(row.get("idea_id") or "").strip()
        if not spec_path or not idea_id:
            print(f"ERROR: invalid mapping row: {row}")
            return 1
        mapped_paths.append(spec_path)
        mapped_ideas[spec_path] = idea_id

    errors: list[str] = []
    expected = set(spec_paths)
    mapped = set(mapped_paths)
    missing = sorted(expected - mapped)
    extra = sorted(mapped - expected)

    if missing:
        errors.append(f"missing spec mappings: {len(missing)}")
    if extra:
        errors.append(f"unknown spec mappings: {len(extra)}")

    if len(mapped_paths) != len(mapped):
        errors.append("duplicate spec_path entries found")

    known_idea_ids = _load_known_idea_ids(repo_root)
    unknown_idea_rows = sorted(
        path for path, idea_id in mapped_ideas.items() if idea_id not in known_idea_ids
    )
    if unknown_idea_rows:
        errors.append(f"mappings with unknown idea_id: {len(unknown_idea_rows)}")

    if errors:
        print("ERROR: spec idea traceability validation failed")
        for item in errors:
            print(f"- {item}")
        if missing:
            print(f"- first missing: {missing[0]}")
        if extra:
            print(f"- first unknown spec path: {extra[0]}")
        if unknown_idea_rows:
            first = unknown_idea_rows[0]
            print(f"- first unknown idea mapping: {first} -> {mapped_ideas[first]}")
        return 1

    print("PASS: spec idea traceability validated")
    print(f"- spec_count={len(spec_paths)}")
    print(f"- mapping_count={len(mapped_paths)}")
    print(f"- known_idea_ids={len(known_idea_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
