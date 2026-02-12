#!/usr/bin/env python3
"""Update SPEC-COVERAGE.md with new specs from specs/. Additive only.

Usage:
  python scripts/update_spec_coverage.py [--dry-run]

When run after pytest in CI, ensures all specs in specs/ have a row.
Additive: adds missing rows; never removes or changes existing rows.
"""

import argparse
import os
import re
from typing import Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_root = os.path.dirname(_api_dir)
SPECS_DIR = os.path.join(_root, "specs")
SPEC_COVERAGE = os.path.join(_root, "docs", "SPEC-COVERAGE.md")
SKIP_SPECS = {"TEMPLATE", "backlog", "placeholder", "test-backlog", "sprint0-graph-foundation-indexer-api"}


def _spec_id_from_path(path: str) -> Optional[str]:
    """Extract NNN from specs/NNN-name.md."""
    base = os.path.basename(path)
    if not base.endswith(".md"):
        return None
    name = base[:-4]
    for skip in SKIP_SPECS:
        if skip in name.lower():
            return None
    m = re.match(r"^(\d{3})-(.+)$", name)
    if m:
        return m.group(1)
    return None


def _spec_title_from_path(path: str) -> str:
    """Derive title from 027-fully-automated-pipeline -> Fully Automated Pipeline."""
    base = os.path.basename(path)
    name = base[:-3] if base.endswith(".md") else base  # .md = 3 chars
    m = re.match(r"^\d{3}-(.+)$", name)
    if m:
        return m.group(1).replace("-", " ").title()
    return name


def _existing_spec_ids(content: str) -> set[str]:
    """Parse table rows to get spec numbers (001, 002, ...)."""
    ids = set()
    for line in content.splitlines():
        m = re.match(r"^\|\s*(\d{3})\s+\w", line)
        if m:
            ids.add(m.group(1))
        m = re.match(r"^\|\s*PLAN\s+", line)
        if m:
            ids.add("PLAN")
    return ids


def _table_insert_point(content: str) -> int:
    """Find line index after last table row (before **Present:**)."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("**Present:**"):
            return i
    return len(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Add missing spec rows to SPEC-COVERAGE.md")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = ap.parse_args()

    if not os.path.isdir(SPECS_DIR):
        print(f"Specs dir not found: {SPECS_DIR}")
        return
    if not os.path.isfile(SPEC_COVERAGE):
        print(f"SPEC-COVERAGE not found: {SPEC_COVERAGE}")
        return

    # Collect specs from specs/
    spec_files = []
    for f in os.listdir(SPECS_DIR):
        if f.endswith(".md"):
            path = os.path.join(SPECS_DIR, f)
            sid = _spec_id_from_path(path)
            if sid:
                spec_files.append((sid, _spec_title_from_path(path)))

    with open(SPEC_COVERAGE, encoding="utf-8") as f:
        content = f.read()

    existing = _existing_spec_ids(content)
    to_add = []
    for sid, title in sorted(spec_files):
        if sid not in existing:
            to_add.append((sid, title))

    if not to_add:
        print("No new specs to add.")
        return

    # Build new rows: | 027 Fully Automated Pipeline | ? | ? | ? | Pending |
    new_rows = []
    for sid, title in sorted(to_add):
        spec_label = f"{sid} {title}" if sid != "PLAN" else "PLAN Month 1 (Graph, indexer)"
        row = f"| {spec_label} | ? | ? | ? | Pending |"
        new_rows.append(row)
        print(f"Would add: {row}")

    if args.dry_run:
        print("(Dry run — no changes written)")
        return

    lines = content.splitlines()
    insert_idx = _table_insert_point(content)
    for i, row in enumerate(new_rows):
        lines.insert(insert_idx + i, row)

    with open(SPEC_COVERAGE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Added {len(new_rows)} row(s) to {SPEC_COVERAGE}")


if __name__ == "__main__":
    main()
