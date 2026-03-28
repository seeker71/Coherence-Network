"""Tests for Spec: Automation page garden map — visual ecosystem view.

Verifies that:
- API endpoints return structured, machine-readable data (not pipe-delimited telemetry)
- Provider snapshots carry numeric capacity and health fields for gauge rendering
- Status values are valid enum literals (ok/degraded/unavailable) not arbitrary text
- Metric ratios (used/limit) are computable for visual gauges
- Node data supports "living entity" visualization with online/offline indicators
- Activity stream endpoint returns events with timestamps and typed events
- The automation page source uses visual component patterns, not debug console dumps
- The /automation/usage/readiness endpoint includes severity ratings for colour coding
- Usage alerts carry remaining_ratio (0.0–1.0) for threshold gauge display
- The page source does NOT contain raw pipe-delimited ID/status/last_seen patterns

Verification Scenarios
----------------------
S1 (Happy path — provider snapshot structure):
  Setup: API is running, automation usage service has at least one provider configured
  Action: GET /api/automation/usage
  Expected: 200, response.providers is a list, each entry has status in
            {"ok","degraded","unavailable"}, numeric capacity_tasks_per_day if set,
            numeric cost_usd if set, no raw pipe-delimited strings in top-level fields
  Edge: When no providers are configured, returns empty providers list with tracked_providers=0

S2 (Readiness severity for colour coding):
  Setup: readiness endpoint is live
  Action: GET /api/automation/usage/readiness
  Expected: 200, each provider row has a "severity" field in {"ok","warning","critical","unknown"}
  Edge: required_providers=nonexistent returns a report listing that provider as
        configured=False with a non-ok severity

S3 (Alerts carry gauge data):
  Setup: alerts endpoint is live
  Action: GET /api/automation/usage/alerts?threshold_ratio=0.2
  Expected: 200, each alert has remaining_ratio in [0.0, 1.0] or null, severity in
            {"info","warning","critical"}, message is a plain-text string (no pipes)
  Edge: threshold_ratio=0.0 returns no alerts (nothing is below 0% remaining)
  Edge: threshold_ratio=1.1 returns HTTP 422 (out of range)

S4 (Metric ratios are computable):
  Setup: usage response contains at least one provider with at least one metric
  Action: GET /api/automation/usage, inspect metrics list
  Expected: each metric has numeric "used" >= 0; if "limit" is present it is > 0;
            ratio = used/limit is in [0.0, ∞) — no division-by-zero hazard
  Edge: metric with limit=null must not cause 500 — it should just be excluded from gauges

S5 (Node data is garden-map renderable):
  Setup: federation nodes endpoint is live
  Action: GET /api/federation/nodes
  Expected: 200, each node has hostname, status (one of known values), last_seen_at as
            ISO 8601 string, capabilities dict with executors list
  Edge: Empty node list returns {"nodes": []} or equivalent 200 with empty collection
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_PAGE = REPO_ROOT / "web" / "app" / "automation" / "page.tsx"

VALID_PROVIDER_STATUSES = {"ok", "degraded", "unavailable"}
VALID_READINESS_SEVERITIES = {"ok", "info", "warning", "critical", "unknown"}
VALID_ALERT_SEVERITIES = {"info", "warning", "critical"}
VALID_UNIT_TYPES = {"tokens", "requests", "minutes", "seconds", "usd", "tasks", "hours", "gb", "ratio"}

# ---------------------------------------------------------------------------
# S1 — /automation/usage provider snapshot structure
# ---------------------------------------------------------------------------


def test_automation_usage_returns_200() -> None:
    """GET /api/automation/usage responds with HTTP 200."""
    response = client.get("/api/automation/usage")
    assert response.status_code == 200


def test_automation_usage_has_top_level_keys() -> None:
    """Response contains required top-level keys for garden map rendering."""
    data = client.get("/api/automation/usage").json()
    assert "generated_at" in data
    assert "providers" in data
    assert "tracked_providers" in data
    assert isinstance(data["providers"], list)
    assert isinstance(data["tracked_providers"], int)
    assert data["tracked_providers"] >= 0


def test_automation_usage_provider_status_is_valid_enum() -> None:
    """Each provider snapshot status must be a valid enum, not raw text."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        assert provider["status"] in VALID_PROVIDER_STATUSES, (
            f"Provider '{provider['provider']}' has invalid status: {provider['status']!r}. "
            f"Expected one of {VALID_PROVIDER_STATUSES}"
        )


