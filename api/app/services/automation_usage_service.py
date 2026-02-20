"""Provider usage adapters, normalized snapshots, and alert evaluation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

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
from app.services import agent_service, telemetry_persistence_service

_CACHE: dict[str, Any] = {"expires_at": 0.0, "overview": None}
_CACHE_TTL_SECONDS = 120.0

_PROVIDER_CONFIG_RULES: dict[str, dict[str, Any]] = {
    "coherence-internal": {"kind": "internal", "all_of": []},
    "openai-codex": {"kind": "custom", "any_of": ["OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"]},
    "claude": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]},
    "openai": {"kind": "openai", "any_of": ["OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"]},
    "github": {"kind": "github", "any_of": ["GITHUB_TOKEN", "GH_TOKEN"]},
    "openrouter": {"kind": "custom", "all_of": ["OPENROUTER_API_KEY"]},
    "anthropic": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]},
    "cursor": {"kind": "custom", "any_of": ["CURSOR_API_KEY", "CURSOR_CLI_MODEL"]},
    "openclaw": {"kind": "custom", "all_of": ["OPENCLAW_API_KEY"]},
    "railway": {"kind": "custom", "all_of": ["RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE"]},
    "supabase": {"kind": "custom", "any_of": ["SUPABASE_ACCESS_TOKEN", "SUPABASE_TOKEN"]},
}

_DEFAULT_REQUIRED_PROVIDERS = (
    "coherence-internal",
    "github",
    "openai",
    "openrouter",
    "railway",
    "supabase",
)
_DEFAULT_PROVIDER_VALIDATION_REQUIRED = (
    "coherence-internal",
    "openai-codex",
    "openrouter",
    "supabase",
    "github",
    "railway",
    "claude",
)

_PROVIDER_ALIASES: dict[str, str] = {
    "clawwork": "openclaw",
}

_PROVIDER_WINDOW_GUARD_DEFAULT_RATIO_BY_WINDOW: dict[str, float] = {
    "hourly": 0.1,
    "weekly": 0.1,
    "monthly": 0.1,
}


def _normalize_provider_name(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return ""
    return _PROVIDER_ALIASES.get(candidate, candidate)


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
) -> UsageMetric:
    return UsageMetric(
        id=id,
        label=label,
        unit=unit,  # type: ignore[arg-type]
        used=max(0.0, float(used)),
        remaining=(None if remaining is None else max(0.0, float(remaining))),
        limit=(None if limit is None else max(0.0, float(limit))),
        window=window,
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
    model = os.getenv("ANTHROPIC_QUOTA_PROBE_MODEL", "claude-3-5-haiku-latest").strip() or "claude-3-5-haiku-latest"
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
        ],
        "openai-codex": [
            "https://platform.openai.com/docs/api-reference/models/list",
        ],
        "claude": [
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


def _finalize_snapshot(snapshot: ProviderUsageSnapshot) -> ProviderUsageSnapshot:
    metric = _primary_metric(snapshot.metrics)
    if metric:
        snapshot.actual_current_usage = metric.used
        snapshot.actual_current_usage_unit = metric.unit
        snapshot.usage_remaining = metric.remaining
        snapshot.usage_remaining_unit = metric.unit if metric.remaining is not None else None
        snapshot.usage_per_time = _metric_time_rate(metric)

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

    if shutil.which("codex") is not None and _cli_ok(["codex", "auth", "status"]):
        return True, "codex_auth_status"

    if candidates:
        return False, f"missing_session_file:{candidates[0]}"
    return False, "missing_codex_oauth_session"


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
    configured, missing, present = _configured_env_status(provider)
    notes: list[str] = []
    if configured:
        return configured, missing, present, notes

    provider_name = provider.strip().lower()
    active_counts = _active_provider_usage_counts()
    active_runs = int(active_counts.get(provider_name, 0))

    if provider_name == "github" and _gh_auth_available():
        return True, [], ["gh_auth"], ["Configured via gh CLI auth session."]
    if provider_name == "railway" and _railway_auth_available():
        return True, [], ["railway_cli_auth"], ["Configured via Railway CLI auth session."]
    if provider_name == "openai-codex":
        oauth_ok, oauth_detail = _codex_oauth_available()
        if oauth_ok:
            return True, [], ["codex_oauth_session"], [f"Configured via Codex OAuth session ({oauth_detail})."]
        if active_runs > 0:
            notes.append("OpenAI Codex observed in runtime usage; treating as configured by active execution context.")
            return True, [], present, notes
    if provider_name == "openclaw" and active_runs > 0:
        openai_key = bool(
            os.getenv("OPENAI_ADMIN_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        codex_active = int(active_counts.get("openai-codex", 0)) > 0
        if openai_key or codex_active:
            notes.append(
                "OpenClaw observed with Codex/OpenAI execution context; treating as configured for runtime validation."
            )
            return True, [], present, notes
    if provider_name == "claude" and active_runs > 0:
        notes.append("Claude observed in runtime usage; treating as configured by active execution context.")
        return True, [], present, notes

    return configured, missing, present, notes


def _required_providers_from_env() -> list[str]:
    raw = os.getenv("AUTOMATION_REQUIRED_PROVIDERS", ",".join(_DEFAULT_REQUIRED_PROVIDERS))
    out = [
        _normalize_provider_name(item)
        for item in str(raw).split(",")
        if str(item).strip()
    ]
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


def _infer_provider_from_model(model_name: str) -> str:
    model = model_name.strip().lower()
    if not model:
        return ""
    if "codex" in model:
        return "openai-codex"
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
        "openclaw": "openclaw",
        "clawwork": "openclaw",
        "claude": "claude",
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
            provider = "openai-codex"
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

    return {k: v for k, v in counts.items() if v > 0}


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


def _build_internal_snapshot() -> ProviderUsageSnapshot:
    usage = agent_service.get_usage_summary()
    execution = usage.get("execution") if isinstance(usage.get("execution"), dict) else {}

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
    snapshot = _build_models_visibility_snapshot(
        provider="openai-codex",
        label="OpenAI visible models",
        models_url=models_url,
        rows=rows,
        headers=response.headers,
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
    has_quota_metric = any(metric.id in {"requests_quota", "tokens_quota"} for metric in snapshot.metrics)
    if not has_quota_metric:
        probe_headers, probe_error = _openai_quota_probe_headers(headers)
        if probe_headers is not None:
            appended = _append_rate_limit_metrics(
                metrics=snapshot.metrics,
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
            if appended:
                snapshot.notes.append("Quota headers sourced from lightweight OpenAI responses probe.")
                snapshot.notes = [
                    note
                    for note in snapshot.notes
                    if "no request/token remaining headers were returned" not in note.lower()
                ]
            else:
                snapshot.notes.append(
                    "OpenAI responses probe completed, but no request/token remaining headers were returned."
                )
        elif probe_error:
            snapshot.notes.append(f"OpenAI responses quota probe failed: {probe_error}")
    return snapshot


def _anthropic_headers() -> dict[str, str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    return {
        "x-api-key": api_key,
        "anthropic-version": os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"),
    }


def _build_claude_snapshot() -> ProviderUsageSnapshot:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not api_key:
        active = int(_active_provider_usage_counts().get("claude", 0))
        if active > 0:
            return _runtime_task_runs_snapshot(
                provider="claude",
                kind="custom",
                active_runs=active,
                note="Using runtime Claude execution evidence (no direct Anthropic key in environment).",
            )
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
    has_quota_metric = any(metric.id in {"requests_quota", "tokens_quota"} for metric in snapshot.metrics)
    if not has_quota_metric:
        probe_headers, probe_error = _claude_quota_probe_headers(_anthropic_headers())
        if probe_headers is not None:
            appended = _append_rate_limit_metrics(
                metrics=snapshot.metrics,
                headers=probe_headers,
                request_limit_keys=("anthropic-ratelimit-requests-limit", "x-ratelimit-limit-requests"),
                request_remaining_keys=("anthropic-ratelimit-requests-remaining", "x-ratelimit-remaining-requests"),
                request_window="minute",
                request_label="Claude request quota",
                token_limit_keys=("anthropic-ratelimit-tokens-limit", "x-ratelimit-limit-tokens"),
                token_remaining_keys=("anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens"),
                token_window="minute",
                token_label="Claude token quota",
            )
            if appended:
                snapshot.notes.append("Quota headers sourced from lightweight Anthropic messages probe.")
                snapshot.notes = [
                    note
                    for note in snapshot.notes
                    if "no request/token remaining headers were returned" not in note.lower()
                ]
            else:
                snapshot.notes.append(
                    "Anthropic messages probe completed, but no request/token remaining headers were returned."
                )
        elif probe_error:
            snapshot.notes.append(f"Anthropic messages quota probe failed: {probe_error}")
    return snapshot


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
        _build_openai_codex_snapshot(),
        _build_claude_snapshot(),
        _build_github_snapshot(),
        _build_openai_snapshot(),
        _build_openrouter_snapshot(),
        _build_config_only_snapshot("anthropic"),
        _build_config_only_snapshot("openclaw"),
        _build_config_only_snapshot("cursor"),
        _build_supabase_snapshot(),
        _build_railway_snapshot(),
    ]
    for snapshot in providers:
        active_count = int(active_usage.get(snapshot.provider, 0))
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


def _limit_coverage_summary(providers: list[ProviderUsageSnapshot]) -> dict[str, Any]:
    candidates = [p for p in providers if p.provider != "coherence-internal"]
    with_limit = []
    with_remaining = []
    missing = []
    partial = []
    for provider in candidates:
        has_limit = any(metric.limit is not None and metric.limit > 0 for metric in provider.metrics)
        has_remaining = any(metric.remaining is not None for metric in provider.metrics)
        if has_limit:
            with_limit.append(provider.provider)
        if has_remaining:
            with_remaining.append(provider.provider)
        if has_limit and not has_remaining:
            partial.append(provider.provider)
        if not has_limit:
            missing.append(provider.provider)
    return {
        "providers_considered": len(candidates),
        "providers_with_limit_metrics": len(with_limit),
        "providers_with_remaining_metrics": len(with_remaining),
        "providers_missing_limit_metrics": sorted(set(missing)),
        "providers_partial_limit_metrics": sorted(set(partial)),
        "coverage_ratio": round((len(with_limit) / len(candidates)), 4) if candidates else 1.0,
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
    unavailable = [p.provider for p in providers if p.status != "ok"]
    overview = ProviderUsageOverview(
        providers=providers,
        unavailable_providers=unavailable,
        tracked_providers=len(providers),
        limit_coverage=_limit_coverage_summary(providers),
    )
    _CACHE["overview"] = overview.model_dump(mode="json")
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return overview


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
                    message=f"{provider.provider} usage provider status={provider.status}",
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
                message=(
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
                    message=(
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
                message=(
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


def provider_readiness_report(*, required_providers: list[str] | None = None, force_refresh: bool = True) -> ProviderReadinessReport:
    required = [
        _normalize_provider_name(item)
        for item in (required_providers or _required_providers_from_env())
        if str(item).strip()
    ]
    if _env_truthy("AUTOMATION_REQUIRE_KEYS_FOR_ACTIVE_PROVIDERS", default=True):
        active_counts = _active_provider_usage_counts()
        for provider_name, count in active_counts.items():
            if count > 0:
                required.append(provider_name)
    required_set = set(required)
    overview = collect_usage_overview(force_refresh=force_refresh)
    by_provider = {row.provider.strip().lower(): row for row in overview.providers}

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

    return ProviderReadinessReport(
        required_providers=sorted(required_set),
        all_required_ready=len(blocking) == 0,
        blocking_issues=blocking,
        recommendations=recommendations,
        providers=rows,
    )


def _probe_openai_codex() -> tuple[bool, str]:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        oauth_ok, oauth_detail = _codex_oauth_available()
        if oauth_ok:
            return True, f"ok_via_codex_oauth_session:{oauth_detail}"
        active = int(_active_provider_usage_counts().get("openai-codex", 0))
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
        return False, f"openai_probe_failed:{exc}"


def _probe_openai() -> tuple[bool, str]:
    api_key = os.getenv("OPENAI_ADMIN_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
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
    openai_codex_active = int(active.get("openai-codex", 0))
    openai_ok, openai_detail = _probe_openai_codex()
    if openai_ok and (openclaw_active > 0 or openai_codex_active > 0):
        return True, f"ok_via_openai_codex_backend:{openai_detail}"
    return False, "missing_openclaw_key_and_openai_codex_backend"


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
        return False, "missing_anthropic_key"
    url = os.getenv("ANTHROPIC_MODELS_URL", "https://api.anthropic.com/v1/models")
    try:
        with httpx.Client(timeout=8.0, headers=_anthropic_headers()) as client:
            response = client.get(url)
            response.raise_for_status()
        return True, "ok"
    except Exception as exc:
        active = int(_active_provider_usage_counts().get("claude", 0))
        if active > 0:
            return True, "ok_via_runtime_usage_after_api_error"
        return False, f"claude_probe_failed:{exc}"


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
        "openai-codex": _probe_openai_codex,
        "openclaw": _probe_openclaw,
        "openrouter": _probe_openrouter,
        "supabase": _probe_supabase,
        "github": _probe_github,
        "railway": _probe_railway,
        "claude": _probe_claude,
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
            strategy_runs = (
                ("direct_probe", lambda: probe()),
                ("refresh_and_reprobe", lambda: _heal_strategy_refresh_and_reprobe(provider, probe)),
                (
                    "runtime_validation",
                    lambda: _heal_strategy_runtime_validation(
                        provider,
                        runtime_window_seconds=validation_window,
                        min_execution_events=min_events,
                    ),
                ),
            )
            for strategy_name, runner in strategy_runs:
                started = time.perf_counter()
                ok, detail = runner()
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

        executor = str(metadata.get("executor") or "").strip().lower()
        executor = "openclaw" if executor == "clawwork" else executor
        model = str(metadata.get("model") or "").strip()
        worker_id = str(metadata.get("worker_id") or "").strip().lower()
        agent_id = str(metadata.get("agent_id") or "").strip().lower()
        repeatable_tool_call = str(metadata.get("repeatable_tool_call") or "").strip().lower()

        inferred = _infer_provider_from_model(model)
        if inferred:
            providers.add(inferred)
        if executor == "openclaw":
            providers.add("openclaw")
        if worker_id.startswith("openai-codex") or agent_id.startswith("openai-codex"):
            providers.add("openai-codex")
        if "codex" in model.lower() or repeatable_tool_call.startswith("codex "):
            providers.add("openai-codex")

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
    readiness_by_provider = {row.provider.strip().lower(): row for row in readiness.providers}
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


def _env_flag(name: str) -> bool:
    return bool(str(os.getenv(name, "")).strip())


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


def _subscription_plans() -> list[SubscriptionPlanEstimate]:
    usage = collect_usage_overview(force_refresh=True)
    provider_by_name = {row.provider.strip().lower(): row for row in usage.providers}

    execution = agent_service.get_usage_summary().get("execution", {})
    tracked_runs = float(execution.get("tracked_runs") or 0.0) if isinstance(execution, dict) else 0.0
    failed_runs = float(execution.get("failed_runs") or 0.0) if isinstance(execution, dict) else 0.0
    success_rate = float(execution.get("success_rate") or 0.0) if isinstance(execution, dict) else 0.0

    rows: list[dict[str, Any]] = [
        {
            "provider": "openai",
            "detected": _env_flag("OPENAI_ADMIN_API_KEY") or _env_flag("OPENAI_API_KEY"),
            "current_tier": os.getenv("OPENAI_SUBSCRIPTION_TIER", "free"),
            "benefits": [
                "Higher token/request throughput for API workloads",
                "Reduced queueing risk for agent execution peaks",
            ],
            "confidence": 0.7,
            "benefit_weight": 1.0,
        },
        {
            "provider": "anthropic",
            "detected": _env_flag("ANTHROPIC_API_KEY"),
            "current_tier": os.getenv("ANTHROPIC_SUBSCRIPTION_TIER", "free"),
            "benefits": [
                "Higher fallback capacity for escalated agent tasks",
                "More resilient execution when primary provider is saturated",
            ],
            "confidence": 0.55,
            "benefit_weight": 0.8,
        },
        {
            "provider": "cursor",
            "detected": _env_flag("CURSOR_API_KEY") or _env_flag("CURSOR_CLI_MODEL"),
            "current_tier": os.getenv("CURSOR_SUBSCRIPTION_TIER", "pro"),
            "benefits": [
                "Higher agent concurrency for implementation and review loops",
                "Lower cycle time for task completion throughput",
            ],
            "confidence": 0.6,
            "benefit_weight": 0.9,
        },
        {
            "provider": "github",
            "detected": _env_flag("GITHUB_TOKEN"),
            "current_tier": os.getenv("GITHUB_SUBSCRIPTION_TIER", "free"),
            "benefits": [
                "More CI minutes and stronger governance controls",
                "Lower deployment latency under heavy PR traffic",
            ],
            "confidence": 0.65,
            "benefit_weight": 0.85,
        },
    ]

    plans: list[SubscriptionPlanEstimate] = []
    for row in rows:
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
