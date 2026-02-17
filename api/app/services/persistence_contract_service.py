"""Global persistence contract checks for core domain data."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.adapters.postgres_store import PostgresGraphStore
from app.services import (
    commit_evidence_service,
    idea_registry_service,
    runtime_event_store,
    spec_registry_service,
    telemetry_persistence_service,
)


def contract_required() -> bool:
    raw = (
        os.getenv("GLOBAL_PERSISTENCE_REQUIRED")
        or os.getenv("PERSISTENCE_CONTRACT_REQUIRED")
        or "auto"
    ).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Auto-mode: enforce whenever a primary database is configured (typical production path).
    return bool(os.getenv("DATABASE_URL", "").strip())


def evaluate(app: Any) -> dict[str, Any]:
    required = contract_required()
    checked_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []

    store = getattr(getattr(app, "state", None), "graph_store", None)
    contributors_assets_contributions = {
        "ok": isinstance(store, PostgresGraphStore),
        "backend": type(store).__name__ if store is not None else "missing",
        "note": "contributors/assets/contributions persist in GraphStore backend",
    }
    if required and not contributors_assets_contributions["ok"]:
        failures.append("contributors_assets_contributions_not_postgresql")

    ideas_info = idea_registry_service.storage_info()
    ideas = {
        "ok": ideas_info.get("backend") == "postgresql",
        "backend": ideas_info.get("backend"),
        "note": "ideas persistence backend",
    }
    if required and not ideas["ok"]:
        failures.append("ideas_not_postgresql")

    specs_info = spec_registry_service.storage_info()
    specs_and_pseudocode = {
        "ok": specs_info.get("backend") == "postgresql",
        "backend": specs_info.get("backend"),
        "note": "spec + pseudocode fields persistence backend",
    }
    if required and not specs_and_pseudocode["ok"]:
        failures.append("specs_pseudocode_not_postgresql")

    runtime_info = runtime_event_store.backend_info()
    usage_runtime = {
        "ok": bool(runtime_info.get("enabled")) and runtime_info.get("backend") == "postgresql",
        "backend": runtime_info.get("backend"),
        "enabled": runtime_info.get("enabled"),
        "events_file_override": runtime_info.get("events_file_override"),
        "note": "runtime usage metrics persistence backend",
    }
    if required and not usage_runtime["ok"]:
        failures.append("runtime_usage_not_postgresql")

    telemetry_info = telemetry_persistence_service.backend_info()
    usage_provider_info = {
        "ok": telemetry_info.get("backend") == "postgresql",
        "backend": telemetry_info.get("backend"),
        "snapshots_path_override": bool(os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH", "").strip()),
        "note": "provider usage snapshots + friction telemetry backend",
    }
    if required and not usage_provider_info["ok"]:
        failures.append("provider_usage_not_postgresql")
    if required and usage_provider_info["snapshots_path_override"]:
        failures.append("provider_usage_file_override_enabled")

    commit_evidence_info = commit_evidence_service.backend_info()
    commit_evidence_tracking = {
        "ok": commit_evidence_info.get("backend") == "postgresql",
        "backend": commit_evidence_info.get("backend"),
        "record_rows": int(commit_evidence_info.get("record_rows") or 0),
        "note": "commit evidence tracking backend",
    }
    if required and not commit_evidence_tracking["ok"]:
        failures.append("commit_evidence_tracking_not_postgresql")

    report = {
        "required": required,
        "pass_contract": len(failures) == 0,
        "checked_at": checked_at,
        "domains": {
            "contributors_assets_contributions": contributors_assets_contributions,
            "ideas": ideas,
            "specs_and_pseudocode": specs_and_pseudocode,
            "usage_runtime_metrics": usage_runtime,
            "usage_provider_info": usage_provider_info,
            "commit_evidence_tracking": commit_evidence_tracking,
        },
        "failures": failures,
    }
    return report