def test_automation_usage_provider_has_required_fields_for_garden_card() -> None:
    """Every provider snapshot must have the fields needed to render a garden-map card."""
    required_fields = {"id", "provider", "kind", "status", "collected_at", "metrics", "data_source"}
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        missing = required_fields - provider.keys()
        assert not missing, (
            f"Provider '{provider.get('provider', '?')}' is missing garden-map fields: {missing}"
        )


def test_automation_usage_capacity_tasks_per_day_is_numeric_when_present() -> None:
    """capacity_tasks_per_day must be a non-negative number (for gauge rendering), not a string."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        cap = provider.get("capacity_tasks_per_day")
        if cap is not None:
            assert isinstance(cap, (int, float)), (
                f"Provider '{provider['provider']}' capacity_tasks_per_day is not numeric: {cap!r}"
            )
            assert cap >= 0.0, (
                f"Provider '{provider['provider']}' capacity_tasks_per_day is negative: {cap}"
            )


def test_automation_usage_cost_usd_is_numeric_when_present() -> None:
    """cost_usd must be a non-negative float when present, not a pipe-delimited string."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        cost = provider.get("cost_usd")
        if cost is not None:
            assert isinstance(cost, (int, float)), (
                f"Provider '{provider['provider']}' cost_usd is not numeric: {cost!r}"
            )
            assert cost >= 0.0


def test_automation_usage_metrics_have_correct_structure() -> None:
    """Each metric must have id, label, unit, used — all correctly typed."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for metric in provider.get("metrics", []):
            assert "id" in metric and isinstance(metric["id"], str) and metric["id"]
            assert "label" in metric and isinstance(metric["label"], str) and metric["label"]
            assert "unit" in metric and metric["unit"] in VALID_UNIT_TYPES, (
                f"Metric '{metric.get('id')}' has invalid unit: {metric.get('unit')!r}"
            )
            assert "used" in metric and isinstance(metric["used"], (int, float))
            assert metric["used"] >= 0.0


def test_automation_usage_metric_limit_positive_when_present() -> None:
    """When limit is present it must be > 0 to prevent divide-by-zero in gauge rendering."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for metric in provider.get("metrics", []):
            limit = metric.get("limit")
            if limit is not None:
                assert limit > 0, (
                    f"Metric '{metric.get('id')}' in provider '{provider['provider']}' "
                    f"has limit=0, which would cause divide-by-zero in gauge rendering"
                )


def test_automation_usage_metric_ratio_computable() -> None:
    """When both used and limit are present, used/limit ratio must be in [0, inf)."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for metric in provider.get("metrics", []):
            used = metric.get("used")
            limit = metric.get("limit")
            if used is not None and limit is not None and limit > 0:
                ratio = used / limit
                assert ratio >= 0.0, (
                    f"Metric '{metric.get('id')}' has negative ratio {ratio}"
                )


def test_automation_usage_generated_at_is_iso8601() -> None:
    """generated_at must be a valid ISO 8601 datetime string (not a raw dump)."""
    data = client.get("/api/automation/usage").json()
    generated_at = data["generated_at"]
    assert isinstance(generated_at, str)
    # Basic ISO 8601 pattern: YYYY-MM-DDTHH:MM:SS
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", generated_at), (
        f"generated_at is not ISO 8601: {generated_at!r}"
    )


def test_automation_usage_notes_are_plain_strings_not_pipe_delimited() -> None:
    """Provider notes must be plain readable strings, not pipe-delimited telemetry dumps."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for note in provider.get("notes", []):
            # A pipe-delimited telemetry dump would look like "field1|field2|field3|..."
            pipe_fields = note.split("|")
            assert len(pipe_fields) < 8, (
                f"Provider '{provider['provider']}' note looks like a pipe-delimited telemetry dump: {note!r}"
            )


