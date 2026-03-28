"""Tests for registry metrics + stats (idea-4deb5bd7c800)."""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
@respx.mock
async def test_registry_metrics_sums_npm_and_github() -> None:
    respx.get(
        "https://api.npmjs.org/downloads/point/last-month/coherence-mcp-server",
    ).mock(return_value=httpx.Response(200, json={"downloads": 100}))
    respx.get("https://api.github.com/repos/seeker71/Coherence-Network").mock(
        return_value=httpx.Response(200, json={"stargazers_count": 7}),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/registry/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_installs"] == 107
    assert len(body["sources"]) == 2
    kinds = {s["source"]: s for s in body["sources"]}
    assert kinds["npm"]["count"] == 100
    assert kinds["github_stars"]["count"] == 7
    assert kinds["npm"]["listing_url"] == "https://www.npmjs.com/package/coherence-mcp-server"


@pytest.mark.asyncio
@respx.mock
async def test_registry_metrics_npm_failure_still_200() -> None:
    respx.get(
        "https://api.npmjs.org/downloads/point/last-month/coherence-mcp-server",
    ).mock(return_value=httpx.Response(503, text="no"))
    respx.get("https://api.github.com/repos/seeker71/Coherence-Network").mock(
        return_value=httpx.Response(200, json={"stargazers_count": 4}),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/registry/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_installs"] == 4
    kinds = {s["source"]: s for s in body["sources"]}
    assert kinds["npm"]["count"] == -1
    assert kinds["npm"].get("error")


@pytest.mark.asyncio
@respx.mock
async def test_registry_stats_has_six_registries_and_npm_counts() -> None:
    respx.get(
        "https://api.npmjs.org/downloads/point/last-month/coherence-mcp-server",
    ).mock(return_value=httpx.Response(200, json={"downloads": 50}))
    respx.get(
        "https://api.npmjs.org/downloads/point/last-week/coherence-mcp-server",
    ).mock(return_value=httpx.Response(200, json={"downloads": 12}))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/api/registry/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_downloads"] == 50
    assert body["weekly_downloads"] == 12
    assert len(body["registries"]) >= 6
    names = {row["name"] for row in body["registries"]}
    assert "Smithery" in names
    assert "askill.sh" in names
