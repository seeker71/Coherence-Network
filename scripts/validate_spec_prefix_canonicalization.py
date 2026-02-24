#!/usr/bin/env python3
"""Validate canonical mapping for duplicated spec numeric prefixes."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _load_map(path: Path) -> dict[str, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "duplicates" not in payload:
        raise ValueError("mapping file missing 'duplicates' object")
    duplicates = payload["duplicates"]
    if not isinstance(duplicates, dict):
        raise ValueError("'duplicates' must be an object")
    return duplicates


def _scan_specs(specs_dir: Path) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for file in sorted(specs_dir.glob("*.md")):
        name = file.name
        if len(name) >= 4 and name[:3].isdigit() and name[3] == "-":
            grouped[name[:3]].append(name)
    return {k: v for k, v in grouped.items() if len(v) > 1}


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    map_path = repo_root / "config" / "spec_prefix_canonical_map.json"
    specs_dir = repo_root / "specs"

    try:
        mapping = _load_map(map_path)
    except Exception as exc:
        print(f"ERROR: failed to load {map_path}: {exc}")
        return 1

    duplicates = _scan_specs(specs_dir)
    errors: list[str] = []

    for prefix, files in sorted(duplicates.items()):
        entry = mapping.get(prefix)
        if not isinstance(entry, dict):
            errors.append(f"prefix {prefix}: missing canonical mapping entry")
            continue
        canonical = str(entry.get("canonical", "")).strip()
        aliases = entry.get("aliases", [])
        if not canonical:
            errors.append(f"prefix {prefix}: canonical is missing")
            continue
        if not isinstance(aliases, list):
            errors.append(f"prefix {prefix}: aliases must be a list")
            continue
        alias_names = [str(item).strip() for item in aliases if str(item).strip()]
        mapped_set = sorted([canonical, *alias_names])
        actual_set = sorted(files)
        if canonical not in actual_set:
            errors.append(f"prefix {prefix}: canonical file not present: {canonical}")
        if mapped_set != actual_set:
            errors.append(
                f"prefix {prefix}: mapped files {mapped_set} do not match actual duplicates {actual_set}"
            )

    extra_entries = sorted(set(mapping.keys()) - set(duplicates.keys()))
    if extra_entries:
        errors.append(f"mapping contains prefixes with no current duplicate set: {extra_entries}")

    if errors:
        print("ERROR: spec prefix canonicalization validation failed")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"OK: duplicate prefix canonicalization valid for {len(duplicates)} prefixes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
