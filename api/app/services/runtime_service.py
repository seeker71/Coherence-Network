"""Runtime telemetry persistence and aggregation service."""

from __future__ import annotations

import json
import os
import time
import base64
import hashlib
import logging
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from app.config_loader import database_url, get_bool, get_float, get_int, get_str
from app.models.runtime import (
    EndpointAttentionReport,
    EndpointAttentionRow,
    EndpointRuntimeSummary,
    IdeaRuntimeSummary,
    RuntimeEvent,
    RuntimeEventCreate,
    WebViewPerformanceReport,
)
from app.services import (
    agent_task_store_service,
    idea_lineage_service,
    route_registry_service,
    runtime_exerciser_service,
    runtime_event_store,
    runtime_web_view_service,
    telemetry_persistence_service,
    value_lineage_service,
)

logger = logging.getLogger(__name__)


_RUNTIME_EVENTS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "cache_key": "",
    "rows": [],
}
_RUNTIME_EVENTS_CACHE_TTL_SECONDS = 30.0
_RUNTIME_EVENTS_FILE_LOCK = threading.Lock()

_LIVE_CHANGE_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "payload": {},
}
_LIVE_CHANGE_CACHE_TTL_SECONDS = 5.0

_RUNTIME_ENDPOINT_CACHE_NAMESPACE = "runtime_endpoint_cache_v1"
_RUNTIME_ENDPOINT_CACHE_DEFAULT_TTL_SECONDS = 120.0
_RUNTIME_ENDPOINT_CACHE_MAX_STALE_SECONDS = 7 * 24 * 60 * 60
_RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES: dict[str, Future[Any]] = {}
_RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK = threading.Lock()
def _runtime_endpoint_cache_max_workers() -> int:
    return max(2, min(get_int("runtime", "endpoint_cache_max_workers", 4), 8))


_RUNTIME_ENDPOINT_CACHE_REFRESH_POOL = ThreadPoolExecutor(
    max_workers=_runtime_endpoint_cache_max_workers(),
    thread_name_prefix="runtime-endpoint-cache-refresh",
)
_RUNTIME_ENDPOINT_CACHE_BUSTER = 0

_DEFAULT_MVP_ACCEPTANCE_POLICY: dict[str, Any] = {
    "version": "2026-03-06",
    "budget": {
        "hosted_base_budget_usd": 0.0,
        "provider_base_budget_usd": 0.0,
    },
    "revenue": {
        "per_accepted_review_usd": 0.0,
    },
    "reinvestment": {
        "ratio": 0.4,
        "allocations": {
            "infrastructure": 0.5,
            "code_quality": 0.3,
            "product_delivery": 0.2,
        },
    },
    "acceptance": {
        "min_accepted_reviews": 1,
        "min_acceptance_rate": 0.7,
        "require_budget_coverage": True,
        "require_revenue_coverage": True,
    },
    "trust": {
        "require_trust_for_payout": True,
        "require_trust_adjusted_revenue_coverage": False,
        "require_payout_readiness": False,
        "revenue_multipliers": {
            "validator": 1.15,
            "anchor": 1.10,
            "cap": 2.0,
        },
        "public_validator": {
            "required": False,
            "quorum": 0,
            "keys": [],
            "attestations": [],
        },
        "public_transparency_anchor": {
            "required": False,
            "min_anchors": 0,
            "trusted_domains": ["rekor.sigstore.dev"],
            "anchors": [],
            "fetch_timeout_seconds": 5.0,
        },
    },
}
_MVP_ACCEPTANCE_POLICY_CACHE: dict[str, Any] | None = None


def _mvp_acceptance_policy_path() -> Path:
    for base in [
        Path(__file__).resolve().parents[3] / "config" / "mvp_acceptance_policy.json",
        Path(__file__).resolve().parents[2] / "config" / "mvp_acceptance_policy.json",
    ]:
        if base.exists():
            return base
    return Path(__file__).resolve().parents[2] / "config" / "mvp_acceptance_policy.json"


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge_dict(base[key], value)
        else:
            merged[key] = value
    return merged


def _load_mvp_acceptance_policy() -> dict[str, Any]:
    global _MVP_ACCEPTANCE_POLICY_CACHE
    if _MVP_ACCEPTANCE_POLICY_CACHE is not None:
        return _MVP_ACCEPTANCE_POLICY_CACHE
    path = _mvp_acceptance_policy_path()
    if not path.exists():
        _MVP_ACCEPTANCE_POLICY_CACHE = dict(_DEFAULT_MVP_ACCEPTANCE_POLICY)
        return _MVP_ACCEPTANCE_POLICY_CACHE
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        _MVP_ACCEPTANCE_POLICY_CACHE = dict(_DEFAULT_MVP_ACCEPTANCE_POLICY)
        return _MVP_ACCEPTANCE_POLICY_CACHE
    if not isinstance(payload, dict):
        _MVP_ACCEPTANCE_POLICY_CACHE = dict(_DEFAULT_MVP_ACCEPTANCE_POLICY)
        return _MVP_ACCEPTANCE_POLICY_CACHE
    _MVP_ACCEPTANCE_POLICY_CACHE = _deep_merge_dict(_DEFAULT_MVP_ACCEPTANCE_POLICY, payload)
    return _MVP_ACCEPTANCE_POLICY_CACHE


def reset_mvp_acceptance_policy_cache() -> None:
    global _MVP_ACCEPTANCE_POLICY_CACHE
    _MVP_ACCEPTANCE_POLICY_CACHE = None


def _default_events_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "runtime_events.json"


def _events_path() -> Path:
    configured = get_str("runtime", "events_path", "")
    return Path(configured) if configured else _default_events_path()


def _default_idea_map_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "runtime_idea_map.json"


def _idea_map_path() -> Path:
    configured = get_str("runtime", "idea_map_path", "")
    return Path(configured) if configured else _default_idea_map_path()


def _logs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "logs"


def _agent_tasks_path() -> Path:
    configured = get_str("runtime", "agent_tasks_path", "")
    if configured:
        return Path(configured)
    return _logs_dir() / "agent_tasks.json"


def _monitor_issues_path() -> Path:
    return _logs_dir() / "monitor_issues.json"


def _status_report_path() -> Path:
    return _logs_dir() / "pipeline_status_report.json"