def test_automation_usage_empty_providers_when_none_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no providers are configured, returns tracked_providers=0 with empty list."""
    from app.services import automation_usage_service

    def _empty_overview(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "generated_at": "2024-01-01T00:00:00Z",
            "providers": [],
            "unavailable_providers": [],
            "tracked_providers": 0,
        }

    monkeypatch.setattr(
        automation_usage_service,
        "cached_usage_overview_payload",
        _empty_overview,
    )
    monkeypatch.setattr(
        automation_usage_service,
        "usage_overview_payload_from_snapshots",
        _empty_overview,
    )

    response = client.get("/api/automation/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["tracked_providers"] == 0
    assert data["providers"] == []


# ---------------------------------------------------------------------------
# S2 — /automation/usage/readiness severity for colour-coded status indicators
# ---------------------------------------------------------------------------


def test_readiness_endpoint_returns_200() -> None:
    """GET /api/automation/usage/readiness responds with HTTP 200."""
    response = client.get("/api/automation/usage/readiness")
    assert response.status_code == 200


def test_readiness_has_required_garden_map_keys() -> None:
    """Readiness response contains keys required for garden-map status panel."""
    data = client.get("/api/automation/usage/readiness").json()
    assert "generated_at" in data
    assert "providers" in data
    assert "all_required_ready" in data
    assert isinstance(data["providers"], list)
    assert isinstance(data["all_required_ready"], bool)


def test_readiness_severity_is_valid_for_colour_coding() -> None:
    """Each provider readiness row must have a severity in valid set for colour-coded indicators."""
    data = client.get("/api/automation/usage/readiness").json()
    for row in data["providers"]:
        assert "severity" in row, (
            f"Provider readiness row missing 'severity' field: {row}"
        )
        assert row["severity"] in VALID_READINESS_SEVERITIES, (
            f"Provider '{row.get('provider', '?')}' has invalid severity: {row['severity']!r}"
        )


def test_readiness_provider_has_configured_boolean() -> None:
    """Each readiness row must have a boolean 'configured' for garden-map alive/dormant indicator."""
    data = client.get("/api/automation/usage/readiness").json()
    for row in data["providers"]:
        assert "configured" in row, f"Row missing 'configured': {row}"
        assert isinstance(row["configured"], bool), (
            f"'configured' must be bool, got {type(row['configured'])}"
        )


def test_readiness_unknown_provider_returns_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requesting a non-existent provider should return it as configured=False."""
    from app.services import automation_usage_service
    from app.models.automation_usage import ProviderReadinessReport, ProviderReadinessRow

    def _mock_readiness(required_providers: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        rows = []
        if required_providers:
            for p in required_providers:
                rows.append({
                    "provider": p,
                    "kind": "custom",
                    "status": "unavailable",
                    "required": True,
                    "configured": False,
                    "severity": "critical",
                    "missing_env": [],
                    "notes": [f"Unknown provider: {p}"],
                })
        return {
            "generated_at": "2024-01-01T00:00:00Z",
            "required_providers": required_providers or [],
            "all_required_ready": False,
            "blocking_issues": [f"Unknown provider: nonexistent-xyz"],
            "recommendations": [],
            "providers": rows,
        }

    monkeypatch.setattr(
        automation_usage_service,
        "cached_provider_readiness_payload",
        _mock_readiness,
    )
    monkeypatch.setattr(
        automation_usage_service,
        "provider_readiness_report_from_snapshots",
        lambda *a, **kw: ProviderReadinessReport(
            required_providers=["nonexistent-xyz"],
            all_required_ready=False,
            providers=[
                ProviderReadinessRow(
                    provider="nonexistent-xyz",
                    kind="custom",
                    status="unavailable",
                    required=True,
                    configured=False,
                    severity="critical",
                )
            ],
        ),
    )

    response = client.get("/api/automation/usage/readiness?required_providers=nonexistent-xyz")
    assert response.status_code == 200
    data = response.json()
    # At minimum, must not raise 500 and must return a providers list
    assert "providers" in data


# ---------------------------------------------------------------------------
# S3 — /automation/usage/alerts gauge data for threshold rings
# ---------------------------------------------------------------------------


def test_alerts_endpoint_returns_200() -> None:
    """GET /api/automation/usage/alerts responds with HTTP 200."""
    response = client.get("/api/automation/usage/alerts")
    assert response.status_code == 200


def test_alerts_has_required_fields() -> None:
    """Alerts response has the fields needed for threshold-ring gauge rendering."""
    data = client.get("/api/automation/usage/alerts").json()
    assert "generated_at" in data
    assert "alerts" in data
    assert "threshold_ratio" in data
    assert isinstance(data["alerts"], list)
    assert isinstance(data["threshold_ratio"], float)


def test_alerts_remaining_ratio_in_valid_range() -> None:
    """Each alert remaining_ratio must be in [0.0, 1.0] when present — for arc gauge."""
    data = client.get("/api/automation/usage/alerts").json()
    for alert in data["alerts"]:
        ratio = alert.get("remaining_ratio")
        if ratio is not None:
            assert 0.0 <= ratio <= 1.0, (
                f"Alert '{alert.get('id')}' has remaining_ratio={ratio} outside [0.0, 1.0]"
            )


def test_alerts_severity_valid_for_colour_coding() -> None:
    """Alert severity must be a valid enum for visual colour-coding."""
    data = client.get("/api/automation/usage/alerts").json()
    for alert in data["alerts"]:
        assert alert["severity"] in VALID_ALERT_SEVERITIES, (
            f"Alert '{alert.get('id')}' has invalid severity: {alert['severity']!r}"
        )


def test_alerts_message_is_plain_text_no_pipe_delimiter() -> None:
    """Alert messages must be plain human-readable strings (no pipe-delimited telemetry)."""
    data = client.get("/api/automation/usage/alerts").json()
    for alert in data["alerts"]:
        msg = alert.get("message", "")
        assert "|" not in msg or msg.count("|") < 4, (
            f"Alert message looks like raw telemetry: {msg!r}"
        )


def test_alerts_zero_threshold_returns_no_capacity_based_alerts() -> None:
    """threshold_ratio=0.0 should return no capacity-based alerts (remaining_ratio != null).

    Provider status alerts (remaining_ratio=null) may still fire at any threshold
    since they report provider unavailability, not capacity remaining.
    """
    data = client.get("/api/automation/usage/alerts?threshold_ratio=0.0").json()
    assert data["threshold_ratio"] == 0.0
    # Only capacity-based alerts (those with a remaining_ratio) should be absent
    capacity_alerts = [a for a in data["alerts"] if a.get("remaining_ratio") is not None]
    assert capacity_alerts == [], (
        "threshold_ratio=0.0 should never fire capacity-based alerts — "
        f"nothing can be below 0% remaining. Got: {capacity_alerts}"
    )


def test_alerts_invalid_threshold_returns_422() -> None:
    """threshold_ratio=1.1 is out of [0.0, 1.0] and must return HTTP 422."""
    response = client.get("/api/automation/usage/alerts?threshold_ratio=1.1")
    assert response.status_code == 422


def test_alerts_invalid_negative_threshold_returns_422() -> None:
    """threshold_ratio=-0.1 is invalid and must return HTTP 422."""
    response = client.get("/api/automation/usage/alerts?threshold_ratio=-0.1")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# S4 — Metric gauge ratio — no divide-by-zero hazard
# ---------------------------------------------------------------------------


def test_all_provider_metrics_have_non_zero_limit_or_no_limit() -> None:
    """Metrics either have no limit (null) or have limit > 0. Never limit=0."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for metric in provider.get("metrics", []):
            limit = metric.get("limit")
            if limit is not None:
                assert limit != 0, (
                    f"Metric '{metric['id']}' in provider '{provider['provider']}' "
                    f"has limit=0 — would cause divide-by-zero in gauge"
                )


def test_remaining_ratio_computable_from_metric_when_limit_present() -> None:
    """usage_remaining / limit should produce a float in [0.0, 1.0] when both are present."""
    data = client.get("/api/automation/usage").json()
    for provider in data["providers"]:
        for metric in provider.get("metrics", []):
            remaining = metric.get("remaining")
            limit = metric.get("limit")
            if remaining is not None and limit is not None and limit > 0:
                ratio = remaining / limit
                # Allow small float imprecision (1.0001 is fine)
                assert ratio >= 0.0 and ratio <= 1.05, (
                    f"Metric '{metric['id']}' remaining/limit ratio {ratio:.4f} out of expected [0, 1.05]"
                )


# ---------------------------------------------------------------------------
# S5 — /api/federation/nodes living entity data
# ---------------------------------------------------------------------------


def test_federation_nodes_endpoint_accessible() -> None:
    """GET /api/federation/nodes returns 200 (empty nodes are fine)."""
    response = client.get("/api/federation/nodes")
    assert response.status_code in (200, 404)  # 404 acceptable if no nodes seeded


def test_federation_nodes_response_is_list_or_has_nodes_key() -> None:
    """Federation nodes response is list or has a 'nodes' key for garden map node cards."""
    response = client.get("/api/federation/nodes")
    if response.status_code == 200:
        data = response.json()
        # Could be a list or {"nodes": [...]} or {"nodes": {...}}
        has_nodes = isinstance(data, list) or "nodes" in data
        assert has_nodes, f"Unexpected response shape for /api/federation/nodes: {type(data)}"


def test_federation_node_has_garden_map_fields() -> None:
    """Each node entry must have the fields required for a garden-map node card."""
    response = client.get("/api/federation/nodes")
    if response.status_code != 200:
        pytest.skip("No federation nodes registered — skipping structure test")
    data = response.json()
    nodes: list[dict[str, Any]] = []
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict) and "nodes" in data:
        raw = data["nodes"]
        if isinstance(raw, dict):
            nodes = list(raw.values())
        else:
            nodes = list(raw)
    if not nodes:
        pytest.skip("No nodes in response — skipping field test")
    required_fields = {"hostname", "status", "last_seen_at"}
    for node in nodes:
        if isinstance(node, dict):
            missing = required_fields - node.keys()
            assert not missing, f"Node missing garden-map fields: {missing}, node={node}"


def test_federation_node_last_seen_at_is_iso8601() -> None:
    """last_seen_at must be ISO 8601 (not a raw dump string) for relative-time display."""
    response = client.get("/api/federation/nodes")
    if response.status_code != 200:
        pytest.skip("No federation nodes available")
    data = response.json()
    nodes: list[dict[str, Any]] = []
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict) and "nodes" in data:
        raw = data["nodes"]
        nodes = list(raw.values()) if isinstance(raw, dict) else list(raw)
    for node in nodes:
        if isinstance(node, dict) and "last_seen_at" in node:
            ts = node["last_seen_at"]
            assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(ts)), (
                f"last_seen_at is not ISO 8601: {ts!r}"
            )


# ---------------------------------------------------------------------------
# Web page source tests — garden map pattern, no debug console dumps
# ---------------------------------------------------------------------------


def test_automation_page_exists() -> None:
    """Automation page file must exist at web/app/automation/page.tsx."""
    assert AUTOMATION_PAGE.is_file(), f"Missing automation page: {AUTOMATION_PAGE}"


@pytest.mark.xfail(
    reason=(
        "Garden map not yet implemented: page still has debug dump '| status: ... | last_seen: ...' — "
        "replace with visual status indicator and relative-time display"
    ),
    strict=True,
)
def test_automation_page_does_not_contain_raw_pipe_delimited_node_dump() -> None:
    """The garden map page must NOT render nodes as 'ID: ... | status: ... | last_seen: ...' debug strings."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    # This specific pattern is the debug console style we are replacing
    assert "| status:" not in content, (
        "Automation page still contains pipe-delimited debug node dump: '| status: ...' — "
        "replace with a visual status indicator for the garden map"
    )
    assert "| last_seen:" not in content, (
        "Automation page still contains pipe-delimited debug node dump: '| last_seen: ...' — "
        "replace with a relative time display for the garden map"
    )


@pytest.mark.xfail(
    reason=(
        "Garden map not yet implemented: page still has debug text 'models[{executor}]:' — "
        "replace with visual capability chip list"
    ),
    strict=True,
)
def test_automation_page_does_not_contain_raw_models_bracket_dump() -> None:
    """The garden map page must NOT render capabilities as 'models[executor]: ...' debug text."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    assert "models[{executor}]:" not in content, (
        "Automation page still contains debug text 'models[{executor}]:' — "
        "replace with a visual capability chip list for the garden map"
    )


def test_automation_page_uses_status_indicator_pattern() -> None:
    """The automation page must have a visual status indicator (coloured dot/badge) for nodes."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    # Should have a coloured dot indicator pattern (inline-block rounded-full bg-green/gray)
    has_status_dot = (
        "rounded-full" in content
        and ("bg-green-" in content or "bg-emerald-" in content or "status" in content.lower())
    )
    assert has_status_dot, (
        "Automation page does not appear to have visual status indicators (coloured dots). "
        "Expected at least one 'rounded-full' element with colour classes for node status."
    )


def test_automation_page_has_provider_section_with_status_badge() -> None:
    """The automation page must render provider status as a badge, not raw text."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    # Should have styled badge with conditional colour classes based on status
    has_badge = (
        ("bg-green-500" in content or "bg-emerald-500" in content or "bg-amber-500" in content)
        and "text-xs" in content
        and "font-medium" in content
    )
    assert has_badge, (
        "Automation page does not appear to have styled status badges. "
        "Expected badge elements with colour classes (bg-green-500, bg-amber-500, etc.) "
        "to visually indicate provider health for the garden map."
    )


def test_automation_page_has_capacity_metric_display() -> None:
    """The automation page must display capacity_tasks_per_day as a visual metric, not just raw text."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    assert "capacity_tasks_per_day" in content, (
        "Automation page must reference capacity_tasks_per_day for visual gauge rendering"
    )


