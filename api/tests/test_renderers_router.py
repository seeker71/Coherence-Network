"""Route-level tests for /api/renderers/* endpoints.

Covers spec R2 (renderer registration), R3 (lookup by MIME type),
R5 (CC split validation at the HTTP boundary), R9 (bundle size cap).
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.renderers import _reset_registry_for_tests


@pytest.fixture
def client():
    _reset_registry_for_tests()
    return TestClient(app)


def _valid_payload(**overrides):
    base = {
        "id": "gltf-viewer-v1",
        "name": "GLTF 3D Viewer",
        "mime_types": ["model/gltf+json", "model/gltf-binary"],
        "creator_id": "contributor:bob",
        "component_url": "https://cdn.example.com/gltf-viewer-v1.js",
        "creation_cost_cc": "12.00",
        "version": "1.0.0",
    }
    base.update(overrides)
    return base


def test_register_renderer_returns_201(client):
    response = client.post("/api/renderers/register", json=_valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "gltf-viewer-v1"
    assert body["mime_types"] == ["model/gltf+json", "model/gltf-binary"]
    assert "created_at" in body


def test_register_duplicate_id_returns_409(client):
    client.post("/api/renderers/register", json=_valid_payload())
    second = client.post("/api/renderers/register", json=_valid_payload())
    assert second.status_code == 409


def test_register_rejects_split_that_does_not_sum_to_one(client):
    payload = _valid_payload(
        cc_split={
            "asset_creator": "0.80",
            "renderer_creator": "0.15",
            "host_node": "0.10",  # total = 1.05
        }
    )
    response = client.post("/api/renderers/register", json=payload)
    assert response.status_code == 422


def test_register_rejects_oversize_bundle(client):
    payload = _valid_payload(max_bundle_bytes=512_001)
    response = client.post("/api/renderers/register", json=payload)
    assert response.status_code == 422


def test_register_rejects_empty_mime_types(client):
    payload = _valid_payload(mime_types=[])
    response = client.post("/api/renderers/register", json=payload)
    assert response.status_code == 422


def test_list_renderers_empty(client):
    response = client.get("/api/renderers")
    assert response.status_code == 200
    assert response.json() == []


def test_list_renderers_after_register(client):
    client.post("/api/renderers/register", json=_valid_payload())
    client.post(
        "/api/renderers/register",
        json=_valid_payload(id="md-v1", mime_types=["text/markdown"]),
    )
    response = client.get("/api/renderers")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert set(ids) == {"gltf-viewer-v1", "md-v1"}


def test_get_renderer_by_id_200(client):
    client.post("/api/renderers/register", json=_valid_payload())
    response = client.get("/api/renderers/gltf-viewer-v1")
    assert response.status_code == 200
    assert response.json()["id"] == "gltf-viewer-v1"


def test_get_renderer_by_id_404(client):
    response = client.get("/api/renderers/nonexistent")
    assert response.status_code == 404


def test_get_renderer_for_mime_returns_match(client):
    client.post("/api/renderers/register", json=_valid_payload())
    response = client.get("/api/renderers/for/model/gltf+json")
    assert response.status_code == 200
    assert response.json()["id"] == "gltf-viewer-v1"


def test_get_renderer_for_mime_404_when_no_match(client):
    response = client.get("/api/renderers/for/audio/midi")
    assert response.status_code == 404


def test_get_renderer_for_mime_highest_version_wins(client):
    client.post(
        "/api/renderers/register",
        json=_valid_payload(id="md-v1", mime_types=["text/markdown"], version="1.0.0"),
    )
    client.post(
        "/api/renderers/register",
        json=_valid_payload(id="md-v2", mime_types=["text/markdown"], version="2.0.0"),
    )
    response = client.get("/api/renderers/for/text/markdown")
    assert response.status_code == 200
    assert response.json()["id"] == "md-v2"
