#!/usr/bin/env python3
"""Catch web imports reaching outside the source copied into the image.

Dockerfile.web uses the repository root as its build context and copies the
canonical `web/` and `form/` trees into the builder. Relative imports may cross
from `web/` into `form/`; imports outside those copied roots resolve in local
dev but fail at `npm run build` inside the image.

This guard surfaces the mismatch at commit-time instead of letting it
become three consecutive failed deploys, as happened 2026-05-24 with
PR #1966 (form-kernel/client.ts importing `../../../experiments/...`).
The healing pattern is to copy a canonical source root in Dockerfile.web or
move the dependency into an existing copied root, never to fork it into a
browser-only vendor copy.

Run:
    python3 scripts/check_web_docker_context.py

Exits 1 if any web TypeScript import escapes the build's copied source roots.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Imports like:  import { x } from "../../../experiments/form-kernel-ts/src/kernel.ts"
# Also catches:  from "../../something-outside-web"
IMPORT_RE = re.compile(
    r"""(?:^|\s)(?:import|from|require\s*\()\s*\(?\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"
FORM_DIR = REPO_ROOT / "form"
COPIED_SOURCE_ROOTS = (WEB_DIR.resolve(), FORM_DIR.resolve())


def import_escapes_build_sources(source_file: Path, import_spec: str) -> bool:
    """True if a relative import resolves outside Docker-copied source roots."""
    if not import_spec.startswith("."):
        return False  # bare specifiers (e.g. "react", "@/components") are fine
    target = (source_file.parent / import_spec).resolve()
    for root in COPIED_SOURCE_ROOTS:
        if target == root or root in target.parents:
            return False
    return True


def scan() -> list[tuple[Path, int, str]]:
    """Return (file, line_no, import_spec) tuples for escapes."""
    findings: list[tuple[Path, int, str]] = []
    for ext in ("*.ts", "*.tsx", "*.mts", "*.cts", "*.js", "*.jsx", "*.mjs"):
        for path in WEB_DIR.rglob(ext):
            # Skip node_modules and build output
            parts = set(path.parts)
            if "node_modules" in parts or ".next" in parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in IMPORT_RE.finditer(text):
                spec = m.group(1)
                if import_escapes_build_sources(path, spec):
                    line_no = text[: m.start()].count("\n") + 1
                    findings.append((path, line_no, spec))
    return findings


def main() -> int:
    findings = scan()
    if not findings:
        print("OK: web imports stay within Docker-copied source roots")
        return 0
    print("ERROR: web imports escape Docker-copied source roots")
    print()
    print("These imports resolve in local dev (full worktree) but fail")
    print("inside the Docker build (only web/ and form/ source are copied).")
    print("Copy the canonical source root or move the dependency; do not fork it.")
    print()
    for path, line, spec in findings:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{line}  →  {spec}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
