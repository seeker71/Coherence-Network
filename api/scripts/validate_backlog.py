#!/usr/bin/env python3
r"""Validate backlog file format.

Checks that backlog files conform to the expected format:
- Numbered items match pattern: ^\d+\.\s+(.+)$
- No duplicate item numbers
- Items are in sequential order (warnings only)

Usage:
    python scripts/validate_backlog.py [backlog_file]
    python scripts/validate_backlog.py specs/006-overnight-backlog.md
    python scripts/validate_backlog.py --all  # validate all backlog files

Exit codes:
    0 - Valid backlog
    1 - Validation errors found
    2 - File not found
"""

import argparse
import glob
import os
import re
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
DEFAULT_BACKLOG = os.path.join(PROJECT_ROOT, "specs", "006-overnight-backlog.md")

# Pattern for numbered items: "1. Item text"
ITEM_PATTERN = re.compile(r"^(\d+)\.\s+(.+)$")


def validate(path: str, verbose: bool = False) -> tuple[bool, list[str], list[str]]:
    """Validate backlog file format.

    Returns:
        (valid, errors, warnings) where valid is True if no errors found
    """
    errors = []
    warnings = []

    if not os.path.isfile(path):
        return False, [f"File not found: {path}"], []

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    numbered = []
    seen_numbers = set()
    last_number = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Skip descriptive lines (metadata)
        if re.match(r"^`", stripped) or re.match(r"^(Use|Work|Progress|Backlog):", stripped, re.IGNORECASE):
            continue

        # Check for numbered items
        m = ITEM_PATTERN.match(stripped)
        if m:
            number = int(m.group(1))
            content = m.group(2).strip()

            # Check for duplicate numbers (error)
            if number in seen_numbers:
                errors.append(f"Line {line_num}: Duplicate item number {number}")
            seen_numbers.add(number)

            # Check for sequential ordering (warning only)
            if last_number > 0 and number != last_number + 1:
                warnings.append(f"Line {line_num}: Non-sequential numbering (item {number} after {last_number})")

            last_number = number
            numbered.append((number, content))

        # Check if line looks like it should be numbered but isn't formatted correctly
        elif re.match(r"^\d+", stripped):
            # Line starts with a number but doesn't match pattern
            errors.append(f"Line {line_num}: Invalid format - expected 'N. Item', got: {stripped[:60]}")

    # Overall validation
    if not numbered:
        # Check if file has any non-comment content
        has_content = any(ln.strip() and not ln.strip().startswith("#") for ln in lines)
        if has_content:
            warnings.append("No numbered items found in backlog")

    return len(errors) == 0, errors, warnings


def find_backlog_files() -> list[str]:
    """Find all backlog markdown files in specs directory."""
    specs_dir = os.path.join(PROJECT_ROOT, "specs")
    if not os.path.isdir(specs_dir):
        return []

    # Find all files with "backlog" in the name
    pattern = os.path.join(specs_dir, "*backlog*.md")
    files = glob.glob(pattern)

    # Exclude test backlogs
    return [f for f in files if "test-backlog" not in os.path.basename(f)]


def main():
    parser = argparse.ArgumentParser(
        description="Validate backlog file format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "backlog_file",
        nargs="?",
        help="Path to backlog file to validate (default: %(default)s)",
        default=None,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all backlog files in specs/ directory",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed validation output",
    )

    args = parser.parse_args()

    # Validate all backlogs if --all is specified
    if args.all:
        backlog_files = find_backlog_files()
        if not backlog_files:
            print("No backlog files found in specs/ directory")
            sys.exit(2)

        print(f"Validating {len(backlog_files)} backlog file(s)...\n")

        all_valid = True
        for path in backlog_files:
            rel_path = os.path.relpath(path, PROJECT_ROOT)
            valid, errors, warnings = validate(path, args.verbose)

            if valid:
                print(f"✅ {rel_path}")
                if warnings and args.verbose:
                    for w in warnings:
                        print(f"   ⚠️  {w}")
            else:
                print(f"❌ {rel_path}")
                all_valid = False
                for e in errors:
                    print(f"   ERROR: {e}")
                if warnings:
                    for w in warnings:
                        print(f"   ⚠️  {w}")

        print(f"\n{'✅' if all_valid else '❌'} Validated {len(backlog_files)} file(s)")
        sys.exit(0 if all_valid else 1)

    # Validate single backlog
    path = args.backlog_file or DEFAULT_BACKLOG

    # Handle relative paths
    if not os.path.isabs(path) and not os.path.isfile(path):
        path = os.path.join(PROJECT_ROOT, path.lstrip("/"))

    valid, errors, warnings = validate(path, args.verbose)

    if valid:
        print(f"✅ {path}")
        if warnings:
            print(f"\n⚠️  {len(warnings)} warning(s):")
            for w in warnings:
                print(f"  - {w}")
        sys.exit(0)
    else:
        print(f"❌ {path}")
        print(f"\n❌ {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        if warnings:
            print(f"\n⚠️  {len(warnings)} warning(s):")
            for w in warnings:
                print(f"  - {w}")
        sys.exit(1)


if __name__ == "__main__":
    main()
