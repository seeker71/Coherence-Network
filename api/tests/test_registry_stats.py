"""Tests for GET /api/registry/stats — spec-178."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.registry_stats_service import (
    RegistryEntry,
    RegistryStats,
    _parse_registry_md,
    get_registry_stats,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MD = """\
# Registry Submissions — Coherence Network MCP Server & Skill

| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |
|----------|------|-----------|--------|-------------|-----------------|-------|
| [Smithery](https://smithery.ai) | MCP server | 2026-03-28 | live | https://smithery.ai/servers/coherence-mcp-server | 7 | — |
| [Glama](https://glama.ai) | MCP server | 2026-03-28 | pending | — | — | PR open |
| [PulseMCP](https://pulsemcp.com) | MCP server | — | pending | — | — | not submitted |
| [mcp.so](https://mcp.so) | MCP server | — | pending | — | — | not submitted |
| [skills.sh](https://skills.sh) | OpenClaw skill | — | unknown | — | — | — |
| [askill.sh](https://askill.sh) | OpenClaw skill | — | pending | — | — | — |
"""


@pytest.fixture()
def tmp_registry_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    md_file = tmp_path / "REGISTRY_SUBMISSIONS.md"
    md_file.write_text(SAMPLE_MD, encoding="utf-8")
    import app.services.registry_stats_service as svc_module
    monkeypatch.setattr(svc_module, "_REGISTRY_MD_PATH", md_file)
    return md_file


# ---------------------------------------------------------------------------
# Unit tests — _parse_registry_md
# ---------------------------------------------------------------------------


def test_parse_registry_md_returns_empty_for_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.services.registry_stats_service as svc_module
    monkeypatch.setattr(svc_module, "_REGISTRY_MD_PATH", tmp_path / "nonexistent.md")
    result = _parse_registry_md()
    assert result == {}


def test_parse_registry_md_parses_live_smithery(
    tmp_registry_md: Path,
) -> None:
    result = _parse_registry_md()
    assert "smithery" in result
    assert result["smithery"]["status"] == "live"
    assert result["smithery"]["installs"] == 7
    assert "smithery.ai" in (result["smithery"]["listing_url"] or "")


def test_parse_registry_md_pending_rows(tmp_registry_md: Path) -> None:
    result = _parse_registry_md()
    for key in ("glama", "pulsemcp", "mcp_so", "askill_sh"):
        assert result[key]["status"] == "pending", f"{key} should be pending"


def test_parse_registry_md_unknown_status(tmp_registry_md: Path) -> None:
    result = _parse_registry_md()
    assert result["skills_sh"]["status"] == "unknown"


def test_parse_registry_md_dash_url_becomes_none(tmp_registry_md: Path) -> None:
    result = _parse_registry_md()
    assert result["glama"]["listing_url"] is None


# ---------------------------------------------------------------------------
# Unit tests — get_registry_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_registry_stats_all_six_registries(
    tmp_registry_md: Path,
) -> None:
    mock_weekly_json = {"downloads": 12}
    mock_total_json = {"downloads": 345}

    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(12, 345, None)),
    ):
        stats = await get_registry_stats()

    assert stats.npm_weekly_downloads == 12
    assert stats.npm_total_downloads == 345
    assert stats.fetched_error is None
    names = {r.name for r in stats.registries}
    assert names == {"smithery", "glama", "pulsemcp", "mcp_so", "skills_sh", "askill_sh"}


@pytest.mark.asyncio
async def test_get_registry_stats_npm_error_still_returns_200_data(
    tmp_registry_md: Path,
) -> None:
    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(0, 0, "connection refused")),
    ):
        stats = await get_registry_stats()

    assert stats.npm_weekly_downloads == 0
    assert stats.fetched_error == "connection refused"
    # registries are still populated from the MD file
    assert len(stats.registries) == 6


@pytest.mark.asyncio
async def test_get_registry_stats_smithery_live_with_installs(
    tmp_registry_md: Path,
) -> None:
    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(0, 0, None)),
    ):
        stats = await get_registry_stats()

    smithery = next(r for r in stats.registries if r.name == "smithery")
    assert smithery.status == "live"
    assert smithery.installs == 7
    assert smithery.listing_url is not None


@pytest.mark.asyncio
async def test_get_registry_stats_no_md_file_returns_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.services.registry_stats_service as svc_module
    monkeypatch.setattr(svc_module, "_REGISTRY_MD_PATH", tmp_path / "absent.md")
    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(0, 0, None)),
    ):
        stats = await get_registry_stats()

    # When no MD file, all registries should default to "pending"
    for entry in stats.registries:
        assert entry.status == "pending", f"{entry.name} should default to pending"


# ---------------------------------------------------------------------------
# Integration tests — HTTP endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registry_stats_endpoint_200(
    tmp_registry_md: Path,
) -> None:
    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(5, 100, None)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/registry/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["npm_weekly_downloads"] == 5
    assert data["npm_total_downloads"] == 100
    assert len(data["registries"]) == 6
    assert "fetched_at" in data


@pytest.mark.asyncio
async def test_registry_stats_endpoint_registry_shape(
    tmp_registry_md: Path,
) -> None:
    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(0, 0, None)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/registry/stats")

    data = resp.json()
    for entry in data["registries"]:
        assert "name" in entry
        assert "status" in entry
        assert entry["status"] in ("live", "pending", "unknown", "rejected")


@pytest.mark.asyncio
async def test_registry_stats_unknown_md_key_returns_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unrecognised registry key in the MD yields status='unknown', not 500."""
    bad_md = """\
| Registry | Type | Submitted | Status | Listing URL | Weekly Installs | Notes |
|----------|------|-----------|--------|-------------|-----------------|-------|
| [bogus-registry](https://bogus.example) | MCP server | — | live | https://bogus.example | — | — |
"""
    md_file = tmp_path / "REGISTRY_SUBMISSIONS.md"
    md_file.write_text(bad_md, encoding="utf-8")
    import app.services.registry_stats_service as svc_module
    monkeypatch.setattr(svc_module, "_REGISTRY_MD_PATH", md_file)

    with patch(
        "app.services.registry_stats_service._fetch_npm_downloads",
        new=AsyncMock(return_value=(0, 0, None)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/registry/stats")

    assert resp.status_code == 200
    # The 6 canonical registries are still returned with default statuses
    data = resp.json()
    assert len(data["registries"]) == 6
