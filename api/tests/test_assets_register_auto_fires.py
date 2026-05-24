"""Auto-fire wiring tests for POST /api/assets/register.

Closes contract gap #1 from PR #1963's e2e investigation: the register
endpoint now fires `ip_registration_service.register_ip_asset` and
`permanent_storage_service.upload_to_arweave/upload_to_ipfs` after the
asset node lands, and surfaces the resulting `sp_ip_id`, `arweave_tx`,
and `ipfs_cid` on the response + the graph node.

Per spec story-protocol-integration.md R1: "If registration fails,
ip_status is failed and the asset remains usable without IP registration."
That escape hatch is what tests 3 and 4 prove.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    graph_service,
    ip_registration_service,
    permanent_storage_service,
)


@pytest.fixture
def client():
    """TestClient with the auto-fire services reset for isolation."""
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()
    yield TestClient(app)
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()


def _payload(content: bytes = b"the body of the article") -> dict:
    """Build a minimal register payload carrying real content bytes."""
    return {
        "type": "text/plain",
        "name": "auto-fire-test-asset",
        "description": "asset under auto-fire register test",
        "content_hash": "sha256:placeholder",
        "concept_tags": [{"concept_id": "lc-land", "weight": 1.0}],
        "creator_id": "contributor:alice",
        "creation_cost_cc": "0.00",
        "metadata": {"content_base64": base64.b64encode(content).decode("ascii")},
    }


def test_register_auto_fires_ip_registration(client):
    """Register lands sp_ip_id + ip_status=registered on the response
    and on the graph node — no manual service call needed."""
    response = client.post("/api/assets/register", json=_payload())
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["sp_ip_id"] is not None
    assert body["sp_ip_id"].startswith("sp:mock:")
    assert body["ip_status"] == "registered"
    assert body.get("ip_reason") in (None, "")

    # Side-effect: the same record is on the graph node.
    node = graph_service.get_node(body["id"])
    assert node["sp_ip_id"] == body["sp_ip_id"]
    assert node["ip_status"] == "registered"

    # Side-effect: the IP service holds the record under the asset uuid.
    asset_uuid = body["id"].removeprefix("asset:")
    ip_status = ip_registration_service.get_ip_status(asset_uuid)
    assert ip_status["ip_status"] == "registered"
    assert ip_status["sp_ip_id"] == body["sp_ip_id"]


def test_register_auto_fires_storage_upload(client):
    """Register with content_base64 lands arweave_tx + ipfs_cid on the
    response and the graph node — uploads happened, no manual call."""
    content = b"the original blueprint, full bytes preserved"
    response = client.post("/api/assets/register", json=_payload(content))
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["arweave_tx"] is not None
    assert body["arweave_tx"].startswith("ar:mock:")
    assert body["ipfs_cid"] is not None
    assert body["ipfs_cid"].startswith("Qm")

    # Side-effect: same on the node so /verification can surface them.
    node = graph_service.get_node(body["id"])
    assert node["arweave_tx"] == body["arweave_tx"]
    assert node["ipfs_cid"] == body["ipfs_cid"]

    # Side-effect: storage service can locate the asset by uuid.
    asset_uuid = body["id"].removeprefix("asset:")
    record = permanent_storage_service.get_storage_record(asset_uuid)
    assert record is not None
    assert record["arweave_tx_id"] == body["arweave_tx"]
    assert record["ipfs_cid"] == body["ipfs_cid"]


def test_register_survives_ip_registration_failure(client, monkeypatch):
    """Mock register_ip_asset to raise — the asset is still created and
    usable; ip_status=failed, ip_reason is set, sp_ip_id is None. Per
    spec R1, the asset remains usable without IP registration."""

    def _boom(asset_id, metadata=None):
        raise RuntimeError("simulated SDK outage")

    monkeypatch.setattr(
        ip_registration_service, "register_ip_asset", _boom
    )

    response = client.post("/api/assets/register", json=_payload())
    assert response.status_code == 201, response.text
    body = response.json()

    # Asset created — id present, the legacy fields all populated.
    assert body["id"].startswith("asset:")
    assert body["sp_ip_id"] is None
    assert body["ip_status"] == "failed"
    assert "simulated SDK outage" in (body.get("ip_reason") or "")

    # Asset is still usable — GET /api/assets/{uuid} resolves it.
    asset_uuid = body["id"].removeprefix("asset:")
    get_response = client.get(f"/api/assets/{asset_uuid}")
    assert get_response.status_code == 200


def test_register_survives_storage_failure(client, monkeypatch):
    """Mock upload_to_arweave to raise — the asset is created, the
    arweave/ipfs refs stay None (or whatever the caller passed in), IP
    registration still fires successfully. One surface failing must not
    take down the others."""

    def _boom(content, metadata=None, *, asset_id=None):
        raise RuntimeError("simulated bundler outage")

    monkeypatch.setattr(
        permanent_storage_service, "upload_to_arweave", _boom
    )

    response = client.post("/api/assets/register", json=_payload())
    assert response.status_code == 201, response.text
    body = response.json()

    # Arweave failed → tx stays None. IPFS still succeeded.
    assert body["arweave_tx"] is None
    assert body["ipfs_cid"] is not None
    assert body["ipfs_cid"].startswith("Qm")

    # IP registration still happened.
    assert body["sp_ip_id"] is not None
    assert body["ip_status"] == "registered"
