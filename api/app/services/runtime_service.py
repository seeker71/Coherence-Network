"""Runtime telemetry persistence and aggregation service."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.models.runtime import IdeaRuntimeSummary, RuntimeEvent, RuntimeEventCreate
from app.services import value_lineage_service


def _default_events_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "runtime_events.json"


def _events_path() -> Path:
    configured = os.getenv("RUNTIME_EVENTS_PATH")
    return Path(configured) if configured else _default_events_path()


def _default_idea_map_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "runtime_idea_map.json"


def _idea_map_path() -> Path:
    configured = os.getenv("RUNTIME_IDEA_MAP_PATH")
    return Path(configured) if configured else _default_idea_map_path()


def _runtime_cost_per_second() -> float:
    return float(os.getenv("RUNTIME_COST_PER_SECOND", "0.002"))


def _ensure_events_store() -> None:
    path = _events_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"events": []}, indent=2), encoding="utf-8")


def _read_store() -> dict:
    _ensure_events_store()
    path = _events_path()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"events": []}
    if not isinstance(data, dict):
        return {"events": []}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    return {"events": events}


def _write_store(data: dict) -> None:
    path = _events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _default_idea_map() -> dict:
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


def _load_idea_map() -> dict:
    path = _idea_map_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_default_idea_map(), indent=2), encoding="utf-8")
        return _default_idea_map()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_idea_map()
    if not isinstance(data, dict):
        return _default_idea_map()
    return data


def resolve_idea_id(endpoint: str, explicit_idea_id: str | None = None) -> str:
    if explicit_idea_id:
        return explicit_idea_id

    map_data = _load_idea_map()
    prefix_map = map_data.get("prefix_map") if isinstance(map_data.get("prefix_map"), dict) else {}
    for prefix, idea_id in prefix_map.items():
        if isinstance(prefix, str) and isinstance(idea_id, str) and endpoint.startswith(prefix):
            return idea_id

    # Derive idea from lineage endpoint references where possible.
    marker = "/api/value-lineage/links/"
    if marker in endpoint:
        tail = endpoint.split(marker, 1)[1]
        lineage_id = tail.split("/", 1)[0]
        link = value_lineage_service.get_link(lineage_id)
        if link:
            return link.idea_id

    if endpoint.startswith("/api"):
        return "oss-interface-alignment"
    if endpoint.startswith("/v1"):
        return "portfolio-governance"
    if endpoint.startswith("/"):
        return "oss-interface-alignment"

    return "unmapped"


def record_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    idea_id = resolve_idea_id(payload.endpoint, payload.idea_id)
    runtime_cost = round((float(payload.runtime_ms) / 1000.0) * _runtime_cost_per_second(), 8)
    event = RuntimeEvent(
        id=f"rt_{uuid4().hex[:12]}",
        source=payload.source,
        endpoint=payload.endpoint,
        method=payload.method.upper(),
        status_code=payload.status_code,
        runtime_ms=round(float(payload.runtime_ms), 4),
        idea_id=idea_id,
        metadata=payload.metadata,
        runtime_cost_estimate=runtime_cost,
    )
    data = _read_store()
    data["events"].append(event.model_dump(mode="json"))
    _write_store(data)
    return event


def list_events(limit: int = 100) -> list[RuntimeEvent]:
    data = _read_store()
    out: list[RuntimeEvent] = []
    for raw in data["events"]:
        try:
            out.append(RuntimeEvent(**raw))
        except Exception:
            continue
    out.sort(key=lambda x: x.recorded_at, reverse=True)
    return out[: max(1, min(limit, 2000))]


def summarize_by_idea(seconds: int = 3600) -> list[IdeaRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = [e for e in list_events(limit=2000) if e.recorded_at >= cutoff]

    grouped: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        grouped.setdefault(event.idea_id or "unmapped", []).append(event)

    summaries: list[IdeaRuntimeSummary] = []
    for idea_id, events in grouped.items():
        total_runtime = round(sum(e.runtime_ms for e in events), 4)
        total_cost = round(sum(e.runtime_cost_estimate for e in events), 8)
        by_source: dict[str, int] = {}
        for event in events:
            by_source[event.source] = by_source.get(event.source, 0) + 1
        summaries.append(
            IdeaRuntimeSummary(
                idea_id=idea_id,
                event_count=len(events),
                total_runtime_ms=total_runtime,
                average_runtime_ms=round(total_runtime / len(events), 4),
                runtime_cost_estimate=total_cost,
                by_source=by_source,
            )
        )
    summaries.sort(key=lambda x: x.runtime_cost_estimate, reverse=True)
    return summaries
