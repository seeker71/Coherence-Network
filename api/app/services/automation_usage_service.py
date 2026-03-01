"""Provider usage adapters, normalized snapshots, and alert evaluation."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.models.automation_usage import (
    ProviderValidationReport,
    ProviderValidationRow,
    ProviderReadinessReport,
    ProviderReadinessRow,
    ProviderUsageOverview,
    ProviderUsageSnapshot,
    SubscriptionPlanEstimate,
    SubscriptionUpgradeEstimatorReport,
    UsageAlert,
    UsageAlertReport,
    UsageMetric,
)
from app.services import (
    agent_runner_registry_service,
    agent_service,
    quality_awareness_service,
    telemetry_persistence_service,
)

_CACHE: dict[str, Any] = {"expires_at": 0.0, "overview": None}
_CACHE_TTL_SECONDS = 120.0
_DB_HOST_EGRESS_SAMPLE_CACHE: dict[str, Any] = {
    "url": "",
    "sample": None,
    "error": "",
    "expires_at": 0.0,
}
_DB_HOST_EGRESS_SAMPLE_CACHE_TTL_SECONDS = 60.0
_DB_HOST_EGRESS_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None}
_RUNTIME_EVENTS_WINDOW_CACHE: dict[tuple[int, str | None, int], dict[str, Any]] = {}
_CODEX_PROVIDER_USAGE_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}
_CODEX_PROVIDER_USAGE_CACHE_TTL_SECONDS = 90.0
_RUNNER_PROVIDER_TELEMETRY_CACHE: dict[str, Any] = {"expires_at": 0.0, "rows": []}
_RUNNER_PROVIDER_TELEMETRY_CACHE_TTL_SECONDS = 20.0
_CURSOR_CLI_CONTEXT_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": {}}
_CLAUDE_CLI_CONTEXT_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": {}}

_PROVIDER_CONFIG_RULES: dict[str, dict[str, Any]] = {
    "coherence-internal": {"kind": "internal", "all_of": []},
    "openai-codex": {"kind": "custom", "any_of": ["OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"]},
    "claude": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]},
    "claude-code": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]},
    "openai": {"kind": "openai", "any_of": ["OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"]},
    "github": {"kind": "github", "any_of": ["GITHUB_TOKEN", "GH_TOKEN"]},
    "openrouter": {"kind": "custom", "all_of": ["OPENROUTER_API_KEY"]},
    "anthropic": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]},
    "cursor": {"kind": "custom", "any_of": ["CURSOR_API_KEY", "CURSOR_CLI_MODEL"]},
    "openclaw": {"kind": "custom", "all_of": ["OPENCLAW_API_KEY"]},
    "railway": {"kind": "custom", "all_of": ["RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE"]},
    "supabase": {"kind": "custom", "any_of": ["SUPABASE_ACCESS_TOKEN", "SUPABASE_TOKEN"]},
    "db-host": {"kind": "custom", "any_of": ["RUNTIME_DATABASE_URL", "DATABASE_URL"]},
}

_DEFAULT_REQUIRED_PROVIDERS = (
    "openai",
    "claude",
    "cursor",
)
_DEFAULT_PROVIDER_VALIDATION_REQUIRED = (
    "coherence-internal",
    "openai-codex",
    "openrouter",
    "github",
    "railway",
    "claude",
    "claude-code",
)

_PROVIDER_ALIASES: dict[str, str] = {
    "clawwork": "openclaw",
    "codex": "openai",
    "openai-codex": "openai",
}

_PROVIDER_FAMILY_ALIASES: dict[str, str] = {
    "codex": "openai",
    "openai-codex": "openai",
    "claude-code": "claude",
}

_READINESS_REQUIRED_PROVIDER_ALLOWLIST = frozenset({"openai", "claude", "cursor"})

_CURSOR_SUBSCRIPTION_LIMITS_BY_TIER: dict[str, tuple[int, int]] = {
    "free": (10, 70),
    "pro": (50, 500),
    "pro_plus": (100, 1000),
}

_CLAUDE_SUBSCRIPTION_LIMITS_BY_TIER: dict[str, tuple[int, int]] = {
    "free": (10, 70),
    "pro": (45, 315),
    "max": (120, 840),
    "team": (120, 840),
}

_PROVIDER_WINDOW_GUARD_DEFAULT_RATIO_BY_WINDOW: dict[str, float] = {
    "hourly": 0.1,
    "weekly": 0.1,
    "monthly": 0.1,
}

_USAGE_ALERT_MESSAGE_MAX_LEN = 480


def _normalize_provider_name(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return ""
    return _PROVIDER_ALIASES.get(candidate, candidate)


def _provider_family_name(value: str | None) -> str:
    normalized = _normalize_provider_name(value)
    if not normalized:
        return ""
    return _PROVIDER_FAMILY_ALIASES.get(normalized, normalized)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _snapshots_path() -> Path:
    configured = os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "automation_usage_snapshots.json"


def _use_db_snapshots() -> bool:
    override = str(os.getenv("AUTOMATION_USAGE_USE_DB", "")).strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    if os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH"):
        return False
    return True


def _ensure_store() -> None:
    if _use_db_snapshots():
        telemetry_persistence_service.ensure_schema()
        legacy_path = _snapshots_path()
        report = telemetry_persistence_service.import_automation_snapshots_from_file(legacy_path)
        if int(report.get("imported") or 0) > 0:
            purge_raw = str(os.getenv("TRACKING_PURGE_IMPORTED_FILES", "1")).strip().lower()
            if purge_raw not in {"0", "false", "no", "off"}:
                try:
                    legacy_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return
    path = _snapshots_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshots": []}, indent=2), encoding="utf-8")


def _read_store() -> list[dict[str, Any]]:
    if _use_db_snapshots():
        _ensure_store()
        return telemetry_persistence_service.list_automation_snapshots(limit=5000)
    _ensure_store()
    try:
        payload = json.loads(_snapshots_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = payload.get("snapshots") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _write_store(rows: list[dict[str, Any]]) -> None:
    if _use_db_snapshots():
        telemetry_persistence_service.ensure_schema()
        max_rows = max(10, min(int(os.getenv("AUTOMATION_USAGE_MAX_SNAPSHOTS", "800")), 5000))
        # Rewrite in insertion order using append behavior.
        for row in rows[-max_rows:]:
            if isinstance(row, dict):
                telemetry_persistence_service.append_automation_snapshot(row, max_rows=max_rows)
        return
    path = _snapshots_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshots": rows}, indent=2), encoding="utf-8")


def _store_snapshot(snapshot: ProviderUsageSnapshot) -> None:
    if _use_db_snapshots():
        max_rows = max(10, min(int(os.getenv("AUTOMATION_USAGE_MAX_SNAPSHOTS", "800")), 5000))
        telemetry_persistence_service.append_automation_snapshot(
            snapshot.model_dump(mode="json"),
            max_rows=max_rows,
        )
        return
    rows = _read_store()
    rows.append(snapshot.model_dump(mode="json"))
    max_rows = max(10, min(int(os.getenv("AUTOMATION_USAGE_MAX_SNAPSHOTS", "800")), 5000))
    if len(rows) > max_rows:
        rows = rows[-max_rows:]
    _write_store(rows)


def _metric(
    *,
    id: str,
    label: str,
    unit: str,
    used: float,
    remaining: float | None = None,
    limit: float | None = None,
    window: str | None = None,
    validation_state: str | None = None,
    validation_detail: str | None = None,
    evidence_source: str | None = None,
) -> UsageMetric:
    return UsageMetric(
        id=id,
        label=label,
        unit=unit,  # type: ignore[arg-type]
        used=max(0.0, float(used)),
        remaining=(None if remaining is None else max(0.0, float(remaining))),
        limit=(None if limit is None else max(0.0, float(limit))),
        window=window,
        validation_state=(str(validation_state).strip().lower() if validation_state else None),
        validation_detail=(str(validation_detail).strip()[:400] if validation_detail else None),
        evidence_source=(str(evidence_source).strip()[:200] if evidence_source else None),
    )


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ratio_threshold(value: Any, *, default: float) -> float:
    parsed = _coerce_float(value)
    if parsed is None:
        return default
    return max(0.0, min(float(parsed), 1.0))


def _truncate_text(value: Any, *, max_len: int) -> str:
    raw = str(value or "").strip()
    if len(raw) <= max_len:
        return raw
    if max_len <= 3:
        return raw[:max_len]
    return f"{raw[: max_len - 3]}..."


def _runtime_events_cache_ttl_seconds() -> float:
    parsed = _coerce_float(os.getenv("AUTOMATION_RUNTIME_EVENTS_CACHE_SECONDS"))
    if parsed is None:
        return 20.0
    return max(0.0, min(float(parsed), 300.0))


def _runtime_event_scan_limit(default: int = 1500) -> int:
    parsed = _coerce_float(os.getenv("AUTOMATION_RUNTIME_EVENT_SCAN_LIMIT"))
    if parsed is None:
        return max(100, min(int(default), 5000))
    return max(100, min(int(parsed), 5000))


def _trim_usage_alert_message(message: str) -> str:
    return _truncate_text(message, max_len=_USAGE_ALERT_MESSAGE_MAX_LEN)


def _metric_window_bucket(window: str | None) -> str:
    raw = str(window or "").strip().lower()
    if not raw:
        return ""
    normalized = raw.replace(" ", "").replace("-", "_")
    direct_map = {
        "hourly": "hourly",
        "minute": "hourly",
        "minutely": "hourly",
        "weekly": "weekly",
        "1w": "weekly",
        "7d": "weekly",
        "rolling_7d": "weekly",
        "monthly": "monthly",
        "1m": "monthly",
        "30d": "monthly",
        "rolling_30d": "monthly",
    }
    if normalized in direct_map:
        return direct_map[normalized]
    if "month" in normalized or "30d" in normalized:
        return "monthly"
    if "week" in normalized or "7d" in normalized or normalized.endswith("1w"):
        return "weekly"
    if (
        "hour" in normalized
        or "minute" in normalized
        or normalized.endswith("h")
        or "day" in normalized
        or "24h" in normalized
    ):
        return "hourly"
    return ""


def _provider_window_guard_ratio_defaults() -> dict[str, float]:
    defaults = dict(_PROVIDER_WINDOW_GUARD_DEFAULT_RATIO_BY_WINDOW)
    env_map = {
        "hourly": "AUTOMATION_PROVIDER_MIN_REMAINING_RATIO_HOURLY",
        "weekly": "AUTOMATION_PROVIDER_MIN_REMAINING_RATIO_WEEKLY",
        "monthly": "AUTOMATION_PROVIDER_MIN_REMAINING_RATIO_MONTHLY",
    }
    for window, env_name in env_map.items():
        defaults[window] = _normalize_ratio_threshold(
            os.getenv(env_name),
            default=defaults[window],
        )
    return defaults


def _provider_window_guard_ratio_policy(defaults: dict[str, float]) -> dict[str, dict[str, float]]:
    policy: dict[str, dict[str, float]] = {"default": dict(defaults)}
    raw = str(os.getenv("AUTOMATION_PROVIDER_WINDOW_GUARD_POLICY_JSON", "")).strip()
    if not raw:
        return policy
    try:
        payload = json.loads(raw)
    except ValueError:
        return policy
    if not isinstance(payload, dict):
        return policy

    for provider_name, settings in payload.items():
        if not isinstance(settings, dict):
            continue
        provider_key = str(provider_name).strip().lower()
        normalized_provider = _normalize_provider_name(provider_key)
        if provider_key == "default":
            target_key = "default"
        elif normalized_provider:
            target_key = normalized_provider
        else:
            continue

        merged = dict(policy.get("default", defaults))
        if target_key in policy:
            merged.update(policy[target_key])
        for window_name, ratio_value in settings.items():
            bucket = _metric_window_bucket(str(window_name))
            if bucket not in defaults:
                continue
            merged[bucket] = _normalize_ratio_threshold(
                ratio_value,
                default=merged.get(bucket, defaults[bucket]),
            )
        policy[target_key] = merged
    return policy


def _header_float(headers: httpx.Headers, *keys: str) -> float | None:
    for key in keys:
        raw = str(headers.get(key, "")).strip()
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _append_rate_limit_metrics(
    *,
    metrics: list[UsageMetric],
    headers: httpx.Headers,
    request_limit_keys: tuple[str, ...],
    request_remaining_keys: tuple[str, ...],
    request_window: str,
    request_label: str,
    token_limit_keys: tuple[str, ...] = (),
    token_remaining_keys: tuple[str, ...] = (),
    token_window: str = "rolling",
    token_label: str = "Token quota",
) -> bool:
    found = False

    req_limit = _header_float(headers, *request_limit_keys)
    req_remaining = _header_float(headers, *request_remaining_keys)
    if req_limit is not None and req_limit > 0:
        req_used = max(0.0, req_limit - (req_remaining or 0.0))
        metrics.append(
            _metric(
                id="requests_quota",
                label=request_label,
                unit="requests",
                used=req_used,
                remaining=req_remaining,
                limit=req_limit,
                window=request_window,
                validation_state="validated",
                validation_detail="Directly measured from provider rate-limit response headers.",
                evidence_source="provider_rate_limit_headers",
            )
        )
        found = True

    tok_limit = _header_float(headers, *token_limit_keys) if token_limit_keys else None
    tok_remaining = _header_float(headers, *token_remaining_keys) if token_remaining_keys else None
    if tok_limit is not None and tok_limit > 0:
        tok_used = max(0.0, tok_limit - (tok_remaining or 0.0))
        metrics.append(
            _metric(
                id="tokens_quota",
                label=token_label,
                unit="tokens",
                used=tok_used,
                remaining=tok_remaining,
                limit=tok_limit,
                window=token_window,
                validation_state="validated",
                validation_detail="Directly measured from provider rate-limit response headers.",
                evidence_source="provider_rate_limit_headers",
            )
        )
        found = True

    return found


def _runtime_task_runs_snapshot(*, provider: str, kind: str, active_runs: int, note: str) -> ProviderUsageSnapshot:
    return ProviderUsageSnapshot(
        id=f"provider_{provider.replace('-', '_')}_{int(time.time())}",
        provider=provider,
        kind=kind,  # type: ignore[arg-type]
        status="ok",
        data_source="runtime_events",
        metrics=[
            _metric(
                id="runtime_task_runs",
                label="Runtime task runs",
                unit="tasks",
                used=float(active_runs),
                window="rolling",
                validation_state="derived",
                validation_detail="Derived from runtime telemetry events; not a provider-reported quota value.",
                evidence_source="runtime_events",
            )
        ],
        notes=[note],
        raw={"runtime_task_runs": active_runs},
    )


def _subset_headers(headers: httpx.Headers, keys: tuple[str, ...]) -> dict[str, str | None]:
    return {key: headers.get(key) for key in keys}


def _record_external_tool_usage(
    *,
    tool_name: str,
    provider: str,
    operation: str,
    resource: str,
    status: str,
    http_status: int | None = None,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    event_payload: dict[str, Any] = {
        "event_id": f"tool_{uuid.uuid4().hex}",
        "occurred_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tool_name": tool_name,
        "provider": provider,
        "operation": operation,
        "resource": resource,
        "status": status,
        "http_status": http_status,
        "duration_ms": duration_ms,
        "payload": payload or {},
    }
    try:
        telemetry_persistence_service.append_external_tool_usage_event(event_payload)
    except Exception:
        return


def _build_models_visibility_snapshot(
    *,
    provider: str,
    label: str,
    models_url: str,
    rows: list[Any],
    headers: httpx.Headers,
    request_limit_keys: tuple[str, ...],
    request_remaining_keys: tuple[str, ...],
    request_window: str,
    request_label: str,
    token_limit_keys: tuple[str, ...],
    token_remaining_keys: tuple[str, ...],
    token_window: str,
    token_label: str,
    rate_header_keys: tuple[str, ...],
    no_header_note: str,
) -> ProviderUsageSnapshot:
    metrics = [
        _metric(
            id="models_visible",
            label=label,
            unit="requests",
            used=float(len(rows)),
            window="probe",
        )
    ]
    has_limit_headers = _append_rate_limit_metrics(
        metrics=metrics,
        headers=headers,
        request_limit_keys=request_limit_keys,
        request_remaining_keys=request_remaining_keys,
        request_window=request_window,
        request_label=request_label,
        token_limit_keys=token_limit_keys,
        token_remaining_keys=token_remaining_keys,
        token_window=token_window,
        token_label=token_label,
    )
    notes: list[str] = []
    if not has_limit_headers:
        notes.append(no_header_note)

    return ProviderUsageSnapshot(
        id=f"provider_{provider.replace('-', '_')}_{int(time.time())}",
        provider=provider,
        kind="custom",
        status="ok",
        data_source="provider_api",
        metrics=metrics,
        notes=notes,
        raw={
            "models_count": len(rows),
            "probe_url": models_url,
            "rate_limit_headers": _subset_headers(headers, rate_header_keys),
        },
    )


def _build_openai_models_visibility_snapshot(
    *,
    models_url: str,
    rows: list[Any],
    headers: httpx.Headers,
) -> ProviderUsageSnapshot:
    return _build_models_visibility_snapshot(
        provider="openai-codex",
        label="OpenAI visible models",
        models_url=models_url,
        rows=rows,
        headers=headers,
        request_limit_keys=("x-ratelimit-limit-requests",),
        request_remaining_keys=("x-ratelimit-remaining-requests",),
        request_window="minute",
        request_label="OpenAI request quota",
        token_limit_keys=("x-ratelimit-limit-tokens",),
        token_remaining_keys=("x-ratelimit-remaining-tokens",),
        token_window="minute",
        token_label="OpenAI token quota",
        rate_header_keys=(
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-tokens",
        ),
        no_header_note="OpenAI models probe succeeded, but no request/token remaining headers were returned.",
    )


def _openai_quota_probe_headers(headers: dict[str, str]) -> tuple[httpx.Headers | None, str | None]:
    probe_url = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")
    model = os.getenv("OPENAI_QUOTA_PROBE_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    payload = {
        "model": model,
        "input": "quota probe",
        "max_output_tokens": 1,
    }
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            response = client.post(probe_url, json=payload)
            response.raise_for_status()
        return response.headers, None
    except Exception as exc:
        return None, str(exc)


def _claude_quota_probe_headers(headers: dict[str, str]) -> tuple[httpx.Headers | None, str | None]:
    probe_url = os.getenv("ANTHROPIC_MESSAGES_URL", "https://api.anthropic.com/v1/messages")
    # claude-haiku-4-5 is the cheapest current model for quota probes.
    # claude-3-5-haiku-latest is not valid as of the claude-4 generation.
    model = os.getenv("ANTHROPIC_QUOTA_PROBE_MODEL", "claude-haiku-4-5").strip() or "claude-haiku-4-5"
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "quota probe"}],
    }
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            response = client.post(probe_url, json=payload)
            response.raise_for_status()
        return response.headers, None
    except Exception as exc:
        return None, str(exc)


def _build_openrouter_snapshot() -> ProviderUsageSnapshot:
    token = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not token:
        return _build_config_only_snapshot("openrouter")

    auth_key_url = os.getenv("OPENROUTER_AUTH_KEY_URL", "https://openrouter.ai/api/v1/auth/key")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            response = client.get(auth_key_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        fallback = _build_config_only_snapshot("openrouter")
        fallback.notes.append(f"OpenRouter key usage probe failed: {exc}")
        fallback.notes = list(dict.fromkeys(fallback.notes))
        fallback.raw["probe_url"] = auth_key_url
        return fallback

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    usage = float(data.get("usage") or 0.0)
    limit = data.get("limit")
    try:
        limit_value = float(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit_value = None
    remaining = max(0.0, limit_value - usage) if limit_value is not None else None

    metrics = [
        _metric(
            id="api_probe",
            label="OpenRouter key probe",
            unit="requests",
            used=1.0,
            window="probe",
        )
    ]
    if limit_value is not None and limit_value > 0:
        metrics.append(
            _metric(
                id="credits_quota",
                label="OpenRouter credits quota",
                unit="usd",
                used=usage,
                remaining=remaining,
                limit=limit_value,
                window="rolling",
            )
        )
    notes: list[str] = []
    if limit_value is None:
        notes.append("OpenRouter auth/key probe succeeded, but no credit limit was returned.")

    return ProviderUsageSnapshot(
        id=f"provider_openrouter_{int(time.time())}",
        provider="openrouter",
        kind="custom",
        status="ok",
        data_source="provider_api",
        metrics=metrics,
        notes=notes,
        raw={
            "probe_url": auth_key_url,
            "key_label": data.get("label"),
            "usage": usage,
            "limit": limit,
            "is_free_tier": data.get("is_free_tier"),
        },
    )


def _apply_quota_probe_to_snapshot(
    *,
    snapshot: ProviderUsageSnapshot,
    probe_headers: httpx.Headers | None,
    probe_error: str | None,
    request_limit_keys: tuple[str, ...],
    request_remaining_keys: tuple[str, ...],
    request_label: str,
    token_limit_keys: tuple[str, ...],
    token_remaining_keys: tuple[str, ...],
    token_label: str,
    success_note: str,
    no_headers_note: str,
    error_note_prefix: str,
) -> ProviderUsageSnapshot:
    has_quota_metric = any(metric.id in {"requests_quota", "tokens_quota"} for metric in snapshot.metrics)
    if has_quota_metric:
        return snapshot

    if probe_headers is not None:
        appended = _append_rate_limit_metrics(
            metrics=snapshot.metrics,
            headers=probe_headers,
            request_limit_keys=request_limit_keys,
            request_remaining_keys=request_remaining_keys,
            request_window="minute",
            request_label=request_label,
            token_limit_keys=token_limit_keys,
            token_remaining_keys=token_remaining_keys,
            token_window="minute",
            token_label=token_label,
        )
        if appended:
            snapshot.notes.append(success_note)
            snapshot.notes = [
                note
                for note in snapshot.notes
                if "no request/token remaining headers were returned" not in note.lower()
            ]
        else:
            snapshot.notes.append(no_headers_note)
        return snapshot

    if probe_error:
        snapshot.notes.append(f"{error_note_prefix}: {probe_error}")
    return snapshot


def _railway_api_probe_snapshot(*, ok: bool, response_headers: httpx.Headers, gql_url: str) -> ProviderUsageSnapshot:
    metrics = [
        _metric(
            id="api_probe",
            label="Railway API probe",
            unit="requests",
            used=1.0 if ok else 0.0,
            window="probe",
        )
    ]
    has_limit_headers = _append_rate_limit_metrics(
        metrics=metrics,
        headers=response_headers,
        request_limit_keys=("x-ratelimit-limit", "ratelimit-limit"),
        request_remaining_keys=("x-ratelimit-remaining", "ratelimit-remaining"),
        request_window="hourly",
        request_label="Railway API request quota",
    )
    notes = [] if ok else ["Railway API probe returned unexpected payload."]
    if ok and not has_limit_headers:
        notes.append("Railway probe succeeded, but no request remaining headers were returned.")
    return ProviderUsageSnapshot(
        id=f"provider_railway_{int(time.time())}",
        provider="railway",
        kind="custom",
        status="ok" if ok else "degraded",
        data_source="provider_api",
        metrics=metrics,
        notes=notes,
        raw={
            "probe_url": gql_url,
            "rate_limit_headers": _subset_headers(
                response_headers,
                ("x-ratelimit-limit", "x-ratelimit-remaining", "ratelimit-limit", "ratelimit-remaining"),
            ),
        },
    )


def _default_official_records(provider: str) -> list[str]:
    links: dict[str, list[str]] = {
        "coherence-internal": [
            "/api/usage",
            "/api/automation/usage",
        ],
        "github": [
            "https://docs.github.com/en/rest/rate-limit/rate-limit",
            "https://docs.github.com/en/rest/billing/billing",
        ],
        "openai": [
            "https://platform.openai.com/docs/api-reference/usage",
            "https://platform.openai.com/docs/api-reference/costs",
            "https://platform.openai.com/docs/api-reference/models/list",
            "https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt",
            "https://openai.com/index/introducing-upgrades-to-codex/",
        ],
        "openai-codex": [
            "https://platform.openai.com/docs/api-reference/models/list",
            "https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt",
            "https://openai.com/index/introducing-upgrades-to-codex/",
        ],
        "claude": [
            "https://docs.anthropic.com/en/api/models-list",
        ],
        "claude-code": [
            "https://docs.anthropic.com/en/api/models-list",
        ],
        "railway": [
            "https://docs.railway.com/reference/public-api",
        ],
        "openrouter": [
            "https://openrouter.ai/docs/api-reference/overview",
        ],
        "supabase": [
            "https://supabase.com/docs/reference/api/introduction",
            "https://supabase.com/docs/reference/api/v1-analytics-endpoints-usage-api-counts",
            "https://supabase.com/docs/reference/api/v1-analytics-endpoints-usage-api-requests-count",
        ],
        "db-host": [
            "https://www.postgresql.org/docs/current/monitoring-stats.html",
            "https://docs.railway.com/reference/metrics",
        ],
    }
    return links.get(provider, [])


def _metric_time_rate(metric: UsageMetric) -> str | None:
    if metric.used <= 0:
        return None
    window = str(metric.window or "").strip().lower()
    denom: float | None = None
    period = ""
    if window == "hourly":
        denom, period = 1.0, "hour"
    elif window == "daily":
        denom, period = 1.0, "day"
    elif window in {"monthly", "rolling_30d"}:
        denom, period = 30.0, "day"
    if not denom or not period:
        return None
    rate = metric.used / denom
    return f"{round(rate, 4)} {metric.unit}/{period}"


def _primary_metric(metrics: list[UsageMetric]) -> UsageMetric | None:
    if not metrics:
        return None
    priority = {
        "runtime_task_runs": 0,
        "tasks_tracked": 1,
        "requests_total": 2,
        "tokens_total": 3,
        "rest_requests": 4,
        "actions_minutes": 5,
        "api_probe": 6,
        "models_visible": 7,
    }
    ordered = sorted(metrics, key=lambda item: priority.get(item.id, 20))
    return ordered[0] if ordered else metrics[0]


def _summary_metric(metrics: list[UsageMetric]) -> UsageMetric | None:
    if not metrics:
        return None
    limited = [metric for metric in metrics if metric.limit is not None and float(metric.limit or 0.0) > 0.0]
    if limited:
        priority = {
            "codex_provider_window_primary": 0,
            "codex_provider_window_secondary": 1,
            "codex_subscription_5h": 2,
            "db_host_egress_monthly_estimated": 3,
            "db_host_window_5h": 4,
            "cursor_subscription_8h": 5,
            "rest_requests": 6,
            "codex_subscription_week": 7,
            "db_host_window_week": 8,
            "cursor_subscription_week": 9,
        }
        validation_priority = {"validated": 0, "derived": 1, "inferred": 1, "unknown": 2}
        ordered = sorted(
            limited,
            key=lambda item: (
                validation_priority.get(str(item.validation_state or "unknown").strip().lower(), 2),
                priority.get(item.id, 20),
            ),
        )
        return ordered[0] if ordered else limited[0]
    return _primary_metric(metrics)


def _metric_quality_rank(metric: UsageMetric) -> tuple[int, int, int, int]:
    validation_priority = {"validated": 0, "derived": 1, "inferred": 1, "unknown": 2}
    validation_state = str(metric.validation_state or "unknown").strip().lower()
    has_remaining = 0 if metric.remaining is not None else 1
    has_limit = 0 if (metric.limit is not None and float(metric.limit or 0.0) > 0.0) else 1
    return (
        validation_priority.get(validation_state, 2),
        has_remaining,
        has_limit,
        -int(float(metric.used or 0.0) > 0.0),
    )


def _merge_metric_rows(base: list[UsageMetric], incoming: list[UsageMetric]) -> list[UsageMetric]:
    merged: dict[tuple[str, str, str], UsageMetric] = {}
    order: list[tuple[str, str, str]] = []
    for metric in [*base, *incoming]:
        key = (metric.id, metric.unit, str(metric.window or ""))
        existing = merged.get(key)
        if existing is None:
            merged[key] = metric
            order.append(key)
            continue
        if _metric_quality_rank(metric) < _metric_quality_rank(existing):
            merged[key] = metric
    return [merged[key] for key in order]


def _data_source_rank(source: str) -> int:
    priority = {
        "provider_api": 0,
        "provider_cli": 1,
        "runtime_events": 2,
        "configuration_only": 3,
        "unknown": 4,
    }
    return priority.get(str(source or "").strip().lower(), 4)


def _status_rank(status: str) -> int:
    priority = {"ok": 0, "degraded": 1, "unavailable": 2}
    return priority.get(str(status or "").strip().lower(), 2)


def _normalize_usage_row_status(snapshot: ProviderUsageSnapshot) -> ProviderUsageSnapshot:
    if snapshot.status != "degraded":
        return snapshot
    has_signal = any(
        (
            float(metric.used or 0.0) > 0.0
            or metric.remaining is not None
            or (metric.limit is not None and float(metric.limit or 0.0) > 0.0)
        )
        for metric in snapshot.metrics
    )
    if has_signal:
        snapshot.status = "ok"
        snapshot.notes = list(dict.fromkeys([*snapshot.notes, "status_normalized_from_degraded:usage_signal_present"]))
    else:
        snapshot.status = "unavailable"
        snapshot.notes = list(dict.fromkeys([*snapshot.notes, "status_normalized_from_degraded:no_usage_signal"]))
    return snapshot


def _merge_provider_snapshot_family(
    base: ProviderUsageSnapshot,
    incoming: ProviderUsageSnapshot,
    *,
    family: str,
) -> ProviderUsageSnapshot:
    base.provider = family
    base.metrics = _merge_metric_rows(base.metrics, incoming.metrics)
    base.notes = list(dict.fromkeys([*base.notes, *incoming.notes]))
    base.official_records = list(dict.fromkeys([*base.official_records, *incoming.official_records]))
    if _status_rank(incoming.status) < _status_rank(base.status):
        base.status = incoming.status
    if _data_source_rank(incoming.data_source) < _data_source_rank(base.data_source):
        base.data_source = incoming.data_source
    if incoming.cost_usd is not None:
        base.cost_usd = max(float(base.cost_usd or 0.0), float(incoming.cost_usd))
    if incoming.capacity_tasks_per_day is not None:
        base.capacity_tasks_per_day = max(
            float(base.capacity_tasks_per_day or 0.0),
            float(incoming.capacity_tasks_per_day),
        )
    if incoming.collected_at > base.collected_at:
        base.collected_at = incoming.collected_at
    for key, value in incoming.raw.items():
        if key not in base.raw:
            base.raw[key] = value
    return _normalize_usage_row_status(_finalize_snapshot(base))


def coalesce_usage_overview_families(overview: ProviderUsageOverview) -> ProviderUsageOverview:
    grouped: dict[str, ProviderUsageSnapshot] = {}
    order: list[str] = []
    for row in overview.providers:
        family = _provider_family_name(row.provider)
        if not family:
            continue
        candidate = ProviderUsageSnapshot(**row.model_dump(mode="json"))
        candidate.provider = family
        existing = grouped.get(family)
        if existing is None:
            grouped[family] = _normalize_usage_row_status(_finalize_snapshot(candidate))
            order.append(family)
            continue
        grouped[family] = _merge_provider_snapshot_family(existing, candidate, family=family)

    merged = [grouped[name] for name in order]
    unavailable = sorted({row.provider for row in merged if row.status != "ok"})
    return ProviderUsageOverview(
        generated_at=overview.generated_at,
        providers=merged,
        unavailable_providers=unavailable,
        tracked_providers=len(merged),
        limit_coverage=dict(overview.limit_coverage),
    )


def _finalize_snapshot(snapshot: ProviderUsageSnapshot) -> ProviderUsageSnapshot:
    primary_metric = _primary_metric(snapshot.metrics)
    summary_metric = _summary_metric(snapshot.metrics)
    current_metric = primary_metric or summary_metric
    if current_metric:
        snapshot.actual_current_usage = current_metric.used
        snapshot.actual_current_usage_unit = current_metric.unit
        snapshot.usage_per_time = _metric_time_rate(current_metric)
    remaining_metric = summary_metric or primary_metric
    if remaining_metric:
        snapshot.usage_remaining = remaining_metric.remaining
        snapshot.usage_remaining_unit = (
            remaining_metric.unit if remaining_metric.remaining is not None else None
        )

    official_records = list(snapshot.official_records)
    raw_urls = [
        str(value).strip()
        for key, value in snapshot.raw.items()
        if key.endswith("_url") and isinstance(value, str) and str(value).strip()
    ]
    official_records.extend(raw_urls)
    official_records.extend(_default_official_records(snapshot.provider))
    snapshot.official_records = list(dict.fromkeys(official_records))

    if snapshot.data_source == "unknown":
        configured_keys = snapshot.raw.get("configured_env_keys")
        if snapshot.provider == "coherence-internal":
            snapshot.data_source = "runtime_events"
        elif snapshot.raw.get("probe") == "railway_cli_auth" or (
            isinstance(configured_keys, list)
            and any(str(item) in {"gh_auth", "railway_cli_auth"} for item in configured_keys)
        ):
            snapshot.data_source = "provider_cli"
        elif any(metric.id == "runtime_task_runs" for metric in snapshot.metrics):
            snapshot.data_source = "runtime_events"
        elif raw_urls or any(metric.id in {"api_probe", "rest_requests", "requests_total"} for metric in snapshot.metrics):
            snapshot.data_source = "provider_api"
        elif isinstance(configured_keys, list):
            snapshot.data_source = "configuration_only"
    return snapshot


def _env_present(name: str) -> bool:
    return bool(str(os.getenv(name, "")).strip())


def _cli_ok(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=8,
        )
    except Exception:
        return False
    return completed.returncode == 0


def _cli_output(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=8,
        )
    except Exception as exc:
        return False, str(exc)
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output


def _gh_auth_available() -> bool:
    if shutil.which("gh") is None:
        return False
    return _cli_ok(["gh", "auth", "status"])


def _railway_auth_available() -> bool:
    if shutil.which("railway") is None:
        return False
    return _cli_ok(["railway", "whoami"])


def _abs_expanded_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    return str(Path(value).expanduser().resolve())


def _codex_oauth_session_candidates() -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(path: str) -> None:
        candidate = _abs_expanded_path(path)
        if not candidate:
            return
        if candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    explicit_session_file = str(os.getenv("AGENT_CODEX_OAUTH_SESSION_FILE", "")).strip()
    if explicit_session_file:
        _append(explicit_session_file)

    codex_home = str(os.getenv("AGENT_CODEX_HOME", "")).strip() or str(os.getenv("CODEX_HOME", "")).strip()
    if codex_home:
        _append(os.path.join(codex_home, "auth.json"))
        _append(os.path.join(codex_home, "oauth.json"))
        _append(os.path.join(codex_home, "credentials.json"))

    home = str(os.getenv("HOME", "")).strip()
    if home:
        _append(os.path.join(home, ".codex", "auth.json"))
        _append(os.path.join(home, ".codex", "oauth.json"))
        _append(os.path.join(home, ".codex", "credentials.json"))
        _append(os.path.join(home, ".config", "codex", "auth.json"))
        _append(os.path.join(home, ".config", "codex", "oauth.json"))

    return candidates


def _codex_oauth_available() -> tuple[bool, str]:
    candidates = _codex_oauth_session_candidates()
    for candidate in candidates:
        try:
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                return True, f"session_file:{candidate}"
        except OSError:
            continue

    if shutil.which("codex") is not None:
        if _cli_ok(["codex", "login", "status"]):
            return True, "codex_login_status"
        if _cli_ok(["codex", "auth", "status"]):
            return True, "codex_auth_status"

    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_codex_oauth_session"


def _load_json_file_dict(path: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _codex_usage_probe_enabled() -> bool:
    raw = str(os.getenv("AUTOMATION_CODEX_USAGE_API_ENABLED", "1")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _codex_oauth_access_context() -> tuple[str | None, str | None, str | None]:
    for candidate in _codex_oauth_session_candidates():
        payload = _load_json_file_dict(candidate)
        if not payload:
            continue
        tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
        access_token = str(
            tokens.get("access_token")
            or payload.get("access_token")
            or tokens.get("id_token")
            or payload.get("id_token")
            or "",
        ).strip()
        if not access_token:
            continue
        if access_token.lower().startswith("bearer "):
            access_token = access_token[7:].strip()
        account_id = str(
            tokens.get("account_id")
            or payload.get("account_id")
            or payload.get("chatgpt_account_id")
            or "",
        ).strip()
        return access_token, (account_id or None), f"session_file:{candidate}"
    return None, None, None


def _codex_window_label(limit_window_seconds: int, fallback: str) -> str:
    seconds = max(0, int(limit_window_seconds))
    if seconds <= 0:
        return str(fallback or "window").strip() or "window"
    if seconds % (7 * 24 * 3600) == 0:
        weeks = max(1, int(seconds / (7 * 24 * 3600)))
        return "7d" if weeks == 1 else f"{weeks}w"
    if seconds % (24 * 3600) == 0:
        days = max(1, int(seconds / (24 * 3600)))
        return "24h" if days == 1 else f"{days}d"
    if seconds % 3600 == 0:
        return f"{max(1, int(seconds / 3600))}h"
    if seconds % 60 == 0:
        return f"{max(1, int(seconds / 60))}m"
    return f"{seconds}s"


def _parse_codex_usage_windows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        return []

    out: list[dict[str, Any]] = []
    for key in ("primary_window", "secondary_window"):
        row = rate_limit.get(key)
        if not isinstance(row, dict):
            continue
        used_percent = _coerce_float(row.get("used_percent"))
        if used_percent is None:
            used_percent = _coerce_float(row.get("utilization"))
        if used_percent is None:
            remaining_percent = _coerce_float(row.get("remaining_percent") or row.get("percent_remaining"))
            if remaining_percent is not None:
                used_percent = 100.0 - remaining_percent
        if used_percent is None:
            continue

        used_percent = max(0.0, min(float(used_percent), 100.0))
        limit_seconds = _coerce_nonnegative_int(row.get("limit_window_seconds"), default=0)
        reset_at_unix = _coerce_nonnegative_int(row.get("reset_at"), default=0)
        reset_at_iso: str | None = None
        if reset_at_unix > 0:
            try:
                reset_at_iso = (
                    datetime.fromtimestamp(reset_at_unix, timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            except Exception:
                reset_at_iso = None

        label = _codex_window_label(limit_seconds, key)
        out.append(
            {
                "metric_id": f"codex_provider_window_{'primary' if key == 'primary_window' else 'secondary'}",
                "source_key": key,
                "label": label,
                "window": label,
                "used_percent": used_percent,
                "remaining_percent": max(0.0, 100.0 - used_percent),
                "limit_window_seconds": limit_seconds,
                "reset_at_unix": reset_at_unix or None,
                "reset_at_iso": reset_at_iso,
            }
        )
    return out


def _codex_provider_usage_payload(*, force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    cached_payload = _CODEX_PROVIDER_USAGE_CACHE.get("payload")
    if (
        not force_refresh
        and isinstance(cached_payload, dict)
        and float(_CODEX_PROVIDER_USAGE_CACHE.get("expires_at") or 0.0) > now
    ):
        return dict(cached_payload)

    usage_url = str(os.getenv("CODEX_USAGE_URL", "https://chatgpt.com/backend-api/wham/usage")).strip()
    payload: dict[str, Any] = {
        "status": "unavailable",
        "error": "",
        "windows": [],
        "plan": None,
        "usage_url": usage_url,
        "auth_source": "",
    }

    if not _codex_usage_probe_enabled():
        payload["status"] = "disabled"
        payload["error"] = "codex_usage_probe_disabled"
    else:
        token, account_id, auth_source = _codex_oauth_access_context()
        payload["auth_source"] = auth_source or ""
        if not token:
            payload["error"] = "missing_codex_oauth_access_token"
        else:
            headers: dict[str, str] = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "coherence-network-automation-usage/1.0",
            }
            if account_id:
                headers["ChatGPT-Account-Id"] = account_id
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=10.0, headers=headers) as client:
                    response = client.get(usage_url)
                    status_code = int(response.status_code)
                    response.raise_for_status()
                    body = response.json()
                duration_ms = int((time.perf_counter() - started) * 1000)
                _record_external_tool_usage(
                    tool_name="codex-api",
                    provider="openai",
                    operation="usage_windows",
                    resource=usage_url,
                    status="success",
                    http_status=status_code,
                    duration_ms=duration_ms,
                )
                body_dict = body if isinstance(body, dict) else {}
                payload["windows"] = _parse_codex_usage_windows(body_dict)
                plan = str(body_dict.get("plan_type") or "").strip()
                credits = body_dict.get("credits")
                if isinstance(credits, dict) and credits.get("balance") is not None:
                    balance = _coerce_float(credits.get("balance"))
                    if balance is not None:
                        plan = f"{plan} (${balance:.2f})" if plan else f"${balance:.2f}"
                payload["plan"] = plan or None
                payload["status"] = "ok"
                if not payload["windows"]:
                    payload["error"] = "codex_usage_windows_missing"
            except Exception as exc:
                status_code = None
                response = getattr(exc, "response", None)
                if response is not None:
                    status_code = int(getattr(response, "status_code", 0) or 0) or None
                duration_ms = int((time.perf_counter() - started) * 1000)
                _record_external_tool_usage(
                    tool_name="codex-api",
                    provider="openai",
                    operation="usage_windows",
                    resource=usage_url,
                    status="error",
                    http_status=status_code,
                    duration_ms=duration_ms,
                    payload={"error": str(exc)},
                )
                payload["status"] = "error"
                payload["error"] = str(exc)

    _CODEX_PROVIDER_USAGE_CACHE["payload"] = dict(payload)
    _CODEX_PROVIDER_USAGE_CACHE["expires_at"] = now + _CODEX_PROVIDER_USAGE_CACHE_TTL_SECONDS
    return payload


def _append_codex_provider_window_metrics(snapshot: ProviderUsageSnapshot) -> bool:
    if _normalize_provider_name(snapshot.provider) != "openai":
        return False

    probe = _codex_provider_usage_payload()
    windows = probe.get("windows") if isinstance(probe.get("windows"), list) else []
    existing_ids = {metric.id for metric in snapshot.metrics}
    appended = False
    raw_windows: list[dict[str, Any]] = []

    for row in windows:
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        if not metric_id or metric_id in existing_ids:
            continue
        used_percent = _coerce_float(row.get("used_percent"))
        if used_percent is None:
            continue
        used_percent = max(0.0, min(float(used_percent), 100.0))
        remaining_percent = max(0.0, 100.0 - used_percent)
        label = str(row.get("label") or "window").strip() or "window"
        window = str(row.get("window") or label).strip() or label
        source_key = str(row.get("source_key") or "window").strip() or "window"
        reset_at_iso = str(row.get("reset_at_iso") or "").strip()
        reset_suffix = f"; resets_at={reset_at_iso}" if reset_at_iso else ""
        snapshot.metrics.append(
            _metric(
                id=metric_id,
                label=f"Codex provider quota ({label})",
                unit="requests",
                used=used_percent,
                remaining=remaining_percent,
                limit=100.0,
                window=window,
                validation_state="validated",
                validation_detail=(
                    "Validated from Codex provider usage API window telemetry "
                    f"({source_key}, percentage of window capacity){reset_suffix}."
                ),
                evidence_source="provider_api_wham_usage",
            )
        )
        raw_windows.append(
            {
                "metric_id": metric_id,
                "source_key": source_key,
                "label": label,
                "window": window,
                "used_percent": round(used_percent, 6),
                "remaining_percent": round(remaining_percent, 6),
                "limit_window_seconds": _coerce_nonnegative_int(row.get("limit_window_seconds"), default=0) or None,
                "reset_at_unix": _coerce_nonnegative_int(row.get("reset_at_unix"), default=0) or None,
                "reset_at_iso": reset_at_iso or None,
            }
        )
        existing_ids.add(metric_id)
        appended = True

    if appended:
        snapshot.notes.append(
            "Codex provider quota windows are sourced from provider API telemetry (percentage-based windows)."
        )
        snapshot.raw["codex_usage_windows"] = raw_windows
        if str(probe.get("plan") or "").strip():
            snapshot.raw["codex_usage_plan"] = str(probe["plan"]).strip()
        if str(probe.get("auth_source") or "").strip():
            snapshot.raw["codex_usage_auth_source"] = str(probe["auth_source"]).strip()
        if str(probe.get("usage_url") or "").strip():
            snapshot.raw["codex_usage_url"] = str(probe["usage_url"]).strip()
    elif str(probe.get("status") or "") == "error":
        error = _truncate_text(probe.get("error"), max_len=180)
        if error:
            snapshot.notes.append(f"Codex provider usage probe failed: {error}")
    if not appended and _append_codex_runner_window_metrics(snapshot):
        return True

    snapshot.notes = list(dict.fromkeys(snapshot.notes))
    return appended


def _runner_provider_telemetry_rows(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    cached_rows = _RUNNER_PROVIDER_TELEMETRY_CACHE.get("rows")
    if (
        not force_refresh
        and isinstance(cached_rows, list)
        and float(_RUNNER_PROVIDER_TELEMETRY_CACHE.get("expires_at") or 0.0) > now
    ):
        return [row for row in cached_rows if isinstance(row, dict)]

    try:
        rows = agent_runner_registry_service.list_runners(include_stale=False, limit=100)
    except Exception:
        rows = []
    normalized = [row for row in rows if isinstance(row, dict)]
    _RUNNER_PROVIDER_TELEMETRY_CACHE["rows"] = normalized
    _RUNNER_PROVIDER_TELEMETRY_CACHE["expires_at"] = now + _RUNNER_PROVIDER_TELEMETRY_CACHE_TTL_SECONDS
    return normalized


def _runner_provider_telemetry(provider: str) -> dict[str, Any]:
    normalized_provider = _normalize_provider_name(provider)
    if not normalized_provider:
        return {}

    def _parse_iso_timestamp(value: Any) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    best_row: dict[str, Any] = {}
    best_score: tuple[int, float] = (-1, 0.0)
    for row in _runner_provider_telemetry_rows():
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        provider_telemetry = (
            metadata.get("provider_telemetry")
            if isinstance(metadata.get("provider_telemetry"), dict)
            else {}
        )
        provider_row = provider_telemetry.get(normalized_provider)
        if not isinstance(provider_row, dict):
            continue

        limits = provider_row.get("limits") if isinstance(provider_row.get("limits"), dict) else {}
        limit_8h = _coerce_nonnegative_int(limits.get("subscription_8h") or limits.get("limit_8h"), default=0)
        limit_week = _coerce_nonnegative_int(limits.get("subscription_week") or limits.get("limit_week"), default=0)
        usage_windows = provider_row.get("usage_windows") if isinstance(provider_row.get("usage_windows"), list) else []
        configured = bool(provider_row.get("configured"))
        auth_detail = str(provider_row.get("auth_source") or provider_row.get("detail") or "").strip()

        priority = 0
        if configured:
            priority += 100
        if limit_8h > 0 and limit_week > 0:
            priority += 40
        if usage_windows:
            priority += 40
        if auth_detail:
            priority += 10

        recency = max(
            _parse_iso_timestamp(row.get("last_seen_at")),
            _parse_iso_timestamp(row.get("updated_at")),
            _parse_iso_timestamp(provider_telemetry.get("generated_at")),
        )
        score = (priority, recency)
        if score > best_score:
            best_score = score
            best_row = provider_row
    if best_row:
        return best_row
    return {}


def _runner_provider_configured(provider: str) -> tuple[bool, str]:
    provider_row = _runner_provider_telemetry(provider)
    if not provider_row:
        return False, ""
    configured = bool(provider_row.get("configured"))
    if not configured:
        return False, ""
    detail = str(provider_row.get("auth_source") or provider_row.get("detail") or "").strip()
    return True, (detail or "runner_provider_telemetry")


def _runner_provider_limits(provider: str) -> tuple[int, int, str]:
    provider_row = _runner_provider_telemetry(provider)
    if not provider_row:
        return 0, 0, ""
    limits = provider_row.get("limits") if isinstance(provider_row.get("limits"), dict) else {}
    limit_8h = _coerce_nonnegative_int(
        limits.get("subscription_8h") or limits.get("limit_8h"),
        default=0,
    )
    limit_week = _coerce_nonnegative_int(
        limits.get("subscription_week") or limits.get("limit_week"),
        default=0,
    )
    source = str(provider_row.get("limits_source") or "runner_provider_telemetry").strip()
    if limit_8h > 0 and limit_week > 0:
        return limit_8h, limit_week, (source or "runner_provider_telemetry")
    return 0, 0, ""


def _runner_openai_usage_windows() -> list[dict[str, Any]]:
    provider_row = _runner_provider_telemetry("openai")
    windows = provider_row.get("usage_windows") if isinstance(provider_row.get("usage_windows"), list) else []
    out: list[dict[str, Any]] = []
    for row in windows:
        if not isinstance(row, dict):
            continue
        metric_id = str(row.get("metric_id") or "").strip()
        used_percent = _coerce_float(row.get("used_percent"))
        if not metric_id or used_percent is None:
            continue
        out.append(row)
    return out


def _append_codex_runner_window_metrics(snapshot: ProviderUsageSnapshot) -> bool:
    if _normalize_provider_name(snapshot.provider) != "openai":
        return False
    windows = _runner_openai_usage_windows()
    if not windows:
        return False

    existing_ids = {metric.id for metric in snapshot.metrics}
    appended = False
    raw_windows: list[dict[str, Any]] = []
    for row in windows:
        metric_id = str(row.get("metric_id") or "").strip()
        if not metric_id or metric_id in existing_ids:
            continue
        used_percent = _coerce_float(row.get("used_percent"))
        if used_percent is None:
            continue
        used_percent = max(0.0, min(float(used_percent), 100.0))
        remaining_percent = max(0.0, 100.0 - used_percent)
        label = str(row.get("label") or "window").strip() or "window"
        window = str(row.get("window") or label).strip() or label
        source_key = str(row.get("source_key") or "window").strip() or "window"
        reset_at_iso = str(row.get("reset_at_iso") or "").strip()
        reset_suffix = f"; resets_at={reset_at_iso}" if reset_at_iso else ""
        snapshot.metrics.append(
            _metric(
                id=metric_id,
                label=f"Codex provider quota ({label})",
                unit="requests",
                used=used_percent,
                remaining=remaining_percent,
                limit=100.0,
                window=window,
                validation_state="validated",
                validation_detail=(
                    "Validated from host-runner Codex provider telemetry "
                    f"({source_key}, percentage of window capacity){reset_suffix}."
                ),
                evidence_source="runner_provider_telemetry",
            )
        )
        raw_windows.append(
            {
                "metric_id": metric_id,
                "source_key": source_key,
                "label": label,
                "window": window,
                "used_percent": round(used_percent, 6),
                "remaining_percent": round(remaining_percent, 6),
                "limit_window_seconds": _coerce_nonnegative_int(row.get("limit_window_seconds"), default=0) or None,
                "reset_at_unix": _coerce_nonnegative_int(row.get("reset_at_unix"), default=0) or None,
                "reset_at_iso": reset_at_iso or None,
            }
        )
        existing_ids.add(metric_id)
        appended = True

    if appended:
        snapshot.notes.append(
            "Codex provider quota windows are sourced from host-runner telemetry (percentage-based windows)."
        )
        snapshot.raw["codex_usage_windows"] = raw_windows
        provider_row = _runner_provider_telemetry("openai")
        plan = str(provider_row.get("plan") or "").strip()
        auth_source = str(provider_row.get("auth_source") or "").strip()
        usage_url = str(provider_row.get("usage_url") or "").strip()
        if plan:
            snapshot.raw["codex_usage_plan"] = plan
        if auth_source:
            snapshot.raw["codex_usage_auth_source"] = auth_source
        if usage_url:
            snapshot.raw["codex_usage_url"] = usage_url
    snapshot.notes = list(dict.fromkeys(snapshot.notes))
    return appended


def _cursor_cli_about_context() -> dict[str, Any]:
    now = time.time()
    cached_payload = _CURSOR_CLI_CONTEXT_CACHE.get("payload")
    if isinstance(cached_payload, dict) and float(_CURSOR_CLI_CONTEXT_CACHE.get("expires_at") or 0.0) > now:
        return dict(cached_payload)

    if shutil.which("agent") is None:
        payload = {"cli_available": False, "logged_in": False, "tier": ""}
        _CURSOR_CLI_CONTEXT_CACHE["payload"] = dict(payload)
        _CURSOR_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
        return payload

    status_ok, status_detail = _cli_output(["agent", "status"])
    _, about_detail = _cli_output(["agent", "about"])
    output = f"{status_detail}\n{about_detail}".strip()
    normalized = output.lower()

    tier = ""
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_clean = key.strip().lower()
        value_clean = value.strip().lower()
        if key_clean in {"plan", "subscription", "subscription type"} and value_clean:
            tier = value_clean.replace(" ", "_")
            break
    if not tier:
        for candidate in ("pro_plus", "pro plus", "pro", "free"):
            if candidate in normalized:
                tier = candidate.replace(" ", "_")
                break

    email = ""
    for line in output.splitlines():
        if "@" not in line:
            continue
        token = line.split()[-1].strip()
        if "@" in token:
            email = token
            break

    payload = {
        "cli_available": True,
        "logged_in": bool(status_ok and ("logged in" in normalized or "authenticated" in normalized)),
        "tier": tier,
        "email": email,
        "detail": _truncate_text(output, max_len=240),
    }
    _CURSOR_CLI_CONTEXT_CACHE["payload"] = dict(payload)
    _CURSOR_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
    return payload


def _cursor_subscription_limits() -> tuple[int, int, str, str]:
    runner_8h, runner_week, runner_source = _runner_provider_limits("cursor")
    if runner_8h > 0 and runner_week > 0:
        provider_row = _runner_provider_telemetry("cursor")
        runner_tier = str(provider_row.get("tier") or "").strip().lower()
        return runner_8h, runner_week, runner_source, runner_tier

    about = _cursor_cli_about_context()
    if not bool(about.get("logged_in")):
        return 0, 0, "", ""
    tier = str(about.get("tier") or "").strip().lower().replace("-", "_")
    limits = _CURSOR_SUBSCRIPTION_LIMITS_BY_TIER.get(tier) if tier else None
    if limits is None:
        tier = "pro"
        limits = _CURSOR_SUBSCRIPTION_LIMITS_BY_TIER[tier]
    return int(limits[0]), int(limits[1]), "cli_subscription_baseline", tier


def _claude_cli_auth_context() -> dict[str, Any]:
    now = time.time()
    cached_payload = _CLAUDE_CLI_CONTEXT_CACHE.get("payload")
    if isinstance(cached_payload, dict) and float(_CLAUDE_CLI_CONTEXT_CACHE.get("expires_at") or 0.0) > now:
        return dict(cached_payload)

    if not _claude_code_cli_available():
        payload = {"cli_available": False, "logged_in": False, "subscription_type": ""}
        _CLAUDE_CLI_CONTEXT_CACHE["payload"] = dict(payload)
        _CLAUDE_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
        return payload
    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=8,
            env={**os.environ, "CLAUDECODE": ""},
        )
    except Exception:
        payload = {"cli_available": True, "logged_in": False, "subscription_type": ""}
        _CLAUDE_CLI_CONTEXT_CACHE["payload"] = dict(payload)
        _CLAUDE_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
        return payload
    if result.returncode != 0:
        payload = {"cli_available": True, "logged_in": False, "subscription_type": ""}
        _CLAUDE_CLI_CONTEXT_CACHE["payload"] = dict(payload)
        _CLAUDE_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
        return payload
    try:
        payload = json.loads(result.stdout.strip())
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    out = {
        "cli_available": True,
        "logged_in": bool(payload.get("loggedIn")),
        "subscription_type": str(payload.get("subscriptionType") or "").strip().lower(),
        "auth_method": str(payload.get("authMethod") or "").strip(),
        "api_provider": str(payload.get("apiProvider") or "").strip(),
    }
    _CLAUDE_CLI_CONTEXT_CACHE["payload"] = dict(out)
    _CLAUDE_CLI_CONTEXT_CACHE["expires_at"] = now + 20.0
    return out


def _claude_subscription_limits() -> tuple[int, int, str, str]:
    runner_8h, runner_week, runner_source = _runner_provider_limits("claude")
    if runner_8h > 0 and runner_week > 0:
        provider_row = _runner_provider_telemetry("claude")
        runner_tier = str(provider_row.get("tier") or "").strip().lower()
        return runner_8h, runner_week, runner_source, runner_tier

    auth = _claude_cli_auth_context()
    tier = str(auth.get("subscription_type") or "").strip().lower().replace("-", "_")
    limits = _CLAUDE_SUBSCRIPTION_LIMITS_BY_TIER.get(tier) if tier else None
    if limits is None:
        return 0, 0, "", tier
    return int(limits[0]), int(limits[1]), "cli_subscription_baseline", tier


def _configured_env_status(provider: str) -> tuple[bool, list[str], list[str]]:
    rule = _PROVIDER_CONFIG_RULES.get(provider, {})
    all_of = [str(item) for item in (rule.get("all_of") or [])]
    any_of = [str(item) for item in (rule.get("any_of") or [])]
    present = [name for name in all_of + any_of if _env_present(name)]

    missing: list[str] = []
    configured = True
    if all_of:
        missing.extend([name for name in all_of if not _env_present(name)])
        configured = configured and len(missing) == 0
    if any_of:
        any_present = any(_env_present(name) for name in any_of)
        if not any_present:
            missing.append(f"one_of({','.join(any_of)})")
        configured = configured and any_present
    return configured, missing, present


def _configured_status(provider: str) -> tuple[bool, list[str], list[str], list[str]]:
    provider_name = _normalize_provider_name(provider)
    configured, missing, present = _configured_env_status(provider_name)
    notes: list[str] = []
    if configured:
        return configured, missing, present, notes

    active_counts = _active_provider_usage_counts()
    active_runs = int(active_counts.get(provider_name, 0))

    if provider_name == "github" and _gh_auth_available():
        return True, [], ["gh_auth"], ["Configured via gh CLI auth session."]
    if provider_name == "railway" and _railway_auth_available():
        return True, [], ["railway_cli_auth"], ["Configured via Railway CLI auth session."]
    if provider_name == "openai":
        oauth_ok, oauth_detail = _codex_oauth_available()
        if oauth_ok:
            return True, [], ["codex_oauth_session"], [f"Configured via Codex OAuth session ({oauth_detail})."]
        runner_ok, runner_detail = _runner_provider_configured("openai")
        if runner_ok:
            detail = runner_detail or "runner_provider_telemetry"
            return True, [], ["runner_provider_telemetry"], [f"Configured via host-runner OpenAI/Codex telemetry ({detail})."]
        if active_runs > 0:
            notes.append("OpenAI observed in runtime usage; treating as configured by active execution context.")
            return True, [], present, notes
    if provider_name == "openclaw" and active_runs > 0:
        openai_key = bool(
            os.getenv("OPENAI_ADMIN_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        codex_active = int(active_counts.get("openai", 0)) > 0
        if openai_key or codex_active:
            notes.append(
                "OpenClaw observed with Codex/OpenAI execution context; treating as configured for runtime validation."
            )
            return True, [], present, notes
    if provider_name == "claude" and active_runs > 0:
        notes.append("Claude observed in runtime usage; treating as configured by active execution context.")
        return True, [], present, notes
    if provider_name == "claude":
        runner_ok, runner_detail = _runner_provider_configured("claude")
        if runner_ok:
            detail = runner_detail or "runner_provider_telemetry"
            return True, [], ["runner_provider_telemetry"], [f"Configured via host-runner Claude telemetry ({detail})."]
        auth = _claude_cli_auth_context()
        if bool(auth.get("logged_in")):
            auth_method = str(auth.get("auth_method") or "cli_session").strip()
            return True, [], ["claude_cli_session"], [f"Configured via Claude CLI session ({auth_method})."]
    if provider_name == "cursor":
        runner_ok, runner_detail = _runner_provider_configured("cursor")
        if runner_ok:
            detail = runner_detail or "runner_provider_telemetry"
            return True, [], ["runner_provider_telemetry"], [f"Configured via host-runner Cursor telemetry ({detail})."]
        about = _cursor_cli_about_context()
        if bool(about.get("logged_in")):
            return True, [], ["cursor_cli_session"], ["Configured via Cursor CLI session."]

    return configured, missing, present, notes


def _required_providers_from_env() -> list[str]:
    raw = os.getenv("AUTOMATION_REQUIRED_PROVIDERS", ",".join(_DEFAULT_REQUIRED_PROVIDERS))
    parsed = [
        _provider_family_name(item)
        for item in str(raw).split(",")
        if str(item).strip()
    ]
    out = [
        provider
        for provider in parsed
        if provider in _READINESS_REQUIRED_PROVIDER_ALLOWLIST
    ]
    out = _dedupe_preserve_order(out)
    for provider in _DEFAULT_REQUIRED_PROVIDERS:
        normalized = _provider_family_name(provider)
        if normalized and normalized in _READINESS_REQUIRED_PROVIDER_ALLOWLIST and normalized not in out:
            out.append(normalized)
    return out if out else list(_DEFAULT_REQUIRED_PROVIDERS)


def _validation_required_providers_from_env() -> list[str]:
    raw = os.getenv(
        "AUTOMATION_PROVIDER_VALIDATION_REQUIRED",
        ",".join(_DEFAULT_PROVIDER_VALIDATION_REQUIRED),
    )
    out = [
        _normalize_provider_name(item)
        for item in str(raw).split(",")
        if str(item).strip()
    ]
    return out if out else list(_DEFAULT_PROVIDER_VALIDATION_REQUIRED)


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _supabase_tracking_enabled() -> bool:
    return _env_truthy("AUTOMATION_TRACK_SUPABASE", default=False)


def _infer_provider_from_model(model_name: str) -> str:
    model = model_name.strip().lower()
    if not model:
        return ""
    if "codex" in model:
        return "openai"
    if model.startswith("cursor/"):
        return "cursor"
    if model.startswith("clawwork/"):
        return "openclaw"
    if model.startswith("openclaw/"):
        return "openclaw"
    if model.startswith("openrouter/") or "openrouter" in model:
        return "openrouter"
    if "claude" in model:
        return "claude"
    if model.startswith(("gpt", "o1", "o3", "o4")) or model.startswith("openai/"):
        return "openai"
    return ""


def _active_provider_usage_counts() -> dict[str, int]:
    usage = agent_service.get_usage_summary()
    by_model = usage.get("by_model") if isinstance(usage, dict) else {}
    execution = usage.get("execution") if isinstance(usage, dict) else {}
    by_executor = execution.get("by_executor") if isinstance(execution, dict) else {}
    by_agent = execution.get("by_agent") if isinstance(execution, dict) else {}
    recent_runs = execution.get("recent_runs") if isinstance(execution, dict) else {}

    counts: dict[str, int] = {}

    model_rows = by_model if isinstance(by_model, dict) else {}
    for model_name, row in model_rows.items():
        provider = _infer_provider_from_model(str(model_name))
        if not provider:
            continue
        row_count = row.get("count") if isinstance(row, dict) else 0
        try:
            value = int(float(row_count or 0))
        except Exception:
            value = 0
        if value > 0:
            counts[provider] = counts.get(provider, 0) + value

    executor_rows = by_executor if isinstance(by_executor, dict) else {}
    executor_provider_map = {
        "cursor": "cursor",
        "codex": "openai",
        "openclaw": "openai",
        "clawwork": "openai",
        "openrouter": "openrouter",
        "claude": "claude-code",
    }
    for executor_name, row in executor_rows.items():
        provider = executor_provider_map.get(str(executor_name).strip().lower(), "")
        if not provider:
            continue
        row_count = row.get("count") if isinstance(row, dict) else 0
        try:
            value = int(float(row_count or 0))
        except Exception:
            value = 0
        if value > 0:
            counts[provider] = max(counts.get(provider, 0), value)

    agent_rows = by_agent if isinstance(by_agent, dict) else {}
    for agent_name, row in agent_rows.items():
        agent = str(agent_name).strip().lower()
        provider = ""
        if agent.startswith("openai-codex"):
            provider = "openai"
        elif agent.startswith("claude"):
            provider = "claude"
        if not provider:
            continue
        row_count = row.get("count") if isinstance(row, dict) else 0
        try:
            value = int(float(row_count or 0))
        except Exception:
            value = 0
        if value > 0:
            counts[provider] = max(counts.get(provider, 0), value)

    recent_rows = recent_runs if isinstance(recent_runs, list) else []
    for row in recent_rows:
        if not isinstance(row, dict):
            continue
        provider = _normalize_provider_name(str(row.get("provider") or ""))
        if not provider:
            continue
        counts[provider] = counts.get(provider, 0) + 1

    normalized_counts: dict[str, int] = {}
    for provider_name, value in counts.items():
        canonical = _normalize_provider_name(provider_name)
        if not canonical or value <= 0:
            continue
        normalized_counts[canonical] = max(normalized_counts.get(canonical, 0), int(value))

    return normalized_counts


def _coalesce_usage_counts_by_family(counts: dict[str, int]) -> dict[str, int]:
    coalesced: dict[str, int] = {}
    for provider_name, value in counts.items():
        family = _provider_family_name(provider_name)
        if not family:
            continue
        try:
            numeric = int(value)
        except Exception:
            continue
        if numeric <= 0:
            continue
        coalesced[family] = max(coalesced.get(family, 0), numeric)
    return coalesced


def _build_config_only_snapshot(provider: str) -> ProviderUsageSnapshot:
    rule = _PROVIDER_CONFIG_RULES.get(provider, {})
    kind = str(rule.get("kind") or "custom")
    configured, missing, present, derived_notes = _configured_status(provider)
    status = "ok" if configured else "unavailable"
    notes = (
        [f"missing_env={','.join(missing)}"] if missing else ["configuration keys detected"]
    )
    notes.extend(derived_notes)
    notes = list(dict.fromkeys(notes))
    return ProviderUsageSnapshot(
        id=f"provider_{provider}_{int(time.time())}",
        provider=provider,
        kind=kind,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        data_source="configuration_only",
        notes=notes,
        raw={"configured_env_keys": present, "missing_env_keys": missing},
    )


def _int_env(name: str, default: int = 0) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _coerce_nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _runtime_events_within_window(
    *,
    window_seconds: int,
    source: str | None = None,
    limit: int = 1500,
) -> list[Any]:
    normalized_window = max(60, int(window_seconds))
    normalized_limit = max(1, min(int(limit), _runtime_event_scan_limit()))
    normalized_source = source if isinstance(source, str) and source.strip() else None
    cache_ttl = _runtime_events_cache_ttl_seconds()
    cache_key = (normalized_window, normalized_source, normalized_limit)
    now = time.time()

    if cache_ttl > 0:
        cached = _RUNTIME_EVENTS_WINDOW_CACHE.get(cache_key)
        if cached and float(cached.get("expires_at") or 0.0) > now:
            events = cached.get("events")
            if isinstance(events, list):
                return events

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=normalized_window)
    try:
        from app.services import runtime_service

        events = runtime_service.list_events(
            limit=normalized_limit,
            since=cutoff,
            source=normalized_source,
        )
    except Exception:
        events = []

    if cache_ttl > 0:
        _RUNTIME_EVENTS_WINDOW_CACHE[cache_key] = {
            "expires_at": now + cache_ttl,
            "events": events,
        }
        # Keep cache bounded to avoid unbounded growth on variable windows.
        if len(_RUNTIME_EVENTS_WINDOW_CACHE) > 48:
            stale_keys = [
                key
                for key, row in _RUNTIME_EVENTS_WINDOW_CACHE.items()
                if float(row.get("expires_at") or 0.0) <= now
            ]
            for key in stale_keys[:24]:
                _RUNTIME_EVENTS_WINDOW_CACHE.pop(key, None)
            if len(_RUNTIME_EVENTS_WINDOW_CACHE) > 48:
                oldest = sorted(
                    _RUNTIME_EVENTS_WINDOW_CACHE.items(),
                    key=lambda item: float(item[1].get("expires_at") or 0.0),
                )
                for key, _row in oldest[: len(_RUNTIME_EVENTS_WINDOW_CACHE) - 48]:
                    _RUNTIME_EVENTS_WINDOW_CACHE.pop(key, None)
    return events


def _cursor_events_within_window(window_seconds: int) -> int:
    events = _runtime_events_within_window(window_seconds=window_seconds, source="worker")

    count = 0
    for event in events:
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        executor = str(metadata.get("executor") or "").strip().lower()
        provider = _normalize_provider_name(str(metadata.get("provider") or ""))
        model = str(metadata.get("model") or "").strip().lower()
        if executor == "cursor" or provider == "cursor" or model.startswith("cursor/"):
            count += 1
    return count


def _claude_events_within_window(window_seconds: int) -> int:
    events = _runtime_events_within_window(window_seconds=window_seconds, source="worker")

    count = 0
    for event in events:
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        executor = str(metadata.get("executor") or "").strip().lower()
        provider = _normalize_provider_name(str(metadata.get("provider") or ""))
        model = str(metadata.get("model") or "").strip().lower()
        agent_id = str(metadata.get("agent_id") or "").strip().lower()
        if (
            executor == "claude"
            or provider in {"claude", "claude-code"}
            or "claude" in model
            or agent_id.startswith("claude")
        ):
            count += 1
    return count


def _codex_events_within_window(window_seconds: int) -> int:
    events = _runtime_events_within_window(window_seconds=window_seconds, source="worker")
    count = 0
    for event in events:
        endpoint = str(getattr(event, "endpoint", "") or "").strip().lower()
        # Avoid double-counting task wrappers; only track execution-like events.
        if endpoint in {
            "/tool:agent-task-completion",
            "tool:agent-task-completion",
            "/tool:agent-task-execution-summary",
            "tool:agent-task-execution-summary",
        }:
            continue
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        model = str(metadata.get("model") or "").strip().lower()
        provider = _normalize_provider_name(str(metadata.get("provider") or ""))
        executor = str(metadata.get("executor") or "").strip().lower()
        agent_id = str(metadata.get("agent_id") or "").strip().lower()
        repeatable_tool_call = str(metadata.get("repeatable_tool_call") or "").strip().lower()
        is_codex = bool(metadata.get("is_openai_codex"))
        if is_codex:
            count += 1
            continue
        if provider == "openai" and (
            "codex" in model
            or "openai-codex" in agent_id
            or repeatable_tool_call.startswith("codex ")
        ):
            count += 1
            continue
        if "codex" in model and (executor in {"openclaw", "codex"} or "openai-codex" in agent_id):
            count += 1
            continue
    return count


def _cursor_subscription_window_metrics(
    *,
    limit_8h: int,
    limit_week: int,
    limit_source: str,
) -> list[UsageMetric]:
    validation_state = "validated" if limit_source == "runner_provider_telemetry" else "derived"
    validation_detail = (
        "Derived from runtime worker-event usage and host-runner Cursor subscription telemetry."
        if limit_source == "runner_provider_telemetry"
        else "Derived from runtime worker-event usage and Cursor CLI subscription-tier baseline."
    )
    evidence_source = (
        "runner_provider_telemetry"
        if limit_source == "runner_provider_telemetry"
        else "runtime_events+cli_subscription_baseline"
    )
    metrics: list[UsageMetric] = []
    if limit_8h > 0:
        used_8h = _cursor_events_within_window(8 * 60 * 60)
        metrics.append(
            _metric(
                id="cursor_subscription_8h",
                label="Cursor subscription runs (8h)",
                unit="requests",
                used=float(min(used_8h, limit_8h)),
                remaining=float(max(0, limit_8h - used_8h)),
                limit=float(limit_8h),
                window="hourly",
                validation_state=validation_state,
                validation_detail=validation_detail,
                evidence_source=evidence_source,
            )
        )
    if limit_week > 0:
        used_week = _cursor_events_within_window(7 * 24 * 60 * 60)
        metrics.append(
            _metric(
                id="cursor_subscription_week",
                label="Cursor subscription runs (7d)",
                unit="requests",
                used=float(min(used_week, limit_week)),
                remaining=float(max(0, limit_week - used_week)),
                limit=float(limit_week),
                window="weekly",
                validation_state=validation_state,
                validation_detail=validation_detail,
                evidence_source=evidence_source,
            )
        )
    return metrics


def _build_cursor_snapshot() -> ProviderUsageSnapshot:
    configured, missing, present, derived_notes = _configured_status("cursor")
    agent_binary = shutil.which("agent")
    cli_ok = False
    cli_detail = ""
    if agent_binary:
        cli_ok, cli_detail = _cli_output(["agent", "--version"])

    metrics: list[UsageMetric] = []
    notes: list[str] = []
    notes.extend(derived_notes)
    if missing:
        notes.append(f"missing_env={','.join(missing)}")
    elif present:
        notes.append("configuration keys detected")
    if agent_binary:
        if cli_ok:
            notes.append(f"cursor_cli_ready: {cli_detail[:120]}")
        else:
            notes.append(f"cursor_cli_probe_failed: {cli_detail[:160]}")
    else:
        notes.append("cursor_cli_missing: install Cursor CLI (`agent`) for runtime execution.")

    limit_8h, limit_week, limit_source, limit_tier = _cursor_subscription_limits()
    if limit_source:
        notes.append(f"cursor_limit_source={limit_source}")
    if limit_tier:
        notes.append(f"cursor_subscription_tier={limit_tier}")

    metrics.extend(
        _cursor_subscription_window_metrics(
            limit_8h=limit_8h,
            limit_week=limit_week,
            limit_source=limit_source,
        )
    )

    runner_ok, _runner_detail = _runner_provider_configured("cursor")
    status = "ok" if configured and ((agent_binary and cli_ok) or runner_ok) else "degraded" if configured else "unavailable"
    if configured and status != "ok":
        notes.append("cursor_cli_probe_unavailable: falling back to runtime/runner telemetry only")
    return ProviderUsageSnapshot(
        id=f"provider_cursor_{int(time.time())}",
        provider="cursor",
        kind="custom",
        status=status,  # type: ignore[arg-type]
        data_source="provider_cli" if agent_binary else ("runtime_events" if runner_ok else "configuration_only"),
        metrics=metrics,
        notes=list(dict.fromkeys(notes)),
        raw={
            "configured_env_keys": present,
            "missing_env_keys": missing,
            "agent_binary": agent_binary or "",
            "cli_probe_ok": cli_ok,
            "cli_probe_detail": cli_detail[:200],
            "limits": {
                "cursor_subscription_8h_limit": limit_8h,
                "cursor_subscription_week_limit": limit_week,
                "cursor_limit_source": limit_source,
                "cursor_subscription_tier": limit_tier,
            },
        },
    )


def _append_codex_subscription_metrics(snapshot: ProviderUsageSnapshot) -> None:
    if _normalize_provider_name(snapshot.provider) != "openai":
        return
    has_provider_windows = _append_codex_provider_window_metrics(snapshot)
    existing = {metric.id for metric in snapshot.metrics}
    used_5h = _codex_events_within_window(5 * 60 * 60)
    used_week = _codex_events_within_window(7 * 24 * 60 * 60)
    if "codex_subscription_5h" not in existing:
        snapshot.metrics.append(
            _metric(
                id="codex_subscription_5h",
                label="Codex task runs (5h)",
                unit="requests",
                used=float(used_5h),
                remaining=None,
                limit=None,
                window="rolling_5h",
                validation_state="derived",
                validation_detail=(
                    "Derived from runtime worker-event counts for execution volume tracking."
                    if has_provider_windows
                    else "Derived from runtime worker-event counts. No validated Codex 5h quota window telemetry was available."
                ),
                evidence_source="runtime_events",
            )
        )
    if "codex_subscription_week" not in existing:
        snapshot.metrics.append(
            _metric(
                id="codex_subscription_week",
                label="Codex task runs (7d)",
                unit="requests",
                used=float(used_week),
                remaining=None,
                limit=None,
                window="rolling_7d",
                validation_state="derived",
                validation_detail=(
                    "Derived from runtime worker-event counts for execution volume tracking."
                    if has_provider_windows
                    else "Derived from runtime worker-event counts. No validated Codex weekly quota window telemetry was available."
                ),
                evidence_source="runtime_events",
            )
        )
    if not has_provider_windows:
        snapshot.notes.append(
            "Codex subscription windows were unavailable from provider API/runner telemetry; tracking execution volume only."
        )
    snapshot.notes = list(dict.fromkeys(snapshot.notes))


def _build_internal_snapshot() -> ProviderUsageSnapshot:
    usage = agent_service.get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    host_runner = usage.get("host_runner") if isinstance(usage.get("host_runner"), dict) else {}

    tracked_runs = float(execution.get("tracked_runs") or 0.0)
    failed_runs = float(execution.get("failed_runs") or 0.0)
    success_runs = float(execution.get("success_runs") or max(0.0, tracked_runs - failed_runs))
    untracked_tasks = float(
        ((execution.get("coverage") or {}).get("completed_or_failed_tasks") or 0.0)
        - ((execution.get("coverage") or {}).get("tracked_task_runs") or 0.0)
    )
    if untracked_tasks < 0:
        untracked_tasks = 0.0
    success_rate = float(execution.get("success_rate") or 0.0)

    metrics = [
        _metric(id="tasks_tracked", label="Tracked task runs", unit="tasks", used=tracked_runs, window="rolling"),
        _metric(id="tasks_failed", label="Failed task runs", unit="tasks", used=failed_runs, window="rolling"),
        _metric(id="tasks_untracked", label="Completed/failed tasks without usage", unit="tasks", used=untracked_tasks, window="rolling"),
    ]
    host_total = float(host_runner.get("total_runs") or 0.0)
    host_failed = float(host_runner.get("failed_runs") or 0.0)
    if host_total > 0:
        metrics.append(
            _metric(
                id="host_runner_tasks_24h",
                label="Host-runner task runs (24h)",
                unit="tasks",
                used=host_total,
                window="daily",
            )
        )
    if host_failed > 0:
        metrics.append(
            _metric(
                id="host_runner_failed_24h",
                label="Host-runner failed tasks (24h)",
                unit="tasks",
                used=host_failed,
                window="daily",
            )
        )
    notes = [f"Execution success rate {round(success_rate * 100.0, 2)}%"]

    return ProviderUsageSnapshot(
        id=f"provider_internal_{int(time.time())}",
        provider="coherence-internal",
        kind="internal",
        status="ok",
        data_source="runtime_events",
        metrics=metrics,
        capacity_tasks_per_day=max(0.0, success_runs * 24.0),
        notes=notes,
        raw={"execution": execution},
    )


def _github_billing_url(owner: str, scope: str) -> str:
    if scope == "user":
        return f"https://api.github.com/users/{owner}/settings/billing/actions"
    return f"https://api.github.com/orgs/{owner}/settings/billing/actions"


def _build_github_snapshot() -> ProviderUsageSnapshot:
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    owner = os.getenv("GITHUB_BILLING_OWNER", "").strip()
    scope = os.getenv("GITHUB_BILLING_SCOPE", "org").strip().lower()
    if not token:
        return ProviderUsageSnapshot(
            id=f"provider_github_{int(time.time())}",
            provider="github",
            kind="github",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set GITHUB_TOKEN (or GH_TOKEN) to enable GitHub usage data."],
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    billing_payload: dict[str, Any] = {}
    rate_payload: dict[str, Any] = {}
    billing_error = None
    rate_error = None
    billing_url = ""

    if owner and scope in {"org", "user"}:
        billing_url = _github_billing_url(owner=owner, scope=scope)
        try:
            with httpx.Client(timeout=8.0, headers=headers) as client:
                response = client.get(billing_url)
                response.raise_for_status()
                billing_payload = response.json()
        except Exception as exc:
            billing_error = str(exc)
    else:
        billing_error = "billing_owner_or_scope_not_configured"

    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            response = client.get("https://api.github.com/rate_limit")
            response.raise_for_status()
            rate_payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        rate_error = str(exc)

    if rate_error:
        return ProviderUsageSnapshot(
            id=f"provider_github_{int(time.time())}",
            provider="github",
            kind="github",
            status="degraded",
            data_source="provider_api",
            notes=[f"GitHub rate-limit probe failed: {rate_error}"],
            raw={"rate_limit_url": "https://api.github.com/rate_limit", "billing_url": billing_url},
        )

    included = float(billing_payload.get("included_minutes") or 0.0)
    used = float(billing_payload.get("total_minutes_used") or 0.0)
    remaining = max(0.0, included - used) if included > 0 else None
    resources = rate_payload.get("resources") if isinstance(rate_payload.get("resources"), dict) else {}
    core = resources.get("core") if isinstance(resources.get("core"), dict) else {}
    core_limit = float(core.get("limit") or 0.0)
    core_remaining = float(core.get("remaining") or 0.0)
    core_used = max(0.0, core_limit - core_remaining) if core_limit > 0 else 0.0

    metrics = [
        _metric(
            id="rest_requests",
            label="GitHub REST core requests",
            unit="requests",
            used=core_used,
            remaining=core_remaining if core_limit > 0 else None,
            limit=core_limit if core_limit > 0 else None,
            window="hourly",
        ),
    ]
    if included > 0:
        metrics.append(
            _metric(
                id="actions_minutes",
                label="GitHub Actions minutes",
                unit="minutes",
                used=used,
                remaining=remaining,
                limit=included,
                window="monthly",
            )
        )

    notes: list[str] = []
    if billing_error:
        notes.append(f"GitHub billing data unavailable: {billing_error}")

    return ProviderUsageSnapshot(
        id=f"provider_github_{int(time.time())}",
        provider="github",
        kind="github",
        status="ok",
        data_source="provider_api",
        metrics=metrics,
        notes=notes,
        raw={
            "included_minutes": included,
            "total_minutes_used": used,
            "minutes_used_breakdown": billing_payload.get("minutes_used_breakdown"),
            "rate_limit": resources,
            "rate_limit_url": "https://api.github.com/rate_limit",
            "billing_url": billing_url,
        },
    )


def _build_openai_codex_snapshot() -> ProviderUsageSnapshot:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        oauth_ok, oauth_detail = _codex_oauth_available()
        if oauth_ok:
            active = int(_active_provider_usage_counts().get("openai-codex", 0))
            if active > 0:
                return _runtime_task_runs_snapshot(
                    provider="openai-codex",
                    kind="custom",
                    active_runs=active,
                    note=f"Using runtime Codex execution evidence with OAuth session ({oauth_detail}).",
                )
            return ProviderUsageSnapshot(
                id=f"provider_openai_codex_{int(time.time())}",
                provider="openai-codex",
                kind="custom",
                status="ok",
                data_source="configuration_only",
                notes=[f"Configured via Codex OAuth session ({oauth_detail})."],
                raw={"auth_mode": "oauth", "oauth_detail": oauth_detail},
            )
        active = int(_active_provider_usage_counts().get("openai-codex", 0))
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="openai-codex",
                kind="custom",
                active_runs=active,
                note="Using runtime Codex execution evidence (no direct OpenAI API key in environment).",
            )
        return ProviderUsageSnapshot(
            id=f"provider_openai_codex_{int(time.time())}",
            provider="openai-codex",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set OPENAI_ADMIN_API_KEY or OPENAI_API_KEY to validate Codex provider access."],
        )

    models_url = os.getenv("OPENAI_MODELS_URL", "https://api.openai.com/v1/models")
    headers = _openai_headers()
    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            response = client.get(models_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        return ProviderUsageSnapshot(
            id=f"provider_openai_codex_{int(time.time())}",
            provider="openai-codex",
            kind="custom",
            status="degraded",
            data_source="provider_api",
            notes=[f"OpenAI models probe failed: {exc}"],
            raw={"probe_url": models_url},
        )

    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    snapshot = _build_openai_models_visibility_snapshot(
        models_url=models_url,
        rows=rows,
        headers=response.headers,
    )
    probe_headers, probe_error = _openai_quota_probe_headers(headers)
    return _apply_quota_probe_to_snapshot(
        snapshot=snapshot,
        probe_headers=probe_headers,
        probe_error=probe_error,
        request_limit_keys=("x-ratelimit-limit-requests",),
        request_remaining_keys=("x-ratelimit-remaining-requests",),
        request_label="OpenAI request quota",
        token_limit_keys=("x-ratelimit-limit-tokens",),
        token_remaining_keys=("x-ratelimit-remaining-tokens",),
        token_label="OpenAI token quota",
        success_note="Quota headers sourced from lightweight OpenAI responses probe.",
        no_headers_note="OpenAI responses probe completed, but no request/token remaining headers were returned.",
        error_note_prefix="OpenAI responses quota probe failed",
    )


def _anthropic_headers() -> dict[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    return {
        "x-api-key": api_key,
        "anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
    }


def _claude_subscription_window_metrics(
    *,
    limit_8h: int,
    limit_week: int,
    limit_source: str,
) -> list[UsageMetric]:
    validation_state = "validated" if limit_source == "runner_provider_telemetry" else "derived"
    validation_detail = (
        "Derived from runtime worker-event usage and host-runner Claude subscription telemetry."
        if limit_source == "runner_provider_telemetry"
        else "Derived from runtime worker-event usage and Claude CLI subscription-tier baseline."
    )
    evidence_source = (
        "runner_provider_telemetry"
        if limit_source == "runner_provider_telemetry"
        else "runtime_events+cli_subscription_baseline"
    )
    metrics: list[UsageMetric] = []
    if limit_8h > 0:
        used_8h = _claude_events_within_window(8 * 60 * 60)
        metrics.append(
            _metric(
                id="claude_subscription_8h",
                label="Claude subscription runs (8h)",
                unit="requests",
                used=float(min(used_8h, limit_8h)),
                remaining=float(max(0, limit_8h - used_8h)),
                limit=float(limit_8h),
                window="hourly",
                validation_state=validation_state,
                validation_detail=validation_detail,
                evidence_source=evidence_source,
            )
        )
    if limit_week > 0:
        used_week = _claude_events_within_window(7 * 24 * 60 * 60)
        metrics.append(
            _metric(
                id="claude_subscription_week",
                label="Claude subscription runs (7d)",
                unit="requests",
                used=float(min(used_week, limit_week)),
                remaining=float(max(0, limit_week - used_week)),
                limit=float(limit_week),
                window="weekly",
                validation_state=validation_state,
                validation_detail=validation_detail,
                evidence_source=evidence_source,
            )
        )
    return metrics


def _build_claude_snapshot_without_api_key() -> ProviderUsageSnapshot | None:
    active = int(_active_provider_usage_counts().get("claude", 0))
    auth = _claude_cli_auth_context()
    runner_ok, runner_detail = _runner_provider_configured("claude")
    limit_8h, limit_week, limit_source, limit_tier = _claude_subscription_limits()
    if active <= 0 and not bool(auth.get("logged_in")) and not runner_ok:
        return None

    notes: list[str] = []
    if runner_ok:
        notes.append(f"Using host-runner Claude telemetry ({runner_detail or 'runner_provider_telemetry'}).")
    elif bool(auth.get("logged_in")):
        auth_method = str(auth.get("auth_method") or "cli_session").strip()
        notes.append(f"Using Claude CLI auth session ({auth_method}).")
    else:
        notes.append("Using runtime Claude execution evidence (no direct Anthropic key in environment).")
    if limit_source:
        notes.append(f"claude_limit_source={limit_source}")
    if limit_tier:
        notes.append(f"claude_subscription_tier={limit_tier}")

    metrics = _claude_subscription_window_metrics(
        limit_8h=limit_8h,
        limit_week=limit_week,
        limit_source=limit_source,
    )
    if active > 0:
        metrics.append(
            _metric(
                id="runtime_task_runs",
                label="Runtime task runs",
                unit="tasks",
                used=float(active),
                window="rolling",
                validation_state="derived",
                validation_detail="Derived from runtime telemetry events; not a provider-reported quota value.",
                evidence_source="runtime_events",
            )
        )
    return ProviderUsageSnapshot(
        id=f"provider_claude_{int(time.time())}",
        provider="claude",
        kind="custom",
        status="ok",
        data_source=("runtime_events" if runner_ok else "provider_cli"),
        metrics=metrics,
        notes=notes,
        raw={
            "cli_logged_in": bool(auth.get("logged_in")),
            "cli_auth_method": str(auth.get("auth_method") or ""),
            "subscription_type": str(auth.get("subscription_type") or ""),
            "limits": {
                "claude_subscription_8h_limit": limit_8h,
                "claude_subscription_week_limit": limit_week,
                "claude_limit_source": limit_source,
                "claude_subscription_tier": limit_tier,
            },
        },
    )


def _build_claude_snapshot() -> ProviderUsageSnapshot:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not api_key:
        fallback = _build_claude_snapshot_without_api_key()
        if fallback is not None:
            return fallback
        return ProviderUsageSnapshot(
            id=f"provider_claude_{int(time.time())}",
            provider="claude",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN to validate Claude provider access."],
        )

    models_url = os.getenv("ANTHROPIC_MODELS_URL", "https://api.anthropic.com/v1/models")
    try:
        with httpx.Client(timeout=8.0, headers=_anthropic_headers()) as client:
            response = client.get(models_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("claude", 0))
        if active > 0:
            snapshot = _runtime_task_runs_snapshot(
                provider="claude",
                kind="custom",
                active_runs=active,
                note=f"Claude models probe failed ({exc}); using runtime execution evidence fallback.",
            )
            snapshot.raw["probe_url"] = models_url
            return snapshot
        return ProviderUsageSnapshot(
            id=f"provider_claude_{int(time.time())}",
            provider="claude",
            kind="custom",
            status="degraded",
            data_source="provider_api",
            notes=[f"Claude models probe failed: {exc}"],
            raw={"probe_url": models_url},
        )

    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    snapshot = _build_models_visibility_snapshot(
        provider="claude",
        label="Claude visible models",
        models_url=models_url,
        rows=rows,
        headers=response.headers,
        request_limit_keys=("anthropic-ratelimit-requests-limit", "x-ratelimit-limit-requests"),
        request_remaining_keys=("anthropic-ratelimit-requests-remaining", "x-ratelimit-remaining-requests"),
        request_window="minute",
        request_label="Claude request quota",
        token_limit_keys=("anthropic-ratelimit-tokens-limit", "x-ratelimit-limit-tokens"),
        token_remaining_keys=("anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens"),
        token_window="minute",
        token_label="Claude token quota",
        rate_header_keys=(
            "anthropic-ratelimit-requests-limit",
            "anthropic-ratelimit-requests-remaining",
            "anthropic-ratelimit-tokens-limit",
            "anthropic-ratelimit-tokens-remaining",
        ),
        no_header_note="Claude models probe succeeded, but no request/token remaining headers were returned.",
    )
    probe_headers, probe_error = _claude_quota_probe_headers(_anthropic_headers())
    return _apply_quota_probe_to_snapshot(
        snapshot=snapshot,
        probe_headers=probe_headers,
        probe_error=probe_error,
        request_limit_keys=("anthropic-ratelimit-requests-limit", "x-ratelimit-limit-requests"),
        request_remaining_keys=("anthropic-ratelimit-requests-remaining", "x-ratelimit-remaining-requests"),
        request_label="Claude request quota",
        token_limit_keys=("anthropic-ratelimit-tokens-limit", "x-ratelimit-limit-tokens"),
        token_remaining_keys=("anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens"),
        token_label="Claude token quota",
        success_note="Quota headers sourced from lightweight Anthropic messages probe.",
        no_headers_note="Anthropic messages probe completed, but no request/token remaining headers were returned.",
        error_note_prefix="Anthropic messages quota probe failed",
    )


def _openrouter_headers() -> dict[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    site_url = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    site_title = os.getenv("OPENROUTER_X_TITLE", "").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_title:
        headers["X-Title"] = site_title
    return headers


def _openrouter_models_probe(models_url: str) -> tuple[dict[str, Any], httpx.Headers]:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=8.0, headers=_openrouter_headers()) as client:
            response = client.get(models_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        status_code = None
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = int(getattr(response, "status_code", 0) or 0) or None
        _record_external_tool_usage(
            tool_name="openrouter-api",
            provider="openrouter",
            operation="list_models",
            resource=models_url,
            status="error",
            http_status=status_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
            payload={"error": str(exc)},
        )
        raise

    _record_external_tool_usage(
        tool_name="openrouter-api",
        provider="openrouter",
        operation="list_models",
        resource=models_url,
        status="success",
        http_status=int(response.status_code),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return payload, response.headers


def _openrouter_probe_failure_snapshot(exc: Exception, *, models_url: str) -> ProviderUsageSnapshot:
    active = int(_active_provider_usage_counts().get("openrouter", 0))
    if active > 0:
        snapshot = _runtime_task_runs_snapshot(
            provider="openrouter",
            kind="custom",
            active_runs=active,
            note=f"OpenRouter models probe failed ({exc}); using runtime execution evidence fallback.",
        )
        snapshot.raw["probe_url"] = models_url
        return snapshot
    return ProviderUsageSnapshot(
        id=f"provider_openrouter_{int(time.time())}",
        provider="openrouter",
        kind="custom",
        status="degraded",
        data_source="provider_api",
        notes=[f"OpenRouter models probe failed: {exc}"],
        raw={"probe_url": models_url},
    )


def _build_openrouter_snapshot() -> ProviderUsageSnapshot:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        active = int(_active_provider_usage_counts().get("openrouter", 0))
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="openrouter",
                kind="custom",
                active_runs=active,
                note="Using runtime OpenRouter execution evidence (no direct OpenRouter key in environment).",
            )
        return ProviderUsageSnapshot(
            id=f"provider_openrouter_{int(time.time())}",
            provider="openrouter",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set OPENROUTER_API_KEY to validate OpenRouter provider access."],
        )

    models_url = os.getenv("OPENROUTER_MODELS_URL", "https://openrouter.ai/api/v1/models")
    try:
        payload, response_headers = _openrouter_models_probe(models_url)
    except Exception as exc:
        return _openrouter_probe_failure_snapshot(exc, models_url=models_url)

    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    return _build_models_visibility_snapshot(
        provider="openrouter",
        label="OpenRouter visible models",
        models_url=models_url,
        rows=rows,
        headers=response_headers,
        request_limit_keys=("x-ratelimit-limit", "ratelimit-limit", "x-ratelimit-limit-requests"),
        request_remaining_keys=("x-ratelimit-remaining", "ratelimit-remaining", "x-ratelimit-remaining-requests"),
        request_window="minute",
        request_label="OpenRouter request quota",
        token_limit_keys=("x-ratelimit-limit-tokens",),
        token_remaining_keys=("x-ratelimit-remaining-tokens",),
        token_window="minute",
        token_label="OpenRouter token quota",
        rate_header_keys=(
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "ratelimit-limit",
            "ratelimit-remaining",
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-tokens",
        ),
        no_header_note="OpenRouter models probe succeeded, but no request/token remaining headers were returned.",
    )


def _supabase_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _supabase_project_probe(token: str, project_url: str) -> tuple[dict[str, Any], httpx.Headers]:
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=8.0, headers=_supabase_headers(token)) as client:
            response = client.get(project_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        status_code = None
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = int(getattr(response, "status_code", 0) or 0) or None
        _record_external_tool_usage(
            tool_name="supabase-management-api",
            provider="supabase",
            operation="get_project",
            resource=project_url,
            status="error",
            http_status=status_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
            payload={"error": str(exc)},
        )
        raise

    _record_external_tool_usage(
        tool_name="supabase-management-api",
        provider="supabase",
        operation="get_project",
        resource=project_url,
        status="success",
        http_status=int(response.status_code),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return payload, response.headers


def _supabase_probe_failure_snapshot(
    exc: Exception,
    *,
    project_url: str,
    project_ref: str,
) -> ProviderUsageSnapshot:
    return ProviderUsageSnapshot(
        id=f"provider_supabase_{int(time.time())}",
        provider="supabase",
        kind="custom",
        status="degraded",
        data_source="provider_api",
        notes=[f"Supabase project probe failed: {exc}"],
        raw={"probe_url": project_url, "project_ref": project_ref},
    )


def _supabase_probe_metrics(headers: httpx.Headers) -> tuple[list[UsageMetric], list[str]]:
    metrics = [
        _metric(
            id="api_probe",
            label="Supabase API probe",
            unit="requests",
            used=1.0,
            window="probe",
        )
    ]
    has_limit_headers = _append_rate_limit_metrics(
        metrics=metrics,
        headers=headers,
        request_limit_keys=("x-ratelimit-limit", "ratelimit-limit"),
        request_remaining_keys=("x-ratelimit-remaining", "ratelimit-remaining"),
        request_window="hourly",
        request_label="Supabase API request quota",
    )
    notes: list[str] = []
    if not has_limit_headers:
        notes.append("Supabase probe succeeded, but no request remaining headers were returned.")

    egress_limit = _coerce_float(os.getenv("SUPABASE_EGRESS_LIMIT_GB"))
    egress_used = _coerce_float(os.getenv("SUPABASE_EGRESS_USED_GB"))
    if egress_limit is not None and egress_limit > 0:
        used = max(0.0, egress_used or 0.0)
        remaining = max(0.0, egress_limit - used)
        metrics.append(
            _metric(
                id="egress_quota",
                label="Supabase egress quota",
                unit="gb",
                used=used,
                remaining=remaining,
                limit=egress_limit,
                window=os.getenv("SUPABASE_EGRESS_WINDOW", "monthly"),
            )
        )
        notes.append("Using SUPABASE_EGRESS_LIMIT_GB/SUPABASE_EGRESS_USED_GB environment inputs for egress tracking.")

    return metrics, notes


def _build_supabase_snapshot() -> ProviderUsageSnapshot:
    token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip() or os.getenv("SUPABASE_TOKEN", "").strip()
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    if not token or not project_ref:
        return ProviderUsageSnapshot(
            id=f"provider_supabase_{int(time.time())}",
            provider="supabase",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set SUPABASE_ACCESS_TOKEN (or SUPABASE_TOKEN) and SUPABASE_PROJECT_REF."],
            raw={"missing_project_ref": not bool(project_ref), "missing_token": not bool(token)},
        )

    base_url = os.getenv("SUPABASE_MANAGEMENT_API_URL", "https://api.supabase.com/v1").rstrip("/")
    project_url = f"{base_url}/projects/{project_ref}"
    try:
        payload, response_headers = _supabase_project_probe(token, project_url)
    except Exception as exc:
        return _supabase_probe_failure_snapshot(exc, project_url=project_url, project_ref=project_ref)

    metrics, notes = _supabase_probe_metrics(response_headers)

    return ProviderUsageSnapshot(
        id=f"provider_supabase_{int(time.time())}",
        provider="supabase",
        kind="custom",
        status="ok",
        data_source="provider_api",
        metrics=metrics,
        notes=list(dict.fromkeys(notes)),
        raw={
            "probe_url": project_url,
            "project_ref": project_ref,
            "project_status": payload.get("status"),
            "project_region": payload.get("region"),
            "project_name": payload.get("name"),
            "rate_limit_headers": _subset_headers(
                response_headers,
                ("x-ratelimit-limit", "x-ratelimit-remaining", "ratelimit-limit", "ratelimit-remaining"),
            ),
        },
    )


def _append_db_host_window_metric(
    metrics: list[UsageMetric],
    *,
    metric_id: str,
    label: str,
    window_seconds: int,
    limit: int,
    window: str,
) -> None:
    if limit <= 0:
        return
    used = len(_runtime_events_within_window(window_seconds=window_seconds, source="api"))
    metrics.append(
        _metric(
            id=metric_id,
            label=label,
            unit="requests",
            used=float(min(used, limit)),
            remaining=float(max(0, limit - used)),
            limit=float(limit),
            window=window,
            validation_state="derived",
            validation_detail="Derived from API runtime-event counts and DB_HOST_* local limit configuration.",
            evidence_source="runtime_events+env_limits",
        )
    )


def _db_host_monthly_limit_gb() -> float | None:
    for env_name in ("DB_EGRESS_MONTHLY_LIMIT_GB", "DB_HOST_MONTHLY_EGRESS_LIMIT_GB", "SUPABASE_EGRESS_LIMIT_GB"):
        value = _coerce_float(os.getenv(env_name))
        if value is not None and value > 0:
            return float(value)
    return None


def _db_host_monthly_seed_gb() -> float:
    for env_name in ("DB_EGRESS_MONTHLY_USED_GB", "SUPABASE_EGRESS_USED_GB"):
        value = _coerce_float(os.getenv(env_name))
        if value is not None and value >= 0:
            return float(value)
    return 0.0


def _db_host_tracker_key(*, db_host: str, db_name: str) -> str:
    combined = f"{db_host or 'unknown'}:{db_name or 'unknown'}".strip().lower()
    normalized = re.sub(r"[^a-z0-9_.:-]+", "_", combined)
    return f"db_egress_tracker::{normalized}"


def _load_db_host_tracker_state(key: str) -> dict[str, Any]:
    try:
        raw = telemetry_persistence_service.get_meta_value(key)
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_db_host_tracker_state(key: str, payload: dict[str, Any]) -> None:
    try:
        telemetry_persistence_service.set_meta_value(key, json.dumps(payload, sort_keys=True))
    except Exception:
        return


def _db_host_egress_engine(db_url: str):
    if _DB_HOST_EGRESS_ENGINE_CACHE["engine"] is not None and _DB_HOST_EGRESS_ENGINE_CACHE["url"] == db_url:
        return _DB_HOST_EGRESS_ENGINE_CACHE["engine"]
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    elif db_url.startswith("postgres"):
        kwargs["connect_args"] = {
            "connect_timeout": max(1, min(_int_env("DB_EGRESS_DB_CONNECT_TIMEOUT_SECONDS", 3), 15))
        }
        kwargs["poolclass"] = NullPool
    engine = create_engine(db_url, **kwargs)
    _DB_HOST_EGRESS_ENGINE_CACHE["url"] = db_url
    _DB_HOST_EGRESS_ENGINE_CACHE["engine"] = engine
    return engine


def _collect_postgres_db_egress_sample(
    db_url: str,
    *,
    force_refresh: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    if "postgres" not in db_url.lower():
        return None, "db_not_postgresql"
    now = time.time()
    if (
        not force_refresh
        and _DB_HOST_EGRESS_SAMPLE_CACHE.get("url") == db_url
        and float(_DB_HOST_EGRESS_SAMPLE_CACHE.get("expires_at") or 0.0) > now
    ):
        cached_sample = _DB_HOST_EGRESS_SAMPLE_CACHE.get("sample")
        cached_error = str(_DB_HOST_EGRESS_SAMPLE_CACHE.get("error") or "").strip()
        return (cached_sample if isinstance(cached_sample, dict) else None), (cached_error or None)

    try:
        engine = _db_host_egress_engine(db_url)
        with engine.connect() as connection:
            stats_row = connection.execute(
                text(
                    """
                    SELECT
                        current_database() AS database_name,
                        COALESCE(tup_returned, 0) AS tup_returned,
                        COALESCE(tup_fetched, 0) AS tup_fetched,
                        stats_reset
                    FROM pg_stat_database
                    WHERE datname = current_database()
                    LIMIT 1
                    """
                )
            ).mappings().first()
            row_size = connection.execute(
                text(
                    """
                    SELECT
                        COALESCE(
                            SUM(pg_relation_size(c.oid)) / NULLIF(SUM(NULLIF(c.reltuples, 0)), 0),
                            0
                        ) AS avg_row_bytes
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'r'
                    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                    """
                )
            ).scalar()
        if not stats_row:
            raise RuntimeError("pg_stat_database row for current_database() was not found")
        stats_reset = stats_row.get("stats_reset")
        sample = {
            "database_name": str(stats_row.get("database_name") or "").strip(),
            "tup_returned": int(float(stats_row.get("tup_returned") or 0)),
            "tup_fetched": int(float(stats_row.get("tup_fetched") or 0)),
            "stats_reset": (stats_reset.isoformat() if isinstance(stats_reset, datetime) else str(stats_reset or "")),
            "avg_row_bytes": float(row_size or 0.0),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        _DB_HOST_EGRESS_SAMPLE_CACHE.update(
            {
                "url": db_url,
                "sample": sample,
                "error": "",
                "expires_at": now + _DB_HOST_EGRESS_SAMPLE_CACHE_TTL_SECONDS,
            }
        )
        return sample, None
    except Exception as exc:
        message = str(exc)
        _DB_HOST_EGRESS_SAMPLE_CACHE.update(
            {
                "url": db_url,
                "sample": None,
                "error": message,
                "expires_at": now + _DB_HOST_EGRESS_SAMPLE_CACHE_TTL_SECONDS,
            }
        )
        return None, message


def _estimate_db_host_monthly_bytes(
    *,
    state: dict[str, Any],
    month_key: str,
    seed_gb: float,
    current_returned: int,
    current_fetched: int,
    avg_row_bytes: float,
    safety_factor: float,
) -> tuple[float, int, list[str]]:
    notes: list[str] = []
    state_month = str(state.get("month") or "").strip()
    if state_month == month_key:
        estimated_monthly_bytes = max(0.0, _coerce_float(state.get("estimated_monthly_bytes")) or 0.0)
    else:
        estimated_monthly_bytes = max(0.0, seed_gb) * (1024.0 ** 3)
        if seed_gb > 0:
            notes.append("Seeded monthly DB egress estimate from DB_EGRESS_MONTHLY_USED_GB/SUPABASE_EGRESS_USED_GB.")

    previous_returned = _coerce_nonnegative_int(state.get("last_tup_returned"), default=current_returned)
    previous_fetched = _coerce_nonnegative_int(state.get("last_tup_fetched"), default=current_fetched)

    delta_rows = 0
    if state_month != month_key:
        notes.append("Initialized monthly DB egress tracker baseline for current month.")
    elif current_returned < previous_returned or current_fetched < previous_fetched:
        notes.append("Detected pg_stat_database counter reset; refreshed DB egress baseline.")
    else:
        delta_rows = max(0, current_returned - previous_returned) + max(0, current_fetched - previous_fetched)
        estimated_monthly_bytes += float(delta_rows) * avg_row_bytes * safety_factor
    return estimated_monthly_bytes, delta_rows, notes


def _db_host_context(db_url: str) -> tuple[str, str, str, dict[str, Any]]:
    parsed = urlparse(db_url)
    db_host = str(parsed.hostname or "").strip()
    db_name = str(parsed.path or "").strip().lstrip("/") or "default"
    db_engine = str(parsed.scheme or "").strip()
    if db_engine.endswith("+psycopg"):
        db_engine = db_engine.split("+", 1)[0]
    raw = {
        "database_host": db_host,
        "database_name": db_name,
        "database_engine": db_engine,
        "database_present": True,
    }
    return db_host, db_name, db_engine, raw


def _append_db_host_runtime_proxy_metrics(metrics: list[UsageMetric]) -> tuple[int, int]:
    api_events_24h = len(_runtime_events_within_window(window_seconds=24 * 60 * 60, source="api"))
    metrics.append(
        _metric(
            id="api_events_24h",
            label="API events touching DB host (24h)",
            unit="requests",
            used=float(api_events_24h),
            window="daily",
            validation_state="derived",
            validation_detail="Derived from API runtime-event counts as an egress-safe proxy for DB load.",
            evidence_source="runtime_events",
        )
    )

    limit_5h = max(0, _int_env("DB_HOST_5H_LIMIT", 0))
    limit_week = max(0, _int_env("DB_HOST_WEEK_LIMIT", 0))
    _append_db_host_window_metric(
        metrics,
        metric_id="db_host_window_5h",
        label="DB host request window (5h)",
        window_seconds=5 * 60 * 60,
        limit=limit_5h,
        window="hourly",
    )
    _append_db_host_window_metric(
        metrics,
        metric_id="db_host_window_week",
        label="DB host request window (7d)",
        window_seconds=7 * 24 * 60 * 60,
        limit=limit_week,
        window="weekly",
    )
    return limit_5h, limit_week


def _build_db_host_monthly_egress_metric(
    *,
    db_url: str,
    db_host: str,
    db_name: str,
) -> tuple[UsageMetric | None, dict[str, Any], list[str]]:
    sample, sample_error = _collect_postgres_db_egress_sample(db_url)
    if sample is None:
        return None, {"egress_measurement_mode": "runtime_event_proxy", "pg_sample_error": sample_error or ""}, []

    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    tracker_key = _db_host_tracker_key(db_host=db_host, db_name=db_name)
    state = _load_db_host_tracker_state(tracker_key)
    limit_gb = _db_host_monthly_limit_gb()
    seed_gb = _db_host_monthly_seed_gb()
    fallback_row_bytes = max(64.0, _coerce_float(os.getenv("DB_EGRESS_FALLBACK_BYTES_PER_ROW")) or 512.0)
    safety_factor = max(1.0, _coerce_float(os.getenv("DB_EGRESS_ESTIMATE_SAFETY_FACTOR")) or 1.25)
    avg_row_bytes = max(64.0, _coerce_float(sample.get("avg_row_bytes")) or fallback_row_bytes)

    current_returned = _coerce_nonnegative_int(sample.get("tup_returned"))
    current_fetched = _coerce_nonnegative_int(sample.get("tup_fetched"))
    estimated_monthly_bytes, delta_rows, notes = _estimate_db_host_monthly_bytes(
        state=state,
        month_key=month_key,
        seed_gb=seed_gb,
        current_returned=current_returned,
        current_fetched=current_fetched,
        avg_row_bytes=avg_row_bytes,
        safety_factor=safety_factor,
    )

    updated_state = {
        "month": month_key,
        "estimated_monthly_bytes": round(float(estimated_monthly_bytes), 3),
        "last_tup_returned": current_returned,
        "last_tup_fetched": current_fetched,
        "last_avg_row_bytes": round(float(avg_row_bytes), 3),
        "safety_factor": round(float(safety_factor), 4),
        "updated_at": now.isoformat(),
        "stats_reset": str(sample.get("stats_reset") or ""),
    }
    _save_db_host_tracker_state(tracker_key, updated_state)

    used_gb = max(0.0, estimated_monthly_bytes / (1024.0 ** 3))
    remaining_gb = max(0.0, limit_gb - used_gb) if limit_gb is not None and limit_gb > 0 else None
    if limit_gb is None:
        notes.append("Set DB_EGRESS_MONTHLY_LIMIT_GB (or DB_HOST_MONTHLY_EGRESS_LIMIT_GB) for hard monthly GB enforcement.")

    metric = _metric(
        id="db_host_egress_monthly_estimated",
        label="DB host estimated egress (monthly)",
        unit="gb",
        used=used_gb,
        remaining=remaining_gb,
        limit=limit_gb,
        window="monthly",
        validation_state="inferred",
        validation_detail=(
            "Estimated from pg_stat_database tuple deltas and relation-size-derived row bytes, "
            f"with safety factor {round(safety_factor, 3)}."
        ),
        evidence_source="pg_stat_database+telemetry_meta",
    )
    raw = {
        "egress_measurement_mode": "pg_stat_database_delta_estimate",
        "estimator_state_key": tracker_key,
        "monthly_limit_gb": limit_gb,
        "monthly_used_gb": round(used_gb, 6),
        "delta_rows_since_last_sample": int(delta_rows),
        "avg_row_bytes": round(avg_row_bytes, 3),
        "safety_factor": round(safety_factor, 4),
        "pg_stats_reset": str(sample.get("stats_reset") or ""),
        "pg_sample_collected_at": str(sample.get("collected_at") or ""),
    }
    return metric, raw, notes


def _build_db_host_snapshot() -> ProviderUsageSnapshot:
    db_url = (
        str(os.getenv("RUNTIME_DATABASE_URL", "")).strip()
        or str(os.getenv("DATABASE_URL", "")).strip()
    )
    if not db_url:
        return ProviderUsageSnapshot(
            id=f"provider_db_host_{int(time.time())}",
            provider="db-host",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set DATABASE_URL or RUNTIME_DATABASE_URL to track DB-host usage windows."],
        )

    db_host, db_name, _db_engine, raw = _db_host_context(db_url)
    metrics: list[UsageMetric] = []
    notes: list[str] = []
    monthly_metric, monthly_raw, monthly_notes = _build_db_host_monthly_egress_metric(
        db_url=db_url,
        db_host=db_host,
        db_name=db_name,
    )
    if monthly_metric is not None:
        metrics.append(monthly_metric)
    if isinstance(monthly_raw, dict):
        raw.update(monthly_raw)
    notes.extend(monthly_notes)

    limit_5h, limit_week = _append_db_host_runtime_proxy_metrics(metrics)

    if monthly_metric is None:
        notes.append("Monthly DB egress estimate unavailable; falling back to runtime event proxy metrics.")
    else:
        notes.append("DB-host monthly egress metric is estimated from PostgreSQL counters; request windows are safety proxies.")
    if limit_5h <= 0 and limit_week <= 0:
        notes.append("Set DB_HOST_5H_LIMIT and DB_HOST_WEEK_LIMIT for hard host-window tracking.")

    return ProviderUsageSnapshot(
        id=f"provider_db_host_{int(time.time())}",
        provider="db-host",
        kind="custom",
        status="ok",
        data_source="provider_api" if monthly_metric is not None else "runtime_events",
        metrics=metrics,
        notes=list(dict.fromkeys(notes)),
        raw=raw,
    )


def _claude_code_cli_available() -> bool:
    return shutil.which("claude") is not None


def _claude_code_cli_logged_in() -> tuple[bool, str]:
    """Check whether the local claude CLI has an active auth session.

    Returns (logged_in, auth_method) where auth_method is e.g. 'oauth_token' or ''.
    Uses `claude auth status --json`; falls back to False on any error.
    """
    if not _claude_code_cli_available():
        return False, ""
    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=8,
            env={**os.environ, "CLAUDECODE": ""},  # prevent nested-session guard
        )
        if result.returncode != 0:
            return False, ""
        data = json.loads(result.stdout.strip())
        if isinstance(data, dict) and data.get("loggedIn"):
            return True, str(data.get("authMethod", ""))
        return False, ""
    except Exception:
        return False, ""


def _build_claude_code_snapshot() -> ProviderUsageSnapshot:
    """Snapshot for the Claude Code CLI executor (claude -p)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    cli_available = _claude_code_cli_available()

    if not cli_available:
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="claude-code",
                kind="custom",
                active_runs=active,
                note="Claude Code CLI not found in PATH; using runtime execution evidence.",
            )
        return ProviderUsageSnapshot(
            id=f"provider_claude_code_{int(time.time())}",
            provider="claude-code",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Claude Code CLI ('claude') not found in PATH. Install via 'npm install -g @anthropic-ai/claude-code'."],
        )

    # Resolve auth method: env key > env OAuth token > local CLI session
    cli_logged_in, cli_auth_method = (False, "")
    if not api_key and not oauth_token:
        cli_logged_in, cli_auth_method = _claude_code_cli_logged_in()

    if not api_key and not oauth_token and not cli_logged_in:
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="claude-code",
                kind="custom",
                active_runs=active,
                note="Claude Code CLI available but no auth configured; using runtime execution evidence.",
            )
        return ProviderUsageSnapshot(
            id=f"provider_claude_code_{int(time.time())}",
            provider="claude-code",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set ANTHROPIC_API_KEY, CLAUDE_CODE_OAUTH_TOKEN, or run 'claude login' to authenticate."],
            raw={"cli_available": True},
        )

    if api_key:
        auth_method = "api_key"
    elif oauth_token:
        auth_method = "oauth_token_env"
    else:
        auth_method = f"cli_session:{cli_auth_method}" if cli_auth_method else "cli_session"

    # CLI is present and auth is resolved; probe the Anthropic models endpoint to confirm connectivity.
    # Only send auth headers when we have explicit env credentials — for CLI session, the probe
    # confirms network reachability; the CLI itself handles auth internally at execution time.
    models_url = os.getenv("ANTHROPIC_MODELS_URL", "https://api.anthropic.com/v1/models")
    probe_headers = _claude_code_headers() if (api_key or oauth_token) else {
        "anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
    }
    try:
        with httpx.Client(timeout=8.0, headers=probe_headers) as client:
            response = client.get(models_url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
    except Exception as exc:
        if cli_logged_in:
            # CLI session is confirmed; network probe failure is non-fatal.
            return ProviderUsageSnapshot(
                id=f"provider_claude_code_{int(time.time())}",
                provider="claude-code",
                kind="custom",
                status="ok",
                data_source="provider_cli",
                metrics=[_metric(id="api_probe", label="Claude Code CLI session", unit="requests", used=1.0, window="probe")],
                notes=[f"auth_method={auth_method}", f"models_probe_skipped:{exc}"],
                raw={"cli_available": True, "cli_logged_in": True},
            )
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            snapshot = _runtime_task_runs_snapshot(
                provider="claude-code",
                kind="custom",
                active_runs=active,
                note=f"Claude Code models probe failed ({exc}); using runtime execution evidence.",
            )
            snapshot.raw["cli_available"] = True
            return snapshot
        return ProviderUsageSnapshot(
            id=f"provider_claude_code_{int(time.time())}",
            provider="claude-code",
            kind="custom",
            status="degraded",
            data_source="provider_api",
            notes=[f"Claude Code models probe failed: {exc}"],
            raw={"probe_url": models_url, "cli_available": True},
        )

    rows = payload.get("data") if isinstance(payload.get("data"), list) else []
    snapshot = _build_models_visibility_snapshot(
        provider="claude-code",
        label="Claude Code visible models",
        models_url=models_url,
        rows=rows,
        headers=response.headers,
        request_limit_keys=("anthropic-ratelimit-requests-limit", "x-ratelimit-limit-requests"),
        request_remaining_keys=("anthropic-ratelimit-requests-remaining", "x-ratelimit-remaining-requests"),
        request_window="minute",
        request_label="Claude Code request quota",
        token_limit_keys=("anthropic-ratelimit-tokens-limit", "x-ratelimit-limit-tokens"),
        token_remaining_keys=("anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens"),
        token_window="minute",
        token_label="Claude Code token quota",
        rate_header_keys=(
            "anthropic-ratelimit-requests-limit",
            "anthropic-ratelimit-requests-remaining",
            "anthropic-ratelimit-tokens-limit",
            "anthropic-ratelimit-tokens-remaining",
        ),
        no_header_note="Claude Code models probe succeeded, but no rate-limit headers were returned.",
    )
    snapshot.raw["cli_available"] = True
    snapshot.raw["cli_logged_in"] = cli_logged_in
    snapshot.notes.append(f"auth_method={auth_method}")

    # Subscription usage limits (5h/weekly windows) are tracked server-side by Anthropic.
    # They are NOT exposed via API headers — only visible in the Anthropic console.
    # Strategy: use --max-budget-usd (CLAUDE_CODE_MAX_BUDGET_USD, default $2/run) to cap per-run cost.
    # Use --output-format json to capture per-model costUSD in task metadata for accumulation.
    max_budget = os.getenv("CLAUDE_CODE_MAX_BUDGET_USD", "2.00")
    snapshot.notes.append(
        f"Subscription usage limits (5h/weekly windows) are server-side only. "
        f"Per-run cap: --max-budget-usd ${max_budget} (CLAUDE_CODE_MAX_BUDGET_USD). "
        f"Set CLAUDE_CODE_MODEL=claude-sonnet-4-5-20250929 (SPEC/TEST/IMPL) and "
        f"CLAUDE_CODE_REVIEW_MODEL=claude-opus-4-5 (REVIEW/HEAL) to enable model-tier routing."
    )

    # Apply quota probe from messages endpoint if we have explicit API key credentials.
    # This gets real per-minute rate limit headers (not available from models GET endpoint).
    if api_key or oauth_token:
        quota_probe_headers, probe_error = _claude_quota_probe_headers(probe_headers)
        snapshot = _apply_quota_probe_to_snapshot(
            snapshot=snapshot,
            probe_headers=quota_probe_headers,
            probe_error=probe_error,
            request_limit_keys=("anthropic-ratelimit-requests-limit", "x-ratelimit-limit-requests"),
            request_remaining_keys=("anthropic-ratelimit-requests-remaining", "x-ratelimit-remaining-requests"),
            request_label="Claude Code API requests quota (per minute)",
            token_limit_keys=("anthropic-ratelimit-tokens-limit", "x-ratelimit-limit-tokens"),
            token_remaining_keys=("anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens"),
            token_label="Claude Code API token quota (per minute)",
            success_note="Rate limit headers sourced from Anthropic messages probe (not models endpoint).",
            no_headers_note="Anthropic messages probe completed, but no rate limit headers were returned.",
            error_note_prefix="Claude Code messages quota probe failed",
        )

    return snapshot


def _build_railway_snapshot() -> ProviderUsageSnapshot:
    token = os.getenv("RAILWAY_TOKEN", "").strip()
    project = os.getenv("RAILWAY_PROJECT_ID", "").strip()
    environment = os.getenv("RAILWAY_ENVIRONMENT", "").strip()
    service = os.getenv("RAILWAY_SERVICE", "").strip()
    if not token or not project or not environment or not service:
        if _railway_auth_available():
            return ProviderUsageSnapshot(
                id=f"provider_railway_{int(time.time())}",
                provider="railway",
                kind="custom",
                status="ok",
                data_source="provider_cli",
                metrics=[
                    _metric(
                        id="api_probe",
                        label="Railway CLI auth probe",
                        unit="requests",
                        used=1.0,
                        window="probe",
                    )
                ],
                notes=["Using Railway CLI auth session as execution evidence."],
                raw={"probe": "railway_cli_auth"},
            )
        return ProviderUsageSnapshot(
            id=f"provider_railway_{int(time.time())}",
            provider="railway",
            kind="custom",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set RAILWAY_TOKEN, RAILWAY_PROJECT_ID, RAILWAY_ENVIRONMENT, and RAILWAY_SERVICE."],
        )

    gql_url = os.getenv("RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2")
    query = {"query": "query { me { id } }"}
    headers = {"Authorization": f"Bearer {token}"}
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            response = client.post(gql_url, json=query)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
        _record_external_tool_usage(
            tool_name="railway-graphql",
            provider="railway",
            operation="probe_me",
            resource=gql_url,
            status="success",
            http_status=int(response.status_code),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:
        status_code = None
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = int(getattr(response, "status_code", 0) or 0) or None
        _record_external_tool_usage(
            tool_name="railway-graphql",
            provider="railway",
            operation="probe_me",
            resource=gql_url,
            status="error",
            http_status=status_code,
            duration_ms=int((time.perf_counter() - started) * 1000),
            payload={"error": str(exc)},
        )
        return ProviderUsageSnapshot(
            id=f"provider_railway_{int(time.time())}",
            provider="railway",
            kind="custom",
            status="degraded",
            data_source="provider_api",
            notes=[f"Railway API probe failed: {exc}"],
            raw={"probe_url": gql_url},
        )

    me = (payload.get("data") or {}).get("me") if isinstance(payload.get("data"), dict) else None
    ok = isinstance(me, dict) and bool(str(me.get("id") or "").strip())
    return _railway_api_probe_snapshot(ok=ok, response_headers=response.headers, gql_url=gql_url)


def _openai_headers() -> dict[str, str]:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"}
    org = os.getenv("OPENAI_ORG_ID", "").strip()
    if org:
        headers["OpenAI-Organization"] = org
    return headers


def _build_openai_snapshot() -> ProviderUsageSnapshot:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        oauth_ok, oauth_detail = _codex_oauth_available()
        active = int(_active_provider_usage_counts().get("openai", 0))
        if oauth_ok:
            if active > 0:
                return _runtime_task_runs_snapshot(
                    provider="openai",
                    kind="openai",
                    active_runs=active,
                    note=f"Using runtime OpenAI/Codex execution evidence with OAuth session ({oauth_detail}).",
                )
            return ProviderUsageSnapshot(
                id=f"provider_openai_{int(time.time())}",
                provider="openai",
                kind="openai",
                status="ok",
                data_source="configuration_only",
                notes=[f"Configured via Codex OAuth session ({oauth_detail})."],
                raw={"auth_mode": "oauth", "oauth_detail": oauth_detail},
            )
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="openai",
                kind="openai",
                active_runs=active,
                note="Using runtime OpenAI/Codex execution evidence (no direct OpenAI API key in environment).",
            )
        return ProviderUsageSnapshot(
            id=f"provider_openai_{int(time.time())}",
            provider="openai",
            kind="openai",
            status="unavailable",
            data_source="configuration_only",
            notes=["Set OPENAI_ADMIN_API_KEY (preferred) or OPENAI_API_KEY to enable usage collection."],
        )

    now = int(time.time())
    start_time = int(os.getenv("OPENAI_USAGE_START_TIME_UNIX", str(now - 30 * 24 * 3600)))
    usage_url = os.getenv(
        "OPENAI_USAGE_URL",
        "https://api.openai.com/v1/organization/usage/completions",
    )
    costs_url = os.getenv("OPENAI_COSTS_URL", "https://api.openai.com/v1/organization/costs")
    headers = _openai_headers()

    usage_payload: dict[str, Any] = {}
    cost_payload: dict[str, Any] = {}
    usage_error = None
    cost_error = None
    usage_status_code: int | None = None
    cost_status_code: int | None = None
    usage_duration_ms = 0
    cost_duration_ms = 0
    usage_started = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            usage_response = client.get(usage_url, params={"start_time": start_time, "end_time": now})
            usage_response.raise_for_status()
            usage_payload = usage_response.json() if isinstance(usage_response.json(), dict) else {}
            usage_status_code = int(usage_response.status_code)
    except Exception as exc:
        usage_error = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            usage_status_code = int(getattr(response, "status_code", 0) or 0) or None
    usage_duration_ms = int((time.perf_counter() - usage_started) * 1000)
    _record_external_tool_usage(
        tool_name="openai-api",
        provider="openai",
        operation="organization_usage_completions",
        resource=usage_url,
        status="success" if usage_error is None else "error",
        http_status=usage_status_code,
        duration_ms=usage_duration_ms,
        payload={"window_start_unix": start_time, "window_end_unix": now},
    )

    cost_started = time.perf_counter()
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            costs_response = client.get(costs_url, params={"start_time": start_time, "end_time": now})
            costs_response.raise_for_status()
            cost_payload = costs_response.json() if isinstance(costs_response.json(), dict) else {}
            cost_status_code = int(costs_response.status_code)
    except Exception as exc:
        cost_error = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            cost_status_code = int(getattr(response, "status_code", 0) or 0) or None
    cost_duration_ms = int((time.perf_counter() - cost_started) * 1000)
    _record_external_tool_usage(
        tool_name="openai-api",
        provider="openai",
        operation="organization_costs",
        resource=costs_url,
        status="success" if cost_error is None else "error",
        http_status=cost_status_code,
        duration_ms=cost_duration_ms,
        payload={"window_start_unix": start_time, "window_end_unix": now},
    )

    records = usage_payload.get("data") if isinstance(usage_payload.get("data"), list) else []
    input_tokens = 0.0
    output_tokens = 0.0
    requests = 0.0
    for row in records:
        if not isinstance(row, dict):
            continue
        input_tokens += float(row.get("input_tokens") or 0.0)
        output_tokens += float(row.get("output_tokens") or 0.0)
        requests += float(row.get("num_model_requests") or row.get("requests") or 0.0)

    total_cost_usd = 0.0
    cost_rows = cost_payload.get("data") if isinstance(cost_payload.get("data"), list) else []
    for row in cost_rows:
        if not isinstance(row, dict):
            continue
        amount = row.get("amount")
        if isinstance(amount, dict):
            total_cost_usd += float(amount.get("value") or 0.0)
        else:
            total_cost_usd += float(row.get("cost") or row.get("total_cost") or 0.0)

    notes: list[str] = []
    status = "ok"
    if usage_error and cost_error:
        status = "degraded"
        notes.append(f"OpenAI usage/cost fetch failed: usage={usage_error}; costs={cost_error}")
    elif usage_error:
        status = "degraded"
        notes.append(f"OpenAI usage fetch failed: {usage_error}")
    elif cost_error:
        status = "degraded"
        notes.append(f"OpenAI costs fetch failed: {cost_error}")

    metrics = []
    if input_tokens + output_tokens > 0:
        metrics.append(
            _metric(
                id="tokens_total",
                label="OpenAI tokens (input+output)",
                unit="tokens",
                used=input_tokens + output_tokens,
                window="rolling_30d",
            )
        )
    if requests > 0:
        metrics.append(
            _metric(
                id="requests_total",
                label="OpenAI model requests",
                unit="requests",
                used=requests,
                window="rolling_30d",
            )
        )

    # Best-effort fallback: when org usage APIs are unavailable, attempt quota headers from a tiny responses probe.
    if usage_error and cost_error:
        try:
            probe_headers, probe_error = _openai_quota_probe_headers(headers)
            if probe_headers is None:
                raise RuntimeError(probe_error or "openai_quota_probe_unavailable")
            has_model_limits = _append_rate_limit_metrics(
                metrics=metrics,
                headers=probe_headers,
                request_limit_keys=("x-ratelimit-limit-requests",),
                request_remaining_keys=("x-ratelimit-remaining-requests",),
                request_window="minute",
                request_label="OpenAI request quota",
                token_limit_keys=("x-ratelimit-limit-tokens",),
                token_remaining_keys=("x-ratelimit-remaining-tokens",),
                token_window="minute",
                token_label="OpenAI token quota",
            )
            if has_model_limits:
                notes.append("Using OpenAI responses probe rate-limit headers as best-effort fallback for remaining quota.")
        except Exception as exc:
            response = getattr(exc, "response", None)
            status_code = None
            if response is not None:
                status_code = int(getattr(response, "status_code", 0) or 0) or None
            _record_external_tool_usage(
                tool_name="openai-api",
                provider="openai",
                operation="responses_quota_probe_fallback",
                resource=os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"),
                status="error",
                http_status=status_code,
                payload={"error": str(exc)},
            )
            notes.append(f"OpenAI responses fallback probe failed: {exc}")

    return ProviderUsageSnapshot(
        id=f"provider_openai_{int(time.time())}",
        provider="openai",
        kind="openai",
        status=status,  # type: ignore[arg-type]
        data_source="provider_api",
        metrics=metrics,
        cost_usd=round(total_cost_usd, 6) if total_cost_usd > 0 else None,
        notes=notes,
        raw={
            "usage_records": len(records),
            "cost_records": len(cost_rows),
            "window_start_unix": start_time,
            "window_end_unix": now,
            "usage_url": usage_url,
            "costs_url": costs_url,
        },
    )


def _collect_provider_snapshots() -> list[ProviderUsageSnapshot]:
    active_usage = _active_provider_usage_counts()
    providers = [
        _build_internal_snapshot(),
        _build_claude_snapshot(),
        _build_claude_code_snapshot(),
        _build_github_snapshot(),
        _build_openai_snapshot(),
        _build_openrouter_snapshot(),
        _build_config_only_snapshot("anthropic"),
        _build_config_only_snapshot("openclaw"),
        _build_cursor_snapshot(),
        _build_db_host_snapshot(),
        _build_railway_snapshot(),
    ]
    if _supabase_tracking_enabled():
        providers.append(_build_supabase_snapshot())
    for snapshot in providers:
        _append_codex_subscription_metrics(snapshot)
        active_count = int(active_usage.get(_normalize_provider_name(snapshot.provider), 0))
        if active_count > 0:
            has_metric = any(metric.id == "runtime_task_runs" for metric in snapshot.metrics)
            if not has_metric:
                snapshot.metrics.append(
                    _metric(
                        id="runtime_task_runs",
                        label="Runtime task runs",
                        unit="tasks",
                        used=float(active_count),
                        window="rolling",
                        validation_state="derived",
                        validation_detail="Derived from runtime telemetry events; not a provider-reported quota value.",
                        evidence_source="runtime_events",
                    )
                )
            snapshot.raw["runtime_task_runs"] = active_count
            if snapshot.status != "ok":
                snapshot.notes.append(
                    "provider observed in runtime usage but key/config is missing or provider checks are failing"
                )
                snapshot.notes = list(dict.fromkeys(snapshot.notes))
        snapshot = _finalize_snapshot(snapshot)
        _store_snapshot(snapshot)
    return providers


def _provider_limit_telemetry_state(snapshot: ProviderUsageSnapshot) -> dict[str, Any]:
    quota_metrics = [metric for metric in snapshot.metrics if metric.limit is not None and metric.limit > 0]
    with_remaining = [metric for metric in quota_metrics if metric.remaining is not None]
    validated_with_remaining = [
        metric
        for metric in with_remaining
        if str(metric.validation_state or "").strip().lower() == "validated"
    ]
    validated_quota = [
        metric
        for metric in quota_metrics
        if str(metric.validation_state or "").strip().lower() == "validated"
    ]

    if not quota_metrics:
        state = "missing_limits"
    elif not with_remaining:
        state = "missing_remaining"
    elif validated_with_remaining:
        state = "hard_limit_ready"
    else:
        state = "derived_or_unvalidated"

    return {
        "state": state,
        "has_limit_metrics": bool(quota_metrics),
        "has_remaining_metrics": bool(with_remaining),
        "has_validated_quota": bool(validated_quota),
        "has_validated_remaining": bool(validated_with_remaining),
        "quota_metric_ids": sorted({metric.id for metric in quota_metrics}),
        "evidence_sources": sorted(
            {
                str(metric.evidence_source).strip()
                for metric in quota_metrics
                if str(metric.evidence_source or "").strip()
            }
        ),
    }


def _limit_coverage_summary(
    providers: list[ProviderUsageSnapshot],
    *,
    required_providers: list[str] | None = None,
    active_usage_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    candidates = [p for p in providers if _normalize_provider_name(p.provider) != "coherence-internal"]
    with_limit: list[str] = []
    with_remaining: list[str] = []
    with_validated_remaining: list[str] = []
    missing: list[str] = []
    partial: list[str] = []

    required = {
        _normalize_provider_name(name)
        for name in (required_providers or [])
        if _normalize_provider_name(name)
    }
    active_counts = {
        _normalize_provider_name(name): int(value)
        for name, value in (active_usage_counts or {}).items()
        if _normalize_provider_name(name)
    }

    required_or_active_status: dict[str, dict[str, Any]] = {}
    required_or_active_missing_hard: list[str] = []
    for provider in candidates:
        provider_name = _normalize_provider_name(provider.provider)
        telemetry = _provider_limit_telemetry_state(provider)
        has_limit = bool(telemetry.get("has_limit_metrics"))
        has_remaining = bool(telemetry.get("has_remaining_metrics"))
        has_validated_remaining = bool(telemetry.get("has_validated_remaining"))

        if has_limit:
            with_limit.append(provider.provider)
        if has_remaining:
            with_remaining.append(provider.provider)
        if has_validated_remaining:
            with_validated_remaining.append(provider.provider)
        if has_limit and not has_remaining:
            partial.append(provider.provider)
        if not has_limit:
            missing.append(provider.provider)

        active_usage = max(0, int(active_counts.get(provider_name, 0)))
        is_required = provider_name in required
        is_required_or_active = is_required or active_usage > 0
        if not is_required_or_active:
            continue

        required_or_active_status[provider_name] = {
            "state": str(telemetry.get("state") or "missing_limits"),
            "required": is_required,
            "active_usage": active_usage,
            "has_limit_metrics": has_limit,
            "has_remaining_metrics": has_remaining,
            "has_validated_remaining": has_validated_remaining,
            "quota_metric_ids": list(telemetry.get("quota_metric_ids") or []),
            "evidence_sources": list(telemetry.get("evidence_sources") or []),
        }
        if not has_validated_remaining:
            required_or_active_missing_hard.append(provider_name)

    required_or_active_list = sorted(required_or_active_status.keys())
    missing_hard_sorted = sorted(set(required_or_active_missing_hard))
    return {
        "providers_considered": len(candidates),
        "providers_with_limit_metrics": len(with_limit),
        "providers_with_remaining_metrics": len(with_remaining),
        "providers_with_validated_remaining_metrics": len(with_validated_remaining),
        "providers_missing_limit_metrics": sorted(set(missing)),
        "providers_partial_limit_metrics": sorted(set(partial)),
        "coverage_ratio": round((len(with_limit) / len(candidates)), 4) if candidates else 1.0,
        "hard_limit_coverage_ratio": (
            round((len(with_validated_remaining) / len(candidates)), 4) if candidates else 1.0
        ),
        "required_or_active_providers": required_or_active_list,
        "required_or_active_provider_status": required_or_active_status,
        "required_or_active_missing_hard_limit_telemetry": missing_hard_sorted,
        "hard_limit_claim_ready": len(missing_hard_sorted) == 0,
    }


def collect_usage_overview(force_refresh: bool = False) -> ProviderUsageOverview:
    now = time.time()
    if (
        not force_refresh
        and _CACHE.get("overview") is not None
        and float(_CACHE.get("expires_at") or 0.0) > now
    ):
        return ProviderUsageOverview(**_CACHE["overview"])

    providers = _collect_provider_snapshots()
    required_providers = _required_providers_from_env()
    active_usage = _active_provider_usage_counts()
    unavailable = [p.provider for p in providers if p.status != "ok"]
    overview = ProviderUsageOverview(
        providers=providers,
        unavailable_providers=unavailable,
        tracked_providers=len(providers),
        limit_coverage=_limit_coverage_summary(
            providers,
            required_providers=required_providers,
            active_usage_counts=active_usage,
        ),
    )
    _CACHE["overview"] = overview.model_dump(mode="json")
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return overview


def compact_usage_overview_payload(
    overview: ProviderUsageOverview,
    *,
    include_raw: bool = False,
    max_metrics_per_provider: int = 16,
    max_notes_per_provider: int = 4,
    max_official_records: int = 4,
) -> dict[str, Any]:
    payload = overview.model_dump(mode="json")
    providers = payload.get("providers")
    if not isinstance(providers, list):
        return payload

    bounded_metrics = max(1, min(int(max_metrics_per_provider), 64))
    bounded_notes = max(0, min(int(max_notes_per_provider), 16))
    bounded_records = max(0, min(int(max_official_records), 16))

    compacted: list[dict[str, Any]] = []
    for row in providers:
        if not isinstance(row, dict):
            continue
        normalized = dict(row)

        metrics = normalized.get("metrics")
        if isinstance(metrics, list):
            trimmed_metrics: list[dict[str, Any]] = []
            for metric in metrics[:bounded_metrics]:
                if not isinstance(metric, dict):
                    continue
                metric_row = dict(metric)
                metric_row["validation_detail"] = _truncate_text(
                    metric_row.get("validation_detail"), max_len=200
                )
                trimmed_metrics.append(metric_row)
            normalized["metrics"] = trimmed_metrics

        notes = normalized.get("notes")
        if isinstance(notes, list):
            normalized["notes"] = [
                _truncate_text(item, max_len=180)
                for item in notes[:bounded_notes]
                if str(item or "").strip()
            ]

        official_records = normalized.get("official_records")
        if isinstance(official_records, list):
            normalized["official_records"] = [
                str(item).strip()
                for item in official_records[:bounded_records]
                if str(item or "").strip()
            ]

        if not include_raw:
            normalized["raw"] = {}
        else:
            raw_row = normalized.get("raw")
            if isinstance(raw_row, dict):
                normalized["raw"] = {
                    key: value
                    for key, value in raw_row.items()
                    if key in {
                        "database_host",
                        "database_name",
                        "database_engine",
                        "egress_measurement_mode",
                        "monthly_limit_gb",
                        "monthly_used_gb",
                        "delta_rows_since_last_sample",
                        "avg_row_bytes",
                        "safety_factor",
                    }
                }
            else:
                normalized["raw"] = {}

        compacted.append(normalized)

    payload["providers"] = compacted
    return payload


def list_usage_snapshots(limit: int = 200) -> list[ProviderUsageSnapshot]:
    rows = _read_store()
    out: list[ProviderUsageSnapshot] = []
    for row in rows:
        try:
            out.append(ProviderUsageSnapshot(**row))
        except Exception:
            continue
    out.sort(key=lambda r: r.collected_at, reverse=True)
    return out[: max(1, min(limit, 2000))]


def list_external_tool_usage_events(
    limit: int = 200,
    *,
    provider: str | None = None,
    tool_name: str | None = None,
) -> list[dict[str, Any]]:
    provider_value = provider.strip() if isinstance(provider, str) and provider.strip() else None
    tool_value = tool_name.strip() if isinstance(tool_name, str) and tool_name.strip() else None
    return telemetry_persistence_service.list_external_tool_usage_events(
        limit=max(1, min(limit, 5000)),
        provider=provider_value,
        tool_name=tool_value,
    )


def _is_openai_permission_gated(notes: list[str]) -> bool:
    joined = " | ".join(str(note).lower() for note in notes)
    return "openai usage/cost fetch failed" in joined and "403" in joined


def _append_usage_alerts_for_provider(
    *,
    provider: ProviderUsageSnapshot,
    provider_name: str,
    required: set[str],
    active_usage: int,
    ratio: float,
    alerts: list[UsageAlert],
    seen_alert_ids: set[str],
) -> None:
    should_alert_status = provider.status != "ok"
    if provider_name not in required and active_usage <= 0:
        should_alert_status = False
    if (
        provider_name == "openai"
        and provider.status == "degraded"
        and _is_openai_permission_gated(provider.notes)
    ):
        should_alert_status = False

    if should_alert_status:
        alert_id = f"usage_alert_{provider.provider}_unavailable"
        if alert_id not in seen_alert_ids:
            alerts.append(
                UsageAlert(
                    id=alert_id,
                    provider=provider.provider,
                    metric_id="provider_status",
                    severity="warning" if provider.status == "degraded" else "critical",
                    message=_trim_usage_alert_message(
                        f"{provider.provider} usage provider status={provider.status}"
                    ),
                )
            )
            seen_alert_ids.add(alert_id)

    for metric in provider.metrics:
        if metric.limit is None or metric.limit <= 0 or metric.remaining is None:
            continue
        remaining_ratio = metric.remaining / metric.limit
        if remaining_ratio > ratio:
            continue
        severity = "critical" if remaining_ratio <= ratio / 2.0 else "warning"
        alert_id = f"usage_alert_{provider.provider}_{metric.id}"
        if alert_id in seen_alert_ids:
            continue
        alerts.append(
            UsageAlert(
                id=alert_id,
                provider=provider.provider,
                metric_id=metric.id,
                severity=severity,  # type: ignore[arg-type]
                message=_trim_usage_alert_message(
                    f"{provider.provider} {metric.label} low remaining: "
                    f"{round(metric.remaining, 2)} / {round(metric.limit, 2)}"
                ),
                remaining_ratio=round(remaining_ratio, 4),
            )
        )
        seen_alert_ids.add(alert_id)

    has_limit_with_remaining = any(
        metric.limit is not None and metric.limit > 0 and metric.remaining is not None
        for metric in provider.metrics
    )
    if (provider_name in required or active_usage > 0) and not has_limit_with_remaining:
        alert_id = f"usage_alert_{provider.provider}_remaining_tracking_gap"
        if alert_id not in seen_alert_ids:
            alerts.append(
                UsageAlert(
                    id=alert_id,
                    provider=provider.provider,
                    metric_id="remaining_tracking_gap",
                    severity="warning" if provider_name in required else "info",
                    message=_trim_usage_alert_message(
                        f"{provider.provider} has no remaining/limit telemetry. "
                        "Configure quota metrics to track usage remaining before reset windows."
                    ),
                )
            )
            seen_alert_ids.add(alert_id)


def _append_readiness_alerts(
    *,
    readiness: ProviderReadinessReport,
    alerts: list[UsageAlert],
    seen_alert_ids: set[str],
) -> None:
    for row in readiness.providers:
        provider_name = _normalize_provider_name(row.provider)
        if not row.required:
            continue
        if row.status == "ok" and row.configured:
            continue

        severity: str = "warning" if row.status == "degraded" else "critical"
        notes = list(row.notes)
        if provider_name == "openai" and _is_openai_permission_gated(notes):
            severity = "warning"

        alert_id = f"usage_alert_{provider_name}_readiness"
        if alert_id in seen_alert_ids:
            continue
        alerts.append(
            UsageAlert(
                id=alert_id,
                provider=provider_name,
                metric_id="provider_readiness",
                severity=severity,  # type: ignore[arg-type]
                message=_trim_usage_alert_message(
                    f"{provider_name} readiness blocking: status={row.status}, configured={row.configured}. "
                    f"Notes: {', '.join(notes[:2]) if notes else 'none'}"
                ),
            )
        )
        seen_alert_ids.add(alert_id)


def evaluate_usage_alerts(threshold_ratio: float = 0.2, *, force_refresh: bool = False) -> UsageAlertReport:
    ratio = max(0.0, min(float(threshold_ratio), 1.0))
    overview = collect_usage_overview(force_refresh=force_refresh)
    readiness = provider_readiness_report(force_refresh=force_refresh)
    required = set(_required_providers_from_env())
    active_counts = _active_provider_usage_counts()

    alerts: list[UsageAlert] = []
    seen_alert_ids: set[str] = set()
    for provider in overview.providers:
        provider_name = _normalize_provider_name(provider.provider)
        _append_usage_alerts_for_provider(
            provider=provider,
            provider_name=provider_name,
            required=required,
            active_usage=int(active_counts.get(provider_name, 0)),
            ratio=ratio,
            alerts=alerts,
            seen_alert_ids=seen_alert_ids,
        )
    _append_readiness_alerts(
        readiness=readiness,
        alerts=alerts,
        seen_alert_ids=seen_alert_ids,
    )

    return UsageAlertReport(threshold_ratio=ratio, alerts=alerts)


def _latest_provider_snapshots(limit: int = 800) -> dict[str, ProviderUsageSnapshot]:
    rows = list_usage_snapshots(limit=max(10, min(int(limit), 2000)))
    by_provider: dict[str, ProviderUsageSnapshot] = {}
    for row in rows:
        provider = _provider_family_name(row.provider)
        if not provider or provider in by_provider:
            continue
        by_provider[provider] = row
    return by_provider


def usage_overview_from_snapshots() -> ProviderUsageOverview:
    by_provider = _latest_provider_snapshots(limit=1000)
    providers = [by_provider[key] for key in sorted(by_provider.keys())]
    unavailable = [row.provider for row in providers if row.status != "ok"]
    required_providers = _required_providers_from_env()
    active_usage = _active_provider_usage_counts()
    return ProviderUsageOverview(
        providers=providers,
        unavailable_providers=unavailable,
        tracked_providers=len(providers),
        limit_coverage=_limit_coverage_summary(
            providers,
            required_providers=required_providers,
            active_usage_counts=active_usage,
        ),
    )


def usage_endpoint_timeout_seconds(default: float = 10.0) -> float:
    parsed = _coerce_float(os.getenv("AUTOMATION_USAGE_ENDPOINT_TIMEOUT_SECONDS"))
    if parsed is None:
        return max(0.1, min(float(default), 10.0))
    return max(0.1, min(float(parsed), 300.0))


def daily_system_summary(
    *,
    window_hours: int = 24,
    top_n: int = 3,
    force_refresh: bool = False,
) -> dict[str, Any]:
    window_seconds = max(3600, min(int(window_hours) * 3600, 30 * 24 * 3600))
    top_count = max(1, min(int(top_n), 20))
    try:
        host_observability_backfill = agent_service.backfill_host_runner_failure_observability(
            window_hours=max(1, int(window_seconds / 3600))
        )
    except Exception:
        host_observability_backfill = {
            "window_hours": max(1, int(window_seconds / 3600)),
            "host_failed_tasks": 0,
            "completion_events_backfilled": 0,
            "friction_events_backfilled": 0,
            "affected_task_ids": [],
            "error": "backfill_failed",
        }
    usage = agent_service.get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}
    host_runner = usage.get("host_runner") if isinstance(usage.get("host_runner"), dict) else {}

    try:
        from app.services import friction_service

        friction_events, _ignored = friction_service.load_events()
        friction_summary = friction_service.summarize(
            friction_events,
            window_days=max(1, int(round(window_seconds / 86400))),
        )
        friction_entry_points = friction_service.friction_entry_points(
            window_days=max(1, int(round(window_seconds / 86400))),
            limit=20,
        )
    except Exception:
        friction_summary = {
            "total_events": 0,
            "open_events": 0,
            "total_energy_loss": 0.0,
            "total_cost_of_delay": 0.0,
            "top_block_types": [],
            "top_stages": [],
        }
        friction_entry_points = {"entry_points": []}

    worker_events = _runtime_events_within_window(window_seconds=window_seconds, source="worker")
    worker_total = len(worker_events)
    worker_failed = sum(1 for event in worker_events if int(getattr(event, "status_code", 0) or 0) >= 400)
    tool_counts: dict[str, dict[str, int]] = {}
    for event in worker_events:
        endpoint = str(getattr(event, "endpoint", "") or "").strip() or "unknown"
        row = tool_counts.setdefault(endpoint, {"count": 0, "failed": 0})
        row["count"] += 1
        if int(getattr(event, "status_code", 0) or 0) >= 400:
            row["failed"] += 1
    top_tools = sorted(
        (
            {"tool": tool, "events": values["count"], "failed": values["failed"]}
            for tool, values in tool_counts.items()
        ),
        key=lambda row: (row["events"], row["failed"]),
        reverse=True,
    )[: max(5, top_count)]

    try:
        from app.services import runtime_service

        attention = runtime_service.summarize_endpoint_attention(
            seconds=window_seconds,
            min_event_count=1,
            limit=max(20, top_count),
        )
        top_attention = [
            {
                "endpoint": row.endpoint,
                "events": row.event_count,
                "attention_score": row.attention_score,
                "runtime_cost_estimate": row.runtime_cost_estimate,
                "friction_event_count": row.friction_event_count,
            }
            for row in attention.endpoints[:top_count]
        ]
    except Exception:
        top_attention = []

    latest_provider_rows = _latest_provider_snapshots(limit=1000)
    if not latest_provider_rows:
        overview = collect_usage_overview(force_refresh=force_refresh)
        latest_provider_rows = {
            _normalize_provider_name(row.provider): row
            for row in overview.providers
            if _normalize_provider_name(row.provider)
        }

    provider_priority = ["github", "openai", "openrouter", "railway", "db-host", "coherence-internal"]
    ordered_provider_keys = sorted(
        latest_provider_rows.keys(),
        key=lambda name: (provider_priority.index(name) if name in provider_priority else 999, name),
    )
    providers: list[dict[str, Any]] = []
    for provider_name in ordered_provider_keys:
        row = latest_provider_rows[provider_name]
        if _normalize_provider_name(row.provider) == "openai":
            _append_codex_subscription_metrics(row)
        metric = _summary_metric(row.metrics)
        providers.append(
            {
                "provider": _normalize_provider_name(row.provider),
                "status": row.status,
                "data_source": row.data_source,
                "usage": (
                    {
                        "label": metric.label,
                        "used": metric.used,
                        "unit": metric.unit,
                        "remaining": metric.remaining,
                        "limit": metric.limit,
                        "window": metric.window,
                        "validation_state": metric.validation_state,
                        "validation_detail": metric.validation_detail,
                        "evidence_source": metric.evidence_source,
                    }
                    if metric is not None
                    else None
                ),
                "notes": row.notes[:2],
            }
        )

    host_failed = int(host_runner.get("failed_runs") or 0)
    friction_total = int(friction_summary.get("total_events") or 0)
    contract_gaps: list[str] = []
    if host_failed > friction_total:
        contract_gaps.append(
            f"failed host-runner tasks ({host_failed}) exceed friction events ({friction_total})"
        )
    if host_failed > worker_failed:
        contract_gaps.append(
            f"failed host-runner tasks ({host_failed}) exceed failed worker tool events ({worker_failed})"
        )
    if int(execution.get("tracked_runs") or 0) == 0 and int(host_runner.get("total_runs") or 0) > 0:
        contract_gaps.append("execution tracked_runs is zero while host-runner task runs exist")
    codex_row = next((row for row in providers if row.get("provider") == "openai"), None)
    codex_usage = codex_row.get("usage") if isinstance(codex_row, dict) else None
    codex_validation = (
        str(codex_usage.get("validation_state") or "").strip().lower()
        if isinstance(codex_usage, dict)
        else ""
    )
    if codex_usage and codex_validation and codex_validation != "validated":
        contract_gaps.append(
            "openai usage is derived from runtime telemetry/local limits; provider hard quota headers/API not available."
        )
    quality_awareness = quality_awareness_service.build_quality_awareness_summary(
        top_n=top_count,
        force_refresh=force_refresh,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": int(window_seconds / 3600),
        "host_failure_observability_backfill": host_observability_backfill,
        "host_runner": host_runner,
        "execution": {
            "tracked_runs": int(execution.get("tracked_runs") or 0),
            "failed_runs": int(execution.get("failed_runs") or 0),
            "success_runs": int(execution.get("success_runs") or 0),
            "coverage": execution.get("coverage") if isinstance(execution.get("coverage"), dict) else {},
        },
        "tool_usage": {
            "worker_events": worker_total,
            "worker_failed_events": worker_failed,
            "top_tools": top_tools,
        },
        "friction": {
            "total_events": friction_total,
            "open_events": int(friction_summary.get("open_events") or 0),
            "top_block_types": list(friction_summary.get("top_block_types") or [])[:top_count],
            "top_stages": list(friction_summary.get("top_stages") or [])[:top_count],
            "entry_points": list(friction_entry_points.get("entry_points") or [])[:top_count],
        },
        "providers": providers,
        "top_attention_areas": top_attention,
        "contract_gaps": contract_gaps,
        "quality_awareness": quality_awareness,
    }


def _provider_limit_guard_result(
    *,
    allowed: bool,
    provider: str,
    reason: str,
    blocked_metrics: list[dict[str, Any]] | None = None,
    evaluated_metrics: list[dict[str, Any]] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "allowed": bool(allowed),
        "provider": provider,
        "reason": reason,
        "blocked_metrics": list(blocked_metrics or []),
        "evaluated_metrics": list(evaluated_metrics or []),
    }
    if status is not None:
        payload["status"] = status
    return payload


def _provider_snapshot_for_guard(
    provider: str,
    *,
    force_refresh: bool,
) -> ProviderUsageSnapshot | None:
    overview = collect_usage_overview(force_refresh=force_refresh)
    return next(
        (
            row
            for row in overview.providers
            if _normalize_provider_name(row.provider) == provider
        ),
        None,
    )


def _provider_guard_thresholds(provider: str) -> dict[str, float]:
    defaults = _provider_window_guard_ratio_defaults()
    policy = _provider_window_guard_ratio_policy(defaults)
    thresholds = dict(policy.get("default", defaults))
    overrides = policy.get(provider)
    if isinstance(overrides, dict):
        thresholds.update(overrides)
    return thresholds


def _evaluate_provider_guard_metrics(
    *,
    snapshot: ProviderUsageSnapshot,
    thresholds: dict[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evaluated: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for metric in snapshot.metrics:
        if metric.limit is None or metric.limit <= 0 or metric.remaining is None:
            continue
        bucket = _metric_window_bucket(metric.window)
        if not bucket:
            continue
        threshold = thresholds.get(bucket)
        if threshold is None:
            continue
        ratio = max(0.0, float(metric.remaining) / float(metric.limit))
        row = {
            "metric_id": metric.id,
            "label": metric.label,
            "window": bucket,
            "raw_window": metric.window,
            "remaining": round(float(metric.remaining), 6),
            "limit": round(float(metric.limit), 6),
            "remaining_ratio": round(ratio, 6),
            "threshold_ratio": round(float(threshold), 6),
        }
        evaluated.append(row)
        if ratio <= float(threshold):
            blocked.append(row)
    return evaluated, blocked


def _provider_missing_quota_telemetry_should_block(provider: str, *, evaluated_metrics: list[dict[str, Any]]) -> bool:
    if evaluated_metrics:
        return False
    if not _env_truthy("AUTOMATION_PROVIDER_WINDOW_GUARD_BLOCK_ON_MISSING_LIMITS", default=False):
        return False
    required = set(_required_providers_from_env())
    active_counts = _active_provider_usage_counts()
    active_usage = int(active_counts.get(provider, 0))
    return provider in required or active_usage > 0


def _provider_blocked_metrics_reason(blocked_metrics: list[dict[str, Any]]) -> str:
    return "; ".join(
        (
            f"{item['window']}::{item['metric_id']} "
            f"remaining={item['remaining']}/{item['limit']} "
            f"ratio={item['remaining_ratio']}<=threshold={item['threshold_ratio']}"
        )
        for item in blocked_metrics
    )


def provider_limit_guard_decision(provider: str, *, force_refresh: bool = False) -> dict[str, Any]:
    normalized_provider = _normalize_provider_name(provider)
    if not normalized_provider:
        return _provider_limit_guard_result(
            allowed=True,
            provider="",
            reason="provider_not_set",
        )

    if not _env_truthy("AUTOMATION_PROVIDER_WINDOW_GUARD_ENABLED", default=True):
        return _provider_limit_guard_result(
            allowed=True,
            provider=normalized_provider,
            reason="window_guard_disabled",
        )

    snapshot = _provider_snapshot_for_guard(normalized_provider, force_refresh=force_refresh)
    if snapshot is None:
        return _provider_limit_guard_result(
            allowed=True,
            provider=normalized_provider,
            reason="provider_snapshot_missing",
        )

    thresholds = _provider_guard_thresholds(normalized_provider)
    evaluated, blocked = _evaluate_provider_guard_metrics(
        snapshot=snapshot,
        thresholds=thresholds,
    )

    if blocked:
        return _provider_limit_guard_result(
            allowed=False,
            provider=normalized_provider,
            reason=_provider_blocked_metrics_reason(blocked),
            blocked_metrics=blocked,
            evaluated_metrics=evaluated,
            status=snapshot.status,
        )

    if _provider_missing_quota_telemetry_should_block(normalized_provider, evaluated_metrics=evaluated):
        return _provider_limit_guard_result(
            allowed=False,
            provider=normalized_provider,
            reason=f"{normalized_provider} has no quota remaining telemetry while guard strict-mode is enabled",
            evaluated_metrics=evaluated,
            status=snapshot.status,
        )

    return _provider_limit_guard_result(
        allowed=True,
        provider=normalized_provider,
        reason="within_window_thresholds",
        evaluated_metrics=evaluated,
        status=snapshot.status,
    )


def _resolved_required_provider_set(
    required_providers: list[str] | None,
    *,
    active_counts: dict[str, int],
) -> set[str]:
    _ = active_counts
    if required_providers:
        requested = _dedupe_preserve_order(
            [
                _provider_family_name(item)
                for item in required_providers
                if _provider_family_name(item)
            ]
        )
        if requested:
            return set(requested)
    required = [
        _provider_family_name(item)
        for item in (required_providers or _required_providers_from_env())
        if _provider_family_name(item) in _READINESS_REQUIRED_PROVIDER_ALLOWLIST
    ]
    required = _dedupe_preserve_order(required)
    if required:
        return set(required)
    return set(_DEFAULT_REQUIRED_PROVIDERS)


def _required_provider_usage_and_limit_contract_state(state_row: dict[str, Any] | None) -> tuple[bool, str]:
    if not isinstance(state_row, dict):
        return False, "missing_limit_telemetry"
    if not bool(state_row.get("has_limit_metrics")):
        return False, "missing_limit_metrics"
    if not bool(state_row.get("has_remaining_metrics")):
        return False, "missing_remaining_metrics"
    evidence_sources = [
        str(item).strip()
        for item in (state_row.get("evidence_sources") or [])
        if str(item).strip()
    ]
    if not evidence_sources:
        return False, "missing_limit_evidence_source"
    return True, "ok"


def _provider_readiness_report_for_overview(
    *,
    overview: ProviderUsageOverview,
    required_set: set[str],
    active_counts: dict[str, int],
) -> ProviderReadinessReport:
    by_provider = {
        family: row
        for row in overview.providers
        if (family := _provider_family_name(row.provider))
    }

    rows: list[ProviderReadinessRow] = []
    blocking: list[str] = []
    recommendations: list[str] = []

    for provider in sorted(set(by_provider.keys()) | set(required_set)):
        snapshot = by_provider.get(provider)
        configured, missing, _present, configured_notes = _configured_status(provider)
        kind = snapshot.kind if snapshot is not None else str(_PROVIDER_CONFIG_RULES.get(provider, {}).get("kind", "custom"))
        status = snapshot.status if snapshot is not None else ("ok" if configured else "unavailable")
        is_required = provider in required_set

        if is_required and (not configured or status != "ok"):
            severity = "critical"
            reason = f"{provider}: status={status}, configured={configured}"
            blocking.append(reason)
            recommendations.append(
                f"Configure provider '{provider}' ({', '.join(missing) if missing else 'connectivity/runtime checks'}) and re-run /api/automation/usage/readiness."
            )
        elif (not configured) or status != "ok":
            severity = "warning"
        else:
            severity = "info"

        notes = list(snapshot.notes) if snapshot is not None else []
        if missing:
            notes.append(f"missing_env={','.join(missing)}")
        notes.extend(configured_notes)
        notes = list(dict.fromkeys(notes))

        rows.append(
            ProviderReadinessRow(
                provider=provider,
                kind=str(kind),
                status=status,  # type: ignore[arg-type]
                required=is_required,
                configured=configured,
                severity=severity,  # type: ignore[arg-type]
                missing_env=missing,
                notes=notes,
            )
        )

    limit_telemetry = _limit_coverage_summary(
        overview.providers,
        required_providers=sorted(required_set),
        active_usage_counts=active_counts,
    )
    strict_limit_telemetry = _env_truthy(
        "AUTOMATION_PROVIDER_READINESS_BLOCK_ON_LIMIT_TELEMETRY",
        default=False,
    )
    provider_limit_status = (
        limit_telemetry.get("required_or_active_provider_status")
        if isinstance(limit_telemetry, dict)
        else {}
    )
    if not isinstance(provider_limit_status, dict):
        provider_limit_status = {}

    for row in rows:
        provider_name = _normalize_provider_name(row.provider)
        state_row = provider_limit_status.get(provider_name)
        state = str(state_row.get("state") or "").strip() if isinstance(state_row, dict) else ""
        if state:
            row.notes = list(dict.fromkeys([*row.notes, f"limit_telemetry_state={state}"]))

        if row.required:
            meets_contract, contract_detail = _required_provider_usage_and_limit_contract_state(state_row)
            if not meets_contract:
                row.severity = "critical"  # type: ignore[assignment]
                blocking.append(f"{provider_name}: {contract_detail}")
                recommendations.append(
                    (
                        f"Provide real usage+limit telemetry for '{provider_name}' "
                        f"(missing={contract_detail}) so readiness can verify subscription quota state."
                    )
                )

            if state and state != "hard_limit_ready":
                if row.severity == "info":
                    row.severity = "warning"  # type: ignore[assignment]
                recommendations.append(
                    (
                        f"Add validated limit+remaining telemetry for '{provider_name}' "
                        f"(current_state={state}) before making numeric-limit claims."
                    )
                )
                if strict_limit_telemetry:
                    blocking.append(f"{provider_name}: limit_telemetry_state={state}")

    blocking = list(dict.fromkeys(blocking))
    recommendations = list(dict.fromkeys(recommendations))
    return ProviderReadinessReport(
        required_providers=sorted(required_set),
        all_required_ready=len(blocking) == 0,
        blocking_issues=blocking,
        recommendations=recommendations,
        providers=rows,
        limit_telemetry=limit_telemetry,
    )


def provider_readiness_report(*, required_providers: list[str] | None = None, force_refresh: bool = True) -> ProviderReadinessReport:
    active_counts = _coalesce_usage_counts_by_family(_active_provider_usage_counts())
    required_set = _resolved_required_provider_set(required_providers, active_counts=active_counts)
    overview = coalesce_usage_overview_families(
        collect_usage_overview(force_refresh=force_refresh)
    )
    return _provider_readiness_report_for_overview(
        overview=overview,
        required_set=required_set,
        active_counts=active_counts,
    )


def provider_readiness_report_from_snapshots(
    *,
    required_providers: list[str] | None = None,
) -> ProviderReadinessReport:
    active_counts = _coalesce_usage_counts_by_family(_active_provider_usage_counts())
    required_set = _resolved_required_provider_set(required_providers, active_counts=active_counts)
    overview = coalesce_usage_overview_families(usage_overview_from_snapshots())
    return _provider_readiness_report_for_overview(
        overview=overview,
        required_set=required_set,
        active_counts=active_counts,
    )


def _probe_openai_codex() -> tuple[bool, str]:
    return _probe_openai()


def _probe_openai() -> tuple[bool, str]:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        oauth_ok, oauth_detail = _codex_oauth_available()
        if oauth_ok:
            return True, f"ok_via_codex_oauth_session:{oauth_detail}"
        active = int(_active_provider_usage_counts().get("openai", 0))
        if active > 0:
            return True, "ok_via_runtime_usage"
        return False, "missing_openai_key"
    url = os.getenv("OPENAI_MODELS_URL", "https://api.openai.com/v1/models")
    try:
        with httpx.Client(timeout=8.0, headers=_openai_headers()) as client:
            response = client.get(url)
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("openai", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_after_api_error"
        return False, f"openai_probe_failed:{exc}"


def _probe_openclaw() -> tuple[bool, str]:
    openclaw_key = os.getenv("OPENCLAW_API_KEY", "").strip()
    if openclaw_key:
        return True, "ok_via_openclaw_key"

    active = _active_provider_usage_counts()
    openclaw_active = int(active.get("openclaw", 0))
    openai_active = int(active.get("openai", 0))
    openai_ok, openai_detail = _probe_openai()
    if openai_ok and (openclaw_active > 0 or openai_active > 0):
        return True, f"ok_via_openai_codex_backend:{openai_detail}"
    return False, "missing_openclaw_key_and_openai_codex_backend"


def _probe_cursor() -> tuple[bool, str]:
    runner_ok, runner_detail = _runner_provider_configured("cursor")
    if runner_ok:
        return True, f"ok_via_runner_telemetry:{runner_detail or 'runner_provider_telemetry'}"
    if shutil.which("agent") is None:
        active = int(_active_provider_usage_counts().get("cursor", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_no_cli"
        return False, "cursor_cli_not_in_path"

    cli_ok, cli_detail = _cli_output(["agent", "--version"])
    if cli_ok:
        return True, f"ok_cursor_cli:{cli_detail[:120]}"

    active = int(_active_provider_usage_counts().get("cursor", 0))
    if active > 0:
        return True, "ok_via_runtime_usage_after_cli_error"
    return False, f"cursor_cli_probe_failed:{cli_detail[:200]}"


def _probe_github() -> tuple[bool, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
    if token:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            with httpx.Client(timeout=8.0, headers=headers) as client:
                response = client.get("https://api.github.com/rate_limit")
                response.raise_for_status()
            return True, "ok"
        except Exception as exc:
            return False, f"github_probe_failed:{exc}"
    if shutil.which("gh") is not None and _cli_ok(["gh", "api", "/rate_limit"]):
        return True, "ok_via_gh_cli"
    return False, "missing_github_auth"


def _probe_openrouter() -> tuple[bool, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        active = int(_active_provider_usage_counts().get("openrouter", 0))
        if active > 0:
            return True, "ok_via_runtime_usage"
        return False, "missing_openrouter_key"
    url = os.getenv("OPENROUTER_MODELS_URL", "https://openrouter.ai/api/v1/models")
    try:
        with httpx.Client(timeout=8.0, headers=_openrouter_headers()) as client:
            response = client.get(url)
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("openrouter", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_after_api_error"
        return False, f"openrouter_probe_failed:{exc}"


def _probe_railway() -> tuple[bool, str]:
    token = os.getenv("RAILWAY_TOKEN", "").strip()
    project = os.getenv("RAILWAY_PROJECT_ID", "").strip()
    environment = os.getenv("RAILWAY_ENVIRONMENT", "").strip()
    service = os.getenv("RAILWAY_SERVICE", "").strip()
    if not token or not project or not environment or not service:
        if shutil.which("railway") is not None and _cli_ok(["railway", "list", "--json"]):
            return True, "ok_via_railway_cli"
        return False, "missing_railway_env"
    gql_url = os.getenv("RAILWAY_GRAPHQL_URL", "https://backboard.railway.com/graphql/v2")
    try:
        with httpx.Client(timeout=8.0, headers={"Authorization": f"Bearer {token}"}) as client:
            response = client.post(gql_url, json={"query": "query { me { id } }"})
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
        me = (payload.get("data") or {}).get("me") if isinstance(payload.get("data"), dict) else None
        ok = isinstance(me, dict) and bool(str(me.get("id") or "").strip())
        return (ok, "ok" if ok else "railway_probe_bad_payload")
    except Exception as exc:
        return False, f"railway_probe_failed:{exc}"


def _probe_supabase() -> tuple[bool, str]:
    token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip() or os.getenv("SUPABASE_TOKEN", "").strip()
    project_ref = os.getenv("SUPABASE_PROJECT_REF", "").strip()
    if not token or not project_ref:
        return False, "missing_supabase_env"
    base_url = os.getenv("SUPABASE_MANAGEMENT_API_URL", "https://api.supabase.com/v1").rstrip("/")
    url = f"{base_url}/projects/{project_ref}"
    try:
        with httpx.Client(timeout=8.0, headers=_supabase_headers(token)) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json() if isinstance(response.json(), dict) else {}
        if isinstance(payload, dict) and (payload.get("id") or payload.get("ref") or payload.get("name")):
            return True, "ok"
        return False, "supabase_probe_bad_payload"
    except Exception as exc:
        return False, f"supabase_probe_failed:{exc}"


def _probe_claude() -> tuple[bool, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not api_key:
        runner_ok, runner_detail = _runner_provider_configured("claude")
        if runner_ok:
            return True, f"ok_via_runner_telemetry:{runner_detail or 'runner_provider_telemetry'}"
        auth = _claude_cli_auth_context()
        if bool(auth.get("logged_in")):
            auth_method = str(auth.get("auth_method") or "cli_session").strip()
            return True, f"ok_via_claude_cli_session:{auth_method}"
        active = int(_active_provider_usage_counts().get("claude", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_no_auth_env"
        return False, "missing_anthropic_key"
    # Use the messages endpoint (POST) for the probe — it returns real rate limit headers
    # and confirms API key validity for the actual execution path.
    # The models GET endpoint does NOT return rate limit headers.
    probe_url = os.getenv("ANTHROPIC_MESSAGES_URL", "https://api.anthropic.com/v1/messages")
    probe_model = os.getenv("ANTHROPIC_QUOTA_PROBE_MODEL", "claude-haiku-4-5").strip() or "claude-haiku-4-5"
    try:
        with httpx.Client(timeout=8.0, headers=_anthropic_headers()) as client:
            response = client.post(
                probe_url,
                json={"model": probe_model, "max_tokens": 1, "messages": [{"role": "user", "content": "probe"}]},
            )
            response.raise_for_status()
        return True, "ok_api_key"
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("claude", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_after_api_error"
        return False, f"claude_probe_failed:{exc}"


def _claude_code_headers() -> dict[str, str]:
    """Build Anthropic API headers preferring ANTHROPIC_API_KEY, then CLAUDE_CODE_OAUTH_TOKEN."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return {
            "x-api-key": api_key,
            "anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
        }
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if oauth_token:
        return {
            "Authorization": f"Bearer {oauth_token}",
            "anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
        }
    return {"anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01")}


def _probe_claude_code() -> tuple[bool, str]:
    """Probe for Claude Code CLI executor: verify binary + auth.

    Auth resolution order (mirrors _build_claude_code_snapshot):
      1. ANTHROPIC_API_KEY  — confirmed via Anthropic models endpoint
      2. CLAUDE_CODE_OAUTH_TOKEN  — confirmed via Anthropic models endpoint
      3. Local CLI session (`claude auth status --json`)  — session presence is sufficient;
         the CLI handles auth internally at execution time, no HTTP probe needed
    """
    if not _claude_code_cli_available():
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_no_cli"
        return False, "claude_cli_not_in_path"

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()

    if not api_key and not oauth_token:
        # Fall back to local CLI session before reporting missing auth.
        cli_logged_in, cli_auth_method = _claude_code_cli_logged_in()
        if cli_logged_in:
            label = f"cli_session:{cli_auth_method}" if cli_auth_method else "cli_session"
            return True, f"ok_cli_session_{label}"
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_no_auth_env"
        return False, "missing_anthropic_key_or_claude_code_oauth_token_and_no_cli_session"

    # Confirm API connectivity via models endpoint using the appropriate auth header.
    url = os.getenv("ANTHROPIC_MODELS_URL", "https://api.anthropic.com/v1/models")
    try:
        with httpx.Client(timeout=8.0, headers=_claude_code_headers()) as client:
            response = client.get(url)
            response.raise_for_status()
        auth_method = "api_key" if api_key else "oauth_token"
        return True, f"ok_cli_and_{auth_method}"
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("claude-code", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_after_api_error"
        return False, f"claude_code_probe_failed:{exc}"


def _probe_internal() -> tuple[bool, str]:
    return True, "ok"


def _record_provider_probe_event(provider: str, ok: bool, detail: str, runtime_ms: float) -> None:
    try:
        from app.models.runtime import RuntimeEventCreate
        from app.services import runtime_service

        runtime_service.record_event(
            RuntimeEventCreate(
                source="worker",
                endpoint=f"tool:provider-validation/{provider}",
                method="RUN",
                status_code=200 if ok else 500,
                runtime_ms=max(0.1, float(runtime_ms)),
                idea_id="coherence-network-agent-pipeline",
                metadata={
                    "provider": provider,
                    "validation_stage": "execution",
                    "validation_result": "pass" if ok else "fail",
                    "probe_detail": detail,
                    "tool_name": "provider_validation_probe",
                },
            )
        )
    except Exception:
        return


def _provider_probe_map() -> dict[str, Callable[[], tuple[bool, str]]]:
    return {
        "coherence-internal": _probe_internal,
        "openai": _probe_openai,
        "openai-codex": _probe_openai,
        "openclaw": _probe_openclaw,
        "cursor": _probe_cursor,
        "openrouter": _probe_openrouter,
        "supabase": _probe_supabase,
        "github": _probe_github,
        "railway": _probe_railway,
        "claude": _probe_claude,
        "claude-code": _probe_claude_code,
    }


def _record_provider_heal_event(
    *,
    provider: str,
    strategy: str,
    ok: bool,
    detail: str,
    round_index: int,
    runtime_ms: float,
) -> None:
    try:
        from app.models.runtime import RuntimeEventCreate
        from app.services import runtime_service

        runtime_service.record_event(
            RuntimeEventCreate(
                source="worker",
                endpoint=f"tool:provider-heal/{provider}",
                method="RUN",
                status_code=200 if ok else 500,
                runtime_ms=max(0.1, float(runtime_ms)),
                idea_id="coherence-network-agent-pipeline",
                metadata={
                    "provider": provider,
                    "heal_strategy": strategy,
                    "heal_round": int(round_index),
                    "heal_result": "pass" if ok else "fail",
                    "heal_detail": detail,
                    "tool_name": "provider_auto_heal",
                },
            )
        )
    except Exception:
        return


def _heal_strategy_refresh_and_reprobe(provider: str, probe: Callable[[], tuple[bool, str]]) -> tuple[bool, str]:
    try:
        collect_usage_overview(force_refresh=True)
    except Exception:
        pass
    try:
        provider_readiness_report(required_providers=[provider], force_refresh=True)
    except Exception:
        pass
    ok, detail = probe()
    return ok, f"refresh_reprobe:{detail}"


def _heal_strategy_runtime_validation(
    provider: str,
    *,
    runtime_window_seconds: int,
    min_execution_events: int,
) -> tuple[bool, str]:
    try:
        report = provider_validation_report(
            required_providers=[provider],
            runtime_window_seconds=runtime_window_seconds,
            min_execution_events=min_execution_events,
            force_refresh=True,
        )
    except Exception as exc:
        return False, f"runtime_validation_failed:{exc}"

    target = None
    for row in report.providers:
        if str(row.provider).strip().lower() == provider:
            target = row
            break
    if target is None:
        return False, "runtime_validation_missing_provider"
    if target.validated_execution and target.readiness_status == "ok":
        return True, "ok_via_runtime_validation"
    return (
        False,
        "runtime_validation_blocked:"
        f"readiness={target.readiness_status};"
        f"validated_execution={target.validated_execution};"
        f"successful_events={target.successful_events}",
    )


def _provider_cli_install_enabled(*, explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return _env_truthy("AUTOMATION_PROVIDER_HEAL_ENABLE_INSTALLS", default=False)


def _provider_install_binary(provider: str) -> str:
    return {
        "cursor": "agent",
        "claude-code": "claude",
    }.get(provider, "")


def _provider_cli_missing_for_auto_heal(provider: str) -> bool:
    binary = _provider_install_binary(provider)
    if not binary:
        return False
    return shutil.which(binary) is None


def _provider_install_commands(provider: str) -> list[str]:
    def _package_bootstrap(packages: list[str]) -> str:
        joined = " ".join(packages)
        return (
            "if command -v apt-get >/dev/null 2>&1; then "
            "apt-get update && DEBIAN_FRONTEND=noninteractive "
            f"apt-get install -y --no-install-recommends {joined}; "
            "elif command -v apk >/dev/null 2>&1; then "
            f"apk add --no-cache {joined}; "
            "elif command -v dnf >/dev/null 2>&1; then "
            f"dnf install -y {joined}; "
            "elif command -v yum >/dev/null 2>&1; then "
            f"yum install -y {joined}; "
            "else echo 'no_supported_pkg_manager'; exit 1; fi"
        )

    ensure_curl_cmd = (
        "if ! command -v curl >/dev/null 2>&1; then "
        f"{_package_bootstrap(['curl'])}; "
        "fi"
    )
    ensure_node_cmd = (
        "if ! command -v npm >/dev/null 2>&1; then "
        f"{_package_bootstrap(['nodejs', 'npm'])}; "
        "fi"
    )
    env_overrides = {
        "cursor": "AUTOMATION_CURSOR_INSTALL_COMMANDS",
        "claude-code": "AUTOMATION_CLAUDE_CODE_INSTALL_COMMANDS",
    }
    default_commands = {
        "cursor": [
            ensure_curl_cmd,
            "curl -fsSL https://cursor.com/install | bash",
        ],
        "claude-code": [
            ensure_curl_cmd,
            ensure_node_cmd,
            "curl -fsSL https://claude.ai/install.sh | bash",
            "npm install -g @anthropic-ai/claude-code",
        ],
    }
    raw = str(os.getenv(env_overrides.get(provider, ""), "")).strip()
    if raw:
        return [item.strip() for item in raw.split("||") if item.strip()]
    return list(default_commands.get(provider, []))


def _run_shell_command(command: str, *, timeout_seconds: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return False, str(exc)

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    combined = stdout if stdout else stderr
    if not combined:
        combined = f"exit_code={result.returncode}"
    return result.returncode == 0, combined[:400]


def _candidate_binary_paths(binary: str) -> list[str]:
    home = str(Path.home())
    candidates = [
        os.path.join(home, ".local", "bin", binary),
        os.path.join(home, ".cursor", "bin", binary),
        os.path.join(home, ".cursor", "agent", "bin", binary),
        os.path.join(home, "bin", binary),
        f"/usr/local/bin/{binary}",
        f"/usr/bin/{binary}",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate).expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _resolve_binary_path(binary: str) -> str:
    discovered = shutil.which(binary)
    if discovered:
        return discovered
    for candidate in _candidate_binary_paths(binary):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _prepend_binary_dir_to_path(binary_path: str) -> None:
    directory = str(Path(binary_path).parent)
    current = str(os.environ.get("PATH", ""))
    parts = [item for item in current.split(os.pathsep) if item]
    if directory in parts:
        return
    os.environ["PATH"] = directory + (os.pathsep + current if current else "")


def _ensure_binary_symlink(binary: str, source_path: str) -> None:
    targets = [f"/usr/local/bin/{binary}", f"/usr/bin/{binary}"]
    for target in targets:
        try:
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            target_path.symlink_to(Path(source_path))
            return
        except Exception:
            continue


def _install_provider_cli(provider: str) -> tuple[bool, str]:
    binary = _provider_install_binary(provider)
    if not binary:
        return False, "install_cli_unsupported_provider"
    resolved = _resolve_binary_path(binary)
    if resolved:
        _prepend_binary_dir_to_path(resolved)
        return False, f"install_cli_skipped_present:{binary}:{resolved}"

    commands = _provider_install_commands(provider)
    if not commands:
        return False, "install_cli_no_commands_configured"

    timeout_seconds = max(
        30,
        min(int(os.getenv("AUTOMATION_PROVIDER_INSTALL_TIMEOUT_SECONDS", "300")), 900),
    )
    details: list[str] = []
    for index, command in enumerate(commands, start=1):
        ok, detail = _run_shell_command(command, timeout_seconds=timeout_seconds)
        details.append(f"cmd{index}:{'ok' if ok else 'fail'}:{detail}")
        if not ok:
            continue
        resolved = _resolve_binary_path(binary)
        if resolved and not shutil.which(binary):
            _ensure_binary_symlink(binary, resolved)
            _prepend_binary_dir_to_path(resolved)
        resolved = _resolve_binary_path(binary)
        if resolved:
            probe_ok, probe_detail = _cli_output([resolved, "--version"])
            if probe_ok:
                return True, f"install_cli_ok:{binary}:{probe_detail[:200]}"
            return True, f"install_cli_ok_version_probe_failed:{probe_detail[:200]}"
    return False, f"install_cli_failed:{'; '.join(details)[:500]}"


def _provider_cli_install_strategy(
    provider: str,
    *,
    attempts: list[dict[str, Any]],
    enable_cli_installs: bool,
) -> tuple[str, Callable[[], tuple[bool, str]]] | None:
    if not enable_cli_installs:
        return None
    if any(str(row.get("strategy", "")).startswith("install_cli") for row in attempts):
        return None
    if not _provider_cli_missing_for_auto_heal(provider):
        return None
    if not _provider_install_binary(provider):
        return None
    return ("install_cli", lambda: _install_provider_cli(provider))


def _provider_requires_cli_binary(provider: str, *, enable_cli_installs: bool) -> bool:
    return enable_cli_installs and bool(_provider_install_binary(provider))


def _detail_indicates_missing_cli(detail: str) -> bool:
    text = str(detail or "").strip().lower()
    if not text:
        return False
    markers = (
        "no_cli",
        "cli_not_in_path",
        "cli_missing",
        "command not found",
        "not found",
    )
    return any(marker in text for marker in markers)


def run_provider_validation_probes(*, required_providers: list[str] | None = None) -> dict[str, Any]:
    required = [
        _normalize_provider_name(item)
        for item in (required_providers or _validation_required_providers_from_env())
        if str(item).strip()
    ]
    probe_map = _provider_probe_map()

    out: list[dict[str, Any]] = []
    for provider in required:
        probe = probe_map.get(provider)
        if probe is None:
            out.append({"provider": provider, "ok": False, "detail": "unsupported_provider"})
            continue
        started = time.perf_counter()
        ok, detail = probe()
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 4)
        _record_provider_probe_event(provider=provider, ok=ok, detail=detail, runtime_ms=elapsed_ms)
        out.append({"provider": provider, "ok": ok, "detail": detail, "runtime_ms": elapsed_ms})
    return {"required_providers": required, "probes": out}


def run_provider_auto_heal(
    *,
    required_providers: list[str] | None = None,
    max_rounds: int = 2,
    runtime_window_seconds: int = 86400,
    min_execution_events: int = 1,
    enable_cli_installs: bool | None = None,
) -> dict[str, Any]:
    requested = required_providers or [
        *_required_providers_from_env(),
        *_validation_required_providers_from_env(),
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in requested:
        provider = _normalize_provider_name(item)
        if not provider or provider in seen:
            continue
        seen.add(provider)
        deduped.append(provider)
    providers = [provider for provider in deduped if provider != "coherence-internal"]

    rounds = max(1, min(int(max_rounds), 6))
    validation_window = max(60, min(int(runtime_window_seconds), 2592000))
    min_events = max(1, min(int(min_execution_events), 10))
    retry_delay_seconds = max(
        0,
        min(int(os.getenv("AUTOMATION_PROVIDER_HEAL_RETRY_DELAY_SECONDS", "2")), 30),
    )
    enable_installs = _provider_cli_install_enabled(explicit=enable_cli_installs)
    probe_map = _provider_probe_map()

    provider_rows: list[dict[str, Any]] = []
    blocking_issues: list[str] = []

    for provider in providers:
        probe = probe_map.get(provider)
        attempts: list[dict[str, Any]] = []
        if probe is None:
            provider_rows.append(
                {
                    "provider": provider,
                    "status": "unavailable",
                    "healed": False,
                    "attempted_rounds": 0,
                    "strategies_tried": [],
                    "attempts": [],
                    "final_detail": "unsupported_provider",
                }
            )
            blocking_issues.append(f"{provider}: unsupported_provider")
            continue

        healed = False
        final_detail = "not_attempted"
        for round_index in range(1, rounds + 1):
            strategy_runs: list[tuple[str, Callable[[], tuple[bool, str]]]] = [("direct_probe", lambda: probe())]
            install_strategy = _provider_cli_install_strategy(
                provider,
                attempts=attempts,
                enable_cli_installs=enable_installs,
            )
            if install_strategy is not None:
                strategy_runs.append(install_strategy)
            strategy_runs.extend(
                [
                    ("refresh_and_reprobe", lambda: _heal_strategy_refresh_and_reprobe(provider, probe)),
                    (
                        "runtime_validation",
                        lambda: _heal_strategy_runtime_validation(
                            provider,
                            runtime_window_seconds=validation_window,
                            min_execution_events=min_events,
                        ),
                    ),
                ]
            )
            for strategy_name, runner in strategy_runs:
                started = time.perf_counter()
                ok, detail = runner()
                if (
                    ok
                    and _provider_requires_cli_binary(provider, enable_cli_installs=enable_installs)
                    and _detail_indicates_missing_cli(detail)
                ):
                    ok = False
                    detail = f"cli_binary_required:{detail}"
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 4)
                _record_provider_heal_event(
                    provider=provider,
                    strategy=strategy_name,
                    ok=ok,
                    detail=detail,
                    round_index=round_index,
                    runtime_ms=elapsed_ms,
                )
                attempts.append(
                    {
                        "round": round_index,
                        "strategy": strategy_name,
                        "ok": ok,
                        "detail": detail,
                        "runtime_ms": elapsed_ms,
                    }
                )
                final_detail = detail
                if ok:
                    healed = True
                    break
            if healed:
                break
            if round_index < rounds and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)

        strategies_tried = list(dict.fromkeys(str(row.get("strategy") or "") for row in attempts if row.get("strategy")))
        provider_status = "ok" if healed else "unavailable"
        provider_rows.append(
            {
                "provider": provider,
                "status": provider_status,
                "healed": healed,
                "attempted_rounds": max((int(row.get("round") or 0) for row in attempts), default=0),
                "strategies_tried": strategies_tried,
                "attempts": attempts,
                "final_detail": final_detail,
            }
        )
        if not healed:
            blocking_issues.append(f"{provider}: {final_detail}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "required_providers": providers,
        "external_provider_count": len(providers),
        "max_rounds": rounds,
        "enable_cli_installs": enable_installs,
        "all_healthy": len(blocking_issues) == 0,
        "blocking_issues": blocking_issues,
        "providers": provider_rows,
    }


def _runtime_validation_rows(*, required_providers: list[str], runtime_window_seconds: int) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(60, min(runtime_window_seconds, 2592000)))

    def _providers_for_event(metadata: dict[str, Any]) -> set[str]:
        providers: set[str] = set()
        explicit = _normalize_provider_name(str(metadata.get("provider") or ""))
        if explicit:
            providers.add(explicit)

        raw_executor = str(metadata.get("executor") or "").strip().lower()
        executor = raw_executor
        if executor in {"clawwork", "openclaw"}:
            # Legacy executor aliases map to codex for canonical execution,
            # but still count as openclaw evidence for compatibility checks.
            providers.add("openclaw")
            executor = "codex"
        model = str(metadata.get("model") or "").strip()
        model_lower = model.lower()
        worker_id = str(metadata.get("worker_id") or "").strip().lower()
        agent_id = str(metadata.get("agent_id") or "").strip().lower()
        repeatable_tool_call = str(metadata.get("repeatable_tool_call") or "").strip().lower()

        inferred = _infer_provider_from_model(model)
        if inferred:
            providers.add(inferred)
        if model_lower.startswith(("openclaw/", "clawwork/")):
            providers.add("openclaw")
        if executor == "openrouter":
            providers.add("openrouter")
        if executor == "codex":
            providers.add("openai")
        if worker_id.startswith("openai-codex") or agent_id.startswith("openai-codex"):
            providers.add("openai")
        if "codex" in model_lower or repeatable_tool_call.startswith("codex "):
            providers.add("openai")

        return {item for item in providers if item}

    try:
        from app.services import runtime_service

        events = runtime_service.list_events(limit=2000)
    except Exception:
        events = []

    for event in events:
        recorded_at = getattr(event, "recorded_at", None)
        if not isinstance(recorded_at, datetime) or recorded_at < cutoff:
            continue
        metadata = getattr(event, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            continue
        providers = _providers_for_event(metadata)
        if not providers:
            continue
        for provider in providers:
            bucket = counts.setdefault(
                provider,
                {"usage_events": 0, "successful_events": 0, "last_event_at": None, "notes": []},
            )
            bucket["usage_events"] += 1
            if int(getattr(event, "status_code", 0)) < 400:
                bucket["successful_events"] += 1
            prev = bucket["last_event_at"]
            if prev is None or recorded_at > prev:
                bucket["last_event_at"] = recorded_at

    for provider in required_providers:
        counts.setdefault(provider, {"usage_events": 0, "successful_events": 0, "last_event_at": None, "notes": []})
    return counts


def provider_validation_report(
    *,
    required_providers: list[str] | None = None,
    runtime_window_seconds: int = 86400,
    min_execution_events: int = 1,
    force_refresh: bool = True,
) -> ProviderValidationReport:
    required = [
        _normalize_provider_name(item)
        for item in (required_providers or _validation_required_providers_from_env())
        if str(item).strip()
    ]
    readiness = provider_readiness_report(required_providers=required, force_refresh=force_refresh)
    readiness_by_provider = {
        _normalize_provider_name(row.provider): row
        for row in readiness.providers
        if _normalize_provider_name(row.provider)
    }
    runtime_rows = _runtime_validation_rows(required_providers=required, runtime_window_seconds=runtime_window_seconds)

    rows: list[ProviderValidationRow] = []
    blocking: list[str] = []
    min_events = max(1, min(int(min_execution_events), 50))

    for provider in required:
        readiness_row = readiness_by_provider.get(provider)
        runtime_row = runtime_rows.get(provider, {"usage_events": 0, "successful_events": 0, "last_event_at": None, "notes": []})
        configured = bool(readiness_row.configured) if readiness_row is not None else False
        readiness_status = readiness_row.status if readiness_row is not None else "unavailable"
        usage_events = int(runtime_row.get("usage_events") or 0)
        successful_events = int(runtime_row.get("successful_events") or 0)
        execution_validated = successful_events >= min_events
        notes = list(readiness_row.notes) if readiness_row is not None else []
        if usage_events < min_events:
            notes.append(f"needs_runtime_events>={min_events}")
        if successful_events < min_events:
            notes.append(f"needs_successful_events>={min_events}")
        notes = list(dict.fromkeys(notes))

        if (not configured) or readiness_status != "ok" or (not execution_validated):
            blocking.append(
                f"{provider}: configured={configured}, readiness_status={readiness_status}, "
                f"successful_events={successful_events}/{min_events}"
            )

        rows.append(
            ProviderValidationRow(
                provider=provider,
                configured=configured,
                readiness_status=readiness_status,
                usage_events=usage_events,
                successful_events=successful_events,
                validated_execution=execution_validated,
                last_event_at=runtime_row.get("last_event_at"),
                notes=notes,
            )
        )

    return ProviderValidationReport(
        required_providers=required,
        runtime_window_seconds=max(60, min(runtime_window_seconds, 2592000)),
        min_execution_events=min_events,
        all_required_validated=len(blocking) == 0,
        blocking_issues=blocking,
        providers=rows,
    )


def _normalize_subscription_tier(provider: str, value: str) -> str:
    normalized_provider = provider.strip().lower()
    normalized_value = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized_provider == "openai":
        aliases = {
            "plus": "pro",
            "chatgpt_plus": "pro",
            "pro": "pro",
            "team": "team",
            "business": "team",
            "enterprise": "team",
        }
        return aliases.get(normalized_value, "free")
    if normalized_provider == "anthropic":
        aliases = {
            "free": "free",
            "pro": "pro",
            "max": "team",
            "max_5x": "team",
            "team": "team",
            "enterprise": "team",
        }
        return aliases.get(normalized_value, "free")
    if normalized_provider == "cursor":
        aliases = {
            "free": "free",
            "pro": "pro",
            "pro_plus": "pro_plus",
            "business": "pro_plus",
            "enterprise": "pro_plus",
        }
        return aliases.get(normalized_value, "free")
    if normalized_provider == "github":
        aliases = {
            "free": "free",
            "pro": "team",
            "team": "team",
            "business": "enterprise",
            "enterprise": "enterprise",
        }
        return aliases.get(normalized_value, "free")
    return normalized_value or "free"


def _subscription_detected(provider: str) -> bool:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai":
        runner_ok, _ = _runner_provider_configured("openai")
        oauth_ok, _ = _codex_oauth_available()
        return runner_ok or oauth_ok or _env_present("OPENAI_ADMIN_API_KEY") or _env_present("OPENAI_API_KEY")
    if normalized_provider == "anthropic":
        runner_ok, _ = _runner_provider_configured("claude")
        auth = _claude_cli_auth_context()
        return runner_ok or bool(auth.get("logged_in")) or _env_present("ANTHROPIC_API_KEY")
    if normalized_provider == "cursor":
        runner_ok, _ = _runner_provider_configured("cursor")
        about = _cursor_cli_about_context()
        return (
            runner_ok
            or bool(about.get("logged_in"))
            or _env_present("CURSOR_API_KEY")
            or _env_present("CURSOR_CLI_MODEL")
        )
    if normalized_provider == "github":
        return _env_present("GITHUB_TOKEN") or _env_present("GH_TOKEN")
    return False


def _subscription_current_tier(provider: str) -> str:
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai":
        row = _runner_provider_telemetry("openai")
        raw_tier = str(row.get("tier") or row.get("plan") or "").strip()
        return _normalize_subscription_tier("openai", raw_tier)
    if normalized_provider == "anthropic":
        row = _runner_provider_telemetry("claude")
        raw_tier = str(row.get("tier") or "").strip()
        if not raw_tier:
            raw_tier = str(_claude_cli_auth_context().get("subscription_type") or "").strip()
        return _normalize_subscription_tier("anthropic", raw_tier)
    if normalized_provider == "cursor":
        row = _runner_provider_telemetry("cursor")
        raw_tier = str(row.get("tier") or "").strip()
        if not raw_tier:
            raw_tier = str(_cursor_cli_about_context().get("tier") or "").strip()
        return _normalize_subscription_tier("cursor", raw_tier)
    if normalized_provider == "github":
        return "free"
    return "free"


def _tier_cost(provider: str, tier: str) -> float:
    normalized_provider = provider.strip().lower()
    normalized_tier = tier.strip().lower()
    catalog: dict[str, dict[str, float]] = {
        "openai": {"free": 0.0, "pro": 20.0, "team": 60.0},
        "anthropic": {"free": 0.0, "pro": 20.0, "team": 60.0},
        "cursor": {"free": 0.0, "pro": 20.0, "pro_plus": 40.0},
        "github": {"free": 0.0, "team": 4.0, "enterprise": 21.0},
    }
    row = catalog.get(normalized_provider, {})
    return float(row.get(normalized_tier, 0.0))


def _next_tier(provider: str, current_tier: str) -> str:
    normalized_provider = provider.strip().lower()
    normalized_tier = current_tier.strip().lower()
    ladders: dict[str, list[str]] = {
        "openai": ["free", "pro", "team"],
        "anthropic": ["free", "pro", "team"],
        "cursor": ["free", "pro", "pro_plus"],
        "github": ["free", "team", "enterprise"],
    }
    ladder = ladders.get(normalized_provider, ["free", "pro"])
    if normalized_tier not in ladder:
        return ladder[0 if len(ladder) == 1 else 1]
    idx = ladder.index(normalized_tier)
    if idx >= len(ladder) - 1:
        return ladder[idx]
    return ladder[idx + 1]


def _subscription_plan_inputs() -> list[dict[str, Any]]:
    return [
        {
            "provider": "openai",
            "detected": _subscription_detected("openai"),
            "current_tier": _subscription_current_tier("openai"),
            "benefits": [
                "Higher token/request throughput for API workloads",
                "Reduced queueing risk for agent execution peaks",
            ],
            "confidence": 0.7,
            "benefit_weight": 1.0,
        },
        {
            "provider": "anthropic",
            "detected": _subscription_detected("anthropic"),
            "current_tier": _subscription_current_tier("anthropic"),
            "benefits": [
                "Higher fallback capacity for escalated agent tasks",
                "More resilient execution when primary provider is saturated",
            ],
            "confidence": 0.55,
            "benefit_weight": 0.8,
        },
        {
            "provider": "cursor",
            "detected": _subscription_detected("cursor"),
            "current_tier": _subscription_current_tier("cursor"),
            "benefits": [
                "Higher agent concurrency for implementation and review loops",
                "Lower cycle time for task completion throughput",
            ],
            "confidence": 0.6,
            "benefit_weight": 0.9,
        },
        {
            "provider": "github",
            "detected": _subscription_detected("github"),
            "current_tier": _subscription_current_tier("github"),
            "benefits": [
                "More CI minutes and stronger governance controls",
                "Lower deployment latency under heavy PR traffic",
            ],
            "confidence": 0.65,
            "benefit_weight": 0.85,
        },
    ]


def _subscription_plans() -> list[SubscriptionPlanEstimate]:
    usage = collect_usage_overview(force_refresh=True)
    provider_by_name = {row.provider.strip().lower(): row for row in usage.providers}

    execution = agent_service.get_usage_summary().get("execution", {})
    tracked_runs = float(execution.get("tracked_runs") or 0.0) if isinstance(execution, dict) else 0.0
    failed_runs = float(execution.get("failed_runs") or 0.0) if isinstance(execution, dict) else 0.0
    success_rate = float(execution.get("success_rate") or 0.0) if isinstance(execution, dict) else 0.0

    plans: list[SubscriptionPlanEstimate] = []
    for row in _subscription_plan_inputs():
        provider = str(row["provider"])
        current_tier = str(row["current_tier"]).strip().lower() or "free"
        next_tier = _next_tier(provider, current_tier)
        current_cost = _tier_cost(provider, current_tier)
        next_cost = _tier_cost(provider, next_tier)
        delta = max(0.0, next_cost - current_cost)
        provider_usage = provider_by_name.get(provider)
        provider_health_penalty = 0.0
        if provider_usage is not None and provider_usage.status != "ok":
            provider_health_penalty = 0.2

        # Heuristic estimator grounded in actual local pipeline metrics:
        # throughput demand (tracked_runs), reliability pressure (failed_runs/success_rate),
        # and provider-specific weight.
        demand = min(10.0, max(0.0, tracked_runs / 10.0))
        reliability_pressure = min(10.0, max(0.0, failed_runs * 2.0 + (1.0 - success_rate) * 10.0))
        weighted_benefit = (demand * 0.55 + reliability_pressure * 0.45) * float(row["benefit_weight"])
        weighted_benefit = max(0.0, weighted_benefit * (1.0 - provider_health_penalty))
        roi = weighted_benefit if delta <= 0 else round(weighted_benefit / delta, 4)

        assumptions = [
            "Costs are monthly and approximate; verify against actual vendor billing.",
            "Benefit score combines observed pipeline throughput and reliability pressure.",
        ]
        if provider_usage is not None:
            assumptions.append(f"Provider status currently observed as {provider_usage.status}.")

        plans.append(
            SubscriptionPlanEstimate(
                provider=provider,
                detected=bool(row["detected"]),
                current_tier=current_tier,
                next_tier=next_tier,
                current_monthly_cost_usd=round(current_cost, 2),
                next_monthly_cost_usd=round(next_cost, 2),
                monthly_upgrade_delta_usd=round(delta, 2),
                estimated_benefit_score=round(weighted_benefit, 4),
                estimated_roi=round(roi, 4),
                confidence=max(0.0, min(float(row["confidence"]), 1.0)),
                assumptions=assumptions,
                expected_benefits=list(row["benefits"]),
            )
        )

    plans.sort(key=lambda p: (p.estimated_roi, p.estimated_benefit_score), reverse=True)
    return plans


def estimate_subscription_upgrades() -> SubscriptionUpgradeEstimatorReport:
    plans = _subscription_plans()
    detected = [row for row in plans if row.detected]
    current = round(sum(row.current_monthly_cost_usd for row in plans), 2)
    nxt = round(sum(row.next_monthly_cost_usd for row in plans), 2)
    delta = round(max(0.0, nxt - current), 2)
    return SubscriptionUpgradeEstimatorReport(
        plans=plans,
        detected_subscriptions=len(detected),
        estimated_current_monthly_cost_usd=current,
        estimated_next_monthly_cost_usd=nxt,
        estimated_monthly_upgrade_delta_usd=delta,
    )
