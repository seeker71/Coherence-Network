"""Canonical route registry service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _default_registry() -> dict:
    return {
        "version": "2026-02-15",
        "milestone": "runtime-value-attribution",
        "api_routes": [
            {
                "path": "/api/inventory/system-lineage",
                "methods": ["GET"],
                "purpose": "Unified questions, ideas, specs, implementation usage, runtime summary",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/inventory/routes/canonical",
                "methods": ["GET"],
                "purpose": "Canonical route set for current milestone",
                "idea_id": "oss-interface-alignment",
            },
            {
                "path": "/api/runtime/events",
                "methods": ["POST", "GET"],
                "purpose": "Runtime event ingestion and inspection",
                "idea_id": "oss-interface-alignment",
            },
            {
                "path": "/api/runtime/ideas/summary",
                "methods": ["GET"],
                "purpose": "Runtime/cost rollup by idea",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/runtime/endpoints/summary",
                "methods": ["GET"],
                "purpose": "Runtime usage rollup by endpoint with root-idea lineage",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/runtime/exerciser/run",
                "methods": ["POST"],
                "purpose": "Run safe GET endpoint exerciser to increase runtime usage coverage continuously",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/value-lineage/links",
                "methods": ["POST"],
                "purpose": "Create idea/spec/implementation lineage",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/value-lineage/links/{lineage_id}/usage-events",
                "methods": ["POST"],
                "purpose": "Append measurable usage/value signal",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/value-lineage/links/{lineage_id}/valuation",
                "methods": ["GET"],
                "purpose": "Value/cost/ROI summary per lineage",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/value-lineage/links/{lineage_id}/payout-preview",
                "methods": ["POST"],
                "purpose": "Role-weight payout attribution preview",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/inventory/flow",
                "methods": ["GET"],
                "purpose": "Unified idea->spec->process->implementation->validation flow inventory",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/inventory/endpoint-traceability",
                "methods": ["GET"],
                "purpose": "Endpoint-level traceability coverage for idea/spec/process/validation",
                "idea_id": "oss-interface-alignment",
            },
            {
                "path": "/api/inventory/gaps/sync-traceability",
                "methods": ["POST"],
                "purpose": "Auto-sync missing idea/spec/process/usage artifacts from endpoint gaps",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/inventory/process-completeness",
                "methods": ["GET"],
                "purpose": "Strict process completeness report with blockers and optional auto-sync",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/inventory/gaps/sync-process-tasks",
                "methods": ["POST"],
                "purpose": "Create deduped tasks for every failing process-completeness blocker",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/inventory/questions/proactive",
                "methods": ["GET"],
                "purpose": "Generate proactive high-ROI questions from recent change history",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/inventory/questions/sync-proactive",
                "methods": ["POST"],
                "purpose": "Sync proactive generated questions into idea question backlog",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/inventory/flow/next-unblock-task",
                "methods": ["POST"],
                "purpose": "Suggest or create highest-priority flow unblock task",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/ideas/storage",
                "methods": ["GET"],
                "purpose": "Idea registry storage backend and row-count inspection",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/agent/tasks/upsert-active",
                "methods": ["POST"],
                "purpose": "Upsert running external work session into persistent task inventory",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/api/agent/visibility",
                "methods": ["GET"],
                "purpose": "Unified pipeline and usage visibility with remaining tracking gaps",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/automation/usage",
                "methods": ["GET"],
                "purpose": "Provider adapter usage and normalized automation capacity metrics",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/automation/usage/alerts",
                "methods": ["GET"],
                "purpose": "Threshold alerts for provider usage remaining capacity",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/api/automation/usage/snapshots",
                "methods": ["GET"],
                "purpose": "Historical normalized provider usage snapshots",
                "idea_id": "coherence-network-agent-pipeline",
            },
        ],
        "web_routes": [
            {
                "path": "/gates",
                "purpose": "Human validation view for release/public contracts",
                "idea_id": "oss-interface-alignment",
            },
            {
                "path": "/search",
                "purpose": "Human discovery interface for graph intelligence",
                "idea_id": "coherence-signal-depth",
            },
            {
                "path": "/api/runtime-beacon",
                "purpose": "Web runtime telemetry forwarder",
                "idea_id": "oss-interface-alignment",
            },
            {
                "path": "/flow",
                "purpose": "Human flow visualization for spec-process-implementation-validation tracking",
                "idea_id": "portfolio-governance",
            },
            {
                "path": "/agent",
                "purpose": "Human visibility console for agent pipeline and usage coverage",
                "idea_id": "coherence-network-agent-pipeline",
            },
            {
                "path": "/automation",
                "purpose": "Human interface for automation provider capacity and alert visibility",
                "idea_id": "coherence-network-agent-pipeline",
            },
        ],
    }


def _registry_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "canonical_routes.json"


def get_canonical_routes() -> dict:
    path = _registry_path()
    if not path.exists():
        base = _default_registry()
    else:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            base = data if isinstance(data, dict) else _default_registry()
        except (OSError, json.JSONDecodeError):
            base = _default_registry()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": base.get("version", "unknown"),
        "milestone": base.get("milestone", "unknown"),
        "api_routes": base.get("api_routes", []),
        "web_routes": base.get("web_routes", []),
    }
