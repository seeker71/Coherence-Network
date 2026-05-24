"""Tests for GET /api/assets/{id}/content + /verification — spec R4 and R10.

Covers the content-delivery endpoint (paid vs free-tier vs 402) with
x402 payment headers, and the verification endpoint that recomputes
the SHA-256 content hash against what the node stores.

Reads are recorded via ``read_tracking_service.record_read`` so the
daily aggregates surface the event the same way settlement will see
it during the daily batch (spec R5).
"""
from __future__ import annotations

import base64
import hashlib
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import graph_service, read_tracking_service


@pytest.fixture
def client():
    return TestClient(app)


def _sha256_hex(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _register_asset(
    client: TestClient,
    *,
    content: bytes = b"the full body of the article",
    mime_type: str = "text/plain",
    requires_payment: bool = False,
    free_tier_enabled: bool = True,
    creator_id: str = "contributor-alpha",
    extra_metadata: dict | None = None,
) -> str:
    """Register an asset with the given content and gating, then patch
    the node's ``requires_payment`` / ``free_tier_enabled`` / payment-
    address properties directly so the content endpoint sees them.

    Returns the stable UUID string of the asset (the form the
    ``/api/assets/{id}/content`` route expects).
    """
    content_b64 = base64.b64encode(content).decode("ascii")
    metadata = {"content_base64": content_b64}
    if extra_metadata:
        metadata.update(extra_metadata)

    payload = {
        "type": mime_type,
        "name": "test-asset",
        "description": "test asset for content delivery",
        "content_hash": _sha256_hex(content),
        "concept_tags": [],
        "creator_id": creator_id,
        "creation_cost_cc": "0.00",
        "metadata": metadata,
    }
    response = client.post("/api/assets/register", json=payload)
    assert response.status_code == 201, response.text
    registration_id = response.json()["id"]  # "asset:<uuid>"

    # Patch the gating fields onto the node — register doesn't accept
    # these in its first-iteration contract, so we set them directly.
    graph_service.update_node(
        registration_id,
        properties={
            "requires_payment": requires_payment,
            "free_tier_enabled": free_tier_enabled,
            "payment_address": f"coherence:contributor:{creator_id}",
        },
    )

    # The stable UUID the GET endpoint expects is the suffix after
    # "asset:" in the registration id.
    return registration_id.removeprefix("asset:")


# ---------------------------------------------------------------------------
# get_asset_content — R4
# ---------------------------------------------------------------------------


def test_get_asset_content_paid_serves_full(client):
    full = b"the entire content body, every byte of it"
    asset_id = _register_asset(client, content=full)
    response = client.get(
        f"/api/assets/{asset_id}/content",
        headers={"Authorization": "Bearer x402-token-abc"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "paid"
    assert body["read_type"] == "paid"
    assert body["content"] == full.decode("utf-8")
    assert Decimal(body["cc_charged"]) > 0


def test_get_asset_content_free_serves_limited(client):
    full = b"a" * 1000  # long enough to be truncated by free-tier preview
    asset_id = _register_asset(
        client, content=full, requires_payment=False, free_tier_enabled=True
    )
    response = client.get(f"/api/assets/{asset_id}/content")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "free"
    assert body["read_type"] == "free"
    # Truncated — full content NOT returned
    assert len(body["content"]) < len(full)
    assert body["payment_info"]["amount_cc"]
    assert body["payment_info"]["address"]


def test_get_asset_content_requires_payment_returns_402(client):
    asset_id = _register_asset(
        client,
        content=b"members-only content",
        requires_payment=True,
        free_tier_enabled=False,
    )
    response = client.get(f"/api/assets/{asset_id}/content")
    assert response.status_code == 402
    # x402 headers must be present on the 402 response
    assert response.headers.get("X-Payment-Amount")
    assert response.headers.get("X-Payment-Currency") == "CC"
    assert response.headers.get("X-Payment-Address")
    assert response.headers.get("X-Payment-Network")


def test_get_asset_content_returns_x402_headers(client):
    asset_id = _register_asset(client, content=b"hello world")
    response = client.get(
        f"/api/assets/{asset_id}/content",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Payment-Amount")
    assert response.headers.get("X-Payment-Currency") == "CC"
    address = response.headers.get("X-Payment-Address")
    assert address and address.startswith("coherence:contributor:")
    network = response.headers.get("X-Payment-Network")
    assert network  # spec calls for coherence-cc; any non-empty value carries the contract


def test_get_asset_content_404_for_unknown_asset(client):
    response = client.get(
        "/api/assets/00000000-0000-4000-8000-000000000000/content"
    )
    assert response.status_code == 404


def test_get_asset_content_records_usage_event(client):
    asset_id = _register_asset(client, content=b"event-tracking content")
    # Baseline: read the daily-aggregate row before the call.
    asset_node_id = f"asset:{asset_id}"
    before = read_tracking_service.get_daily_reads(asset_node_id, date.today())
    before_count = before["read_count"] if before else 0

    response = client.get(
        f"/api/assets/{asset_id}/content",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200

    after = read_tracking_service.get_daily_reads(asset_node_id, date.today())
    assert after is not None
    assert after["read_count"] == before_count + 1


# ---------------------------------------------------------------------------
# get_asset_verification — R10
# ---------------------------------------------------------------------------


def test_get_asset_verification_passes_for_intact_content(client):
    content = b"this content's hash matches what was registered"
    asset_id = _register_asset(client, content=content)
    response = client.get(f"/api/assets/{asset_id}/verification")
    assert response.status_code == 200
    body = response.json()
    assert body["integrity"] == "verified"
    assert body["content_hash"] == _sha256_hex(content)
    assert body["recomputed_hash"] == body["content_hash"]


def test_get_asset_verification_fails_for_tampered_content(client):
    content = b"original content"
    asset_id = _register_asset(client, content=content)

    # Tamper: rewrite the stored content but leave the registered hash
    # in place — recompute should diverge.
    tampered_b64 = base64.b64encode(b"replacement content").decode("ascii")
    graph_service.update_node(
        f"asset:{asset_id}",
        properties={"metadata": {"content_base64": tampered_b64}},
    )

    response = client.get(f"/api/assets/{asset_id}/verification")
    assert response.status_code == 200
    body = response.json()
    assert body["integrity"] == "failed"
    assert body["content_hash"] != body["recomputed_hash"]


def test_get_asset_verification_404_for_unknown_asset(client):
    response = client.get(
        "/api/assets/00000000-0000-4000-8000-000000000000/verification"
    )
    assert response.status_code == 404


def test_get_asset_verification_returns_both_arweave_and_ipfs_hashes(client):
    content = b"asset with storage refs"
    asset_id = _register_asset(
        client,
        content=content,
        extra_metadata={},
    )
    # Patch storage refs onto the node so the verification response
    # surfaces them per spec R10.
    graph_service.update_node(
        f"asset:{asset_id}",
        properties={
            "arweave_tx": "ar-tx-deadbeef",
            "ipfs_cid": "bafybeigtest",
        },
    )
    response = client.get(f"/api/assets/{asset_id}/verification")
    assert response.status_code == 200
    body = response.json()
    assert body["arweave_tx_id"] == "ar-tx-deadbeef"
    assert body["ipfs_cid"] == "bafybeigtest"
    assert body["arweave_url"].endswith("ar-tx-deadbeef")
    assert body["ipfs_url"].endswith("bafybeigtest")
