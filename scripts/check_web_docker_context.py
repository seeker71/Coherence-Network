#!/usr/bin/env python3
"""Catch web/ imports reaching above the Docker build context.

Dockerfile.web sets `web/` as its build context. Imports of the form
`../../../experiments/...` or any path that climbs above `web/` resolve
in local dev (the worktree has the full repo) but fail at `npm run build`
inside the Docker image (the context is sandboxed to `web/`).

This guard surfaces the mismatch at commit-time instead of letting it
become three consecutive failed deploys, as happened 2026-05-24 with
PR #1966 (form-kernel/client.ts importing `../../../experiments/...`).
The healing pattern is to vendor the needed files into `web/lib/.../vendor/`.

Run:
    python3 scripts/check_web_docker_context.py

Exits 1 if any web/ TypeScript file imports a path that escapes the
web/ tree.
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


def import_escapes_web(source_file: Path, import_spec: str) -> bool:
    """True if a relative import resolves outside the web/ tree."""
    if not import_spec.startswith("."):
        return False  # bare specifiers (e.g. "react", "@/components") are fine
    target = (source_file.parent / import_spec).resolve()
    try:
        target.relative_to(WEB_DIR.resolve())
    except ValueError:
        return True
    return False


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
                if import_escapes_web(path, spec):
                    line_no = text[: m.start()].count("\n") + 1
                    findings.append((path, line_no, spec))
    return findings


def main() -> int:
    findings = scan()
    if not findings:
        print("OK: no web/ imports escape the Docker build context")
        return 0
    print("ERROR: web/ imports escape the Docker build context")
    print()
    print("These imports resolve in local dev (full worktree) but fail")
    print("inside the Docker build (context is sandboxed to web/).")
    print("Vendor the needed files into web/lib/.../vendor/ to heal.")
    print()
    for path, line, spec in findings:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{line}  →  {spec}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
