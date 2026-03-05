"""Events store and idea map for runtime telemetry."""

from __future__ import annotations

import json
from typing import Any

from app.models.runtime import RuntimeEvent
from app.services import runtime_event_store

from app.services.runtime import paths as runtime_paths


def coerce_runtime_event_rows(payload: Any, *, limit: int) -> list[RuntimeEvent]:
    if not isinstance(payload, list):
        return []
    rows: list[RuntimeEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(RuntimeEvent(**raw))
        except Exception:
            continue
    rows.sort(key=lambda row: row.recorded_at, reverse=True)
    return rows[: max(1, min(int(limit), 5000))]


def default_idea_map() -> dict:
    return {
        "prefix_map": {
            "/api/health": "oss-interface-alignment",
            "/api/ideas": "portfolio-governance",
            "/api/inventory": "portfolio-governance",
            "/api/agent": "portfolio-governance",
            "/api/value-lineage": "portfolio-governance",
            "/api/gates": "oss-interface-alignment",
            "/api/runtime": "oss-interface-alignment",
            "/api/health-proxy": "oss-interface-alignment",
            "/v1": "portfolio-governance",
            "/api": "oss-interface-alignment",
            "/gates": "oss-interface-alignment",
            "/search": "coherence-signal-depth",
            "/": "oss-interface-alignment",
        }
    }


def load_idea_map() -> dict:
    path = runtime_paths.idea_map_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_idea_map(), indent=2), encoding="utf-8")
        return default_idea_map()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default_idea_map()
    if not isinstance(data, dict):
        return default_idea_map()
    return data


def ensure_events_store() -> None:
    if runtime_event_store.enabled():
        runtime_event_store.ensure_schema()
        return
    path = runtime_paths.events_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"events": []}, indent=2), encoding="utf-8")


def read_store() -> dict:
    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(limit=5000)
        return {"events": [row.model_dump(mode="json") for row in rows]}
    ensure_events_store()
    path = runtime_paths.events_path()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"events": []}
    if not isinstance(data, dict):
        return {"events": []}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    return {"events": events}


def write_store(data: dict) -> None:
    if runtime_event_store.enabled():
        return
    path = runtime_paths.events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
