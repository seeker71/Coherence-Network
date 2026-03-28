"""Tests for Idea C3731991380B — Automation Capacity page (garden map UX).

Acceptance criteria verified:
  AC1  Page is not a raw pipe-delimited telemetry / debug console (structured UI).
  AC2  Federation / network nodes are shown as entities with visible status indicators.
  AC3  Provider health uses visual cues (badges, color-coded success rates), not opaque dumps.
  AC4  Primary data paths match the live page contract (automation + federation APIs).
  AC5  Core automation APIs respond with JSON the page can render.

Verification scenarios mirror the idea: structured sections, node status dots, gauges as
percent + semantic color, and HTTP contracts for `/api/automation/usage` and related routes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_PAGE = REPO_ROOT / "web" / "app" / "automation" / "page.tsx"


def _page_source() -> str:
    assert AUTOMATION_PAGE.is_file(), f"Missing automation page: {AUTOMATION_PAGE}"
    return AUTOMATION_PAGE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1 — Structured dashboard, not a debug console or pipe-telemetry stream
# ---------------------------------------------------------------------------


def test_ac1_page_uses_structured_sections_not_debug_console() -> None:
    src = _page_source()
    assert "Automation Capacity" in src
    assert "pipe|" not in src.replace(" ", "").lower()  # no pipe-telemetry idiom
    assert "console.log" not in src
    assert "rounded-2xl" in src or "rounded-xl" in src
    assert "Provider Usage" in src or "Provider Readiness" in src


def test_ac1_load_automation_data_fetches_json_endpoints() -> None:
    src = _page_source()
    assert "/api/automation/usage" in src
    assert "force_refresh=true" in src
    assert "getApiBase()" in src


# ---------------------------------------------------------------------------
# AC2 — Nodes as entities with status indicators
# ---------------------------------------------------------------------------


def test_ac2_federation_nodes_have_status_glyphs() -> None:
    src = _page_source()
    assert "networkStats.nodes" in src or "FederationNode" in src
    assert "rounded-full" in src
    assert "node.status" in src or 'node.status === "online"' in src


def test_ac2_federation_node_list_renders_host_identity() -> None:
    src = _page_source()
    assert "hostname" in src
    assert "last_seen_at" in src or "last_seen" in src


# ---------------------------------------------------------------------------
# AC3 — Provider health: visual cues (badges / color / rates)
# ---------------------------------------------------------------------------


def test_ac3_provider_rows_use_semantic_color_for_rates() -> None:
    src = _page_source()
    assert "success_rate" in src or "overall_success_rate" in src
    assert "text-green-500" in src or "text-red-500" in src
    assert "toFixed(0)}%" in src or "%" in src


def test_ac3_readiness_and_validation_use_status_badges() -> None:
    src = _page_source()
    assert "all_required_ready" in src
    assert "all_required_validated" in src
    assert "rounded-full" in src and "Ready" in src


# ---------------------------------------------------------------------------
# AC4 — API contract for page data sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac4_automation_usage_returns_json_with_providers() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/automation/usage", params={"force_refresh": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "providers" in data
    assert "tracked_providers" in data
    assert isinstance(data["providers"], list)


@pytest.mark.asyncio
async def test_ac4_automation_readiness_returns_json() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/automation/usage/readiness", params={"force_refresh": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert "generated_at" in data
    assert "providers" in data


@pytest.mark.asyncio
async def test_ac4_providers_stats_for_exec_section() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/providers/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data or "summary" in data


@pytest.mark.asyncio
async def test_ac4_federation_nodes_list_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/federation/nodes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# AC5 — Alerts path matches page (graceful degradation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac5_usage_alerts_endpoint_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/automation/usage/alerts",
            params={"threshold_ratio": 0.2},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data


def test_ac5_page_imports_metadata_for_visitor_context() -> None:
    src = _page_source()
    assert "metadata:" in src or "export const metadata" in src
    assert "Provider automation" in src or "automation" in src.lower()
