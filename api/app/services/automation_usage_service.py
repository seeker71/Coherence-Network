"""Provider usage adapters, normalized snapshots, and alert evaluation."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.models.automation_usage import (
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
from app.services import agent_service

_CACHE: dict[str, Any] = {"expires_at": 0.0, "overview": None}
_CACHE_TTL_SECONDS = 120.0

_PROVIDER_CONFIG_RULES: dict[str, dict[str, Any]] = {
    "coherence-internal": {"kind": "internal", "all_of": []},
    "openai": {"kind": "openai", "any_of": ["OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"]},
    "github": {"kind": "github", "all_of": ["GITHUB_TOKEN", "GITHUB_BILLING_OWNER", "GITHUB_BILLING_SCOPE"]},
    "openrouter": {"kind": "custom", "all_of": ["OPENROUTER_API_KEY"]},
    "anthropic": {"kind": "custom", "any_of": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]},
    "cursor": {"kind": "custom", "any_of": ["CURSOR_API_KEY", "CURSOR_CLI_MODEL"]},
    "railway": {"kind": "custom", "all_of": ["RAILWAY_TOKEN", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE"]},
    "vercel": {"kind": "custom", "all_of": ["VERCEL_TOKEN", "VERCEL_PROJECT_ID"]},
}

_DEFAULT_REQUIRED_PROVIDERS = ("coherence-internal", "github", "openai", "railway", "vercel")


def _snapshots_path() -> Path:
    configured = os.getenv("AUTOMATION_USAGE_SNAPSHOTS_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "logs" / "automation_usage_snapshots.json"


def _ensure_store() -> None:
    path = _snapshots_path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshots": []}, indent=2), encoding="utf-8")


def _read_store() -> list[dict[str, Any]]:
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
    path = _snapshots_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshots": rows}, indent=2), encoding="utf-8")


def _store_snapshot(snapshot: ProviderUsageSnapshot) -> None:
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


def _env_present(name: str) -> bool:
    return bool(str(os.getenv(name, "")).strip())


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


def _required_providers_from_env() -> list[str]:
    raw = os.getenv("AUTOMATION_REQUIRED_PROVIDERS", ",".join(_DEFAULT_REQUIRED_PROVIDERS))
    out = [item.strip().lower() for item in str(raw).split(",") if item.strip()]
    return out if out else list(_DEFAULT_REQUIRED_PROVIDERS)


def _build_config_only_snapshot(provider: str) -> ProviderUsageSnapshot:
    rule = _PROVIDER_CONFIG_RULES.get(provider, {})
    kind = str(rule.get("kind") or "custom")
    configured, missing, present = _configured_env_status(provider)
    status = "ok" if configured else "unavailable"
    notes = (
        [f"missing_env={','.join(missing)}"] if missing else ["configuration keys detected"]
    )
    return ProviderUsageSnapshot(
        id=f"provider_{provider}_{int(time.time())}",
        provider=provider,
        kind=kind,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
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
    token = os.getenv("GITHUB_TOKEN", "").strip()
    owner = os.getenv("GITHUB_BILLING_OWNER", "").strip()
    scope = os.getenv("GITHUB_BILLING_SCOPE", "org").strip().lower()
    if not token or not owner or scope not in {"org", "user"}:
        return ProviderUsageSnapshot(
            id=f"provider_github_{int(time.time())}",
            provider="github",
            kind="github",
            status="unavailable",
            notes=["Set GITHUB_TOKEN, GITHUB_BILLING_OWNER, and GITHUB_BILLING_SCOPE=org|user to enable real usage data."],
        )

    url = _github_billing_url(owner=owner, scope=scope)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=8.0, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return ProviderUsageSnapshot(
            id=f"provider_github_{int(time.time())}",
            provider="github",
            kind="github",
            status="degraded",
            notes=[f"GitHub billing request failed: {exc}"],
        )

    included = float(payload.get("included_minutes") or 0.0)
    used = float(payload.get("total_minutes_used") or 0.0)
    remaining = max(0.0, included - used)

    return ProviderUsageSnapshot(
        id=f"provider_github_{int(time.time())}",
        provider="github",
        kind="github",
        status="ok",
        metrics=[
            _metric(
                id="actions_minutes",
                label="GitHub Actions minutes",
                unit="minutes",
                used=used,
                remaining=remaining,
                limit=included if included > 0 else None,
                window="monthly",
            ),
        ],
        raw={
            "included_minutes": included,
            "total_minutes_used": used,
            "minutes_used_breakdown": payload.get("minutes_used_breakdown"),
        },
    )


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
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            usage_response = client.get(usage_url, params={"start_time": start_time, "end_time": now})
            usage_response.raise_for_status()
            usage_payload = usage_response.json() if isinstance(usage_response.json(), dict) else {}
    except Exception as exc:
        usage_error = str(exc)
    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            costs_response = client.get(costs_url, params={"start_time": start_time, "end_time": now})
            costs_response.raise_for_status()
            cost_payload = costs_response.json() if isinstance(costs_response.json(), dict) else {}
    except Exception as exc:
        cost_error = str(exc)

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

    return ProviderUsageSnapshot(
        id=f"provider_openai_{int(time.time())}",
        provider="openai",
        kind="openai",
        status=status,  # type: ignore[arg-type]
        metrics=metrics,
        cost_usd=round(total_cost_usd, 6) if total_cost_usd > 0 else None,
        notes=notes,
        raw={
            "usage_records": len(records),
            "cost_records": len(cost_rows),
            "window_start_unix": start_time,
            "window_end_unix": now,
        },
    )


def _collect_provider_snapshots() -> list[ProviderUsageSnapshot]:
    providers = [
        _build_internal_snapshot(),
        _build_github_snapshot(),
        _build_openai_snapshot(),
        _build_config_only_snapshot("openrouter"),
        _build_config_only_snapshot("anthropic"),
        _build_config_only_snapshot("cursor"),
        _build_config_only_snapshot("railway"),
        _build_config_only_snapshot("vercel"),
    ]
    for snapshot in providers:
        _store_snapshot(snapshot)
    return providers


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


def evaluate_usage_alerts(threshold_ratio: float = 0.2) -> UsageAlertReport:
    ratio = max(0.0, min(float(threshold_ratio), 1.0))
    overview = collect_usage_overview(force_refresh=True)

    alerts: list[UsageAlert] = []
    for provider in overview.providers:
        if provider.status != "ok":
            alerts.append(
                UsageAlert(
                    id=f"usage_alert_{provider.provider}_unavailable",
                    provider=provider.provider,
                    metric_id="provider_status",
                    severity="warning" if provider.status == "degraded" else "critical",
                    message=f"{provider.provider} usage provider status={provider.status}",
                )
            )

        for metric in provider.metrics:
            if metric.limit is None or metric.limit <= 0:
                continue
            if metric.remaining is None:
                continue
            remaining_ratio = metric.remaining / metric.limit
            if remaining_ratio <= ratio:
                severity = "critical" if remaining_ratio <= ratio / 2.0 else "warning"
                alerts.append(
                    UsageAlert(
                        id=f"usage_alert_{provider.provider}_{metric.id}",
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

    return UsageAlertReport(threshold_ratio=ratio, alerts=alerts)


def provider_readiness_report(*, required_providers: list[str] | None = None, force_refresh: bool = True) -> ProviderReadinessReport:
    required = [item.strip().lower() for item in (required_providers or _required_providers_from_env()) if item.strip()]
    required_set = set(required)
    overview = collect_usage_overview(force_refresh=force_refresh)
    by_provider = {row.provider.strip().lower(): row for row in overview.providers}

    rows: list[ProviderReadinessRow] = []
    blocking: list[str] = []
    recommendations: list[str] = []

    for provider in sorted(set(by_provider.keys()) | set(required_set)):
        snapshot = by_provider.get(provider)
        configured, missing, _present = _configured_env_status(provider)
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
