"""Endpoint and events cache for runtime telemetry."""

from __future__ import annotations

import json
import re
import hashlib
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from app.config_loader import get_int
from app.services import runtime_event_store, telemetry_persistence_service

from app.services.runtime import paths as runtime_paths

logger = logging.getLogger(__name__)

RUNTIME_EVENTS_CACHE_TTL_SECONDS = 30.0
RUNTIME_ENDPOINT_CACHE_NAMESPACE = "runtime_endpoint_cache_v1"
RUNTIME_ENDPOINT_CACHE_DEFAULT_TTL_SECONDS = 120.0
RUNTIME_ENDPOINT_CACHE_MAX_STALE_SECONDS = 7 * 24 * 60 * 60
RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK = threading.Lock()
RUNTIME_ENDPOINT_CACHE_REFRESH_POOL = ThreadPoolExecutor(
    max_workers=max(2, min(get_int("runtime", "endpoint_cache_max_workers", default=4), 8)),
    thread_name_prefix="runtime-endpoint-cache-refresh",
)
RUNTIME_ENDPOINT_CACHE_BUSTER = 0


def runtime_events_store_cache_key() -> str:
    if runtime_event_store.enabled():
        url = (
            os.getenv("RUNTIME_DATABASE_URL", "").strip()
            or os.getenv("DATABASE_URL", "").strip()
            or "<runtime-database>"
        )
        return f"db:{url}"
    return f"file:{runtime_paths.events_path()}"


def runtime_events_cache_key(limit: int, since: datetime | None, source: str | None) -> str:
    cutoff = "all"
    if since is not None:
        since_ts = int(since.timestamp())
        cutoff = str(since_ts // max(1, int(RUNTIME_EVENTS_CACHE_TTL_SECONDS)))
    source_value = str(source or "").strip().lower() or "all"
    return f"store={runtime_events_store_cache_key()}|limit={limit}|cutoff={cutoff}|source={source_value}"


def runtime_endpoint_cache_ttl_seconds(
    cache_name: str, default: float = RUNTIME_ENDPOINT_CACHE_DEFAULT_TTL_SECONDS
) -> float:
    env_suffix = re.sub(r"[^A-Za-z0-9]+", "_", cache_name).strip("_").upper()
    env_key = f"RUNTIME_ENDPOINT_CACHE_TTL_{env_suffix}"
    raw = str(os.getenv(env_key) or "").strip()
    if not raw:
        return max(1.0, min(float(default), 86400.0))
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return max(1.0, min(float(default), 86400.0))
    return max(1.0, min(float(parsed), 86400.0))


def runtime_endpoint_cache_meta_key(endpoint: str, params: dict[str, Any] | None = None) -> str:
    scope_parts = [
        str(os.getenv("RUNTIME_EVENTS_PATH") or ""),
        str(os.getenv("RUNTIME_DATABASE_URL") or ""),
        str(os.getenv("DATABASE_URL") or ""),
        str(os.getenv("PYTEST_CURRENT_TEST") or ""),
        str(runtime_events_store_cache_key()),
        str(RUNTIME_ENDPOINT_CACHE_BUSTER),
    ]
    scope_digest = hashlib.sha1("||".join(scope_parts).encode("utf-8")).hexdigest()[:12]
    canonical = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha1(f"{endpoint}|{canonical}".encode("utf-8")).hexdigest()
    return f"{RUNTIME_ENDPOINT_CACHE_NAMESPACE}::{scope_digest}::{endpoint}::{digest}"


def parse_runtime_cache_timestamp(raw: Any) -> datetime | None:
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


def runtime_endpoint_cache_read(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[Any | None, float | None]:
    key = runtime_endpoint_cache_meta_key(endpoint, params)
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
    stored_at = parse_runtime_cache_timestamp(envelope.get("stored_at"))
    if stored_at is None:
        return payload, None
    age_seconds = max(0.0, (datetime.now(timezone.utc) - stored_at).total_seconds())
    if age_seconds > float(RUNTIME_ENDPOINT_CACHE_MAX_STALE_SECONDS):
        return None, None
    return payload, age_seconds


def runtime_endpoint_cache_write(
    endpoint: str, payload: Any, params: dict[str, Any] | None = None
) -> None:
    key = runtime_endpoint_cache_meta_key(endpoint, params)
    envelope = {
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    telemetry_persistence_service.set_meta_value(
        key,
        json.dumps(envelope, separators=(",", ":"), default=str),
    )


_RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES: dict[str, Future[Any]] = {}


def runtime_endpoint_cache_schedule_refresh(
    endpoint: str,
    *,
    producer: Callable[[], Any],
    params: dict[str, Any] | None = None,
) -> bool:
    key = runtime_endpoint_cache_meta_key(endpoint, params)
    with RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK:
        active = _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.get(key)
        if active is not None and not active.done():
            return False

        def _run_refresh() -> Any:
            payload = producer()
            runtime_endpoint_cache_write(endpoint, payload, params=params)
            return payload

        future = RUNTIME_ENDPOINT_CACHE_REFRESH_POOL.submit(_run_refresh)
        _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES[key] = future

        def _cleanup(done_future: Future[Any]) -> None:
            with RUNTIME_ENDPOINT_CACHE_REFRESH_LOCK:
                current = _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.get(key)
                if current is done_future:
                    _RUNTIME_ENDPOINT_CACHE_REFRESH_FUTURES.pop(key, None)
            try:
                done_future.result()
            except Exception:
                logger.exception("runtime endpoint cache refresh failed", extra={"endpoint": endpoint})

        future.add_done_callback(_cleanup)
        return True


def runtime_endpoint_cached_value(
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
        runtime_endpoint_cache_write(endpoint, payload, params=params)
        return payload

    ttl = runtime_endpoint_cache_ttl_seconds(endpoint, default=fresh_ttl_seconds)
    cached_payload, cached_age = runtime_endpoint_cache_read(endpoint, params=params)
    if cached_payload is not None and cached_age is not None and cached_age <= ttl:
        return cached_payload
    if cached_payload is not None:
        runtime_endpoint_cache_schedule_refresh(
            endpoint,
            producer=refresh_producer,
            params=params,
        )
        return cached_payload
    try:
        payload = refresh_producer()
        runtime_endpoint_cache_write(endpoint, payload, params=params)
        return payload
    except Exception:
        if fallback_producer is not None:
            fallback_payload = fallback_producer()
            runtime_endpoint_cache_write(endpoint, fallback_payload, params=params)
            return fallback_payload
        raise
