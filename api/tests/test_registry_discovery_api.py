from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_registry_submission_inventory_reports_core_requirement_met() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")

    assert resp.status_code == 200
    payload = resp.json()

    assert payload["summary"]["target_count"] >= 5
    assert payload["summary"]["submission_ready_count"] >= 5
    assert payload["summary"]["core_requirement_met"] is True


@pytest.mark.asyncio
async def test_registry_submission_inventory_lists_mcp_and_skill_targets() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")

    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = {item["registry_id"] for item in items}
    categories = {item["category"] for item in items}

    # Spec-180 registries: smithery, glama, pulsemcp, mcp-so, skills-sh, askill-sh
    assert {
        "smithery",
        "glama",
        "pulsemcp",
        "mcp-so",
        "skills-sh",
        "askill-sh",
    }.issubset(ids)
    assert categories == {"mcp", "skill"}


@pytest.mark.asyncio
async def test_registry_submission_inventory_anchors_targets_to_local_assets() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/discovery/registry-submissions")

    assert resp.status_code == 200
    items = resp.json()["items"]

    for item in items:
        assert item["source_paths"], f"Expected source paths for {item['registry_id']}"
        assert item["required_files"], f"Expected required files for {item['registry_id']}"
        assert item["missing_files"] == []
        assert item["status"] == "submission_ready"
        for rel_path in item["required_files"]:
            assert (REPO_ROOT / rel_path).exists(), f"Missing required file: {rel_path}"


@pytest.mark.asyncio
async def test_registry_submission_inventory_route_is_tagged_in_openapi() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")

    assert resp.status_code == 200
    operation = resp.json()["paths"]["/api/discovery/registry-submissions"]["get"]
    assert "discovery" in operation["tags"]
