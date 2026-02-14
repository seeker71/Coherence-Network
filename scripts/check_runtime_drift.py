#!/usr/bin/env python3
"""Fail when runtime drift exceeds known allowlist baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def check_drift(audit: dict[str, Any], allowlist: dict[str, Any]) -> list[str]:
    errs: list[str] = []

    missing = set(audit.get("missing_for_web", []))
    known_missing = set(allowlist.get("known_missing_for_web", []))
    extra_missing = sorted(missing - known_missing)
    if extra_missing:
        errs.append(f"new missing_for_web paths not in allowlist: {extra_missing}")

    unmounted = set(((audit.get("agent_router") or {}).get("unmounted_paths") or []))
    known_unmounted = set(allowlist.get("known_unmounted_agent_paths", []))
    extra_unmounted = sorted(unmounted - known_unmounted)
    if extra_unmounted:
        errs.append(f"new unmounted agent paths not in allowlist: {extra_unmounted}")

    return errs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--audit",
        default="docs/system_audit/runtime_surface_audit_2026-02-14.json",
        help="Path to runtime surface audit JSON",
    )
    p.add_argument(
        "--allowlist",
        default="docs/system_audit/runtime_drift_allowlist.json",
        help="Path to drift allowlist JSON",
    )
    args = p.parse_args()

    audit = _load(Path(args.audit))
    allowlist = _load(Path(args.allowlist))
    errs = check_drift(audit, allowlist)
    if errs:
        print("ERROR: runtime drift exceeded baseline")
        for e in errs:
            print(f"- {e}")
        return 1

    print("OK: runtime drift within allowlist baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
