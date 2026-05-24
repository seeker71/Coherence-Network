"""Acceptance tests for the federated value flow.

When an asset on instance A is mirrored to instance B and B serves a read
of A's content, value should flow back to A's creator without either
side surrendering authority.

The tests demonstrate the freedom-preserving shape:

- Mirror an asset and the origin fields persist (A authoritative for assets).
- Receive a signed read-attribution from a serving peer, verify, bridge it
  into local read-tracking under a federated reader_id.
- Reject envelopes with bad or missing signatures — 401, nothing stored.
- Settlement-share computation walks federated attestations, produces
  per-peer envelopes signed with the secret we share with each peer.
- Outgoing envelopes land in our outbox; incoming envelopes (a peer settling
  OUR serving fee) land in our inbox after signature verification.
- Local-reader assertions still work alongside federated reads — federation
  does not displace the existing read path; it sits next to it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.federation import (
    AssetMirrorManifest,
    ComputeFederatedSharesRequest,
    FederatedInstance,
    ReadAttributionEnvelope,
    SettlementShareEnvelope,
)
from app.services import (
    federation_service,
    federation_value_flow_service,
    read_tracking_service,
)
from app.services.federation_value_flow_service import (
    FEDERATED_READER_PREFIX,
    SignatureRejection,
    federated_reader_id,
    is_federated_reader_id,
    parse_federated_reader_id,
    sign_read_attribution,
    sign_settlement_share,
)

BASE = "http://test"

# Peer secrets used by the tests. The serving instance ("peer-b") signs
# read-attribution envelopes; the origin instance ("peer-a") signs
# settlement-share envelopes.
PEER_B_SECRET = "peer-b-test-secret"
PEER_A_SECRET = "peer-a-test-secret"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_offset(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


@pytest.fixture(autouse=True)
def _fresh_value_flow_state(monkeypatch):
    """Reset value-flow tables and register the two test peers.

    The origin instance (self) is configured via FEDERATION_INSTANCE_ID so
    settlement envelopes carry a deterministic origin_instance_id. Both
    peers register with their shared secret in `public_key` (the field is
    historically named, but functions as the symmetric federation secret).
    """
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", "self-instance")
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", "self-instance-secret")

    federation_service._ensure_schema()
    federation_value_flow_service._reset_for_tests()
    read_tracking_service._reset_for_tests()

    federation_service.register_instance(
        FederatedInstance(
            instance_id="peer-b",
            name="Peer B (serving instance)",
            endpoint_url="https://peer-b.example",
            public_key=PEER_B_SECRET,
            registered_at=_iso_now(),
        )
    )
    federation_service.register_instance(
        FederatedInstance(
            instance_id="peer-a",
            name="Peer A (origin instance)",
            endpoint_url="https://peer-a.example",
            public_key=PEER_A_SECRET,
            registered_at=_iso_now(),
        )
    )

    yield

    federation_value_flow_service._reset_for_tests()
    read_tracking_service._reset_for_tests()


def _signed_attribution(
    *,
    asset_origin_id: str,
    reader_instance_id: str,
    reader_subject: str | None = "reader-42",
    read_type: str = "paid",
    cc_amount: float = 1.0,
    observed_at: str | None = None,
    secret: str = PEER_B_SECRET,
    concept_resonance: dict | None = None,
) -> ReadAttributionEnvelope:
    unsigned = {
        "asset_origin_id": asset_origin_id,
        "reader_instance_id": reader_instance_id,
        "reader_subject": reader_subject,
        "read_type": read_type,
        "cc_amount": cc_amount,
        "concept_resonance": concept_resonance,
        "observed_at": observed_at or _iso_now(),
    }
    signature = sign_read_attribution(unsigned, secret)
    return ReadAttributionEnvelope(**unsigned, signature=signature)


# ---------------------------------------------------------------------------
# 1. Mirror records the origin fields verbatim.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mirror_asset_records_origin():
    """POST mirror creates a FederatedAssetMirrorRecord with origin fields."""
    payload = {
        "local_asset_id": "local-asset-1",
        "origin_instance_id": "peer-a",
        "origin_asset_id": "origin-asset-1",
        "origin_url": "https://peer-a.example/assets/origin-asset-1",
        "origin_payment_address": "wallet:creator-on-peer-a",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/value/mirror-asset", json=payload)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["local_asset_id"] == "local-asset-1"
        assert body["origin_instance_id"] == "peer-a"
        assert body["origin_asset_id"] == "origin-asset-1"
        assert body["origin_url"] == payload["origin_url"]
        assert body["origin_payment_address"] == "wallet:creator-on-peer-a"
        assert body["mirrored_at"]

        # The list endpoint surfaces it.
        r = await c.get("/api/federation/value/mirrors")
        assert r.status_code == 200
        mirrors = r.json()
        assert len(mirrors) == 1
        assert mirrors[0]["local_asset_id"] == "local-asset-1"


# ---------------------------------------------------------------------------
# 2. Signed read-attribution: stored + bridged into read tracking.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_attribution_envelope_recorded():
    """A signed envelope from a registered peer verifies, stores, and bridges."""
    envelope = _signed_attribution(
        asset_origin_id="my-asset-1",
        reader_instance_id="peer-b",
        reader_subject="reader-99",
        cc_amount=2.5,
        concept_resonance={"lc-trust-over-fear": 0.8},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/value/read-attribution",
            json=envelope.model_dump(mode="json"),
        )
        assert r.status_code == 201, r.text
        ack = r.json()
        assert ack["status"] == "verified"
        assert ack["federated_reader_id"] == "federated:peer-b:reader-99"

        # The attestation surfaces in the list endpoint.
        r = await c.get(
            "/api/federation/value/read-attestations",
            params={"asset_origin_id": "my-asset-1"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        att = body["attestations"][0]
        assert att["signature_verified"] is True
        assert att["status"] == "verified"
        assert att["cc_amount"] == 2.5

    # Bridge confirmed: read_tracking sees the read under the federated id.
    events = read_tracking_service.get_read_events("my-asset-1")
    assert len(events) == 1
    bridged = events[0]
    assert bridged["reader_id"] == "federated:peer-b:reader-99"
    assert bridged["cc_amount"] == 2.5
    assert bridged["read_type"] == "paid"


# ---------------------------------------------------------------------------
# 3. Bad signature: 401, nothing stored.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_attribution_rejects_unverifiable_signature():
    """A tampered or unsigned envelope is rejected with no side effects."""
    envelope = _signed_attribution(
        asset_origin_id="my-asset-2",
        reader_instance_id="peer-b",
        reader_subject="reader-99",
        cc_amount=1.0,
    )
    payload = envelope.model_dump(mode="json")
    # Tamper: bump cc_amount after signing — signature no longer matches.
    payload["cc_amount"] = 999.0

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/value/read-attribution", json=payload)
        assert r.status_code == 401, r.text

        # Nothing stored.
        r = await c.get(
            "/api/federation/value/read-attestations",
            params={"asset_origin_id": "my-asset-2"},
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0

    # No bridged read either.
    assert read_tracking_service.get_read_events("my-asset-2") == []

    # Unregistered peer → also rejected.
    unregistered = _signed_attribution(
        asset_origin_id="my-asset-2",
        reader_instance_id="peer-z-unknown",
        reader_subject="reader-1",
        secret="some-other-secret",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/value/read-attribution",
            json=unregistered.model_dump(mode="json"),
        )
        assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 4. Settlement computation walks federated reads for the period.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settlement_share_computes_for_federated_reads():
    """Seed federated attestations, run compute, assert per-peer share."""
    period_start = _iso_offset(-3600)
    period_end = _iso_offset(3600)
    observed = _iso_offset(0)

    # Two reads of two of our assets, served by peer-b.
    for asset_origin_id, cc in [("my-asset-1", 4.0), ("my-asset-2", 6.0)]:
        env = _signed_attribution(
            asset_origin_id=asset_origin_id,
            reader_instance_id="peer-b",
            reader_subject="reader-7",
            cc_amount=cc,
            observed_at=observed,
        )
        federation_value_flow_service.receive_read_attribution(env)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/value/settlement-share/compute",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "mark_settled": True,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["serving_share"] == 0.20
        assert body["creator_share"] == 0.80
        assert body["attestations_settled"] == 2
        assert len(body["envelopes"]) == 1
        env = body["envelopes"][0]
        assert env["origin_instance_id"] == "self-instance"
        assert env["serving_instance_id"] == "peer-b"
        assert env["read_count"] == 2
        # 10 CC total → 2 to serving, 8 to creator.
        assert env["cc_amount_to_serving"] == 2.0
        assert env["cc_amount_to_creator"] == 8.0
        # Asset breakdown is per-asset, sorted by asset_origin_id.
        assert len(env["asset_breakdown"]) == 2
        assert env["asset_breakdown"][0]["asset_origin_id"] == "my-asset-1"
        assert env["asset_breakdown"][0]["cc_amount_to_serving"] == 0.8
        assert env["asset_breakdown"][1]["cc_amount_to_serving"] == 1.2


# ---------------------------------------------------------------------------
# 5. Outgoing settlement envelopes land in our outbox, signed for the peer.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settlement_share_envelope_stored_in_outbox():
    """Computed envelopes are durable in the outbox and verifiable by the peer's secret."""
    period_start = _iso_offset(-3600)
    period_end = _iso_offset(3600)
    observed = _iso_offset(0)

    env = _signed_attribution(
        asset_origin_id="my-asset-3",
        reader_instance_id="peer-b",
        reader_subject="reader-5",
        cc_amount=5.0,
        observed_at=observed,
    )
    federation_value_flow_service.receive_read_attribution(env)

    federation_value_flow_service.compute_federated_shares(
        ComputeFederatedSharesRequest(
            period_start=period_start,
            period_end=period_end,
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(
            "/api/federation/value/settlement-share/outbox",
            params={"serving_instance_id": "peer-b"},
        )
        assert r.status_code == 200, r.text
        envelopes = r.json()
        assert len(envelopes) == 1
        out = envelopes[0]
        assert out["serving_instance_id"] == "peer-b"
        assert out["read_count"] == 1
        # 5 CC → 1 to serving, 4 to creator.
        assert out["cc_amount_to_serving"] == 1.0
        assert out["cc_amount_to_creator"] == 4.0
        assert out["signature"]

    # The signature is verifiable with the peer's secret — the peer (B)
    # could now POST this envelope back to their own inbox endpoint.
    envelope_model = SettlementShareEnvelope(**out)
    assert federation_value_flow_service.verify_settlement_share(
        envelope_model, PEER_B_SECRET
    )


# ---------------------------------------------------------------------------
# 6. Inbox receives signed envelopes from peers who owe us a serving fee.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_federated_settlement_inbox_lists_incoming():
    """A peer's signed settlement envelope verifies and lands in our inbox."""
    period_start = _iso_offset(-3600)
    period_end = _iso_offset(3600)

    unsigned = {
        "origin_instance_id": "peer-a",
        "serving_instance_id": "self-instance",
        "period_start": period_start,
        "period_end": period_end,
        "read_count": 4,
        "cc_amount_to_serving": 1.2,
        "cc_amount_to_creator": 4.8,
        "serving_share": 0.20,
        "creator_share": 0.80,
        "asset_breakdown": [
            {
                "asset_origin_id": "peer-a-asset-1",
                "read_count": 4,
                "cc_amount_to_serving": 1.2,
            }
        ],
    }
    signature = sign_settlement_share(unsigned, PEER_A_SECRET)
    envelope = {**unsigned, "signature": signature}

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/value/settlement-share",
            json=envelope,
        )
        assert r.status_code == 201, r.text
        ack = r.json()
        assert ack["status"] == "verified"
        assert ack["inbox_id"] >= 1

        # Inbox listing shows the entry.
        r = await c.get(
            "/api/federation/value/settlement-share/inbox",
            params={"origin_instance_id": "peer-a"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        entry = body["entries"][0]
        assert entry["origin_instance_id"] == "peer-a"
        assert entry["signature_verified"] is True
        assert entry["cc_amount_to_serving"] == 1.2

    # Tampering on inbound is rejected.
    bad = dict(envelope)
    bad["cc_amount_to_serving"] = 9999.0
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/value/settlement-share", json=bad)
        assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 7. Sovereignty: local reads remain untouched by federation work.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sovereignty_local_reads_unchanged_after_federation_work():
    """Local-reader assertions still work alongside federated ones."""
    # Local read.
    read_tracking_service.record_read(
        "asset-xyz",
        reader_id="local-reader-1",
        read_type="paid",
        cc_amount=3.0,
    )
    # Federated read of the same asset.
    env = _signed_attribution(
        asset_origin_id="asset-xyz",
        reader_instance_id="peer-b",
        reader_subject="reader-9",
        read_type="paid",
        cc_amount=1.5,
    )
    federation_value_flow_service.receive_read_attribution(env)

    events = read_tracking_service.get_read_events("asset-xyz")
    assert len(events) == 2
    reader_ids = {e["reader_id"] for e in events}
    assert "local-reader-1" in reader_ids
    assert "federated:peer-b:reader-9" in reader_ids

    local_only = [
        e for e in events if not is_federated_reader_id(e["reader_id"])
    ]
    fed_only = [e for e in events if is_federated_reader_id(e["reader_id"])]
    assert len(local_only) == 1
    assert len(fed_only) == 1
    assert local_only[0]["cc_amount"] == 3.0
    assert fed_only[0]["cc_amount"] == 1.5

    # Parser round-trip.
    parsed = parse_federated_reader_id(fed_only[0]["reader_id"])
    assert parsed == ("peer-b", "reader-9")
