#!/usr/bin/env python3
# spec: full-code-traceability
# idea: full-code-traceability
"""Phase 1.1 — Backfill idea_id into spec file frontmatter.

Scans all specs/*.md files for existing idea references (explicit or body-level),
and writes idea_id into the frontmatter of files that are missing it.

Usage:
    python3 scripts/backfill_spec_idea_links.py           # dry-run, report only
    python3 scripts/backfill_spec_idea_links.py --apply   # write changes

Output: CSV report to data/backfill_spec_idea_links.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
DATA_DIR = REPO_ROOT / "data"

_IDEA_ID_PATTERNS = [
    re.compile(r"idea[_-]id:\s*[\"']?([a-z0-9][a-z0-9-]{2,})[\"']?", re.IGNORECASE),
    re.compile(r"parent_idea[_-]id:\s*[\"']?([a-z0-9][a-z0-9-]{2,})[\"']?", re.IGNORECASE),
    re.compile(r"\*\*idea_id\*\*:\s*`([a-z0-9][a-z0-9-]{2,})`", re.IGNORECASE),
    re.compile(r"idea `([a-z0-9][a-z0-9-]{2,})`"),
]

_NOISE_VALUES = frozenset({
    "none", "null", "n/a", "string", "object", "array", "number",
    "boolean", "integer", "required", "type", "slug", "id", "true", "false",
    "tracked", "properties", "added", "example", "spec", "idea",
})


def extract_idea_id(content: str) -> tuple[str | None, float, str]:
    """Extract idea_id from spec content.

    Returns (idea_id, confidence, method).
    """
    for pattern in _IDEA_ID_PATTERNS:
        m = pattern.search(content)
        if m:
            val = m.group(1).lower().strip("\"'").rstrip(".,;)")
            if val not in _NOISE_VALUES and len(val) >= 3:
                return val, 1.0, "explicit"
    return None, 0.0, "none"


def has_idea_id(content: str) -> bool:
    idea_id, _, _ = extract_idea_id(content)
    return idea_id is not None


def inject_idea_id(spec_file: Path, content: str, idea_id: str) -> bool:
    """Inject idea_id into spec frontmatter. Returns True if file was changed."""
    fm_pattern = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
    m = fm_pattern.match(content)
    if m:
        if "idea_id" in m.group(1):
            return False  # Already present
        new_fm = m.group(1) + f"\nidea_id: {idea_id}"
        new_content = "---\n" + new_fm + "\n---" + content[m.end():]
    else:
        new_content = f"---\nidea_id: {idea_id}\n---\n\n" + content
    spec_file.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill idea_id into spec frontmatter")
    parser.add_argument("--apply", action="store_true", help="Write changes to files")
    parser.add_argument("--min-confidence", type=float, default=0.85,
                        help="Minimum confidence to auto-write (default: 0.85)")
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    report_path = DATA_DIR / "backfill_spec_idea_links.csv"

    rows = []
    updated = 0
    skipped = 0
    needs_review = 0

    spec_files = sorted(SPECS_DIR.glob("*.md"))
    total = 0
    for spec_file in spec_files:
        if spec_file.name == "TEMPLATE.md":
            continue
        total += 1
        try:
            content = spec_file.read_text(errors="replace")
        except OSError as exc:
            rows.append({
                "spec_file": spec_file.name,
                "idea_id_found": "",
                "confidence": 0.0,
                "action_taken": f"error: {exc}",
            })
            continue

        if has_idea_id(content):
            idea_id, conf, method = extract_idea_id(content)
            rows.append({
                "spec_file": spec_file.name,
                "idea_id_found": idea_id or "",
                "confidence": conf,
                "action_taken": "already_linked",
            })
            skipped += 1
            continue

        idea_id, confidence, method = extract_idea_id(content)

        if idea_id and confidence >= args.min_confidence:
            action = "needs_review"
            if args.apply:
                changed = inject_idea_id(spec_file, content, idea_id)
                action = "written" if changed else "skipped_no_change"
                if changed:
                    updated += 1
            else:
                action = f"would_write:{idea_id}"
                updated += 1
        else:
            needs_review += 1
            action = "needs_review"

        rows.append({
            "spec_file": spec_file.name,
            "idea_id_found": idea_id or "",
            "confidence": round(confidence, 3),
            "action_taken": action,
        })

    # Write CSV
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["spec_file", "idea_id_found", "confidence", "action_taken"])
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    print(f"=== Spec Idea Link Backfill ===")
    print(f"Total spec files:   {total}")
    print(f"Already linked:     {skipped}")
    print(f"Updated/would-update: {updated}")
    print(f"Needs review:       {needs_review}")
    print(f"Coverage after:     {(skipped + updated) * 100 // max(total, 1)}%")
    print(f"Report written to:  {report_path}")

    if not args.apply:
        print("\nDry run. Use --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
