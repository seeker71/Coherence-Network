"""Tests for POST /api/render-events — the economic loop closure.

Covers spec R4 (render event logs and attributes CC) end-to-end:
- registering a renderer with a custom split means render events use it
- no registered renderer falls back to platform default
- asset override beats renderer default
- cc_pool derives from duration_ms at the base rate
- the three shares sum to cc_pool within rounding
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.renderers import _reset_registry_for_tests
from app.routers.render_events import _reset_events_for_tests


@pytest.fixture
def client():
    _reset_registry_for_tests()
    _reset_events_for_tests()
    return TestClient(app)


def _register_renderer(client, **overrides):
    base = {
        "id": "r1",
        "name": "R1",
        "mime_types": ["text/markdown"],
        "creator_id": "contributor:bob",
        "component_url": "https://cdn.example.com/r1.js",
        "creation_cost_cc": "1.00",
        "version": "1.0.0",
    }
    base.update(overrides)
    return client.post("/api/renderers/register", json=base)


def _render(client, **overrides):
    base = {
        "asset_id": "asset:a1",
        "renderer_id": "r1",
        "reader_id": "contributor:charlie",
        "duration_ms": 15000,
    }
    base.update(overrides)
    return client.post("/api/render-events", json=base)


def test_render_event_with_default_split_and_pool(client):
    _register_renderer(client)
    response = _render(client, duration_ms=15000)
    assert response.status_code == 201
    body = response.json()
    # cc_pool = 15000 * 0.00001 = 0.15
    assert Decimal(body["cc_pool"]) == Decimal("0.15000")
    # default 80/15/5 because renderer registered without cc_split
    assert Decimal(body["cc_asset_creator"]) == Decimal("0.120000")
    assert Decimal(body["cc_renderer_creator"]) == Decimal("0.022500")
    assert Decimal(body["cc_host_node"]) == Decimal("0.007500")


def test_render_event_uses_renderer_custom_split(client):
    _register_renderer(
        client,
        cc_split={
            "asset_creator": "0.70",
            "renderer_creator": "0.25",
            "host_node": "0.05",
        },
    )
    response = _render(client, duration_ms=10000)
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["cc_pool"]) == Decimal("0.10000")
    assert Decimal(body["cc_asset_creator"]) == Decimal("0.070000")
    assert Decimal(body["cc_renderer_creator"]) == Decimal("0.025000")
    assert Decimal(body["cc_host_node"]) == Decimal("0.005000")


def test_render_event_asset_override_beats_renderer_default(client):
    _register_renderer(
        client,
        cc_split={
            "asset_creator": "0.70",
            "renderer_creator": "0.25",
            "host_node": "0.05",
        },
    )
    response = _render(
        client,
        duration_ms=10000,
        asset_cc_split_override={
            "asset_creator": "0.95",
            "renderer_creator": "0.025",
            "host_node": "0.025",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["cc_asset_creator"]) == Decimal("0.095000")


def test_render_event_unknown_renderer_uses_platform_default(client):
    # no renderer registered
    response = _render(client, renderer_id="unknown-renderer", duration_ms=20000)
    assert response.status_code == 201
    body = response.json()
    # platform default 80/15/5
    assert Decimal(body["cc_pool"]) == Decimal("0.20000")
    assert Decimal(body["cc_asset_creator"]) == Decimal("0.160000")


def test_render_event_shares_sum_to_pool(client):
    _register_renderer(client)
    response = _render(client, duration_ms=7777)
    body = response.json()
    total = (
        Decimal(body["cc_asset_creator"])
        + Decimal(body["cc_renderer_creator"])
        + Decimal(body["cc_host_node"])
    )
    assert total == Decimal(body["cc_pool"])


def test_render_event_rejects_negative_duration(client):
    _register_renderer(client)
    response = _render(client, duration_ms=-1)
    assert response.status_code == 422


def test_render_event_zero_duration_yields_zero_pool(client):
    _register_renderer(client)
    response = _render(client, duration_ms=0)
    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["cc_pool"]) == Decimal("0")


def test_get_render_event_by_id(client):
    _register_renderer(client)
    created = _render(client).json()
    event_id = created["id"]
    response = client.get(f"/api/render-events/{event_id}")
    assert response.status_code == 200
    assert response.json()["id"] == event_id


def test_get_render_event_404(client):
    response = client.get("/api/render-events/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
