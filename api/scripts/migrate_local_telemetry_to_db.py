#!/usr/bin/env python3
"""Migrate local telemetry files to DB backend with verification and optional purge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from app.services import automation_usage_service, friction_service, telemetry_persistence_service


def _count_automation_file(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    rows = payload.get("snapshots") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if isinstance(row, dict))


def _count_friction_file(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            count += 1
    return count


def _verify_and_migrate() -> dict[str, Any]:
    telemetry_persistence_service.ensure_schema()
    automation_file = Path(os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", "")).resolve() if os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH") else automation_usage_service._snapshots_path().resolve()  # type: ignore[attr-defined]
    friction_file = friction_service.friction_file_path().resolve()

    automation_file_before = _count_automation_file(automation_file)
    friction_file_before = _count_friction_file(friction_file)

    automation_import = telemetry_persistence_service.import_automation_snapshots_from_file(automation_file)
    friction_import = telemetry_persistence_service.import_friction_events_from_file(friction_file)
    backend = telemetry_persistence_service.backend_info()

    automation_db_count = int(backend.get("automation_snapshot_rows") or 0)
    friction_db_count = int(backend.get("friction_event_rows") or 0)
    parity_ok = automation_db_count >= automation_file_before and friction_db_count >= friction_file_before

    return {
        "backend": backend,
        "automation": {
            "legacy_file": str(automation_file),
            "legacy_count": automation_file_before,
            "imported": int(automation_import.get("imported") or 0),
            "skipped": int(automation_import.get("skipped") or 0),
            "db_count": automation_db_count,
        },
        "friction": {
            "legacy_file": str(friction_file),
            "legacy_count": friction_file_before,
            "imported": int(friction_import.get("imported") or 0),
            "skipped": int(friction_import.get("skipped") or 0),
            "db_count": friction_db_count,
        },
        "parity_ok": parity_ok,
    }


def _purge_legacy_files(report: dict[str, Any]) -> dict[str, Any]:
    deleted: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    for key in ("automation", "friction"):
        row = report.get(key) if isinstance(report.get(key), dict) else {}
        path_raw = row.get("legacy_file")
        if not isinstance(path_raw, str) or not path_raw.strip():
            continue
        path = Path(path_raw)
        if not path.exists():
            missing.append(str(path))
            continue
        try:
            path.unlink()
            deleted.append(str(path))
        except OSError:
            failed.append(str(path))
    return {"deleted": deleted, "missing": missing, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local telemetry files to DB backend")
    parser.add_argument("--purge-local", action="store_true", help="Delete legacy local files after parity verification")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive purge when --purge-local is set")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    args = parser.parse_args()

    report = _verify_and_migrate()
    if not report.get("parity_ok"):
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Parity check failed. Refusing to purge local files.")
            print(json.dumps(report, indent=2))
        return 1

    purge_report: dict[str, Any] | None = None
    if args.purge_local:
        if not args.yes:
            print("Refusing purge without --yes")
            return 1
        purge_report = _purge_legacy_files(report)
        report["purge"] = purge_report
        if purge_report.get("failed"):
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(json.dumps(report, indent=2))
            return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Telemetry migration report:")
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
