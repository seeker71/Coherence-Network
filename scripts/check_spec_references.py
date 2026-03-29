#!/usr/bin/env python3
# spec: 183-full-traceability-chain
# idea: full-traceability-chain
"""Phase 2.3 CI check: source files must have spec reference comments.

Exit 0 = compliant. Exit 1 = violations found.
Usage:
  python3 scripts/check_spec_references.py              # check all enforced files
  python3 scripts/check_spec_references.py --changed-only  # only git-changed files
  python3 scripts/check_spec_references.py --files a.py b.py  # specific files
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

# Only enforce spec comments in these subdirectories
ENFORCED_DIRS = {"routers", "services"}

EXEMPT_NAMES = {"__init__.py", "conftest.py", "py.typed"}
EXEMPT_PREFIXES = ("test_",)
EXEMPT_FRAGMENTS = {"tests", "node_modules", "__pycache__", ".git", "scripts"}

_SPEC_PATTERNS = [
    re.compile(r"#\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"#\s*Implements:\s*spec[_-]?\S+", re.IGNORECASE),
    re.compile(r"//\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"Spec:\s*\S+", re.IGNORECASE),
]


def is_exempt(f: Path) -> bool:
    if f.name in EXEMPT_NAMES:
        return True
    if any(f.name.startswith(p) for p in EXEMPT_PREFIXES):
        return True
    parts = set(f.parts)
    if parts & EXEMPT_FRAGMENTS:
        return True
    # Only enforce within routers/ and services/ under api/app or web/app
    if not any(d in f.parts for d in ENFORCED_DIRS):
        return True
    return False


def has_spec_comment(f: Path) -> bool:
    try:
        lines = f.read_text(errors="replace").splitlines()[:5]
        return any(p.search(line) for line in lines for p in _SPEC_PATTERNS)
    except OSError:
        return True  # can't read → don't fail CI


def get_changed_files() -> list[Path]:
    """Return list of files changed relative to origin/main."""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if not r.stdout.strip():
            r = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
        return [REPO_ROOT / f.strip() for f in r.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def collect_all_enforced_files() -> list[Path]:
    files: list[Path] = []
    for base in (API_APP, WEB_APP):
        if not base.exists():
            continue
        for ext in ("*.py", "*.ts", "*.tsx"):
            for f in base.rglob(ext):
                if not is_exempt(f):
                    files.append(f)
    return files


def check_files(files: list[Path]) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for f in files:
        if is_exempt(f):
            continue
        if f.suffix not in (".py", ".ts", ".tsx"):
            continue
        if not f.exists():
            continue
        if not has_spec_comment(f):
            violations.append((f, "Missing '# spec: <id>' in first 5 lines"))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check spec reference comments in source files")
    parser.add_argument("--changed-only", action="store_true", help="Only check git-changed files")
    parser.add_argument("--files", nargs="*", help="Explicit file list to check")
    parser.add_argument("--report", action="store_true", help="Print full coverage report")
    args = parser.parse_args()

    if args.files:
        files = [Path(f) for f in args.files]
    elif args.changed_only:
        files = get_changed_files()
    else:
        files = collect_all_enforced_files()

    violations = check_files(files)

    if args.report:
        total = len([f for f in files if f.exists() and not is_exempt(f)
                     and f.suffix in (".py", ".ts", ".tsx")])
        covered = total - len(violations)
        pct = round(covered * 100.0 / max(total, 1), 1)
        print(f"Source file spec coverage: {covered}/{total} ({pct}%)")
        if violations:
            print("\nViolations:")
            for f, msg in violations:
                try:
                    rel = f.relative_to(REPO_ROOT)
                except ValueError:
                    rel = f
                print(f"  {rel}: {msg}")
    elif violations:
        for f, msg in violations:
            try:
                rel = f.relative_to(REPO_ROOT)
            except ValueError:
                rel = f
            print(f"VIOLATION: {rel}: {msg}")

    if violations:
        print(f"\n{len(violations)} file(s) missing spec reference comments. Add '# spec: <spec-id>' to the first 5 lines.")
        return 1

    if args.report:
        print("All checked files have spec reference comments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
