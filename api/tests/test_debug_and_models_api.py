"""Tests for the debug and models API endpoints."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ═══════════════════════════════════════════════════════════════════════════════
# Debug endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_debug_status_returns_default_state():
    """GET /api/debug/status returns the default debug configuration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/debug/status")
    assert r.status_code == 200
    data = r.json()
    assert "enabled" in data
    assert "log_level" in data
    assert "trace_endpoints" in data
    assert isinstance(data["trace_endpoints"], list)


@pytest.mark.asyncio
async def test_patch_debug_enables_debug_mode():
    """PATCH /api/debug/status with enabled=true sets log level to DEBUG."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/debug/status", json={"enabled": True})
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["log_level"] == "DEBUG"


@pytest.mark.asyncio
async def test_patch_debug_disables_debug_mode():
    """PATCH /api/debug/status with enabled=false resets log level to INFO."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First enable
        await client.patch("/api/debug/status", json={"enabled": True})
        # Then disable
        r = await client.patch("/api/debug/status", json={"enabled": False})
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["log_level"] == "INFO"


@pytest.mark.asyncio
async def test_patch_debug_sets_custom_log_level():
    """PATCH /api/debug/status with log_level sets the level."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/debug/status", json={"log_level": "WARNING"})
    assert r.status_code == 200
    assert r.json()["log_level"] == "WARNING"


@pytest.mark.asyncio
async def test_patch_debug_rejects_invalid_log_level():
    """PATCH /api/debug/status with invalid log_level returns 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/debug/status", json={"log_level": "BANANA"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_debug_adds_trace_endpoint():
    """PATCH /api/debug/status can add a trace endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/debug/status", json={"trace_endpoint_add": "/api/ideas"})
    assert r.status_code == 200
    assert "/api/ideas" in r.json()["trace_endpoints"]


@pytest.mark.asyncio
async def test_patch_debug_removes_trace_endpoint():
    """PATCH /api/debug/status can remove a trace endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch("/api/debug/status", json={"trace_endpoint_add": "/api/ideas"})
        r = await client.patch("/api/debug/status", json={"trace_endpoint_remove": "/api/ideas"})
    assert r.status_code == 200
    assert "/api/ideas" not in r.json()["trace_endpoints"]


# ═══════════════════════════════════════════════════════════════════════════════
# Models endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_models_returns_executors():
    """GET /api/models returns models grouped by executor."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert "executors" in data
    assert "total" in data
    assert isinstance(data["executors"], dict)
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_get_models_routing_returns_config():
    """GET /api/models/routing returns the routing configuration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/models/routing")
    assert r.status_code == 200
    data = r.json()
    assert "task_type_tier_mapping" in data
    assert "executor_tiers" in data
    assert "fallback_chains" in data
    assert "openrouter_task_overrides" in data


@pytest.mark.asyncio
async def test_patch_models_routing_updates_tier(tmp_path, monkeypatch):
    """PATCH /api/models/routing can update task type tier mappings."""
    # Create a temporary routing config so we don't modify the real one
    temp_config = tmp_path / "model_routing.json"
    temp_config.write_text(json.dumps({
        "task_type_tier_mapping": {"spec": "strong", "impl": "strong"},
        "executor_tiers": {"claude": {"strong": ["claude-sonnet-4-6"]}},
        "fallback_chains": {},
        "openrouter_task_overrides": {},
    }))

    from app.routers import models as models_router
    monkeypatch.setattr(models_router, "_ROUTING_PATH", temp_config)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/models/routing", json={
            "task_type_tier_set": {"impl": "fast"},
        })
    assert r.status_code == 200
    data = r.json()
    assert data["task_type_tier_mapping"]["impl"] == "fast"

    # Verify persistence
    saved = json.loads(temp_config.read_text())
    assert saved["task_type_tier_mapping"]["impl"] == "fast"


@pytest.mark.asyncio
async def test_patch_models_routing_rejects_invalid_tier():
    """PATCH /api/models/routing rejects invalid tier values."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/models/routing", json={
            "task_type_tier_set": {"spec": "turbo"},
        })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_models_routing_adds_openrouter_override(tmp_path, monkeypatch):
    """PATCH /api/models/routing can set openrouter task overrides."""
    temp_config = tmp_path / "model_routing.json"
    temp_config.write_text(json.dumps({
        "task_type_tier_mapping": {},
        "executor_tiers": {},
        "fallback_chains": {},
        "openrouter_task_overrides": {},
    }))

    from app.routers import models as models_router
    monkeypatch.setattr(models_router, "_ROUTING_PATH", temp_config)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch("/api/models/routing", json={
            "openrouter_override_set": {"spec": "openrouter/google/gemini-2.5-flash"},
        })
    assert r.status_code == 200
    data = r.json()
    assert data["openrouter_task_overrides"]["spec"] == "openrouter/google/gemini-2.5-flash"