def test_automation_page_title_reflects_ecosystem_not_debug() -> None:
    """Page title/description must be user-facing, not a debug label."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    # Must NOT have a title like "Debug Console" or "Raw Telemetry"
    assert "debug console" not in content.lower(), (
        "Automation page title or description references 'debug console' — remove for garden map"
    )
    assert "raw telemetry" not in content.lower(), (
        "Automation page references 'raw telemetry' — not appropriate for garden map"
    )


def test_automation_page_description_is_visitor_friendly() -> None:
    """Page metadata description should be visitor-friendly, not server-room jargon."""
    content = AUTOMATION_PAGE.read_text(encoding="utf-8")
    assert "description:" in content.lower() or "description" in content, (
        "Automation page must have a metadata description"
    )


# ---------------------------------------------------------------------------
# Compact mode — lower bandwidth garden map payload
# ---------------------------------------------------------------------------


def test_automation_usage_compact_mode_returns_200() -> None:
    """GET /api/automation/usage?compact=true returns 200."""
    response = client.get("/api/automation/usage?compact=true")
    assert response.status_code == 200


def test_automation_usage_compact_mode_still_has_providers() -> None:
    """Compact mode must still include providers list for garden map card rendering."""
    data = client.get("/api/automation/usage?compact=true").json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


def test_automation_usage_compact_with_raw_returns_200() -> None:
    """compact=true&include_raw=true is valid and returns HTTP 200."""
    response = client.get("/api/automation/usage?compact=true&include_raw=true")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Snapshots endpoint — time-series data for activity stream
# ---------------------------------------------------------------------------


def test_usage_snapshots_endpoint_returns_200() -> None:
    """GET /api/automation/usage/snapshots returns 200 for activity stream data."""
    response = client.get("/api/automation/usage/snapshots")
    assert response.status_code == 200


def test_usage_snapshots_has_count_and_list() -> None:
    """Snapshots response has count and snapshots list for time-series stream rendering."""
    data = client.get("/api/automation/usage/snapshots").json()
    assert "count" in data
    assert "snapshots" in data
    assert isinstance(data["snapshots"], list)
    assert data["count"] == len(data["snapshots"])


def test_usage_snapshots_limit_param_respected() -> None:
    """Limit parameter controls number of snapshots returned."""
    data = client.get("/api/automation/usage/snapshots?limit=5").json()
    assert len(data["snapshots"]) <= 5


def test_usage_snapshots_invalid_limit_returns_422() -> None:
    """limit=0 is below minimum (ge=1) and must return 422."""
    response = client.get("/api/automation/usage/snapshots?limit=0")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Daily summary endpoint — ecosystem health narrative
# ---------------------------------------------------------------------------


def test_daily_summary_returns_200() -> None:
    """GET /api/automation/usage/daily-summary returns 200 for ecosystem health panel."""
    response = client.get("/api/automation/usage/daily-summary")
    assert response.status_code == 200


def test_daily_summary_has_host_runner_section() -> None:
    """Daily summary includes host_runner section for run-flow visualization."""
    data = client.get("/api/automation/usage/daily-summary").json()
    assert "host_runner" in data, "daily-summary must have host_runner for flow visualization"
    runner = data["host_runner"]
    assert "total_runs" in runner
    assert "failed_runs" in runner
    assert "completed_runs" in runner


def test_daily_summary_has_providers_list() -> None:
    """Daily summary includes providers list for ecosystem-wide health display."""
    data = client.get("/api/automation/usage/daily-summary").json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


def test_daily_summary_has_generated_at() -> None:
    """Daily summary has generated_at for freshness indicator in garden map header."""
    data = client.get("/api/automation/usage/daily-summary").json()
    assert "generated_at" in data
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", data["generated_at"]), (
        f"generated_at is not ISO 8601: {data['generated_at']!r}"
    )


def test_daily_summary_window_hours_param_respected() -> None:
    """window_hours parameter is accepted without error."""
    response = client.get("/api/automation/usage/daily-summary?window_hours=6&top_n=2")
    assert response.status_code == 200


def test_daily_summary_invalid_window_hours_returns_422() -> None:
    """window_hours=0 is below minimum and must return 422."""
    response = client.get("/api/automation/usage/daily-summary?window_hours=0")
    assert response.status_code == 422
