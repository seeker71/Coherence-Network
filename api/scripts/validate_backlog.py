#!/usr/bin/env python3
"""Validate backlog file format. Exit 0 if valid, 1 if invalid."""

import os
import re
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
DEFAULT_BACKLOG = os.path.join(PROJECT_ROOT, "specs", "006-overnight-backlog.md")


def validate(path: str) -> tuple[bool, list[str]]:
    """Return (valid, list of error messages)."""
    errors = []
    if not os.path.isfile(path):
        return False, [f"File not found: {path}"]
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    numbered = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^`", stripped) or re.match(r"^Use:", stripped) or re.match(r"^Work ", stripped):
            continue  # Skip descriptive lines
        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            numbered.append((int(m.group(1)), m.group(2).strip()))
        elif re.match(r"^\d+", stripped):
            errors.append(f"Line {i}: expected format 'N. Item', got: {stripped[:50]}...")
    if not numbered and any(ln.strip() and not ln.strip().startswith("#") for ln in lines):
        errors.append("No numbered items found")
    return len(errors) == 0, errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BACKLOG
    if not os.path.isabs(path) and not os.path.isfile(path):
        path = os.path.join(PROJECT_ROOT, path.lstrip("/"))
    valid, errors = validate(path)
    if valid:
        print(f"OK: {path}")
        sys.exit(0)
    for e in errors:
        print(f"ERROR: {e}")
    sys.exit(1)


if __name__ == "__main__":
    main()
