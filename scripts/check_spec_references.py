#!/usr/bin/env python3
# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Phase 2.3 CI check: new/modified source files must have a spec reference comment.

Checks that files in api/app/routers/ and api/app/services/ (and web/app/) have
a spec reference comment in the first 5 lines:
    # spec: NNN-name
    # idea: idea-slug

Files in api/tests/, scripts/, __init__.py, and conftest.py are exempt.

Exit 0 = all checked files compliant.
Exit 1 = violations found.

Usage:
    python3 scripts/check_spec_references.py                        # check all files
    python3 scripts/check_spec_references.py --changed-only         # only git-changed files
    python3 scripts/check_spec_references.py --files a.py b.py      # specific files
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_APP = REPO_ROOT / "api" / "app"
WEB_APP = REPO_ROOT / "web" / "app"

# Directories that must have spec comments
ENFORCED_DIRS = {"routers", "services"}

# Files/patterns that are exempt
EXEMPT_NAMES = {"__init__.py", "conftest.py", "py.typed"}
EXEMPT_PREFIXES = ("test_",)
EXEMPT_PATH_FRAGMENTS = {"tests", "node_modules", "__pycache__", "scripts"}

# Comment patterns that count as a valid spec reference (checked in first 5 lines)
_SPEC_REF_PATTERNS = [
    re.compile(r"#\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"#\s*Implements:\s*spec[_-]?\S+", re.IGNORECASE),
    re.compile(r"//\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"//\s*Implements:\s*spec[_-]?\S+", re.IGNORECASE),
    re.compile(r"Spec:\s*\S+", re.IGNORECASE),
]


def _is_exempt(file_path: Path) -> bool:
    """Return True if this file is exempt from spec-comment requirements."""
    name = file_path.name
    if name in EXEMPT_NAMES:
        return True
    if any(name.startswith(p) for p in EXEMPT_PREFIXES):
        return True
    parts = set(file_path.parts)
    if parts & EXEMPT_PATH_FRAGMENTS:
        return True
    # Only enforce for routers and services
    if not any(d in file_path.parts for d in ENFORCED_DIRS):
        return True
    return False


def _has_spec_comment(file_path: Path) -> bool:
    """Check if file has a spec reference comment in the first 5 lines."""
    try:
        content = file_path.read_text(errors="replace")
    except OSError:
        return True  # Can't read — don't block
    lines = content.splitlines()[:5]
    for line in lines:
        for pattern in _SPEC_REF_PATTERNS:
            if pattern.search(line):
                return True
    return False


def _get_changed_files() -> list[Path]:
    """Get files changed vs origin/main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if result.returncode != 0 or not result.stdout.strip():
            # Fall back to staged
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
        return [REPO_ROOT / f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def _gather_all_enforced_files() -> list[Path]:
    """Gather all .py and .ts/.tsx files in enforced directories."""
    files = []
    for base in (API_APP, WEB_APP):
        if not base.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx"):
            files.extend(base.rglob(ext))
    return files


def check_files(files: list[Path]) -> list[str]:
    """Check each file and return list of violation messages."""
    violations = []
    for f in files:
        if not f.exists() or not f.is_file():
            continue
        if _is_exempt(f):
            continue
        if not _has_spec_comment(f):
            try:
                rel = f.relative_to(REPO_ROOT)
            except ValueError:
                rel = f
            violations.append(
                f"FAIL {rel}: missing spec reference comment "
                f"(expected '# spec: NNN' in first 5 lines)"
            )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="CI check: source files must have spec reference comments")
    parser.add_argument("--changed-only", action="store_true",
                        help="Only check files changed vs origin/main")
    parser.add_argument("--files", nargs="*", metavar="FILE",
                        help="Specific files to check")
    parser.add_argument("--warn", action="store_true",
                        help="Warn but don't fail (exit 0 even with violations)")
    args = parser.parse_args()

    if args.files:
        files = [Path(f) for f in args.files]
    elif args.changed_only:
        changed = _get_changed_files()
        files = [
            f for f in changed
            if f.suffix in (".py", ".ts", ".tsx")
        ]
    else:
        files = _gather_all_enforced_files()

    violations = check_files(files)

    if violations:
        print(f"Traceability spec-comment violations ({len(violations)}):\n")
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nFix: add '# spec: NNN-spec-name' to the first 5 lines of the file.",
            file=sys.stderr,
        )
        print(
            "     Files in api/tests/, scripts/, __init__.py, conftest.py are exempt.",
            file=sys.stderr,
        )
        if not args.warn:
            return 1
    else:
        checked = len([f for f in files if not _is_exempt(f) and f.exists()])
        print(f"OK: all {checked} checked files have spec reference comments.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
