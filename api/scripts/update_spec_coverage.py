#!/usr/bin/env python3
"""Update SPEC-COVERAGE.md and STATUS.md when tests pass. Additive only.

Usage:
  python scripts/update_spec_coverage.py [--dry-run] [--tests-passed]

- Run after pytest in CI (script runs only after pytest step; CI sets CI=true).
- Locally: pass --tests-passed to allow writes; otherwise no-op.
- --dry-run: preview changes without writing; exit 0.
Additive: adds missing spec rows to SPEC-COVERAGE; never removes or changes
existing Present/Spec'd/Tested marks. Updates STATUS.md test count and/or
Specs Implemented / Specs Pending from SPEC-COVERAGE.
"""

import argparse
import os
import re
import subprocess
import sys
from typing import Optional

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_root = os.path.dirname(_api_dir)
SPECS_DIR = os.path.join(_root, "specs")
SPEC_COVERAGE = os.path.join(_root, "docs", "SPEC-COVERAGE.md")
STATUS_MD = os.path.join(_root, "docs", "STATUS.md")
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
    name = base[:-3] if base.endswith(".md") else base
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


def _get_test_count() -> Optional[int]:
    """Test count from env TEST_COUNT or from pytest --co -q."""
    raw = os.environ.get("TEST_COUNT", "").strip()
    if raw and raw.isdigit():
        return int(raw)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--co", "-q"],
            cwd=_api_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (result.stdout or "") + (result.stderr or "")
        # e.g. "74 tests collected" or "74 items collected"
        m = re.search(r"(\d+)\s+(?:tests?|items?)\s+collected", out, re.I)
        if m:
            return int(m.group(1))
    except (subprocess.SubprocessError, ValueError):
        pass
    return None


def _parse_spec_coverage_table(content: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Parse SPEC-COVERAGE Status Summary table: (implemented, pending) as (sid, label)."""
    implemented: list[tuple[str, str]] = []
    pending: list[tuple[str, str]] = []
    for line in content.splitlines():
        if not line.strip().startswith("|") or "| Spec |" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p]
        if len(parts) < 2:
            continue
        spec_cell = parts[0]
        present_cell = parts[1] if len(parts) > 1 else ""
        if spec_cell.startswith("PLAN"):
            sid, label = "PLAN", spec_cell
        else:
            m = re.match(r"^(\d{3})\s+(.+)$", spec_cell)
            if not m:
                continue
            sid, label = m.group(1), m.group(2).strip()
        if "✓" in present_cell:
            implemented.append((sid, label))
        elif "?" in present_cell:
            pending.append((sid, label))
    return (implemented, pending)


def _format_specs_implemented(implemented: list[tuple[str, str]]) -> str:
    """Format as STATUS.md Specs Implemented bullets (labels from SPEC-COVERAGE table)."""
    if not implemented:
        return "- None"
    lines = []
    for sid, label in implemented:
        lines.append(f"- {label}" if sid == "PLAN" else f"- {sid} {label}")
    return "\n".join(lines)


def _format_specs_pending(pending: list[tuple[str, str]]) -> str:
    """Format as STATUS.md Specs Pending section."""
    if not pending:
        return "- None"
    return "\n".join(f"- {sid} {label}" for sid, label in pending)


def _update_status_sections(
    status_content: str,
    spec_coverage_content: str,
    test_count: Optional[int],
) -> str:
    """Update Specs Implemented, Specs Pending, and optionally Test Count in STATUS.md."""
    implemented, pending = _parse_spec_coverage_table(spec_coverage_content)
    # Build replacement blocks
    impl_block = _format_specs_implemented(implemented)
    pend_block = _format_specs_pending(pending)

    # Match section content until next ## (allow \n\n or \n before next heading)
    _until_next_h2 = r"(?=\n+\s*## )"
    out = status_content
    # Replace ## Specs Implemented ... until next ##
    out = re.sub(
        r"(## Specs Implemented\n)(.*?)" + _until_next_h2,
        lambda m: m.group(1) + impl_block + "\n\n",
        out,
        flags=re.DOTALL,
    )
    # Replace ## Specs Pending Implementation ... until next ##
    out = re.sub(
        r"(## Specs Pending Implementation\n)(.*?)" + _until_next_h2,
        lambda m: m.group(1) + pend_block + "\n\n",
        out,
        flags=re.DOTALL,
    )
    if test_count is not None:
        # Replace ## Test Count ... until next ## (one or more bullet lines)
        out = re.sub(
            r"(## Test Count\n\n)((?:- .*\n?)+?)" + _until_next_h2,
            lambda m: m.group(1) + f"- {test_count} tests (CI runs full suite)\n",
            out,
            count=1,
            flags=re.DOTALL,
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Add missing spec rows and update STATUS when tests pass")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    ap.add_argument("--tests-passed", action="store_true", help="Allow writes (required when not in CI)")
    args = ap.parse_args()

    in_ci = os.environ.get("CI") == "true"
    if not in_ci and not args.tests_passed:
        print("Skipping (tests not confirmed passed). Use --tests-passed or run in CI.")
        return 0

    if not os.path.isdir(SPECS_DIR):
        print(f"Specs dir not found: {SPECS_DIR}")
        return 1
    if not os.path.isfile(SPEC_COVERAGE):
        print(f"SPEC-COVERAGE not found: {SPEC_COVERAGE}")
        return 1

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

    new_rows = []
    for sid, title in sorted(to_add):
        spec_label = f"{sid} {title}" if sid != "PLAN" else "PLAN Month 1 (Graph, indexer)"
        row = f"| {spec_label} | ? | ? | ? | Pending |"
        new_rows.append(row)
        print(f"Would add: {row}")

    if not to_add:
        print("No new specs to add.")
    if args.dry_run:
        # STATUS preview
        if os.path.isfile(STATUS_MD):
            with open(STATUS_MD, encoding="utf-8") as f:
                status_content = f.read()
            test_count = _get_test_count()
            _ = _update_status_sections(status_content, content, test_count)
            print("(Dry run — STATUS would be updated from SPEC-COVERAGE and test count)")
        print("(Dry run — no changes written)")
        return 0

    # Write SPEC-COVERAGE if needed
    if to_add:
        lines = content.splitlines()
        insert_idx = _table_insert_point(content)
        for i, row in enumerate(new_rows):
            lines.insert(insert_idx + i, row)
        with open(SPEC_COVERAGE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Added {len(new_rows)} row(s) to {SPEC_COVERAGE}")
        with open(SPEC_COVERAGE, encoding="utf-8") as f:
            content = f.read()

    # Update STATUS.md (test count and/or Specs Implemented / Pending)
    if os.path.isfile(STATUS_MD):
        with open(STATUS_MD, encoding="utf-8") as f:
            status_content = f.read()
        test_count = _get_test_count()
        new_status = _update_status_sections(status_content, content, test_count)
        if new_status != status_content:
            with open(STATUS_MD, "w", encoding="utf-8") as f:
                f.write(new_status)
            print("Updated STATUS.md (Specs Implemented/Pending and/or Test Count)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
