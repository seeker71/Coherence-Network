#!/usr/bin/env python3
# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Phase 2.3 CI check: source files must have spec reference comments.
Exit 0 = compliant. Exit 1 = violations found.
Usage: python3 scripts/check_spec_references.py [--changed-only] [--files a.py b.py]
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_APP = REPO_ROOT / "api" / "app"
WEB_APP = REPO_ROOT / "web" / "app"
ENFORCED_DIRS = {"routers", "services"}
EXEMPT_NAMES = {"__init__.py", "conftest.py", "py.typed"}
EXEMPT_PREFIXES = ("test_",)
EXEMPT_FRAGMENTS = {"tests", "node_modules", "__pycache__", "scripts"}
_SPEC_PATTERNS = [
    re.compile(r"#\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"#\s*Implements:\s*spec[_-]?\S+", re.IGNORECASE),
    re.compile(r"//\s*spec:\s*\S+", re.IGNORECASE),
    re.compile(r"Spec:\s*\S+", re.IGNORECASE),
]

def is_exempt(f):
    if f.name in EXEMPT_NAMES: return True
    if any(f.name.startswith(p) for p in EXEMPT_PREFIXES): return True
    if set(f.parts) & EXEMPT_FRAGMENTS: return True
    if not any(d in f.parts for d in ENFORCED_DIRS): return True
    return False

def has_spec_comment(f):
    try:
        lines = f.read_text(errors="replace").splitlines()[:5]
        return any(p.search(line) for line in lines for p in _SPEC_PATTERNS)
    except OSError:
        return True

def get_changed_files():
    try:
        r = subprocess.run(["git","diff","--name-only","origin/main...HEAD"], capture_output=True, text=True, cwd=str(REPO_ROOT))
        if not r.stdout.strip():
            r = subprocess.run(["git","diff","--cached","--name-only"], capture_output=True, text=True, cwd=str(REPO_ROOT))
        return [REPO_ROOT/f.strip() for f in r.stdout.splitlines() if f.strip()]
    except Exception:
        return []

def check_files(files):
    violations = []
    for f in files:
        if not f.exists() or not f.is_file() or is_exempt(f): continue
        if not has_spec_comment(f):
            try: rel = f.relative_to(REPO_ROOT)
            except ValueError: rel = f
            violations.append(f"FAIL {rel}: missing spec reference comment (expected '# spec: NNN' in first 5 lines)")
    return violations

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--files", nargs="*", metavar="FILE")
    parser.add_argument("--warn", action="store_true")
    args = parser.parse_args()
    if args.files:
        files = [Path(f) for f in args.files]
    elif args.changed_only:
        files = [f for f in get_changed_files() if f.suffix in (".py",".ts",".tsx")]
    else:
        files = []
        for base in (API_APP, WEB_APP):
            if base.exists():
                for ext in ("*.py","*.ts","*.tsx"):
                    files.extend(base.rglob(ext))
    violations = check_files(files)
    if violations:
        print(f"Traceability spec-comment violations ({len(violations)}):", file=sys.stderr)
        for v in violations: print(f"  {v}", file=sys.stderr)
        print("Fix: add '# spec: NNN-name' to the first 5 lines.", file=sys.stderr)
        if not args.warn: return 1
    else:
        checked = len([f for f in files if not is_exempt(f) and f.exists()])
        print(f"OK: all {checked} checked files have spec reference comments.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
