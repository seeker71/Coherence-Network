#!/usr/bin/env python3
"""Validate thread commit evidence artifacts for phase-gated process."""

from __future__ import annotations

import argparse
import json
import subprocess
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
    "idea_ids",
    "spec_ids",
    "task_ids",
    "contributors",
    "agent",
    "evidence_refs",
    "change_files",
}
EVIDENCE_PREFIX = "docs/system_audit/commit_evidence_"
EVIDENCE_SUFFIX = ".json"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _latest_evidence_file(root: Path) -> Path | None:
    files = sorted((root / "docs" / "system_audit").glob("commit_evidence_*.json"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _is_non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(x, str) and x.strip() for x in value)


def _changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head]
    out = subprocess.check_output(cmd, cwd=str(repo_root), text=True)
    rows = [line.strip() for line in out.splitlines() if line.strip()]
    return sorted(set(rows))


def _evidence_files_from_changes(changed_files: list[str], repo_root: Path) -> list[Path]:
    out: list[Path] = []
    for rel in changed_files:
        if rel.startswith(EVIDENCE_PREFIX) and rel.endswith(EVIDENCE_SUFFIX):
            out.append(repo_root / rel)
    return out


def validate(data: dict[str, Any], *, changed_files: list[str] | None = None) -> list[str]:
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

    if not _is_non_empty_string_list(data.get("idea_ids")):
        errors.append("idea_ids must be a non-empty list of strings")
    if not _is_non_empty_string_list(data.get("spec_ids")):
        errors.append("spec_ids must be a non-empty list of strings")
    if not _is_non_empty_string_list(data.get("task_ids")):
        errors.append("task_ids must be a non-empty list of strings")
    if not _is_non_empty_string_list(data.get("evidence_refs")):
        errors.append("evidence_refs must be a non-empty list of strings")
    if not _is_non_empty_string_list(data.get("change_files")):
        errors.append("change_files must be a non-empty list of strings")

    contributors = data.get("contributors")
    if not isinstance(contributors, list) or not contributors:
        errors.append("contributors must be a non-empty list")
    else:
        for idx, row in enumerate(contributors):
            if not isinstance(row, dict):
                errors.append(f"contributors[{idx}] must be an object")
                continue
            contributor_id = str(row.get("contributor_id") or "").strip()
            contributor_type = str(row.get("contributor_type") or "").strip().lower()
            roles = row.get("roles")
            if not contributor_id:
                errors.append(f"contributors[{idx}].contributor_id is required")
            if contributor_type not in {"human", "machine"}:
                errors.append(f"contributors[{idx}].contributor_type must be human|machine")
            if not _is_non_empty_string_list(roles):
                errors.append(f"contributors[{idx}].roles must be a non-empty list of strings")

    agent = data.get("agent")
    if not isinstance(agent, dict):
        errors.append("agent must be an object")
    else:
        if not str(agent.get("name") or "").strip():
            errors.append("agent.name is required")
        if not str(agent.get("version") or "").strip():
            errors.append("agent.version is required")

    if changed_files is not None and isinstance(data.get("change_files"), list):
        declared = {
            str(x).strip()
            for x in data.get("change_files", [])
            if isinstance(x, str) and str(x).strip()
        }
        expected = {
            path
            for path in changed_files
            if not (path.startswith(EVIDENCE_PREFIX) and path.endswith(EVIDENCE_SUFFIX))
        }
        missing_coverage = sorted(path for path in expected if path not in declared)
        if missing_coverage:
            errors.append(f"change_files missing changed paths: {missing_coverage}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=str,
        default="",
        help="Specific evidence file to validate. Defaults to latest commit_evidence_*.json",
    )
    parser.add_argument(
        "--base",
        type=str,
        default="",
        help="Base git ref for changed-file validation (e.g. origin/main or SHA).",
    )
    parser.add_argument(
        "--head",
        type=str,
        default="HEAD",
        help="Head git ref for changed-file validation (default: HEAD).",
    )
    parser.add_argument(
        "--require-changed-evidence",
        action="store_true",
        help="Require at least one changed commit_evidence_*.json in the git diff range.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    changed_files: list[str] | None = None
    evidence_paths: list[Path] = []

    if args.base:
        try:
            changed_files = _changed_files(repo_root, args.base, args.head)
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: failed to compute changed files for range {args.base}..{args.head}: {exc}")
            return 1
        evidence_paths = _evidence_files_from_changes(changed_files, repo_root)
        if args.require_changed_evidence and not evidence_paths:
            print("ERROR: no changed commit evidence file found in diff range")
            print(f"Range: {args.base}..{args.head}")
            return 1

    if args.file:
        evidence_paths = [Path(args.file)]
    elif not evidence_paths:
        latest = _latest_evidence_file(repo_root)
        if latest is None or not latest.is_file():
            print("ERROR: no commit evidence file found under docs/system_audit/")
            return 1
        evidence_paths = [latest]

    had_error = False
    for path in evidence_paths:
        if not path.is_file():
            print(f"ERROR: evidence file does not exist: {path}")
            had_error = True
            continue
        data = _load_json(path)
        errors = validate(data, changed_files=changed_files)
        if errors:
            print(f"ERROR: evidence validation failed for {path}")
            for e in errors:
                print(f"- {e}")
            had_error = True
            continue
        print(f"OK: evidence validation passed for {path}")

    if had_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
