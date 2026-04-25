#!/usr/bin/env python3
"""CI gate: check that new/modified specs have idea_id and code files have spec refs.

Exit 0 if compliant, exit 1 if violations found.
Used as a pre-commit hook or CI check.

Usage:
    python3 scripts/check_traceability.py                    # check all files
    python3 scripts/check_traceability.py --changed-only     # check only git-changed files
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
API_DIR = REPO_ROOT / "api" / "app"


def _get_changed_files() -> list[str]:
    """Get files changed vs main branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            # Fall back to staged files
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def check_spec_has_idea(spec_file: Path) -> str | None:
    """Check if a spec file references an idea. Returns error message or None."""
    if spec_file.name == "TEMPLATE.md":
        return None
    content = spec_file.read_text(errors="replace")

    # Check for idea_id in frontmatter or content
    patterns = [
        r"idea[_-]id:\s*\S+",
        r"parent_idea[_-]id:\s*\S+",
        r"Idea:\s*\S+",
        r"idea `[a-z0-9-]+`",
        r"Links to idea:",
    ]
    for p in patterns:
        if re.search(p, content, re.IGNORECASE):
            return None

    return f"  {spec_file.name}: missing idea_id (add 'idea_id: <id>' to frontmatter)"


def check_code_has_spec(code_file: Path) -> str | None:
    """Check if a code file references a spec. Returns error message or None."""
    # Skip test files, __init__, and conftest
    if code_file.name in ("__init__.py", "conftest.py") or code_file.name.startswith("test_"):
        return None
    # Skip very small files (< 20 lines — likely just imports/config)
    content = code_file.read_text(errors="replace")
    if content.count("\n") < 20:
        return None

    patterns = [
        r"[Ss]pec\s+\d{2,3}",
        r"spec[_-]\d{2,3}",
        r"specs/\d+-",
        r"Implements:\s*spec",
    ]
    for p in patterns:
        if re.search(p, content):
            return None

    rel = code_file.relative_to(REPO_ROOT)
    return f"  {rel}: no spec reference (add '# Implements: spec-XXX' header)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-only", action="store_true", help="Only check files changed vs main")
    parser.add_argument("--warn", action="store_true", help="Warn but don't fail (exit 0)")
    args = parser.parse_args()

    violations: list[str] = []

    if args.changed_only:
        changed = _get_changed_files()
        spec_files = [REPO_ROOT / f for f in changed if f.startswith("specs/") and f.endswith(".md")]
        code_files = [REPO_ROOT / f for f in changed if f.startswith("api/app/") and f.endswith(".py")]
    else:
        spec_files = list(SPECS_DIR.glob("*.md"))
        code_files = [f for f in API_DIR.rglob("*.py") if "__pycache__" not in str(f)]

    # Check specs
    for f in spec_files:
        if f.exists():
            err = check_spec_has_idea(f)
            if err:
                violations.append(err)

    # Check code (only routers and services — the most important)
    important_dirs = {"routers", "services"}
    for f in code_files:
        if f.exists() and any(d in f.parts for d in important_dirs):
            err = check_code_has_spec(f)
            if err:
                violations.append(err)

    if violations:
        print(f"Traceability violations ({len(violations)}):\n")
        for v in violations:
            print(v)
        print(f"\nFix: add 'idea_id: <id>' to spec frontmatter")
        print(f"     add '# Implements: spec-XXX' to code file headers")
        if not args.warn:
            sys.exit(1)
    else:
        print("Traceability: all checked files have proper links.")

    # Report coverage
    total_specs = len(spec_files)
    total_code = len([f for f in code_files if f.exists() and any(d in f.parts for d in important_dirs)])
    linked_specs = total_specs - sum(1 for v in violations if "specs/" in v or "missing idea_id" in v)
    linked_code = total_code - sum(1 for v in violations if "no spec reference" in v)
    print(f"\nCoverage: specs {linked_specs}/{total_specs}, code {linked_code}/{total_code}")


if __name__ == "__main__":
    main()
