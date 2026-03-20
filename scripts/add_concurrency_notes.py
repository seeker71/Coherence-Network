#!/usr/bin/env python3
"""SQ9: Add '## Concurrency Behavior' section to specs with API endpoints."""

import os
import re
import sys

SPECS_DIR = os.path.join(os.path.dirname(__file__), "..", "specs")

CONCURRENCY_SECTION = """## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.
"""

# Patterns that indicate the spec has API endpoints
API_PATTERNS = [
    re.compile(r"^## API Contract", re.MULTILINE),
    re.compile(r"\bPOST\b"),
    re.compile(r"\bPUT\b"),
    re.compile(r"\bPATCH\b"),
    re.compile(r"\bDELETE\b"),
]

# Specs 112-119 are gold standard; skip them
GOLD_STANDARD_RE = re.compile(r"^11[2-9]-")

# Sections to insert before (whichever comes first)
INSERT_BEFORE = [
    "## Failure and Retry",
    "## Risks",
    "## Verification",
]


def has_api_endpoints(content: str) -> bool:
    return any(p.search(content) for p in API_PATTERNS)


def already_has_concurrency(content: str) -> bool:
    return "## Concurrency Behavior" in content


def insert_concurrency_section(content: str) -> str | None:
    """Insert concurrency section before the first matching heading. Returns None if no anchor found."""
    earliest_pos = None
    for heading in INSERT_BEFORE:
        pos = content.find(heading)
        if pos != -1 and (earliest_pos is None or pos < earliest_pos):
            earliest_pos = pos

    if earliest_pos is None:
        return None

    return content[:earliest_pos] + CONCURRENCY_SECTION + "\n" + content[earliest_pos:]


def main():
    modified = []
    skipped_gold = []
    skipped_no_api = []
    skipped_already = []
    skipped_no_anchor = []

    for fname in sorted(os.listdir(SPECS_DIR)):
        if not fname.endswith(".md"):
            continue

        # Skip gold standard specs 112-119
        if GOLD_STANDARD_RE.match(fname):
            skipped_gold.append(fname)
            continue

        fpath = os.path.join(SPECS_DIR, fname)
        with open(fpath, "r") as f:
            content = f.read()

        if not has_api_endpoints(content):
            skipped_no_api.append(fname)
            continue

        if already_has_concurrency(content):
            skipped_already.append(fname)
            continue

        new_content = insert_concurrency_section(content)
        if new_content is None:
            skipped_no_anchor.append(fname)
            continue

        with open(fpath, "w") as f:
            f.write(new_content)
        modified.append(fname)

    print("=== SQ9: Add Concurrency Behavior Notes ===")
    print(f"Modified:           {len(modified)}")
    print(f"Skipped (gold):     {len(skipped_gold)}")
    print(f"Skipped (no API):   {len(skipped_no_api)}")
    print(f"Skipped (already):  {len(skipped_already)}")
    print(f"Skipped (no anchor):{len(skipped_no_anchor)}")
    if modified:
        print("\nModified files:")
        for f in modified:
            print(f"  {f}")
    if skipped_no_anchor:
        print("\nSkipped (no insertion anchor):")
        for f in skipped_no_anchor:
            print(f"  {f}")


if __name__ == "__main__":
    main()
