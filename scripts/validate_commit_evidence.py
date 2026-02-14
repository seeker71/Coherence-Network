#!/usr/bin/env python3
"""Validate thread commit evidence artifacts for phase-gated process."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VALID_STATUS = {"pass", "fail", "pending"}
REQUIRED_TOP_LEVEL = {
    "date",
    "thread_branch",
    "commit_scope",
    "files_owned",
    "local_validation",
    "ci_validation",
    "deploy_validation",
    "phase_gate",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _latest_evidence_file(root: Path) -> Path | None:
    files = sorted((root / "docs" / "system_audit").glob("commit_evidence_*.json"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")
        return errors

    for key in ("local_validation", "ci_validation", "deploy_validation"):
        status = (data.get(key) or {}).get("status")
        if status not in VALID_STATUS:
            errors.append(f"{key}.status must be one of {sorted(VALID_STATUS)}")

    phase_gate = data.get("phase_gate") or {}
    if not isinstance(phase_gate.get("can_move_next_phase"), bool):
        errors.append("phase_gate.can_move_next_phase must be boolean")

    can_move = phase_gate.get("can_move_next_phase")
    if can_move is True:
        if (data.get("local_validation") or {}).get("status") != "pass":
            errors.append("can_move_next_phase=true requires local_validation.status=pass")
        if (data.get("ci_validation") or {}).get("status") != "pass":
            errors.append("can_move_next_phase=true requires ci_validation.status=pass")
        if (data.get("deploy_validation") or {}).get("status") != "pass":
            errors.append("can_move_next_phase=true requires deploy_validation.status=pass")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=str,
        default="",
        help="Specific evidence file to validate. Defaults to latest commit_evidence_*.json",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    path = Path(args.file) if args.file else _latest_evidence_file(repo_root)
    if path is None or not path.is_file():
        print("ERROR: no commit evidence file found under docs/system_audit/")
        return 1

    data = _load_json(path)
    errors = validate(data)
    if errors:
        print(f"ERROR: evidence validation failed for {path}")
        for e in errors:
            print(f"- {e}")
        return 1

    print(f"OK: evidence validation passed for {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
