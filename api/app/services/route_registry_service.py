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
