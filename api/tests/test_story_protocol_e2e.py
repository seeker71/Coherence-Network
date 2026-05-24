"""End-to-end integration flow for the story-protocol-integration arc.

Walks the full creator journey through the HTTP API in one shot:

    register asset  →  IP registration  →  permanent storage
        →  reader fetches content (free + paid + 402)
        →  read tracking aggregates (auto-seeds render events via bridge)
        →  evidence submission + 2-of-3 verification
        →  daily settlement (with 5× evidence multiplier)
        →  integrity verification
        →  list operations (evidence + settlement)

The per-service flow tests prove the individual surfaces in isolation:

  - test_ip_registration.py                       — R1, R7
  - test_evidence_flow.py                         — R9
  - test_settlement_flow.py                       — R8
  - test_permanent_storage.py                     — R3, R10
  - test_read_tracking.py                         — R5, R6
  - test_read_tracking_settlement_bridge.py       — bridge to settlement
  - test_assets_content.py                        — R4, R10
  - test_story_protocol.py                        — pure logic

This file is additive coverage — it proves the pieces compose into a
working user-facing flow.

Two e2e contract gaps that surfaced in PR #1963 are now both closed:

  - ``POST /api/assets/register`` auto-fires
    ``ip_registration_service.register_ip_asset`` and
    ``permanent_storage_service.upload_to_arweave/upload_to_ipfs`` per
    spec R1 (closed 2026-05-24); the helper below reads the resulting
    sp_ip_id / arweave_tx / ipfs_cid straight off the response body.
  - ``read_tracking_service.record_read`` now bridges to
    ``render_attribution_service.log_render_event`` so settlement sees
    each content read without manual ``_RENDER_EVENTS`` seeding.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.render_events import _reset_events_for_tests
from app.services import (
    evidence_service,
    graph_service,
    ip_registration_service,
    permanent_storage_service,
    read_tracking_service,
    settlement_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """TestClient with every story-protocol service reset for isolation."""
    _reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()
    read_tracking_service._reset_for_tests()
    yield TestClient(app)
    _reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()
    read_tracking_service._reset_for_tests()


# ---------------------------------------------------------------------------
# Helpers — walk the registration + IP + storage portion of the flow
# ---------------------------------------------------------------------------


def _sha256_hex(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _register_with_ip_and_storage(
    client: TestClient,
    *,
    content: bytes,
    creator_id: str = "contributor:alice",
    concept_tags: list[dict] | None = None,
    requires_payment: bool = False,
    free_tier_enabled: bool = True,
) -> tuple[str, str, dict, dict, dict]:
    """Register an asset — auto-fire pipeline lands sp_ip_id, arweave_tx
    and ipfs_cid on the response. Patches payment gating onto the node
    since those settings aren't part of the registration contract.

    Returns: (uuid_str, node_id, registration_body, ip_record, storage_pair)
    where ``ip_record`` and ``storage_pair`` reshape the auto-fire results
    into the shapes the rest of the e2e expects.
    """
    if concept_tags is None:
        concept_tags = [
            {"concept_id": "lc-land", "weight": 0.8},
            {"concept_id": "lc-beauty", "weight": 0.2},
        ]
    content_b64 = base64.b64encode(content).decode("ascii")
    payload = {
        "type": "text/plain",
        "name": "e2e-asset",
        "description": "asset under e2e test",
        "content_hash": _sha256_hex(content),
        "concept_tags": concept_tags,
        "creator_id": creator_id,
        "creation_cost_cc": "0.00",
        "metadata": {"content_base64": content_b64},
    }

    # Register — IP registration + Arweave + IPFS auto-fire inside the
    # handler. All three refs land on the response.
    response = client.post("/api/assets/register", json=payload)
    assert response.status_code == 201, response.text
    registration = response.json()
    node_id = registration["id"]
    uuid_str = node_id.removeprefix("asset:")

    assert registration["ip_status"] == "registered"
    assert registration["sp_ip_id"] is not None
    assert registration["arweave_tx"] is not None
    assert registration["arweave_tx"].startswith("ar:mock:")
    assert registration["ipfs_cid"] is not None
    assert registration["ipfs_cid"].startswith("Qm")

    ip_record = {
        "sp_ip_id": registration["sp_ip_id"],
        "ip_status": registration["ip_status"],
    }
    storage_pair = {
        "arweave": {"arweave_tx_id": registration["arweave_tx"]},
        "ipfs": {"ipfs_cid": registration["ipfs_cid"]},
    }

    # Payment gating isn't part of the registration contract — patch it
    # onto the node so the content-delivery endpoint sees the test's
    # intended payment posture.
    graph_service.update_node(
        node_id,
        properties={
            "requires_payment": requires_payment,
            "free_tier_enabled": free_tier_enabled,
            "payment_address": f"coherence:contributor:{creator_id}",
        },
    )
    return uuid_str, node_id, registration, ip_record, storage_pair


# ---------------------------------------------------------------------------
# 1. Happy path — full creator → settlement with 5× evidence multiplier
# ---------------------------------------------------------------------------


def test_full_creator_to_settlement_flow(client):
    """The full arc: register → IP → storage → 3 paid reads →
    submit verified evidence → run settlement with 5× multiplier →
    verify content integrity → list evidence + settlements."""
    content = b"the full body of the article, every byte of it, real content"
    uuid_str, node_id, registration, ip_record, storage = (
        _register_with_ip_and_storage(client, content=content)
    )
    assert registration["concept_tags"][0]["concept_id"] == "lc-land"

    # --- Reader fetches content (paid) — 3 reads ---
    for reader_n in range(3):
        response = client.get(
            f"/api/assets/{uuid_str}/content",
            headers={"Authorization": f"Bearer x402-token-reader-{reader_n}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tier"] == "paid"
        assert body["read_type"] == "paid"
        assert body["content"] == content.decode("utf-8")
        assert response.headers.get("X-Payment-Amount")
        assert response.headers.get("X-Payment-Currency") == "CC"
        assert response.headers.get("X-Payment-Address").startswith(
            "coherence:contributor:"
        )

    # --- Side-effect: read_tracking_service saw all 3 reads as paid ---
    # get_asset_content forwards read_type, payment_token, cc_amount, and
    # concept_resonance_snapshot to record_read; record_read in turn fires
    # the render-event bridge with cc_amount as the settlement pool. The
    # daily aggregate partitions cleanly between paid/free.
    agg = read_tracking_service.get_daily_aggregates(asset_id=node_id)
    assert agg["per_asset"][node_id]["total"] == 3
    assert agg["per_asset"][node_id]["paid_reads"] == 3
    assert agg["per_asset"][node_id]["free_reads"] == 0

    # --- Render events were auto-seeded by the bridge — no manual hop ---
    today = date.today()

    # --- Evidence submission — photos + GPS + attestations ---
    evidence_service.register_community_location(37.78, -122.41)
    ev_response = client.post(
        "/api/evidence",
        json={
            "asset_id": node_id,
            "submitter_id": "contributor:bob",
            "photo_urls": ["https://arweave.net/evidence-tx-1"],
            "gps": {"lat": 37.78, "lng": -122.41},
            "attestation_count": 3,
            "description": "built the thing, here is proof",
        },
    )
    assert ev_response.status_code == 201
    evidence_id = ev_response.json()["id"]

    # --- Evidence verification — 2-of-3 check passes all three ---
    verify_response = client.post(f"/api/evidence/{evidence_id}/verify")
    assert verify_response.status_code == 200
    verify_body = verify_response.json()
    assert verify_body["verified"] is True
    assert verify_body["factors_satisfied"] == 3
    assert Decimal(verify_body["cc_multiplier_applicable"]) == Decimal("5")

    # --- Settlement — aggregates 3 reads and applies 5× multiplier ---
    settle_response = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    )
    assert settle_response.status_code == 201
    batch = settle_response.json()
    assert batch["batch_date"] == today.isoformat()
    assert batch["total_read_count"] == 3
    # 3 paid reads × 0.01 CC (DEFAULT_CONTENT_CC_AMOUNT) = 0.03 base CC;
    # × 5 multiplier = 0.15 CC distributed.
    assert Decimal(batch["total_cc_distributed"]) == Decimal("0.15")
    entry = next(e for e in batch["entries"] if e["asset_id"] == node_id)
    assert Decimal(entry["evidence_multiplier"]) == Decimal("5")
    assert Decimal(entry["effective_cc_pool"]) == Decimal("0.15")
    assert entry["read_count"] == 3

    # --- Integrity verification — passes against unchanged content ---
    verif_response = client.get(f"/api/assets/{uuid_str}/verification")
    assert verif_response.status_code == 200
    verif_body = verif_response.json()
    assert verif_body["integrity"] == "verified"
    assert verif_body["content_hash"] == _sha256_hex(content)
    assert verif_body["arweave_tx_id"] == storage["arweave"]["arweave_tx_id"]
    assert verif_body["ipfs_cid"] == storage["ipfs"]["ipfs_cid"]
    assert verif_body["sp_ip_id"] == ip_record["sp_ip_id"]
    assert verif_body["arweave_url"].endswith(storage["arweave"]["arweave_tx_id"])
    assert verif_body["ipfs_url"].endswith(storage["ipfs"]["ipfs_cid"])

    # --- List operations ---
    list_ev = client.get(f"/api/evidence?asset_id={node_id}")
    assert list_ev.status_code == 200
    assert any(e["id"] == evidence_id for e in list_ev.json())

    list_settle = client.get("/api/settlement")
    assert list_settle.status_code == 200
    assert any(b["batch_date"] == today.isoformat() for b in list_settle.json())

    # --- Per-asset evidence view exposes the multiplier ---
    asset_view = client.get(f"/api/evidence/asset/{node_id}").json()
    assert asset_view["asset_id"] == node_id
    assert Decimal(asset_view["cc_multiplier_applicable"]) == Decimal("5")
    assert len(asset_view["submissions"]) == 1


# ---------------------------------------------------------------------------
# 2. Free-tier variant — no payment, still tracked, lower settlement CC
# ---------------------------------------------------------------------------


def test_free_tier_flow(client):
    """Free-tier reader path: no Authorization → 200 with truncated
    preview, read_type=free, settlement still aggregates the reads but
    without the evidence multiplier the CC is base-only."""
    content = b"a" * 1000  # long enough for free-tier preview to truncate
    uuid_str, node_id, _, _, _ = _register_with_ip_and_storage(
        client,
        content=content,
        requires_payment=False,
        free_tier_enabled=True,
    )

    # Free-tier read — no Authorization header
    response = client.get(f"/api/assets/{uuid_str}/content")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "free"
    assert body["read_type"] == "free"
    # Preview is truncated — full content not served
    assert len(body["content"]) < len(content)
    assert body["payment_info"]["amount_cc"]

    # Side-effect: read recorded as free
    agg = read_tracking_service.get_daily_aggregates(asset_id=node_id)
    assert agg["per_asset"][node_id]["free_reads"] == 1
    assert agg["per_asset"][node_id]["paid_reads"] == 0

    # Settlement: the free-tier read auto-seeded a render event via the
    # bridge with cc_pool=0 (free reads carry no CC). The batch still
    # counts the read; CC distributed is 0 with no multiplier.
    today = date.today()
    settle_body = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    ).json()
    assert settle_body["total_read_count"] == 1
    assert Decimal(settle_body["total_cc_distributed"]) == Decimal("0")
    entry = next(e for e in settle_body["entries"] if e["asset_id"] == node_id)
    assert Decimal(entry["evidence_multiplier"]) == Decimal("1")
    assert entry["read_count"] == 1


# ---------------------------------------------------------------------------
# 3. Derivative variant — second asset references first, royalty split
# ---------------------------------------------------------------------------


def test_derivative_flow(client):
    """A second asset is derived from the first; record_derivative
    captures the parent/child royalty split with the default 15/85.
    """
    parent_content = b"the original blueprint everyone is building on"
    parent_uuid, parent_node_id, _, _, _ = _register_with_ip_and_storage(
        client, content=parent_content, creator_id="contributor:original"
    )

    derivative_content = b"a translation of the original, into another tongue"
    deriv_uuid, deriv_node_id, _, _, _ = _register_with_ip_and_storage(
        client, content=derivative_content, creator_id="contributor:translator"
    )

    # Record the derivative relationship via the IP-registration service.
    derivative_record = ip_registration_service.record_derivative(
        parent_uuid, deriv_uuid, "translation"
    )
    assert derivative_record["royalty_split"] == {"parent": 0.15, "derivative": 0.85}
    assert derivative_record["parent_asset_id"] == parent_uuid
    assert derivative_record["derivative_asset_id"] == deriv_uuid

    # Reader fetches the derivative — paid read records on the derivative.
    response = client.get(
        f"/api/assets/{deriv_uuid}/content",
        headers={"Authorization": "Bearer x402-derivative-reader"},
    )
    assert response.status_code == 200
    assert response.json()["tier"] == "paid"

    # Settlement on the derivative — the royalty split lives at the IP
    # layer (record_derivative), not inside settlement's CC distribution
    # in this iteration. The single paid read already auto-seeded a
    # render event via the bridge, so settlement aggregates without
    # extra wiring.
    today = date.today()
    batch = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    ).json()
    deriv_entry = next(e for e in batch["entries"] if e["asset_id"] == deriv_node_id)
    assert deriv_entry["read_count"] == 1

    # The royalty split is queryable via the IP service — the derivative
    # carries the parent reference for any downstream royalty router.
    parent_status = ip_registration_service.get_ip_status(parent_uuid)
    deriv_status = ip_registration_service.get_ip_status(deriv_uuid)
    assert parent_status["ip_status"] == "registered"
    assert deriv_status["ip_status"] == "registered"


# ---------------------------------------------------------------------------
# 4. Integrity-check variant — content tampered, verification fails
# ---------------------------------------------------------------------------


def test_integrity_check_after_tampered_content(client):
    """The recomputed hash diverges from the registered hash when the
    stored content is rewritten — verification returns integrity=failed.
    """
    original = b"the content the creator originally registered"
    uuid_str, node_id, _, _, _ = _register_with_ip_and_storage(
        client, content=original
    )

    # First pass — verification passes against unchanged content.
    pre = client.get(f"/api/assets/{uuid_str}/verification").json()
    assert pre["integrity"] == "verified"

    # Tamper: rewrite the stored content but leave the registered hash.
    tampered = b"someone swapped the bytes - the hash on the node is now wrong"
    tampered_b64 = base64.b64encode(tampered).decode("ascii")
    graph_service.update_node(
        node_id, properties={"metadata": {"content_base64": tampered_b64}}
    )

    post = client.get(f"/api/assets/{uuid_str}/verification").json()
    assert post["integrity"] == "failed"
    assert post["content_hash"] == _sha256_hex(original)
    assert post["recomputed_hash"] == _sha256_hex(tampered)
    assert post["content_hash"] != post["recomputed_hash"]
