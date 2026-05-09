"""Tests for the assets-api spec (specs/assets-api.md).

Covers the legacy POST /api/assets, GET /api/assets/{id}, and
GET /api/assets endpoints — the four-type taxonomy
(CODE / MODEL / CONTENT / DATA) and pagination contract. Sibling tests
for the MIME-aware POST /api/assets/register live in
test_asset_registration.py; this file is the chain-healing test
referenced from specs/assets-api.md `test:` frontmatter.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_payload(**overrides):
    base = {
        "type": "CODE",
        "description": "test asset for chain-healing",
    }
    base.update(overrides)
    return base


def test_create_asset_returns_201_with_uuid_and_type(client):
    response = client.post("/api/assets", json=_create_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "CODE"
    assert body["description"] == "test asset for chain-healing"
    # UUID-shaped id (string carrying a UUID)
    assert "-" in body["id"]
    assert len(body["id"]) >= 32


@pytest.mark.parametrize(
    "asset_type",
    ["CODE", "MODEL", "CONTENT", "DATA"],
)
def test_create_asset_accepts_each_pipeline_type(client, asset_type):
    response = client.post("/api/assets", json=_create_payload(type=asset_type))
    assert response.status_code == 201
    assert response.json()["type"] == asset_type


def test_create_asset_rejects_invalid_type(client):
    response = client.post(
        "/api/assets",
        json=_create_payload(type="not-a-real-type"),
    )
    # Pydantic enum validation returns 422
    assert response.status_code == 422


def test_get_asset_returns_404_when_missing(client):
    # Random UUID that won't resolve to an asset node
    response = client.get("/api/assets/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    body = response.json()
    assert "Asset not found" in body.get("detail", "")


def test_list_assets_supports_pagination(client):
    response = client.get("/api/assets", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    # Paginated response carries items + pagination metadata
    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert "total" in body


def test_list_assets_default_limit_returns_listing(client):
    response = client.get("/api/assets")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    # Default limit is 100; just verify it didn't exceed cap
    assert body["limit"] <= 1000
