#!/usr/bin/env python3
"""Migrate file-based tracking domains into PostgreSQL-backed stores.

Domains covered:
- commit evidence tracking
- idea tracking
- spec tracking
- asset/contributor/contribution tracking
- telemetry tracking (automation/friction/task metrics)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.adapters.postgres_store import (
    AssetModel,
    ContributionModel,
    ContributorModel,
    PostgresGraphStore,
)
from app.models.asset import Asset
from app.models.contribution import Contribution
from app.models.contributor import Contributor
from app.models.spec_registry import SpecRegistryCreate, SpecRegistryUpdate
from app.services import (
    automation_usage_service,
    commit_evidence_registry_service,
    friction_service,
    idea_registry_service,
    idea_service,
    metrics_service,
    spec_registry_service,
    telemetry_persistence_service,
)


def _require_postgres_database_url() -> str:
    url = str(os.getenv("DATABASE_URL") or "").strip()
    if "postgres" not in url.lower():
        raise RuntimeError("DATABASE_URL must point to PostgreSQL for this migration")
    return url


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            count += 1
    return count


def _legacy_graph_store_path() -> Path:
    configured = os.getenv("GRAPH_STORE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "graph_store.json"


def _legacy_governance_sqlite_path() -> Path:
    configured = os.getenv("GOVERNANCE_LEGACY_SQLITE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "governance_registry.db"


def _migrate_telemetry() -> dict[str, Any]:
    telemetry_persistence_service.ensure_schema()

    automation_file = automation_usage_service._snapshots_path().resolve()  # type: ignore[attr-defined]
    friction_file = friction_service.friction_file_path().resolve()
    metrics_file = Path(os.getenv("METRICS_FILE_PATH") or metrics_service.METRICS_FILE).resolve()

    automation_legacy_count = 0
    if automation_file.exists():
        try:
            payload = json.loads(automation_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        rows = payload.get("snapshots") if isinstance(payload, dict) else []
        if isinstance(rows, list):
            automation_legacy_count = sum(1 for row in rows if isinstance(row, dict))

    friction_legacy_count = _count_jsonl(friction_file)
    metrics_legacy_count = _count_jsonl(metrics_file)

    automation_import = telemetry_persistence_service.import_automation_snapshots_from_file(automation_file)
    friction_import = telemetry_persistence_service.import_friction_events_from_file(friction_file)
    metrics_import = telemetry_persistence_service.import_task_metrics_from_file(metrics_file)

    backend = telemetry_persistence_service.backend_info()
    parity_ok = (
        int(backend.get("automation_snapshot_rows") or 0) >= automation_legacy_count
        and int(backend.get("friction_event_rows") or 0) >= friction_legacy_count
        and int(backend.get("task_metric_rows") or 0) >= metrics_legacy_count
    )
    return {
        "parity_ok": parity_ok,
        "automation": {
            "legacy_file": str(automation_file),
            "legacy_count": automation_legacy_count,
            "imported": int(automation_import.get("imported") or 0),
            "skipped": int(automation_import.get("skipped") or 0),
            "db_count": int(backend.get("automation_snapshot_rows") or 0),
        },
        "friction": {
            "legacy_file": str(friction_file),
            "legacy_count": friction_legacy_count,
            "imported": int(friction_import.get("imported") or 0),
            "skipped": int(friction_import.get("skipped") or 0),
            "db_count": int(backend.get("friction_event_rows") or 0),
        },
        "metrics": {
            "legacy_file": str(metrics_file),
            "legacy_count": metrics_legacy_count,
            "imported": int(metrics_import.get("imported") or 0),
            "skipped": int(metrics_import.get("skipped") or 0),
            "db_count": int(backend.get("task_metric_rows") or 0),
        },
    }


def _migrate_commit_evidence() -> dict[str, Any]:
    evidence_dir = Path(os.getenv("IDEA_COMMIT_EVIDENCE_DIR") or Path(__file__).resolve().parents[2] / "docs" / "system_audit")
    legacy_count = len(list(evidence_dir.glob("commit_evidence_*.json"))) if evidence_dir.exists() else 0
    import_report = commit_evidence_registry_service.import_from_dir(evidence_dir, limit=5000)
    backend = commit_evidence_registry_service.backend_info()
    parity_ok = int(backend.get("rows") or 0) >= legacy_count
    return {
        "parity_ok": parity_ok,
        "legacy_dir": str(evidence_dir),
        "legacy_count": legacy_count,
        "imported": int(import_report.get("imported") or 0),
        "skipped": int(import_report.get("skipped") or 0),
        "db_count": int(backend.get("rows") or 0),
    }


def _migrate_graph_store(database_url: str) -> dict[str, Any]:
    path = _legacy_graph_store_path().resolve()
    if not path.exists():
        return {
            "parity_ok": True,
            "legacy_file": str(path),
            "legacy_counts": {"contributors": 0, "assets": 0, "contributions": 0},
            "migrated": {"contributors": 0, "assets": 0, "contributions": 0},
            "skipped": {"contributors": 0, "assets": 0, "contributions": 0},
            "db_counts": {"contributors": 0, "assets": 0, "contributions": 0},
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}

    raw_contributors = payload.get("contributors") if isinstance(payload, dict) else []
    raw_assets = payload.get("assets") if isinstance(payload, dict) else []
    raw_contributions = payload.get("contributions") if isinstance(payload, dict) else []

    contributors = [row for row in raw_contributors if isinstance(row, dict)]
    assets = [row for row in raw_assets if isinstance(row, dict)]
    contributions = [row for row in raw_contributions if isinstance(row, dict)]

    store = PostgresGraphStore(database_url)
    migrated = {"contributors": 0, "assets": 0, "contributions": 0}
    skipped = {"contributors": 0, "assets": 0, "contributions": 0}

    with store._session() as session:  # noqa: SLF001
        existing_contributors = {str(row.id) for row in session.query(ContributorModel.id).all()}
        existing_assets = {str(row.id) for row in session.query(AssetModel.id).all()}
        existing_contributions = {str(row.id) for row in session.query(ContributionModel.id).all()}

        for row in contributors:
            try:
                contributor = Contributor(**row)
            except Exception:
                skipped["contributors"] += 1
                continue
            if str(contributor.id) in existing_contributors:
                skipped["contributors"] += 1
                continue
            session.add(
                ContributorModel(
                    id=contributor.id,
                    type=contributor.type.value,
                    name=contributor.name,
                    email=contributor.email,
                    wallet_address=contributor.wallet_address,
                    hourly_rate=float(contributor.hourly_rate) if contributor.hourly_rate else None,
                    created_at=contributor.created_at,
                )
            )
            existing_contributors.add(str(contributor.id))
            migrated["contributors"] += 1

        for row in assets:
            try:
                asset = Asset(**row)
            except Exception:
                skipped["assets"] += 1
                continue
            if str(asset.id) in existing_assets:
                skipped["assets"] += 1
                continue
            session.add(
                AssetModel(
                    id=asset.id,
                    type=asset.type.value,
                    description=asset.description,
                    total_cost=float(asset.total_cost) if asset.total_cost else 0.0,
                    created_at=asset.created_at,
                )
            )
            existing_assets.add(str(asset.id))
            migrated["assets"] += 1

        for row in contributions:
            try:
                contribution = Contribution(**row)
            except Exception:
                skipped["contributions"] += 1
                continue
            if str(contribution.id) in existing_contributions:
                skipped["contributions"] += 1
                continue
            if str(contribution.contributor_id) not in existing_contributors or str(contribution.asset_id) not in existing_assets:
                skipped["contributions"] += 1
                continue
            session.add(
                ContributionModel(
                    id=contribution.id,
                    contributor_id=contribution.contributor_id,
                    asset_id=contribution.asset_id,
                    cost_amount=float(Decimal(str(contribution.cost_amount))),
                    coherence_score=float(contribution.coherence_score),
                    timestamp=contribution.timestamp,
                    meta=contribution.metadata,
                )
            )
            existing_contributions.add(str(contribution.id))
            migrated["contributions"] += 1

        db_counts = {
            "contributors": int(session.query(ContributorModel.id).count()),
            "assets": int(session.query(AssetModel.id).count()),
            "contributions": int(session.query(ContributionModel.id).count()),
        }

    parity_ok = (
        db_counts["contributors"] >= len(contributors)
        and db_counts["assets"] >= len(assets)
        and db_counts["contributions"] >= len(contributions)
    )

    return {
        "parity_ok": parity_ok,
        "legacy_file": str(path),
        "legacy_counts": {
            "contributors": len(contributors),
            "assets": len(assets),
            "contributions": len(contributions),
        },
        "migrated": migrated,
        "skipped": skipped,
        "db_counts": db_counts,
    }


def _migrate_ideas() -> dict[str, Any]:
    existing = idea_registry_service.load_ideas()
    legacy_path = Path(os.getenv("IDEA_PORTFOLIO_PATH") or Path(__file__).resolve().parents[2] / "logs" / "idea_portfolio.json").resolve()
    migrated = 0
    source = "registry"
    if not existing:
        ideas, source = idea_service._read_legacy_file_ideas()  # type: ignore[attr-defined]
        idea_registry_service.save_ideas(ideas, bootstrap_source=f"{source}+migrated")
        migrated = len(ideas)
    current = idea_registry_service.load_ideas()
    return {
        "parity_ok": len(current) >= len(existing),
        "legacy_file": str(legacy_path),
        "legacy_file_exists": legacy_path.exists(),
        "migrated": migrated,
        "source": source,
        "db_count": len(current),
    }


def _migrate_specs() -> dict[str, Any]:
    sqlite_path = _legacy_governance_sqlite_path().resolve()
    if not sqlite_path.exists():
        return {
            "parity_ok": True,
            "legacy_file": str(sqlite_path),
            "legacy_count": 0,
            "migrated": 0,
            "updated": 0,
            "skipped": 0,
            "db_count": spec_registry_service.summary().get("count", 0),
        }

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM spec_registry_entries").fetchall()
    except sqlite3.DatabaseError:
        rows = []
    finally:
        conn.close()

    migrated = 0
    updated = 0
    skipped = 0
    for row in rows:
        data = dict(row)
        spec_id = str(data.get("spec_id") or "").strip()
        title = str(data.get("title") or "").strip()
        summary = str(data.get("summary") or "").strip()
        if not spec_id or not title or not summary:
            skipped += 1
            continue

        create_payload = SpecRegistryCreate(
            spec_id=spec_id,
            title=title,
            summary=summary,
            potential_value=float(data.get("potential_value") or 0.0),
            actual_value=float(data.get("actual_value") or 0.0),
            estimated_cost=float(data.get("estimated_cost") or 0.0),
            actual_cost=float(data.get("actual_cost") or 0.0),
            idea_id=(str(data.get("idea_id") or "").strip() or None),
            process_summary=(str(data.get("process_summary") or "").strip() or None),
            pseudocode_summary=(str(data.get("pseudocode_summary") or "").strip() or None),
            implementation_summary=(str(data.get("implementation_summary") or "").strip() or None),
            created_by_contributor_id=(str(data.get("created_by_contributor_id") or "").strip() or None),
        )
        if spec_registry_service.get_spec(spec_id) is None:
            created = spec_registry_service.create_spec(create_payload)
            if created is not None:
                migrated += 1
                continue

        updated_row = spec_registry_service.update_spec(
            spec_id,
            SpecRegistryUpdate(
                title=title,
                summary=summary,
                potential_value=float(data.get("potential_value") or 0.0),
                actual_value=float(data.get("actual_value") or 0.0),
                estimated_cost=float(data.get("estimated_cost") or 0.0),
                actual_cost=float(data.get("actual_cost") or 0.0),
                idea_id=(str(data.get("idea_id") or "").strip() or None),
                process_summary=(str(data.get("process_summary") or "").strip() or None),
                pseudocode_summary=(str(data.get("pseudocode_summary") or "").strip() or None),
                implementation_summary=(str(data.get("implementation_summary") or "").strip() or None),
                updated_by_contributor_id=(str(data.get("updated_by_contributor_id") or "").strip() or None),
            ),
        )
        if updated_row is not None:
            updated += 1
        else:
            skipped += 1

    summary = spec_registry_service.summary()
    db_count = int(summary.get("count") or 0)
    parity_ok = db_count >= len(rows)
    return {
        "parity_ok": parity_ok,
        "legacy_file": str(sqlite_path),
        "legacy_count": len(rows),
        "migrated": migrated,
        "updated": updated,
        "skipped": skipped,
        "db_count": db_count,
    }


def _purge_files(files: list[Path]) -> dict[str, list[str]]:
    deleted: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    for path in files:
        resolved = path.resolve()
        if not resolved.exists():
            missing.append(str(resolved))
            continue
        try:
            resolved.unlink()
            deleted.append(str(resolved))
        except OSError:
            failed.append(str(resolved))
    return {"deleted": deleted, "missing": missing, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate tracking domains to PostgreSQL")
    parser.add_argument("--purge-local", action="store_true", help="Delete legacy local files after successful parity checks")
    parser.add_argument("--yes", action="store_true", help="Confirm local-file purge when --purge-local is set")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    database_url = _require_postgres_database_url()

    report = {
        "database": "postgresql",
        "telemetry": _migrate_telemetry(),
        "commit_evidence": _migrate_commit_evidence(),
        "ideas": _migrate_ideas(),
        "specs": _migrate_specs(),
        "graph_store": _migrate_graph_store(database_url),
    }

    parity_ok = all(
        bool(report.get(domain, {}).get("parity_ok"))
        for domain in ("telemetry", "commit_evidence", "ideas", "specs", "graph_store")
    )
    report["parity_ok"] = parity_ok

    if not parity_ok:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Parity check failed. Refusing to purge local files.")
            print(json.dumps(report, indent=2))
        return 1

    if args.purge_local:
        if not args.yes:
            print("Refusing purge without --yes")
            return 1
        files_to_purge = [
            Path(report["telemetry"]["automation"]["legacy_file"]),
            Path(report["telemetry"]["friction"]["legacy_file"]),
            Path(report["telemetry"]["metrics"]["legacy_file"]),
            Path(report["ideas"]["legacy_file"]),
            Path(report["specs"]["legacy_file"]),
            Path(report["graph_store"]["legacy_file"]),
        ]
        report["purge"] = _purge_files(files_to_purge)
        if report["purge"].get("failed"):
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(json.dumps(report, indent=2))
            return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Tracking migration report:")
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