def _path_signature(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size": 0, "mtime_ns": 0}
    return {
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _runtime_cost_per_second() -> float:
    return get_float("runtime", "cost_per_second", 0.002)


def estimate_runtime_cost(runtime_ms: float) -> float:
    return round((max(0.0, float(runtime_ms)) / 1000.0) * _runtime_cost_per_second(), 8)


def _runtime_events_store_cache_key() -> str:
    if runtime_event_store.enabled():
        db_url = database_url("runtime") or database_url(None)
        url = db_url or "<runtime-database>"
        return f"db:{url}"
    return f"file:{_events_path()}"


def _runtime_events_cache_key(limit: int, since: datetime | None, source: str | None) -> str:
    cutoff = "all"
    if since is not None:
        since_ts = int(since.timestamp())
        cutoff = str(since_ts // max(1, int(_RUNTIME_EVENTS_CACHE_TTL_SECONDS)))
    source_value = str(source or "").strip().lower() or "all"
    return f"store={_runtime_events_store_cache_key()}|limit={limit}|cutoff={cutoff}|source={source_value}"


def _runtime_endpoint_cache_ttl_seconds(cache_name: str, default: float = _RUNTIME_ENDPOINT_CACHE_DEFAULT_TTL_SECONDS) -> float:
    parsed = get_float("runtime", "endpoint_cache_ttl_seconds", default)
    return max(1.0, min(float(parsed), 86400.0))


def _runtime_endpoint_cache_meta_key(endpoint: str, params: dict[str, Any] | None = None) -> str:
    scope_parts = [
        get_str("runtime", "events_path") or "",
        get_str("database_overrides", "runtime") or "",
        database_url(None) or "",
        str(get_bool("api", "testing", False)),
        get_str("api", "test_context_id") or "",
        str(_runtime_events_store_cache_key()),
        str(_RUNTIME_ENDPOINT_CACHE_BUSTER),
    ]
    scope_digest = hashlib.sha1("||".join(scope_parts).encode("utf-8")).hexdigest()[:12]
    canonical = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha1(f"{endpoint}|{canonical}".encode("utf-8")).hexdigest()
    return f"{_RUNTIME_ENDPOINT_CACHE_NAMESPACE}::{scope_digest}::{endpoint}::{digest}"


def _parse_runtime_cache_timestamp(raw: Any) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _runtime_endpoint_cache_read(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[Any | None, float | None]:
    key = _runtime_endpoint_cache_meta_key(endpoint, params)
    raw = telemetry_persistence_service.get_meta_value(key)
    if not raw:
        return None, None
    try:
        envelope = json.loads(raw)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(envelope, dict) or "payload" not in envelope:
        return None, None
    payload = envelope.get("payload")
    stored_at = _parse_runtime_cache_timestamp(envelope.get("stored_at"))
    if stored_at is None:
        return payload, None
    age_seconds = max(0.0, (datetime.now(timezone.utc) - stored_at).total_seconds())
    if age_seconds > float(_RUNTIME_ENDPOINT_CACHE_MAX_STALE_SECONDS):
        return None, None
    return payload, age_seconds


def _runtime_endpoint_cache_write(endpoint: str, payload: Any, params: dict[str, Any] | None = None) -> None:
    key = _runtime_endpoint_cache_meta_key(endpoint, params)
    envelope = {
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    telemetry_persistence_service.set_meta_value(
        key,
        json.dumps(envelope, separators=(",", ":"), default=str),
    )


def _runtime_endpoint_cache_schedule_refresh(
    endpoint: str,
    *,
    producer: Callable[[], Any],
    params: dict[str, Any] | None = None,
) -> bool:
    key = _runtime_endpoint_cache_meta_key(endpoint, params)
    with _RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK:
        active = _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.get(key)
        if active is not None and not active.done():
            return False

        def _run_refresh() -> Any:
            payload = producer()
            _runtime_endpoint_cache_write(endpoint, payload, params=params)
            return payload

        future = _RUNTIME_ENDPOINT_CACHE_REFRESH_POOL.submit(_run_refresh)
        _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES[key] = future

        def _cleanup(done_future: Future[Any]) -> None:
            with _RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK:
                current = _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.get(key)
                if current is done_future:
                    _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.pop(key, None)
            try:
                done_future.result()
            except Exception:
                logger.exception("runtime endpoint cache refresh failed", extra={"endpoint": endpoint})

        future.add_done_callback(_cleanup)
        return True


def _runtime_endpoint_cached_value(
    endpoint: str,
    *,
    fresh_ttl_seconds: float,
    refresh_producer: Callable[[], Any],
    fallback_producer: Callable[[], Any] | None = None,
    params: dict[str, Any] | None = None,
    force_refresh: bool = False,
) -> Any:
    if force_refresh:
        payload = refresh_producer()
        _runtime_endpoint_cache_write(endpoint, payload, params=params)
        return payload

    ttl = _runtime_endpoint_cache_ttl_seconds(endpoint, default=fresh_ttl_seconds)
    cached_payload, cached_age = _runtime_endpoint_cache_read(endpoint, params=params)
    if cached_payload is not None and cached_age is not None and cached_age <= ttl:
        return cached_payload
    if cached_payload is not None:
        _runtime_endpoint_cache_schedule_refresh(
            endpoint,
            producer=refresh_producer,
            params=params,
        )
        return cached_payload
    try:
        payload = refresh_producer()
        _runtime_endpoint_cache_write(endpoint, payload, params=params)
        return payload
    except Exception:
        if fallback_producer is not None:
            fallback_payload = fallback_producer()
            _runtime_endpoint_cache_write(endpoint, fallback_payload, params=params)
            return fallback_payload
        raise


def _coerce_runtime_event_rows(payload: Any, *, limit: int) -> list[RuntimeEvent]:
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


def _invalidate_runtime_events_cache() -> None:
    _RUNTIME_EVENTS_CACHE["expires_at"] = 0.0
    _RUNTIME_EVENTS_CACHE["rows"] = []

    try:
        from app.services import automation_usage_service

        automation_usage_service.invalidate_cache()
    except (ImportError, Exception):
        pass

    _RUNTIME_EVENTS_CACHE["rows"] = []


def _ensure_events_store() -> None:
    if runtime_event_store.enabled():
        runtime_event_store.ensure_schema()
        return
    path = _events_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"events": []}, indent=2), encoding="utf-8")


def _read_store() -> dict:
    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(limit=5000)
        return {"events": [row.model_dump(mode="json") for row in rows]}
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
    if runtime_event_store.enabled():
        # Writes happen via record_event() for DB-backed storage.
        return
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


def _normalize_path(endpoint: str) -> str:
    cleaned = str(endpoint or "").strip()
    if not cleaned:
        return "/"
    path = cleaned.split("?", 1)[0].strip()
    if not path:
        return "/"
    return path if path.startswith("/") else f"/{path}"


def _canonical_api_routes() -> list[dict]:
    routes = route_registry_service.get_canonical_routes().get("api_routes", [])
    if not isinstance(routes, list):
        return []
    return [row for row in routes if isinstance(row, dict) and isinstance(row.get("path"), str)]


def _template_regex(template: str) -> str:
    escaped = re.escape(template)
    return "^" + re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", escaped) + "$"


def _method_allowed(route: dict, method: str | None) -> bool:
    if not method:
        return True
    methods = route.get("methods")
    if not isinstance(methods, list) or not methods:
        return True
    normalized = method.strip().upper()
    return normalized in {
        m.strip().upper() for m in methods if isinstance(m, str) and m.strip()
    }


def _match_canonical_route(endpoint: str, method: str | None = None) -> dict | None:
    path = _normalize_path(endpoint)
    routes = _canonical_api_routes()

    for row in routes:
        template = str(row.get("path") or "").strip()
        if template == path and _method_allowed(row, method):
            return row

    for row in routes:
        template = str(row.get("path") or "").strip()
        if "{" not in template or "}" not in template:
            continue
        if not _method_allowed(row, method):
            continue
        if re.match(_template_regex(template), path):
            return row

    return None


def normalize_endpoint(endpoint: str, method: str | None = None) -> str:
    path = _normalize_path(endpoint)
    canonical = _match_canonical_route(path, method=method)
    if isinstance(canonical, dict):
        canonical_path = str(canonical.get("path") or "").strip()
        if canonical_path:
            return canonical_path
    return path


def resolve_origin_idea_id(idea_id: str | None) -> str:
    return idea_lineage_service.resolve_origin_idea_id(idea_id)


def resolve_idea_id(
    endpoint: str,
    explicit_idea_id: str | None = None,
    method: str | None = None,
) -> str:
    if explicit_idea_id:
        return explicit_idea_id

    canonical = _match_canonical_route(endpoint, method=method)
    if isinstance(canonical, dict):
        canonical_idea_id = str(canonical.get("idea_id") or "").strip()
        if canonical_idea_id:
            return canonical_idea_id

    normalized_endpoint = normalize_endpoint(endpoint, method=method)
    map_data = _load_idea_map()
    prefix_map = map_data.get("prefix_map") if isinstance(map_data.get("prefix_map"), dict) else {}
    for prefix, idea_id in prefix_map.items():
        if isinstance(prefix, str) and isinstance(idea_id, str) and normalized_endpoint.startswith(prefix):
            return idea_id

    # Derive idea from lineage endpoint references where possible.
    marker = "/api/value-lineage/links/"
    if marker in endpoint:
        tail = endpoint.split(marker, 1)[1]
        lineage_id = tail.split("/", 1)[0]
        link = value_lineage_service.get_link(lineage_id)
        if link:
            return link.idea_id

    if normalized_endpoint.startswith("/api"):
        return "oss-interface-alignment"
    if normalized_endpoint.startswith("/v1"):
        return "portfolio-governance"
    if normalized_endpoint.startswith("/"):
        return "oss-interface-alignment"

    return "unmapped"


def record_event(payload: RuntimeEventCreate) -> RuntimeEvent:
    normalized_endpoint = normalize_endpoint(payload.endpoint, payload.method)
    raw_endpoint = _normalize_path(payload.raw_endpoint or payload.endpoint)
    idea_id = resolve_idea_id(endpoint=payload.endpoint, explicit_idea_id=payload.idea_id, method=payload.method)
    origin_idea_id = resolve_origin_idea_id(idea_id)
    runtime_cost = estimate_runtime_cost(float(payload.runtime_ms))
    metadata = dict(payload.metadata)
    if raw_endpoint != normalized_endpoint:
        metadata.setdefault("normalized_from", raw_endpoint)
    event = RuntimeEvent(
        id=f"rt_{uuid4().hex[:12]}",
        source=payload.source,
        endpoint=normalized_endpoint,
        raw_endpoint=raw_endpoint,
        method=payload.method.upper(),
        status_code=payload.status_code,
        runtime_ms=round(float(payload.runtime_ms), 4),
        idea_id=idea_id,
        origin_idea_id=origin_idea_id,
        metadata=metadata,
        runtime_cost_estimate=runtime_cost,
    )
    if runtime_event_store.enabled():
        runtime_event_store.write_event(event)
    else:
        with _RUNTIME_EVENTS_FILE_LOCK:
            data = _read_store()
            data["events"].append(event.model_dump(mode="json"))
            _write_store(data)
    _invalidate_runtime_events_cache()
    return event


def list_events(
    limit: int = 100,
    since: datetime | None = None,
    source: str | None = None,
) -> list[RuntimeEvent]:
    requested_limit = max(1, min(int(limit), 5000))
    source_value = str(source or "").strip().lower()
    cache_key = _runtime_events_cache_key(requested_limit, since, source_value or None)
    now = time.time()
    if (
        _RUNTIME_EVENTS_CACHE.get("expires_at", 0.0) > now
        and _RUNTIME_EVENTS_CACHE.get("cache_key") == cache_key
        and isinstance(_RUNTIME_EVENTS_CACHE.get("rows"), list)
    ):
        return [row.model_copy(deep=True) for row in _RUNTIME_EVENTS_CACHE["rows"][:requested_limit]]

    if runtime_event_store.enabled():
        rows = runtime_event_store.list_events(
            limit=max(1, min(requested_limit, 5000)),
            since=since,
            source=source_value or None,
        )
        out: list[RuntimeEvent] = []
        for event in rows:
            try:
                if not event.raw_endpoint:
                    event.raw_endpoint = event.endpoint
                if source_value and str(event.source).strip().lower() != source_value:
                    continue
                event.endpoint = normalize_endpoint(event.endpoint, event.method)
                if not event.origin_idea_id:
                    event.origin_idea_id = resolve_origin_idea_id(event.idea_id)
                out.append(event)
            except Exception:
                continue
        out.sort(key=lambda x: x.recorded_at, reverse=True)
        out = out[:requested_limit]
        _RUNTIME_EVENTS_CACHE["expires_at"] = now + _RUNTIME_EVENTS_CACHE_TTL_SECONDS
        _RUNTIME_EVENTS_CACHE["cache_key"] = cache_key
        _RUNTIME_EVENTS_CACHE["rows"] = out
        return out

    data = _read_store()
    out: list[RuntimeEvent] = []
    for raw in data["events"]:
        try:
            event = RuntimeEvent(**raw)
            if not event.raw_endpoint:
                event.raw_endpoint = event.endpoint
            if source_value and str(event.source).strip().lower() != source_value:
                continue
            event.endpoint = normalize_endpoint(event.endpoint, event.method)
            if not event.origin_idea_id:
                event.origin_idea_id = resolve_origin_idea_id(event.idea_id)
            out.append(event)
        except Exception:
            continue
    out.sort(key=lambda x: x.recorded_at, reverse=True)
    out = out[:requested_limit]
    _RUNTIME_EVENTS_CACHE["expires_at"] = now + _RUNTIME_EVENTS_CACHE_TTL_SECONDS
    _RUNTIME_EVENTS_CACHE["cache_key"] = cache_key
    _RUNTIME_EVENTS_CACHE["rows"] = out
    return out


def cached_runtime_events(
    *,
    limit: int = 100,
    source: str | None = None,
    force_refresh: bool = False,
) -> list[RuntimeEvent]:
    requested_limit = max(1, min(int(limit), 5000))
    source_value = str(source or "").strip().lower() or None
    params = {
        "limit": requested_limit,
        "source": source_value or "",
    }
    payload = _runtime_endpoint_cached_value(
        "runtime_events_list",
        fresh_ttl_seconds=45.0,
        refresh_producer=lambda: [
            row.model_dump(mode="json")
            for row in list_events(limit=requested_limit, source=source_value)
        ],
        params=params,
        force_refresh=force_refresh,
    )
    rows = _coerce_runtime_event_rows(payload, limit=requested_limit)
    if rows:
        return rows
    return list_events(limit=requested_limit, source=source_value)


def live_change_token(force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    if (
        not force_refresh
        and isinstance(_LIVE_CHANGE_CACHE.get("payload"), dict)
        and float(_LIVE_CHANGE_CACHE.get("expires_at") or 0.0) > now
    ):
        return dict(_LIVE_CHANGE_CACHE["payload"])

    runtime_checkpoint: dict[str, Any]
    try:
        if runtime_event_store.enabled():
            runtime_checkpoint = runtime_event_store.checkpoint(
                exclude_endpoints=["/api/runtime/change-token"],
            )
        else:
            runtime_checkpoint = {
                "enabled": False,
                "count": None,
                "max_recorded_at": None,
                "file": _path_signature(_events_path()),
            }
    except Exception as exc:
        runtime_checkpoint = {"error": str(exc), "enabled": runtime_event_store.enabled()}

    task_checkpoint: dict[str, Any]
    try:
        if agent_task_store_service.enabled():
            task_checkpoint = agent_task_store_service.checkpoint()
        else:
            task_checkpoint = {
                "enabled": False,
                "count": None,
                "max_updated_at": None,
                "file": _path_signature(_agent_tasks_path()),
            }
    except Exception as exc:
        task_checkpoint = {"error": str(exc), "enabled": agent_task_store_service.enabled()}

    try:
        telemetry_checkpoint = telemetry_persistence_service.checkpoint()
    except Exception as exc:
        telemetry_checkpoint = {"error": str(exc)}

    file_checkpoints = {
        "monitor_issues": _path_signature(_monitor_issues_path()),
        "status_report": _path_signature(_status_report_path()),
    }

    components: dict[str, Any] = {
        "runtime": runtime_checkpoint,
        "tasks": task_checkpoint,
        "telemetry": telemetry_checkpoint,
        "files": file_checkpoints,
    }
    token_basis = json.dumps(components, sort_keys=True, default=str)
    token = hashlib.sha256(token_basis.encode("utf-8")).hexdigest()[:24]
    payload = {
        "token": token,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
    _LIVE_CHANGE_CACHE["expires_at"] = now + _LIVE_CHANGE_CACHE_TTL_SECONDS
    _LIVE_CHANGE_CACHE["payload"] = payload
    return dict(payload)


def summarize_by_idea(
    seconds: int = 3600,
    event_limit: int = 2000,
    summary_limit: int = 500,
    summary_offset: int = 0,
    event_rows: list[RuntimeEvent] | None = None,
) -> list[IdeaRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    if event_rows is None:
        rows = list_events(limit=max(1, min(int(event_limit), 5000)), since=cutoff)
    else:
        rows = [row for row in event_rows if row.recorded_at >= cutoff]

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
    safe_offset = max(0, int(summary_offset))
    safe_limit = max(1, min(int(summary_limit), 2000))
    return summaries[safe_offset:safe_offset + safe_limit]


def _metadata_float(metadata: dict[str, Any], key: str, fallback: float = 0.0) -> float:
    try:
        return float(metadata.get(key))
    except Exception:
        return fallback


def _mvp_policy_value(*keys: str, default: Any) -> Any:
    node: Any = _load_mvp_acceptance_policy()
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return default if node is None else node


def _policy_non_negative_float(*keys: str, default: float) -> float:
    raw = _mvp_policy_value(*keys, default=default)
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(0.0, parsed)


def _policy_non_negative_int(*keys: str, default: int) -> int:
    raw = _mvp_policy_value(*keys, default=default)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(0, parsed)


def _policy_ratio(*keys: str, default: float) -> float:
    return min(1.0, max(0.0, _policy_non_negative_float(*keys, default=default)))


def _policy_bool(*keys: str, default: bool) -> bool:
    raw = _mvp_policy_value(*keys, default=default)
    if isinstance(raw, bool):
        return raw
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _policy_list_of_dicts(*keys: str) -> list[dict[str, Any]]:
    raw = _mvp_policy_value(*keys, default=[])
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            out.append(row)
    return out


def _allocation_ratios() -> dict[str, float]:
    infra = _policy_non_negative_float("reinvestment", "allocations", "infrastructure", default=0.5)
    code_quality = _policy_non_negative_float("reinvestment", "allocations", "code_quality", default=0.3)
    product_delivery = _policy_non_negative_float("reinvestment", "allocations", "product_delivery", default=0.2)
    total = infra + code_quality + product_delivery
    if total <= 0:
        return {"infrastructure": 0.5, "code_quality": 0.3, "product_delivery": 0.2}
    return {
        "infrastructure": round(infra / total, 6),
        "code_quality": round(code_quality / total, 6),
        "product_delivery": round(product_delivery / total, 6),
    }


def _budget_revenue_reinvestment_payload(totals: dict[str, Any]) -> dict[str, Any]:
    hosted_budget = _policy_non_negative_float("budget", "hosted_base_budget_usd", default=0.0)
    provider_budget = _policy_non_negative_float("budget", "provider_base_budget_usd", default=0.0)
    base_budget = round(hosted_budget + provider_budget, 6)

    revenue_per_accepted = _policy_non_negative_float("revenue", "per_accepted_review_usd", default=0.0)
    accepted_reviews = int(totals.get("accepted_reviews") or 0)
    estimated_revenue = round(float(accepted_reviews) * revenue_per_accepted, 6)

    total_cost = float(totals.get("total_cost_usd") or 0.0)
    operating_surplus = round(estimated_revenue - total_cost, 6)
    reinvestment_ratio = _policy_ratio("reinvestment", "ratio", default=0.4)
    reinvestment_pool = round(max(0.0, operating_surplus) * reinvestment_ratio, 6)
    ratios = _allocation_ratios()

    return {
        "budget": {
            "hosted_base_budget_usd": round(hosted_budget, 6),
            "provider_base_budget_usd": round(provider_budget, 6),
            "base_budget_usd": base_budget,
        },
        "revenue": {
            "revenue_per_accepted_review_usd": round(revenue_per_accepted, 6),
            "estimated_revenue_usd": estimated_revenue,
            "operating_surplus_usd": operating_surplus,
        },
        "reinvestment": {
            "reinvestment_ratio": round(reinvestment_ratio, 6),
            "reinvestment_pool_usd": reinvestment_pool,
            "allocations": {
                "infrastructure_usd": round(reinvestment_pool * ratios["infrastructure"], 6),
                "code_quality_usd": round(reinvestment_pool * ratios["code_quality"], 6),
                "product_delivery_usd": round(reinvestment_pool * ratios["product_delivery"], 6),
            },
        },
    }


def _trust_multiplier_component(kind: str, default: float) -> float:
    return max(1.0, _policy_non_negative_float("trust", "revenue_multipliers", kind, default=default))


def _trust_adjusted_revenue_proof(
    *,
    estimated_revenue_usd: float,
    total_cost_usd: float,
    public_validator: dict[str, Any],
    transparency_anchor: dict[str, Any],
) -> dict[str, Any]:
    validator_pass = bool(public_validator.get("pass"))
    anchor_pass = bool(transparency_anchor.get("pass"))

    multiplier = 1.0
    if validator_pass:
        multiplier *= _trust_multiplier_component("validator", 1.15)
    if anchor_pass:
        multiplier *= _trust_multiplier_component("anchor", 1.10)
    multiplier_cap = _trust_multiplier_component("cap", 2.0)
    multiplier = min(multiplier, multiplier_cap)

    baseline_revenue = max(0.0, float(estimated_revenue_usd))
    trust_adjusted_revenue = round(max(0.0, baseline_revenue * multiplier), 6)
    uplift = round(max(0.0, trust_adjusted_revenue - baseline_revenue), 6)
    trust_adjusted_surplus = round(trust_adjusted_revenue - max(0.0, float(total_cost_usd)), 6)

    require_trust_for_payout = _policy_bool("trust", "require_trust_for_payout", default=True)
    trust_ready = (
        (not bool(public_validator.get("required")) or validator_pass)
        and (not bool(transparency_anchor.get("required")) or anchor_pass)
    )
    payout_ready = (trust_adjusted_revenue >= max(0.0, float(total_cost_usd))) and (
        trust_ready if require_trust_for_payout else True
    )

    return {
        "trust": {
            "public_validator_pass": validator_pass,
            "public_transparency_anchor_pass": anchor_pass,
        },
        "revenue": {
            "estimated_revenue_usd": round(baseline_revenue, 6),
            "trust_adjusted_revenue_usd": trust_adjusted_revenue,
            "trust_revenue_uplift_usd": uplift,
            "trust_multiplier": round(multiplier, 6),
            "trust_adjusted_operating_surplus_usd": trust_adjusted_surplus,
        },
        "payout_ready": bool(payout_ready),
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_hex_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _public_validator_keys() -> list[dict[str, Any]]:
    rows = _policy_list_of_dicts("trust", "public_validator", "keys")
    out: list[dict[str, Any]] = []
    for row in rows:
        validator_id = str(row.get("id") or "").strip()
        public_key_b64 = str(row.get("public_key_base64") or "").strip()
        if not validator_id or not public_key_b64:
            continue
        out.append(
            {
                "id": validator_id,
                "public_key_base64": public_key_b64,
                "source": str(row.get("source") or "").strip(),
                "label": str(row.get("label") or "").strip(),
            }
        )
    return out


def _public_validator_attestations() -> list[dict[str, Any]]:
    rows = _policy_list_of_dicts("trust", "public_validator", "attestations")
    out: list[dict[str, Any]] = []
    for row in rows:
        validator_id = str(row.get("id") or row.get("validator_id") or "").strip()
        signature_b64 = str(row.get("signature_base64") or "").strip()
        if not validator_id or not signature_b64:
            continue
        out.append(
            {
                "id": validator_id,
                "signature_base64": signature_b64,
            }
        )
    return out


def _public_validator_report(
    *,
    claim_payload: dict[str, Any],
) -> dict[str, Any]:
    keys = _public_validator_keys()
    attestations = _public_validator_attestations()
    configured_count = len(keys)
    required = _policy_bool("trust", "public_validator", "required", default=False)
    default_quorum = 1 if required and configured_count > 0 else 0
    required_quorum = _policy_non_negative_int("trust", "public_validator", "quorum", default=default_quorum)
    if required and required_quorum <= 0:
        required_quorum = 1

    key_by_id = {str(row["id"]): row for row in keys}
    claim_bytes = _canonical_json_bytes(claim_payload)
    claim_sha256 = _sha256_hex_bytes(claim_bytes)
    verified_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    for att in attestations:
        validator_id = str(att.get("id") or "").strip()
        key_row = key_by_id.get(validator_id)
        if not key_row:
            rows.append(
                {
                    "id": validator_id,
                    "verified": False,
                    "reason": "unknown_validator_id",
                }
            )
            continue
        public_key_b64 = str(key_row.get("public_key_base64") or "").strip()
        signature_b64 = str(att.get("signature_base64") or "").strip()
        try:
            verify_key = VerifyKey(base64.b64decode(public_key_b64))
            verify_key.verify(claim_bytes, base64.b64decode(signature_b64))
            verified = True
            reason = ""
            verified_ids.add(validator_id)
        except (ValueError, BadSignatureError, TypeError):
            verified = False
            reason = "invalid_signature"
        rows.append(
            {
                "id": validator_id,
                "source": str(key_row.get("source") or ""),
                "label": str(key_row.get("label") or ""),
                "verified": verified,
                "reason": reason,
            }
        )

    verified_count = len(verified_ids)
    quorum_pass = verified_count >= required_quorum if required_quorum > 0 else True
    return {
        "required": required,
        "required_quorum": required_quorum,
        "configured_validators": configured_count,
        "attestations_submitted": len(attestations),
        "valid_signatures": verified_count,
        "pass": quorum_pass,
        "claim_sha256": claim_sha256,
        "validators": rows,
    }


def _trusted_transparency_domains() -> list[str]:
    raw = _mvp_policy_value("trust", "public_transparency_anchor", "trusted_domains", default=["rekor.sigstore.dev"])
    if isinstance(raw, str):
        source = [segment.strip().lower() for segment in raw.split(",")]
    elif isinstance(raw, list):
        source = [str(segment or "").strip().lower() for segment in raw]
    else:
        source = []
    out: list[str] = []
    seen: set[str] = set()
    for domain in source:
        if not domain or domain in seen:
            continue
        seen.add(domain)
        out.append(domain)
    return out or ["rekor.sigstore.dev"]


def _public_transparency_anchors() -> list[dict[str, Any]]:
    rows = _policy_list_of_dicts("trust", "public_transparency_anchor", "anchors")
    out: list[dict[str, Any]] = []
    for row in rows:
        url = str(row.get("url") or row.get("entry_url") or "").strip()
        if not url:
            continue
        out.append(
            {
                "id": str(row.get("id") or "").strip(),
                "url": url,
                "claim_sha256": str(row.get("claim_sha256") or "").strip().lower(),
                "source": str(row.get("source") or "").strip(),
            }
        )
    return out


def _transparency_entry_text(url: str) -> str:
    timeout_seconds = max(
        0.5,
        min(
            _policy_non_negative_float("trust", "public_transparency_anchor", "fetch_timeout_seconds", default=5.0),
            20.0,
        ),
    )
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text or ""


def _transparency_anchor_report(*, claim_sha256: str) -> dict[str, Any]:
    required = _policy_bool("trust", "public_transparency_anchor", "required", default=False)
    anchors = _public_transparency_anchors()
    trusted_domains = _trusted_transparency_domains()
    default_min = 1 if required else 0
    min_valid = _policy_non_negative_int("trust", "public_transparency_anchor", "min_anchors", default=default_min)
    if required and min_valid <= 0:
        min_valid = 1

    claim_hash = str(claim_sha256 or "").strip().lower()
    valid_count = 0
    rows: list[dict[str, Any]] = []

    for anchor in anchors:
        url = str(anchor.get("url") or "").strip()
        parsed = urlparse(url)
        domain = str(parsed.netloc or "").strip().lower()
        domain_trusted = domain in set(trusted_domains)
        anchor_hash = str(anchor.get("claim_sha256") or "").strip().lower()
        hash_match = bool(anchor_hash) and anchor_hash == claim_hash
        content_match = False
        reason = ""
        if not domain_trusted:
            reason = "untrusted_domain"
        elif not hash_match:
            reason = "claim_hash_mismatch"
        else:
            try:
                body = _transparency_entry_text(url)
                content_match = claim_hash in body.lower()
                if not content_match:
                    reason = "claim_hash_not_found_in_entry"
            except Exception:
                reason = "entry_fetch_failed"

        verified = domain_trusted and hash_match and content_match
        if verified:
            valid_count += 1
        rows.append(
            {
                "id": str(anchor.get("id") or ""),
                "url": url,
                "source": str(anchor.get("source") or ""),
                "domain": domain,
                "domain_trusted": domain_trusted,
                "hash_match": hash_match,
                "content_match": content_match,
                "verified": verified,
                "reason": reason,
            }
        )

    report_pass = valid_count >= min_valid if min_valid > 0 else True
    return {
        "required": required,
        "required_min_anchors": min_valid,
        "trusted_domains": trusted_domains,
        "anchors_submitted": len(anchors),
        "valid_anchors": valid_count,
        "pass": report_pass,
        "claim_sha256": claim_hash,
        "anchors": rows,
    }


def summarize_mvp_acceptance(
    *,
    seconds: int = 86400,
    event_limit: int = 2000,
) -> dict[str, Any]:
    window_seconds = max(60, min(int(seconds), 60 * 60 * 24 * 30))
    requested_limit = max(100, min(int(event_limit), 5000))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = list_events(limit=requested_limit, since=cutoff)

    task_rows: dict[str, dict[str, Any]] = {}

    for event in rows:
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        tracking_kind = str(metadata.get("tracking_kind") or "").strip()
        task_id = str(metadata.get("task_id") or "").strip()
        if not task_id:
            continue
        task_row = task_rows.setdefault(
            task_id,
            {
                "task_id": task_id,
                "task_type": "",
                "final_status": "",
                "review_pass_fail": "",
                "verified_assertions": "",
                "review_accepted": False,
                "infrastructure_cost_usd": 0.0,
                "external_provider_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            },
        )

        if tracking_kind == "agent_task_completion":
            task_row["task_type"] = str(metadata.get("task_type") or task_row["task_type"] or "").strip()
            task_row["final_status"] = str(metadata.get("task_final_status") or task_row["final_status"] or "").strip()
            pass_fail = str(metadata.get("review_pass_fail") or "").strip().upper()
            if pass_fail in {"PASS", "FAIL"}:
                task_row["review_pass_fail"] = pass_fail
                task_row["review_accepted"] = pass_fail == "PASS"
            verified = str(metadata.get("verified_assertions") or "").strip()
            if verified:
                task_row["verified_assertions"] = verified
            continue

        if tracking_kind != "agent_tool_call":
            continue

        infra = _metadata_float(metadata, "infrastructure_cost_usd", fallback=float(event.runtime_cost_estimate or 0.0))
        external = _metadata_float(metadata, "external_provider_cost_usd", fallback=0.0)
        total = _metadata_float(metadata, "total_cost_usd", fallback=infra + external)

        task_row["infrastructure_cost_usd"] = round(float(task_row["infrastructure_cost_usd"]) + max(0.0, infra), 6)
        task_row["external_provider_cost_usd"] = round(float(task_row["external_provider_cost_usd"]) + max(0.0, external), 6)
        task_row["total_cost_usd"] = round(float(task_row["total_cost_usd"]) + max(0.0, total), 6)

    task_values = list(task_rows.values())
    task_values.sort(key=lambda row: (float(row.get("total_cost_usd") or 0.0), str(row.get("task_id") or "")), reverse=True)

    completed_tasks = [row for row in task_values if str(row.get("final_status") or "").strip() == "completed"]
    completed_reviews = [
        row
        for row in completed_tasks
        if str(row.get("task_type") or "").strip().lower() == "review"
    ]
    accepted_reviews = [row for row in completed_reviews if bool(row.get("review_accepted"))]

    infra_total = round(sum(float(row.get("infrastructure_cost_usd") or 0.0) for row in task_values), 6)
    external_total = round(sum(float(row.get("external_provider_cost_usd") or 0.0) for row in task_values), 6)
    total_cost = round(sum(float(row.get("total_cost_usd") or 0.0) for row in task_values), 6)
    acceptance_rate = (
        round(float(len(accepted_reviews)) / float(len(completed_reviews)), 6)
        if completed_reviews
        else 0.0
    )
    totals = {
        "tasks_seen": len(task_values),
        "completed_tasks": len(completed_tasks),
        "review_tasks_completed": len(completed_reviews),
        "accepted_reviews": len(accepted_reviews),
        "acceptance_rate": acceptance_rate,
        "infrastructure_cost_usd": infra_total,
        "external_provider_cost_usd": external_total,
        "total_cost_usd": total_cost,
    }
    economics = _budget_revenue_reinvestment_payload(totals)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_seconds": window_seconds,
        "event_limit": requested_limit,
        "totals": totals,
        "tasks": task_values,
        "budget": economics["budget"],
        "revenue": economics["revenue"],
        "reinvestment": economics["reinvestment"],
    }


def evaluate_mvp_acceptance_judge(
    *,
    seconds: int = 86400,
    event_limit: int = 2000,
) -> dict[str, Any]:
    summary = summarize_mvp_acceptance(seconds=seconds, event_limit=event_limit)
    totals = summary.get("totals") if isinstance(summary.get("totals"), dict) else {}
    budget = summary.get("budget") if isinstance(summary.get("budget"), dict) else {}
    revenue = summary.get("revenue") if isinstance(summary.get("revenue"), dict) else {}
    claim_payload = {
        "judge_id": "coherence_mvp_acceptance_judge_v1",
        "window_seconds": int(summary.get("window_seconds") or 0),
        "event_limit": int(summary.get("event_limit") or 0),
        "totals": {
            "accepted_reviews": int(totals.get("accepted_reviews") or 0),
            "acceptance_rate": float(totals.get("acceptance_rate") or 0.0),
            "total_cost_usd": float(totals.get("total_cost_usd") or 0.0),
        },
        "budget": {"base_budget_usd": float(budget.get("base_budget_usd") or 0.0)},
        "revenue": {"estimated_revenue_usd": float(revenue.get("estimated_revenue_usd") or 0.0)},
    }
    public_validator = _public_validator_report(claim_payload=claim_payload)
    transparency_anchor = _transparency_anchor_report(claim_sha256=str(public_validator.get("claim_sha256") or ""))

    min_accepted_reviews = _policy_non_negative_int("acceptance", "min_accepted_reviews", default=1)
    min_acceptance_rate = _policy_ratio("acceptance", "min_acceptance_rate", default=0.7)
    require_budget_coverage = _policy_bool("acceptance", "require_budget_coverage", default=True)
    require_revenue_coverage = _policy_bool("acceptance", "require_revenue_coverage", default=True)
    require_trust_adjusted_revenue_coverage = _policy_bool(
        "trust",
        "require_trust_adjusted_revenue_coverage",
        default=False,
    )
    require_payout_readiness = _policy_bool("trust", "require_payout_readiness", default=False)

    accepted_reviews = int(totals.get("accepted_reviews") or 0)
    acceptance_rate = float(totals.get("acceptance_rate") or 0.0)
    total_cost_usd = float(totals.get("total_cost_usd") or 0.0)
    base_budget_usd = float(budget.get("base_budget_usd") or 0.0)
    estimated_revenue_usd = float(revenue.get("estimated_revenue_usd") or 0.0)
    business_proof = _trust_adjusted_revenue_proof(
        estimated_revenue_usd=estimated_revenue_usd,
        total_cost_usd=total_cost_usd,
        public_validator=public_validator,
        transparency_anchor=transparency_anchor,
    )
    trust_revenue = (
        business_proof.get("revenue")
        if isinstance(business_proof.get("revenue"), dict)
        else {}
    )
    trust_adjusted_revenue_usd = float(trust_revenue.get("trust_adjusted_revenue_usd") or 0.0)

    assertions: list[dict[str, Any]] = [
        {
            "id": "accepted_reviews_minimum",
            "expected": f">= {min_accepted_reviews}",
            "actual": str(accepted_reviews),
            "pass": accepted_reviews >= min_accepted_reviews,
        },
        {
            "id": "acceptance_rate_minimum",
            "expected": f">= {round(min_acceptance_rate, 6)}",
            "actual": str(round(acceptance_rate, 6)),
            "pass": acceptance_rate >= min_acceptance_rate,
        },
    ]

    if require_budget_coverage and base_budget_usd > 0.0:
        assertions.append(
            {
                "id": "base_budget_covers_total_cost",
                "expected": f"total_cost_usd <= {round(base_budget_usd, 6)}",
                "actual": str(round(total_cost_usd, 6)),
                "pass": total_cost_usd <= base_budget_usd,
            }
        )

    if require_revenue_coverage:
        assertions.append(
            {
                "id": "estimated_revenue_covers_total_cost",
                "expected": f"estimated_revenue_usd >= {round(total_cost_usd, 6)}",
                "actual": str(round(estimated_revenue_usd, 6)),
                "pass": estimated_revenue_usd >= total_cost_usd,
            }
        )
    if require_trust_adjusted_revenue_coverage:
        assertions.append(
            {
                "id": "trust_adjusted_revenue_covers_total_cost",
                "expected": f"trust_adjusted_revenue_usd >= {round(total_cost_usd, 6)}",
                "actual": str(round(trust_adjusted_revenue_usd, 6)),
                "pass": trust_adjusted_revenue_usd >= total_cost_usd,
            }
        )
    if require_payout_readiness:
        assertions.append(
            {
                "id": "payout_readiness",
                "expected": "payout_ready == true",
                "actual": str(bool(business_proof.get("payout_ready"))).lower(),
                "pass": bool(business_proof.get("payout_ready")),
            }
        )
    if bool(public_validator.get("required")):
        assertions.append(
            {
                "id": "public_validator_quorum",
                "expected": f"valid_signatures >= {int(public_validator.get('required_quorum') or 0)}",
                "actual": str(int(public_validator.get("valid_signatures") or 0)),
                "pass": bool(public_validator.get("pass")),
            }
        )
    if bool(transparency_anchor.get("required")):
        assertions.append(
            {
                "id": "public_transparency_anchor",
                "expected": f"valid_anchors >= {int(transparency_anchor.get('required_min_anchors') or 0)}",
                "actual": str(int(transparency_anchor.get("valid_anchors") or 0)),
                "pass": bool(transparency_anchor.get("pass")),
            }
        )

    overall_pass = all(bool(item.get("pass")) for item in assertions)
    return {
        "pass": overall_pass,
        "assertions": assertions,
        "summary": summary,
        "contract": {
            "judge_id": "coherence_mvp_acceptance_judge_v1",
            "external_validation_endpoint": "/api/runtime/mvp/acceptance-judge",
            "claim_payload": claim_payload,
            "claim_sha256": str(public_validator.get("claim_sha256") or ""),
            "public_validator": public_validator,
            "public_transparency_anchor": transparency_anchor,
            "business_proof": business_proof,
            "measurement": {
                "acceptance_rate_formula": "accepted_reviews / review_tasks_completed",
                "total_cost_formula": "sum(task.total_cost_usd)",
                "base_budget_formula": "hosted_base_budget_usd + provider_base_budget_usd",
                "estimated_revenue_formula": "accepted_reviews * revenue_per_accepted_review_usd",
                "trust_adjusted_revenue_formula": "estimated_revenue_usd * trust_multiplier",
                "trust_revenue_uplift_formula": "trust_adjusted_revenue_usd - estimated_revenue_usd",
                "reinvestment_pool_formula": "max(0, estimated_revenue_usd - total_cost_usd) * reinvestment_ratio",
                "public_validator_formula": "valid_signatures >= required_quorum",
                "public_transparency_anchor_formula": "valid_anchors >= required_min_anchors",
                "payout_readiness_formula": "trust_adjusted_revenue_usd >= total_cost_usd and required trust gates pass",
            },
            "implementation_evidence": {
                "summary_endpoint": "/api/runtime/mvp/acceptance-summary",
                "required_summary_fields": [
                    "totals.accepted_reviews",
                    "totals.acceptance_rate",
                    "totals.total_cost_usd",
                    "budget.base_budget_usd",
                    "revenue.estimated_revenue_usd",
                    "reinvestment.reinvestment_pool_usd",
                ],
                "public_validator_inputs": [
                    "mvp_acceptance_policy.trust.public_validator.keys",
                    "mvp_acceptance_policy.trust.public_validator.attestations",
                    "mvp_acceptance_policy.trust.public_validator.quorum",
                    "mvp_acceptance_policy.trust.public_validator.required",
                ],
                "public_transparency_inputs": [
                    "mvp_acceptance_policy.trust.public_transparency_anchor.anchors",
                    "mvp_acceptance_policy.trust.public_transparency_anchor.trusted_domains",
                    "mvp_acceptance_policy.trust.public_transparency_anchor.min_anchors",
                    "mvp_acceptance_policy.trust.public_transparency_anchor.required",
                ],
                "trust_revenue_inputs": [
                    "mvp_acceptance_policy.trust.revenue_multipliers.validator",
                    "mvp_acceptance_policy.trust.revenue_multipliers.anchor",
                    "mvp_acceptance_policy.trust.revenue_multipliers.cap",
                    "mvp_acceptance_policy.trust.require_trust_adjusted_revenue_coverage",
                    "mvp_acceptance_policy.trust.require_trust_for_payout",
                    "mvp_acceptance_policy.trust.require_payout_readiness",
                ],
            },
        },
    }


def cached_runtime_ideas_summary_payload(
    *,
    seconds: int = 3600,
    limit: int = 200,
    offset: int = 0,
    event_limit: int | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    window_seconds = max(60, min(int(seconds), 60 * 60 * 24 * 30))
    requested_limit = max(1, min(int(limit), 2000))
    requested_offset = max(0, int(offset))
    scan_limit = (
        max(1, min(int(event_limit), 5000))
        if event_limit is not None
        else max(300, min(1500, requested_limit * 20))
    )
    params = {
        "seconds": window_seconds,
        "limit": requested_limit,
        "offset": requested_offset,
        "event_limit": scan_limit,
    }
    return _runtime_endpoint_cached_value(
        "runtime_ideas_summary",
        fresh_ttl_seconds=90.0,
        refresh_producer=lambda: {
            "window_seconds": window_seconds,
            "offset": requested_offset,
            "limit": requested_limit,
            "ideas": [
                row.model_dump(mode="json")
                for row in summarize_by_idea(
                    seconds=window_seconds,
                    event_limit=scan_limit,
                    summary_limit=requested_limit,
                    summary_offset=requested_offset,
                )
            ],
        },
        params=params,
        force_refresh=force_refresh,
    )


def summarize_by_endpoint(seconds: int = 3600, summary_limit: int = 500) -> list[EndpointRuntimeSummary]:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = list_events(limit=2000, since=cutoff)

    grouped: dict[str, list[RuntimeEvent]] = {}
    for event in rows:
        grouped.setdefault(event.endpoint, []).append(event)

    summaries: list[EndpointRuntimeSummary] = []
    for endpoint, events in grouped.items():
        methods = sorted({e.method.upper() for e in events})
        by_source: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        idea_counts: dict[str, int] = {}
        paid_tool_event_count = 0
        paid_tool_failure_count = 0
        paid_tool_runtime_ms = 0.0
        paid_tool_runtime_cost = 0.0

        for event in events:
            by_source[event.source] = by_source.get(event.source, 0) + 1
            status_key = str(event.status_code)
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            idea_key = str(event.idea_id or "unmapped")
            idea_counts[idea_key] = idea_counts.get(idea_key, 0) + 1

            metadata = event.metadata if isinstance(event.metadata, dict) else {}
            if bool(metadata.get("is_paid_provider")):
                paid_tool_event_count += 1
                paid_tool_runtime_ms += float(event.runtime_ms or 0.0)
                raw_runtime_cost = metadata.get("runtime_cost_usd")
                if raw_runtime_cost is not None:
                    try:
                        paid_tool_runtime_cost += float(raw_runtime_cost)
                    except (TypeError, ValueError):
                        paid_tool_runtime_cost += float(event.runtime_cost_estimate)
                else:
                    paid_tool_runtime_cost += float(event.runtime_cost_estimate)
                if event.status_code >= 400:
                    paid_tool_failure_count += 1

        primary_idea_id = max(idea_counts.items(), key=lambda item: item[1])[0]
        total_runtime = round(sum(e.runtime_ms for e in events), 4)
        total_cost = round(sum(e.runtime_cost_estimate for e in events), 8)
        paid_tool_ratio = float(paid_tool_event_count) / float(len(events)) if events else 0.0
        paid_tool_average_runtime_ms = (
            round((paid_tool_runtime_ms / paid_tool_event_count), 4) if paid_tool_event_count else 0.0
        )
        summaries.append(
            EndpointRuntimeSummary(
                endpoint=endpoint,
                methods=methods,
                idea_id=primary_idea_id,
                origin_idea_id=resolve_origin_idea_id(primary_idea_id),
                event_count=len(events),
                total_runtime_ms=total_runtime,
                average_runtime_ms=round(total_runtime / len(events), 4),
                runtime_cost_estimate=total_cost,
                paid_tool_event_count=paid_tool_event_count,
                paid_tool_failure_count=paid_tool_failure_count,
                paid_tool_ratio=round(paid_tool_ratio, 4),
                paid_tool_runtime_cost=round(paid_tool_runtime_cost, 8),
                paid_tool_average_runtime_ms=paid_tool_average_runtime_ms,
                by_source=by_source,
                status_counts=status_counts,
            )
        )
    summaries.sort(key=lambda x: (x.runtime_cost_estimate, x.endpoint), reverse=True)
    return summaries[: max(1, min(int(summary_limit), 2000))]


def summarize_web_view_performance(
    *,
    seconds: int = 21600,
    limit: int = 100,
    route_prefix: str | None = None,
    event_limit: int = 5000,
) -> WebViewPerformanceReport:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    requested_limit = max(1, min(int(limit), 500))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = list_events(limit=max(1, min(int(event_limit), 5000)), since=cutoff)
    return runtime_web_view_service.summarize_web_view_performance_from_rows(
        rows=rows,
        window_seconds=window_seconds,
        requested_limit=requested_limit,
        route_prefix=(route_prefix or "").strip() or None,
    )


def cached_web_view_performance_payload(
    *,
    seconds: int = 21600,
    limit: int = 100,
    route_prefix: str | None = None,
    event_limit: int | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    window_seconds = max(60, min(int(seconds), 60 * 60 * 24 * 30))
    requested_limit = max(1, min(int(limit), 500))
    normalized_route_prefix = (route_prefix or "").strip() or None
    scan_limit = (
        max(1, min(int(event_limit), 5000))
        if event_limit is not None
        else max(300, min(1500, requested_limit * 30))
    )
    params = {
        "seconds": window_seconds,
        "limit": requested_limit,
        "route_prefix": normalized_route_prefix or "",
        "event_limit": scan_limit,
    }

    def _refresh() -> dict[str, Any]:
        report = summarize_web_view_performance(
            seconds=window_seconds,
            limit=requested_limit,
            route_prefix=normalized_route_prefix,
            event_limit=scan_limit,
        )
        return report.model_dump(mode="json")

    def _fallback() -> dict[str, Any]:
        return WebViewPerformanceReport(
            window_seconds=window_seconds,
            route_prefix=normalized_route_prefix,
            total_routes=0,
            rows=[],
        ).model_dump(mode="json")

    return _runtime_endpoint_cached_value(
        "runtime_web_view_summary",
        fresh_ttl_seconds=120.0,
        refresh_producer=_refresh,
        fallback_producer=_fallback,
        params=params,
        force_refresh=force_refresh,
    )


def _parse_status_code(value: str) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _tool_success_streak_target() -> int:
    return max(1, min(get_int("runtime", "tool_success_streak_target", 3), 20))


def _is_success_status_code(status_code: int) -> bool:
    return 200 <= int(status_code) < 400


def _recent_success_streak(endpoint_events: list[RuntimeEvent]) -> int:
    if not endpoint_events:
        return 0
    ordered_events = sorted(endpoint_events, key=lambda event: event.recorded_at, reverse=True)
    streak = 0
    for event in ordered_events:
        if _is_success_status_code(int(getattr(event, "status_code", 0) or 0)):
            streak += 1
            continue
        break
    return streak


def _load_idea_value_rows() -> dict[str, dict[str, float]]:
    try:
        from app.services import idea_service
    except Exception:
        return {}

    rows: dict[str, dict[str, float]] = {}
    try:
        ideas = idea_service.list_ideas()
    except Exception:
        return rows

    for idea in ideas.ideas:
        rows[str(idea.id)] = {
            "potential_value": float(idea.potential_value or 0.0),
            "actual_value": float(idea.actual_value or 0.0),
            "estimated_cost": float(idea.estimated_cost or 0.0),
            "actual_cost": float(idea.actual_cost or 0.0),
            "confidence": float(idea.confidence or 0.0),
        }
    return rows


def _endpoint_friction_counts(seconds: int) -> dict[str, int]:
    from app.services import friction_service

    try:
        events, _ignored = friction_service.load_events()
    except Exception:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, min(seconds, 60 * 60 * 24 * 30)))
    counts: dict[str, int] = {}
    for event in events:
        if event.timestamp < cutoff:
            continue
        endpoint = str(getattr(event, "endpoint", "") or "").strip()
        if not endpoint:
            continue
        counts[endpoint] = counts.get(endpoint, 0) + 1
    return counts


def _attention_reasons(
    *,
    success_rate: float,
    paid_ratio: float,
    friction_density: float,
    value_gap: float,
    cost_per_event: float,
    event_count: int,
    recent_success_streak: int,
    success_streak_target: int,
    failure_recovered: bool,
) -> list[str]:
    reasons: list[str] = []
    if event_count < 5:
        reasons.append("low_sample")
    if success_rate < 0.90:
        reasons.append(f"low_success_rate:{round(success_rate * 100.0, 2)}%")
    if recent_success_streak > 0:
        streak_label = "recovered_success_streak" if failure_recovered else "success_streak"
        reasons.append(f"{streak_label}:{recent_success_streak}/{success_streak_target}")
    if paid_ratio > 0.0:
        reasons.append(f"paid_requests:{round(paid_ratio * 100.0, 2)}%")
    if friction_density > 0.0:
        reasons.append(f"friction_density:{round(friction_density * 100.0, 2)}%")
    if value_gap > 1.0:
        reasons.append(f"value_gap:{round(value_gap, 4)}")
    if cost_per_event > 0.002:
        reasons.append(f"cost_per_event:{round(cost_per_event, 6)}")
    return reasons


def _endpoint_attention_score(
    *,
    event_count: int,
    success_rate: float,
    paid_ratio: float,
    friction_density: float,
    value_gap: float,
    cost_per_event: float,
    attention_threshold: float,
) -> tuple[float, bool]:
    """Compute attention score and whether attention_threshold is exceeded."""
    failure_score = (1.0 - success_rate) * 100.0
    paid_score = min(paid_ratio * 60.0, 30.0)
    cost_score = min(cost_per_event * 1000.0, 25.0)
    friction_score = min(friction_density * 300.0, 20.0)
    value_gap_score = min(value_gap / 5.0, 25.0)
    sample_score = min(event_count / 20.0, 1.0) * 10.0

    attention_score = (
        failure_score * min(event_count / 5.0, 1.0)
        + paid_score
        + cost_score
        + friction_score
        + value_gap_score
        + sample_score
    )
    return attention_score, attention_score >= attention_threshold


def _endpoint_attention_status_counts(
    row: EndpointRuntimeSummary,
) -> tuple[int, int]:
    success_count = 0
    failure_count = 0
    for code_str, count in row.status_counts.items():
        code = _parse_status_code(code_str)
        if _is_success_status_code(code):
            success_count += _safe_int(count, 0)
        else:
            failure_count += _safe_int(count, 0)
    return success_count, failure_count


def _endpoint_attention_paid_counts(
    endpoint_events: list[RuntimeEvent],
) -> tuple[int, int]:
    paid_tool_event_count = 0
    paid_tool_failure_count = 0
    for event in endpoint_events:
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        if bool(metadata.get("is_paid_provider")):
            paid_tool_event_count += 1
            if event.status_code >= 400:
                paid_tool_failure_count += 1
    return paid_tool_event_count, paid_tool_failure_count


def _build_endpoint_attention_row(
    row: EndpointRuntimeSummary,
    *,
    min_event_count: int,
    attention_threshold: float,
    endpoint_events: list[RuntimeEvent],
    friction_count: int,
    idea_rows: dict[str, dict[str, float]],
) -> EndpointAttentionRow | None:
    event_count = int(row.event_count)
    if event_count < max(1, int(min_event_count)):
        return None

    success_count, failure_count = _endpoint_attention_status_counts(row)

    success_rate = float(success_count) / float(event_count) if event_count else 0.0
    success_streak_target = _tool_success_streak_target()
    recent_success_streak = _recent_success_streak(endpoint_events)
    failure_recovered = bool(failure_count > 0 and recent_success_streak >= success_streak_target)

    paid_tool_event_count, paid_tool_failure_count = _endpoint_attention_paid_counts(endpoint_events)

    paid_ratio = float(paid_tool_event_count) / float(event_count) if event_count else 0.0
    friction_density_raw = (float(friction_count) / float(event_count)) if event_count else 0.0
    friction_density = min(max(friction_density_raw, 0.0), 1.0)

    idea_data = idea_rows.get(row.idea_id) or idea_rows.get(row.origin_idea_id, {})
    potential_value = _safe_float(idea_data.get("potential_value", 0.0))
    actual_value = _safe_float(idea_data.get("actual_value", 0.0))
    estimated_cost = _safe_float(idea_data.get("estimated_cost", 0.0))
    actual_cost = _safe_float(idea_data.get("actual_cost", 0.0))
    idea_confidence = _safe_float(idea_data.get("confidence", 0.0), default=0.0)

    value_gap = max(potential_value - actual_value, 0.0)
    cost_per_event = float(row.runtime_cost_estimate) / float(max(event_count, 1))

    confidence = min(event_count / 20.0, 1.0) * 0.75 + 0.25 * idea_confidence
    attention_score, needs_attention = _endpoint_attention_score(
        event_count=event_count,
        success_rate=success_rate,
        paid_ratio=paid_ratio,
        friction_density=friction_density,
        value_gap=value_gap,
        cost_per_event=cost_per_event,
        attention_threshold=attention_threshold,
    )

    return EndpointAttentionRow(
        endpoint=row.endpoint,
        methods=row.methods,
        idea_id=row.idea_id,
        origin_idea_id=row.origin_idea_id,
        event_count=event_count,
        success_count=success_count,
        failure_count=failure_count,
        success_rate=round(success_rate, 4),
        runtime_cost_estimate=round(float(row.runtime_cost_estimate), 8),
        cost_per_event=round(cost_per_event, 8),
        paid_tool_event_count=paid_tool_event_count,
        paid_tool_failure_count=paid_tool_failure_count,
        paid_tool_ratio=round(paid_ratio, 4),
        friction_event_count=friction_count,
        friction_event_density=round(friction_density, 4),
        potential_value=round(potential_value, 4),
        actual_value=round(actual_value, 4),
        estimated_cost=round(estimated_cost, 4),
        actual_cost=round(actual_cost, 4),
        value_gap=round(value_gap, 4),
        attention_score=round(attention_score, 3),
        confidence=round(max(0.0, min(confidence, 1.0)), 4),
        recent_success_streak=recent_success_streak,
        success_streak_target=success_streak_target,
        failure_recovered=failure_recovered,
        needs_attention=needs_attention,
        reasons=_attention_reasons(
            success_rate=success_rate,
            paid_ratio=paid_ratio,
            friction_density=friction_density,
            value_gap=value_gap,
            cost_per_event=cost_per_event,
            event_count=event_count,
            recent_success_streak=recent_success_streak,
            success_streak_target=success_streak_target,
            failure_recovered=failure_recovered,
        ),
    )


def summarize_endpoint_attention(
    *,
    seconds: int = 3600,
    min_event_count: int = 1,
    attention_threshold: float = 40.0,
    limit: int | None = None,
) -> EndpointAttentionReport:
    window_seconds = max(60, min(seconds, 60 * 60 * 24 * 30))
    endpoint_rows = summarize_by_endpoint(seconds=window_seconds)
    friction_by_endpoint = _endpoint_friction_counts(window_seconds)
    idea_rows = _load_idea_value_rows()

    window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    attention_events = list_events(limit=2000, since=window_start)
    by_endpoint: dict[str, list[RuntimeEvent]] = {}
    for event in attention_events:
        by_endpoint.setdefault(event.endpoint, []).append(event)

    rows: list[EndpointAttentionRow] = []
    for row in endpoint_rows:
        built = _build_endpoint_attention_row(
            row,
            min_event_count=min_event_count,
            attention_threshold=attention_threshold,
            endpoint_events=by_endpoint.get(row.endpoint, []),
            friction_count=int(friction_by_endpoint.get(row.endpoint, 0)),
            idea_rows=idea_rows,
        )
        if built is None:
            continue
        rows.append(built)

    rows.sort(key=lambda row: row.attention_score, reverse=True)
    if limit is not None:
        rows = rows[: max(1, min(int(limit), len(rows), 2000))]

    attention_count = sum(1 for row in rows if row.needs_attention)
    return EndpointAttentionReport(
        window_seconds=window_seconds,
        attention_threshold=round(float(attention_threshold), 3),
        min_event_count=max(1, int(min_event_count)),
        total_endpoints=len(rows),
        attention_count=attention_count,
        endpoints=rows,
    )


def verify_internal_vs_public_usage(
    *,
    public_api_base: str,
    runtime_window_seconds: int = 86400,
    timeout_seconds: float = 8.0,
) -> dict[str, object]:
    window_seconds = max(60, min(runtime_window_seconds, 60 * 60 * 24 * 30))
    internal = summarize_by_endpoint(seconds=window_seconds)
    internal_by_endpoint = {row.endpoint: row for row in internal}

    public_url = f"{public_api_base.rstrip('/')}/api/runtime/endpoints/summary"
    public_rows: list[dict] = []
    error = ""
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(public_url, params={"seconds": window_seconds})
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("endpoints"), list):
            public_rows = [row for row in payload["endpoints"] if isinstance(row, dict)]
        else:
            error = "public_payload_invalid"
    except Exception as exc:
        error = str(exc)

    public_by_endpoint: dict[str, dict] = {}
    for row in public_rows:
        endpoint = str(row.get("endpoint") or "").strip()
        if endpoint:
            public_by_endpoint[endpoint] = row

    internal_only = sorted(set(internal_by_endpoint.keys()) - set(public_by_endpoint.keys()))
    public_only = sorted(set(public_by_endpoint.keys()) - set(internal_by_endpoint.keys()))
    overlap = sorted(set(internal_by_endpoint.keys()) & set(public_by_endpoint.keys()))

    missing_public_records = [
        endpoint for endpoint in overlap if int(public_by_endpoint[endpoint].get("event_count") or 0) <= 0
    ]
    pass_contract = not error and len(missing_public_records) == 0

    return {
        "runtime_window_seconds": window_seconds,
        "public_api_base": public_api_base.rstrip("/"),
        "pass_contract": pass_contract,
        "error": error,
        "internal_endpoint_count": len(internal_by_endpoint),
        "public_endpoint_count": len(public_by_endpoint),
        "overlap_count": len(overlap),
        "internal_only_endpoints": internal_only,
        "public_only_endpoints": public_only,
        "missing_public_records": missing_public_records,
    }


async def run_get_endpoint_exerciser(
    *,
    app,
    base_url: str,
    cycles: int = 1,
    max_endpoints: int = 250,
    delay_ms: int = 0,
    timeout_seconds: float = 8.0,
    runtime_window_seconds: int = 86400,
) -> dict:
    return await runtime_exerciser_service.run_get_endpoint_exerciser(
        app=app,
        base_url=base_url,
        cycles=cycles,
        max_endpoints=max_endpoints,
        delay_ms=delay_ms,
        timeout_seconds=timeout_seconds,
        runtime_window_seconds=runtime_window_seconds,
    )
