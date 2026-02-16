#!/usr/bin/env python3
"""Fail when internal API/docs/tests introduce /v1 routes.

Allowed exceptions are external provider contracts (OpenAI/Ollama compatibility).
"""

from __future__ import annotations

import re
from pathlib import Path


SCAN_DIRS = ("api", "web", "docs", "specs", "scripts", ".github")
SCAN_FILES = ("AGENTS.md", "CLAUDE.md", "README.md", "README_AUTOMATION.md")
ALLOW_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "api/.env.example",
    "api/scripts/agent_runner.py",
    "api/scripts/heal_with_ollama.py",
    "api/scripts/check_pipeline.py",
    "api/app/services/automation_usage_service.py",
    "docs/AGENT-DEBUGGING.md",
    "docs/API-KEYS-SETUP.md",
    "docs/OLLAMA-CLAUDE-LOCAL.md",
    "scripts/validate_no_v1_api_usage.py",
    "specs/TEMPLATE.md",
}
EXCLUDE_PREFIXES = ("docs/system_audit/", "api/logs/")

V1_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(/v1)(?:[/?\"'`\\s]|$)")


def _iter_targets(root: Path) -> list[Path]:
    out: list[Path] = []
    for item in SCAN_FILES:
        path = root / item
        if path.is_file():
            out.append(path)
    for base in SCAN_DIRS:
        root_dir = root / base
        if not root_dir.exists():
            continue
        for path in root_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel.startswith(EXCLUDE_PREFIXES):
                continue
            out.append(path)
    return sorted(set(out))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in _iter_targets(root):
        rel = path.relative_to(root).as_posix()
        if rel in ALLOW_FILES:
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".lock", ".map"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if V1_PATTERN.search(text):
            offenders.append(rel)

    if offenders:
        print("ERROR: /v1 usage detected in non-allowed files:")
        for rel in offenders:
            print(f"- {rel}")
        print("Use /api routes for internal APIs.")
        return 1

    print("OK: no internal /v1 API usage detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
