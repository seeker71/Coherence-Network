"""Tests for spec-178: MCP/skill registry stats endpoint.

Covers:
- GET /api/registry/stats happy path
- All 6 registries are always present
- npm error is handled gracefully (no 500)
- Service parse logic for REGISTRY_SUBMISSIONS.md
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_REGISTRY_NAMES = {"smithery", "glama", "pulsemcp", "mcp_so", "skills_sh", "askill_sh"}


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestRegistryStatsEndpoint:
    """GET /api/registry/stats"""

    def test_returns_200(self):
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(5, 42, None),
        ):
            response = client.get("/api/registry/stats")
        assert response.status_code == 200

    def test_response_shape(self):
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(5, 42, None),
        ):
            data = client.get("/api/registry/stats").json()

        assert "npm_weekly_downloads" in data
        assert "npm_total_downloads" in data
        assert "registries" in data
        assert "fetched_at" in data

    def test_exactly_6_registries(self):
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(0, 0, None),
        ):
            data = client.get("/api/registry/stats").json()

        names = {r["name"] for r in data["registries"]}
        assert names == EXPECTED_REGISTRY_NAMES

    def test_all_registries_have_valid_status(self):
        valid_statuses = {"live", "pending", "unknown", "rejected"}
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(0, 0, None),
        ):
            data = client.get("/api/registry/stats").json()

        for reg in data["registries"]:
            assert reg["status"] in valid_statuses, f"Invalid status for {reg['name']}: {reg['status']}"

    def test_npm_error_returns_200_not_500(self):
        """Network failure fetching npm stats must NOT cause a 500."""
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(0, 0, "Connection refused"),
        ):
            response = client.get("/api/registry/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["npm_weekly_downloads"] == 0
        assert data["fetched_error"] == "Connection refused"

    def test_npm_downloads_are_integers(self):
        with patch(
            "app.services.registry_stats_service._fetch_npm_downloads",
            new_callable=AsyncMock,
            return_value=(17, 350, None),
        ):
            data = client.get("/api/registry/stats").json()

        assert isinstance(data["npm_weekly_downloads"], int)
        assert isinstance(data["npm_total_downloads"], int)
        assert data["npm_weekly_downloads"] == 17
        assert data["npm_total_downloads"] == 350


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

class TestParseRegistryMd:
    """Unit tests for _parse_registry_md."""

    def test_parse_live_row(self, tmp_path: Path):
        md = tmp_path / "REGISTRY_SUBMISSIONS.md"
        md.write_text(
            "| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |\n"
            "|----------|------|-----------|--------|-------------|-----------------|-------|\n"
            "| [Smithery](https://smithery.ai) | MCP server | 2026-03-28 | live | https://smithery.ai/servers/coherence | 7 | — |\n",
            encoding="utf-8",
        )
        from app.services import registry_stats_service as svc
        original = svc._REGISTRY_MD_PATH
        svc._REGISTRY_MD_PATH = md
        try:
            result = svc._parse_registry_md()
        finally:
            svc._REGISTRY_MD_PATH = original

        assert "smithery" in result
        assert result["smithery"]["status"] == "live"
        assert result["smithery"]["listing_url"] == "https://smithery.ai/servers/coherence"
        assert result["smithery"]["installs"] == 7

    def test_parse_pending_row_no_url(self, tmp_path: Path):
        md = tmp_path / "REGISTRY_SUBMISSIONS.md"
        md.write_text(
            "| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |\n"
            "|----------|------|-----------|--------|-------------|-----------------|-------|\n"
            "| Glama | MCP server | — | pending | — | — | — |\n",
            encoding="utf-8",
        )
        from app.services import registry_stats_service as svc
        original = svc._REGISTRY_MD_PATH
        svc._REGISTRY_MD_PATH = md
        try:
            result = svc._parse_registry_md()
        finally:
            svc._REGISTRY_MD_PATH = original

        assert "glama" in result
        assert result["glama"]["status"] == "pending"
        assert result["glama"]["listing_url"] is None
        assert result["glama"]["installs"] is None

    def test_missing_file_returns_empty_dict(self, tmp_path: Path):
        from app.services import registry_stats_service as svc
        original = svc._REGISTRY_MD_PATH
        svc._REGISTRY_MD_PATH = tmp_path / "nonexistent.md"
        try:
            result = svc._parse_registry_md()
        finally:
            svc._REGISTRY_MD_PATH = original

        assert result == {}


# ---------------------------------------------------------------------------
# Integration: stats merges MD data with defaults
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_registry_stats_merges_md(tmp_path: Path):
    """When the MD has a live entry, it overrides the default pending status."""
    md = tmp_path / "REGISTRY_SUBMISSIONS.md"
    md.write_text(
        "| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |\n"
        "|----------|------|-----------|--------|-------------|-----------------|-------|\n"
        "| smithery | MCP server | 2026-03-28 | live | https://smithery.ai/servers/coherence | 12 | — |\n",
        encoding="utf-8",
    )

    from app.services import registry_stats_service as svc
    original_path = svc._REGISTRY_MD_PATH
    svc._REGISTRY_MD_PATH = md
    try:
        with patch.object(svc, "_fetch_npm_downloads", new_callable=AsyncMock, return_value=(3, 20, None)):
            stats = await svc.get_registry_stats()
    finally:
        svc._REGISTRY_MD_PATH = original_path

    smithery = next(r for r in stats.registries if r.name == "smithery")
    assert smithery.status == "live"
    assert smithery.listing_url == "https://smithery.ai/servers/coherence"
    assert smithery.installs == 12

    # Other registries default to pending
    glama = next(r for r in stats.registries if r.name == "glama")
    assert glama.status == "pending"
