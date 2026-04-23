"""Tests for POST /api/assets/register and GET /api/assets/{id}/registration.

Covers spec R1 — MIME-aware asset registration with content provenance
and concept tags.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _valid_payload(**overrides):
    base = {
        "type": "model/gltf+json",
        "name": "Forest Scene",
        "description": "A detailed 3D forest environment",
        "content_hash": "sha256:abc123",
        "arweave_tx": "tx_abc123",
        "ipfs_cid": "QmXyz",
        "concept_tags": [
            {"concept_id": "lc-land", "weight": 0.8},
            {"concept_id": "lc-beauty", "weight": 0.4},
        ],
        "creator_id": "contributor:alice",
        "creation_cost_cc": "5.00",
        "metadata": {"vertices": 50000, "textures": 12},
    }
    base.update(overrides)
    return base


def test_register_asset_returns_201_with_mime_type(client):
    response = client.post("/api/assets/register", json=_valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "model/gltf+json"
    assert body["name"] == "Forest Scene"
    assert body["content_hash"] == "sha256:abc123"
    assert body["arweave_tx"] == "tx_abc123"
    assert body["ipfs_cid"] == "QmXyz"
    assert body["creator_id"] == "contributor:alice"
    assert Decimal(body["creation_cost_cc"]) == Decimal("5.00")
    assert body["metadata"]["vertices"] == 50000
    assert body["id"].startswith("asset:")
    assert "created_at" in body


def test_register_asset_stores_concept_tags(client):
    response = client.post("/api/assets/register", json=_valid_payload())
    body = response.json()
    assert len(body["concept_tags"]) == 2
    tags = {t["concept_id"]: t["weight"] for t in body["concept_tags"]}
    assert tags["lc-land"] == 0.8
    assert tags["lc-beauty"] == 0.4


def test_register_asset_accepts_empty_concept_tags(client):
    response = client.post(
        "/api/assets/register",
        json=_valid_payload(concept_tags=[]),
    )
    assert response.status_code == 201
    assert response.json()["concept_tags"] == []


def test_register_asset_rejects_concept_tag_weight_above_one(client):
    response = client.post(
        "/api/assets/register",
        json=_valid_payload(concept_tags=[{"concept_id": "lc-x", "weight": 1.5}]),
    )
    assert response.status_code == 422


def test_register_asset_rejects_missing_required_fields(client):
    payload = _valid_payload()
    del payload["content_hash"]
    response = client.post("/api/assets/register", json=payload)
    assert response.status_code == 422


def test_get_registration_roundtrip(client):
    created = client.post("/api/assets/register", json=_valid_payload()).json()
    asset_id = created["id"]
    response = client.get(f"/api/assets/{asset_id}/registration")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == asset_id
    assert fetched["type"] == "model/gltf+json"
    assert fetched["content_hash"] == "sha256:abc123"
    assert len(fetched["concept_tags"]) == 2


def test_get_registration_404_for_missing(client):
    response = client.get("/api/assets/nonexistent/registration")
    assert response.status_code == 404


def test_register_accepts_mime_without_storage_refs(client):
    payload = _valid_payload(arweave_tx=None, ipfs_cid=None)
    response = client.post("/api/assets/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["arweave_tx"] is None
    assert body["ipfs_cid"] is None


def test_legacy_create_asset_still_works(client):
    """Spec constraint: existing POST /api/assets must not break."""
    response = client.post(
        "/api/assets",
        json={"type": "CODE", "description": "legacy-asset via old endpoint"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "CODE"
    assert body["description"] == "legacy-asset via old endpoint"
