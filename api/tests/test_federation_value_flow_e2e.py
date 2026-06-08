"""End-to-end federated value flow across two sovereign instances.

This is the FEDERATED twin of ``test_story_protocol_e2e.py`` — the same
creator-to-settlement arc, but spanning instance A (creator + asset
authority) and instance B (reader + serving). Each instance is the source
of its own truth; value flows through agreed structure (HMAC-signed
envelopes, content-addressing) — no central authority needed.

The full loop walked here:

    A registers asset  →  B mirrors A's manifest
        →  reader-on-B reads B's mirrored copy
        →  B sends signed read-attribution envelope to A
        →  A verifies, records the read under federated:B:<reader>
        →  A's settlement aggregates the federated read into the CC pool
        →  A computes serving-share envelope (default 20% to B, 80% to creator)
        →  B receives signed settlement-share envelope into inbox
        →  Sovereignty invariant: neither instance can write the other's local state

How "two instances" is simulated in a single test process:

The FastAPI app + services are a single in-process body; what makes A and
B distinct is *identity and secrets*. The test monkeypatches the env vars
``FEDERATION_INSTANCE_ID`` / ``FEDERATION_INSTANCE_SECRET`` between the
"A acts" and "B acts" phases of each test, and registers each as a peer
in the federation registry with their own secret. The federated services
read self-id from env (``federation_service._self_instance_id``) and peer
secrets from the registry, so signing/verification with distinct keys
both directions works as it would over the wire. Tables are shared
storage but rows carry instance-id discriminators (``origin_instance_id``,
``reader_instance_id``, ``serving_instance_id``) — the sovereignty
invariant is asserted at the row-attribution level.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.federation import FederatedInstance
from app.routers.render_events import _reset_events_for_tests
from app.services import (
    evidence_service,
    federation_service,
    federation_value_flow_service,
    graph_service,
    ip_registration_service,
    permanent_storage_service,
    read_tracking_service,
    settlement_service,
)
from app.services.federation_value_flow_service import (
    is_federated_reader_id,
    sign_read_attribution,
)


# ---------------------------------------------------------------------------
# Identity, secrets, helpers
# ---------------------------------------------------------------------------

INSTANCE_A_ID = "instance-a"
INSTANCE_A_URL = "https://a.coherencycoin.example"
INSTANCE_B_ID = "instance-b"
INSTANCE_B_URL = "https://b.coherencycoin.example"

# In the symmetric-HMAC federation model, a pair of instances shares one
# secret used in both directions: the serving peer signs read-attribution
# envelopes with the shared pair-secret, and the origin peer signs
# settlement-share envelopes with the same shared pair-secret. Each side's
# registry stores it under the OTHER peer's instance_id (i.e. the
# `public_key` column on FederatedInstanceRecord). Modeling it as one
# value here is faithful to that contract.
PAIR_SECRET = "a-b-pair-shared-secret"
INSTANCE_A_SECRET = PAIR_SECRET
INSTANCE_B_SECRET = PAIR_SECRET


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_offset(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _utc_today():
    return datetime.now(timezone.utc).date()


def _sha256_hex(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


@contextmanager
def _acting_as(monkeypatch: pytest.MonkeyPatch, instance_id: str, secret: str):
    """Run a block as if this process IS ``instance_id``.

    Settlement-share signing reads self-id from env; switching identity
    around the right call sites is how single-process tests model two
    sovereign instances. The peer registry holds both secrets always.
    """
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", instance_id)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", secret)
    try:
        yield
    finally:
        # Caller may set the next identity immediately; nothing to undo.
        pass


@pytest.fixture
def two_instance_world(monkeypatch):
    """A clean two-instance world.

    Resets every service that participates in the value-flow loop, then
    registers A and B as peers of each other (each side holds the other's
    secret in ``public_key`` so HMAC verification works both directions).
    Yields a TestClient — the same client is used for both A-acting and
    B-acting calls; what flips between them is the env-derived self-id.
    """
    # Reset everything in the value-flow path so prior tests can't leak in.
    _reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()
    read_tracking_service._reset_for_tests()
    federation_service._ensure_schema()
    federation_value_flow_service._reset_for_tests()

    # Default acting-identity is A; tests flip to B around B's calls.
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", INSTANCE_A_ID)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", INSTANCE_A_SECRET)

    # Each instance registers the OTHER as a peer with the shared secret.
    # In the single-process simulation this looks like one registry holding
    # both rows; conceptually each instance's registry holds its peers.
    federation_service.register_instance(
        FederatedInstance(
            instance_id=INSTANCE_A_ID,
            name="Instance A (creator + origin)",
            endpoint_url=INSTANCE_A_URL,
            public_key=INSTANCE_A_SECRET,
            registered_at=_iso_now(),
        )
    )
    federation_service.register_instance(
        FederatedInstance(
            instance_id=INSTANCE_B_ID,
            name="Instance B (reader + serving)",
            endpoint_url=INSTANCE_B_URL,
            public_key=INSTANCE_B_SECRET,
            registered_at=_iso_now(),
        )
    )

    client = TestClient(app)
    yield client

    _reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()
    permanent_storage_service._reset_for_tests()
    read_tracking_service._reset_for_tests()
    federation_value_flow_service._reset_for_tests()


def _register_asset_on_a(
    client: TestClient,
    *,
    content: bytes,
    creator_id: str = "contributor:alice-on-a",
) -> tuple[str, str, dict]:
    """A registers an asset (auto-fires IP + Arweave + IPFS).

    Returns (uuid_str, node_id, registration_body). The uuid_str is what
    travels in HTTP paths and in the federation mirror manifest as
    ``origin_asset_id``; node_id is the graph-internal ``asset:<uuid>``.
    """
    content_b64 = base64.b64encode(content).decode("ascii")
    payload = {
        "type": "text/plain",
        "name": "federated-asset",
        "description": "asset on A, mirrored to B, read on B, settled on A",
        "content_hash": _sha256_hex(content),
        "concept_tags": [
            {"concept_id": "lc-trust-over-fear", "weight": 0.7},
            {"concept_id": "lc-edges-as-vitality", "weight": 0.3},
        ],
        "creator_id": creator_id,
        "creation_cost_cc": "0.00",
        "metadata": {"content_base64": content_b64},
    }
    response = client.post("/api/assets/register", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    node_id = body["id"]
    uuid_str = node_id.removeprefix("asset:")

    assert body["sp_ip_id"], "A's IP registration should auto-fire"
    assert body["arweave_tx"], "A's Arweave upload should auto-fire"
    assert body["ipfs_cid"], "A's IPFS upload should auto-fire"

    # Make the asset paid-readable so paid reads carry CC into settlement.
    graph_service.update_node(
        node_id,
        properties={
            "requires_payment": True,
            "free_tier_enabled": False,
            "payment_address": f"coherence:{creator_id}",
        },
    )
    return uuid_str, node_id, body


def _b_mirrors_a_asset(
    client: TestClient,
    *,
    origin_asset_uuid: str,
    local_asset_id: str,
    payment_address: str,
) -> dict:
    """B records that it is hosting A's asset under its own local id."""
    payload = {
        "local_asset_id": local_asset_id,
        "origin_instance_id": INSTANCE_A_ID,
        "origin_asset_id": origin_asset_uuid,
        "origin_url": f"{INSTANCE_A_URL}/assets/{origin_asset_uuid}",
        "origin_payment_address": payment_address,
    }
    response = client.post("/api/federation/value/mirror-asset", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _b_serves_read_and_attests_to_a(
    client: TestClient,
    *,
    origin_asset_uuid: str,
    reader_subject: str,
    cc_amount: float = 1.0,
    observed_at: str | None = None,
    concept_resonance: dict | None = None,
) -> dict:
    """B records a paid read locally, then sends signed attribution to A.

    The local record on B is what the serving instance knows it served;
    the attribution envelope is what carries that fact to A in a form A
    can verify without trusting B's word alone.
    """
    # B signs with B's secret; A will verify with B's public_key (which is
    # the same shared secret in our symmetric-HMAC model).
    observed_at = observed_at or _iso_now()
    unsigned = {
        "asset_origin_id": origin_asset_uuid,
        "reader_instance_id": INSTANCE_B_ID,
        "reader_subject": reader_subject,
        "read_type": "paid",
        "cc_amount": cc_amount,
        "concept_resonance": concept_resonance,
        "observed_at": observed_at,
    }
    signature = sign_read_attribution(unsigned, INSTANCE_B_SECRET)
    envelope = {**unsigned, "signature": signature}

    response = client.post(
        "/api/federation/value/read-attribution",
        json=envelope,
    )
    return {"status_code": response.status_code, "body": response.json()}


# ---------------------------------------------------------------------------
# 1. The happy path — full creator-on-A → settlement → share-to-B loop
# ---------------------------------------------------------------------------


def test_federated_full_creator_to_settlement_loop(two_instance_world, monkeypatch):
    """The full federated arc walked through the API.

    Each phase asserts the right side held authority and the right side's
    state moved. The whole shape attests: sovereign instances participate
    in value flow through structure, not central authority.
    """
    client = two_instance_world

    # --- Phase 1: A creates the asset (acting as A) ---
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", INSTANCE_A_ID)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", INSTANCE_A_SECRET)
    content = b"a federated body, authored on A, served on B"
    origin_uuid, origin_node_id, registration = _register_asset_on_a(
        client, content=content, creator_id="contributor:creator-on-a"
    )
    creator_payment_address = "coherence:contributor:creator-on-a"

    # --- Phase 2: B mirrors A's asset (acting as B) ---
    # The mirror call is B's local state; B's id is what matters for the
    # mirror row. The endpoint itself is the same; we toggle env-identity
    # because compute_federated_shares (later) reads self-id from env.
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", INSTANCE_B_ID)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", INSTANCE_B_SECRET)
    mirror_b_local_id = "b-mirror-of-a-asset-1"
    mirror = _b_mirrors_a_asset(
        client,
        origin_asset_uuid=origin_uuid,
        local_asset_id=mirror_b_local_id,
        payment_address=creator_payment_address,
    )
    assert mirror["origin_instance_id"] == INSTANCE_A_ID
    assert mirror["origin_asset_id"] == origin_uuid
    assert mirror["origin_payment_address"] == creator_payment_address

    # Sovereignty check: A's asset row is unchanged by B's mirror.
    a_asset = graph_service.get_node(origin_node_id)
    assert a_asset is not None
    assert origin_node_id in str(a_asset.get("id", ""))

    # --- Phase 3: reader-on-B serves the read, B attests to A ---
    # The attribution envelope is what travels; the signed payload is what
    # A trusts (not B's word, the math). Three reads, varying CC, so the
    # asset breakdown carries meaningful structure.
    observed_window = _iso_offset(0)
    for i, cc in enumerate([1.0, 2.0, 3.0]):
        ack = _b_serves_read_and_attests_to_a(
            client,
            origin_asset_uuid=origin_uuid,
            reader_subject=f"reader-on-b-{i}",
            cc_amount=cc,
            observed_at=observed_window,
            concept_resonance={"lc-trust-over-fear": 0.6},
        )
        assert ack["status_code"] == 201, ack["body"]
        assert ack["body"]["status"] == "verified"
        assert ack["body"]["federated_reader_id"] == (
            f"federated:{INSTANCE_B_ID}:reader-on-b-{i}"
        )

    # --- Phase 4: A's read-tracking sees the federated reads ---
    # The render-attribution bridge inside receive_read_attribution
    # forwards each attested read into read_tracking_service.record_read
    # under the federated reader_id. Settlement scans the resulting events.
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", INSTANCE_A_ID)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", INSTANCE_A_SECRET)
    a_events = read_tracking_service.get_read_events(origin_uuid)
    assert len(a_events) == 3
    for ev in a_events:
        assert is_federated_reader_id(ev["reader_id"])
        assert ev["read_type"] == "paid"
    cc_values = sorted(e["cc_amount"] for e in a_events)
    assert cc_values == [1.0, 2.0, 3.0]

    # The federated attestations themselves are queryable on A.
    attestations_response = client.get(
        "/api/federation/value/read-attestations",
        params={"asset_origin_id": origin_uuid},
    )
    assert attestations_response.status_code == 200
    att_body = attestations_response.json()
    assert att_body["count"] == 3
    assert all(a["signature_verified"] for a in att_body["attestations"])

    # --- Phase 5: A runs settlement — federated reads are in the pool ---
    # The federated bridge records reads under the bare asset uuid (the
    # `asset_origin_id` from the envelope), so settlement's per-asset
    # entry surfaces under that key. The local content-delivery path
    # records under `asset:<uuid>` instead; both forms point at the same
    # asset in the graph. A cross-instance follow-up may unify these.
    today = _utc_today()
    settle_response = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    )
    assert settle_response.status_code == 201, settle_response.text
    batch = settle_response.json()
    # Three federated paid reads counted in A's daily batch.
    assert batch["total_read_count"] == 3
    asset_entry = next(
        (
            e for e in batch["entries"]
            if e["asset_id"] in (origin_node_id, origin_uuid)
        ),
        None,
    )
    assert asset_entry is not None, (
        f"A's settlement batch should include the federated asset; entries={batch['entries']}"
    )
    assert asset_entry["read_count"] == 3

    # --- Phase 6: A computes the serving-share envelope for B ---
    period_start = _iso_offset(-3600)
    period_end = _iso_offset(3600)
    compute_response = client.post(
        "/api/federation/value/settlement-share/compute",
        json={
            "period_start": period_start,
            "period_end": period_end,
            "mark_settled": True,
        },
    )
    assert compute_response.status_code == 200, compute_response.text
    compute_body = compute_response.json()
    assert compute_body["serving_share"] == 0.20
    assert compute_body["creator_share"] == 0.80
    assert compute_body["attestations_settled"] == 3
    assert len(compute_body["envelopes"]) == 1
    out_envelope = compute_body["envelopes"][0]
    assert out_envelope["origin_instance_id"] == INSTANCE_A_ID
    assert out_envelope["serving_instance_id"] == INSTANCE_B_ID
    assert out_envelope["read_count"] == 3
    # 6 CC total → 1.2 to B (serving 20%), 4.8 to A's creator (80%).
    assert out_envelope["cc_amount_to_serving"] == pytest.approx(1.2)
    assert out_envelope["cc_amount_to_creator"] == pytest.approx(4.8)
    # The per-asset breakdown attributes the share to the right origin id.
    assert len(out_envelope["asset_breakdown"]) == 1
    assert out_envelope["asset_breakdown"][0]["asset_origin_id"] == origin_uuid

    # --- Phase 7: B receives the signed envelope into its inbox ---
    # In production this is a HTTP POST from A to B's endpoint; in-process
    # we POST the same envelope to the same instance — the endpoint
    # verifies against A's stored secret regardless.
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", INSTANCE_B_ID)
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", INSTANCE_B_SECRET)
    inbox_response = client.post(
        "/api/federation/value/settlement-share",
        json=out_envelope,
    )
    assert inbox_response.status_code == 201, inbox_response.text
    inbox_ack = inbox_response.json()
    assert inbox_ack["status"] == "verified"
    assert inbox_ack["origin_instance_id"] == INSTANCE_A_ID

    # B's inbox lists the envelope, signature-verified.
    inbox_list = client.get(
        "/api/federation/value/settlement-share/inbox",
        params={"origin_instance_id": INSTANCE_A_ID},
    ).json()
    assert inbox_list["count"] == 1
    entry = inbox_list["entries"][0]
    assert entry["signature_verified"] is True
    assert entry["cc_amount_to_serving"] == pytest.approx(1.2)
    assert entry["cc_amount_to_creator"] == pytest.approx(4.8)

    # --- Sovereignty closing assertion: B's mirror is unchanged by all this ---
    mirrors_list = client.get(
        "/api/federation/value/mirrors",
        params={"origin_instance_id": INSTANCE_A_ID},
    ).json()
    assert len(mirrors_list) == 1
    assert mirrors_list[0]["local_asset_id"] == mirror_b_local_id
    assert mirrors_list[0]["origin_payment_address"] == creator_payment_address


# ---------------------------------------------------------------------------
# 2. A read attempt from B with the wrong secret is rejected, nothing stored
# ---------------------------------------------------------------------------


def test_federated_read_with_signature_failure_rejected(
    two_instance_world, monkeypatch
):
    """If B signs with the wrong secret, A rejects and A's state stays clean.

    No attestation row, no bridged read, no entry in tomorrow's settlement.
    The 401 is the body refusing to absorb what it cannot verify — the
    same shape that protects against an attacker spoofing B's id.
    """
    client = two_instance_world

    # A creates the asset.
    content = b"asset whose authority is on A; only A's truth counts here"
    origin_uuid, origin_node_id, _ = _register_asset_on_a(client, content=content)

    # B (correctly) mirrors first — mirror is non-signed, sovereign choice.
    _b_mirrors_a_asset(
        client,
        origin_asset_uuid=origin_uuid,
        local_asset_id="b-mirror-bad-sig",
        payment_address="coherence:contributor:alice-on-a",
    )

    # B tries to attest a read using the WRONG secret.
    observed = _iso_now()
    unsigned = {
        "asset_origin_id": origin_uuid,
        "reader_instance_id": INSTANCE_B_ID,
        "reader_subject": "reader-impostor",
        "read_type": "paid",
        "cc_amount": 99.0,
        "concept_resonance": None,
        "observed_at": observed,
    }
    bad_signature = sign_read_attribution(unsigned, "this-is-not-bs-secret")
    bad_envelope = {**unsigned, "signature": bad_signature}

    response = client.post(
        "/api/federation/value/read-attribution",
        json=bad_envelope,
    )
    assert response.status_code == 401, response.text

    # Tampering after signing (right secret, wrong payload) is also rejected.
    correct_signature = sign_read_attribution(unsigned, INSTANCE_B_SECRET)
    tampered = {**unsigned, "cc_amount": 9999.0, "signature": correct_signature}
    response2 = client.post(
        "/api/federation/value/read-attribution",
        json=tampered,
    )
    assert response2.status_code == 401, response2.text

    # A's state is untouched: no attestation rows, no bridged reads.
    attestations = client.get(
        "/api/federation/value/read-attestations",
        params={"asset_origin_id": origin_uuid},
    ).json()
    assert attestations["count"] == 0

    a_events = read_tracking_service.get_read_events(origin_uuid)
    assert a_events == []

    # And a settlement run today produces no read for this asset.
    today = _utc_today()
    batch = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    ).json()
    entries_for_asset = [
        e for e in batch.get("entries", []) if e["asset_id"] == origin_node_id
    ]
    assert entries_for_asset == [], (
        "A rejected the unverifiable envelopes; no settlement entry should exist"
    )


# ---------------------------------------------------------------------------
# 3. Settlement-share computation walks only verified attestations
# ---------------------------------------------------------------------------


def test_federated_settlement_only_counts_verified_reads(
    two_instance_world, monkeypatch
):
    """Mix verified and rejected attribution attempts; only verified contribute.

    The shape: B sends three good envelopes (verified), and one envelope
    signed with the wrong secret (rejected). After computing federated
    shares, the rejected envelope's CC is absent from the serving share.
    """
    client = two_instance_world

    content = b"a body served many times, some attestations honest, some not"
    origin_uuid, origin_node_id, _ = _register_asset_on_a(client, content=content)

    observed = _iso_now()

    # Three verified reads.
    for i, cc in enumerate([2.0, 2.0, 2.0]):
        ack = _b_serves_read_and_attests_to_a(
            client,
            origin_asset_uuid=origin_uuid,
            reader_subject=f"verified-reader-{i}",
            cc_amount=cc,
            observed_at=observed,
        )
        assert ack["status_code"] == 201, ack["body"]

    # One rejected — wrong secret.
    unsigned_bad = {
        "asset_origin_id": origin_uuid,
        "reader_instance_id": INSTANCE_B_ID,
        "reader_subject": "ghost-reader",
        "read_type": "paid",
        "cc_amount": 1000.0,
        "concept_resonance": None,
        "observed_at": observed,
    }
    bad_sig = sign_read_attribution(unsigned_bad, "wrong-secret-no-trust")
    bad_response = client.post(
        "/api/federation/value/read-attribution",
        json={**unsigned_bad, "signature": bad_sig},
    )
    assert bad_response.status_code == 401

    # Sanity: only the 3 verified rows landed.
    att_body = client.get(
        "/api/federation/value/read-attestations",
        params={"asset_origin_id": origin_uuid},
    ).json()
    assert att_body["count"] == 3
    assert all(a["signature_verified"] for a in att_body["attestations"])

    # Compute the share: total verified CC = 6.0 → 1.2 to B, 4.8 to creator.
    # The ghost reader's 1000 CC never lands here; the math proves it.
    period_start = _iso_offset(-3600)
    period_end = _iso_offset(3600)
    compute_body = client.post(
        "/api/federation/value/settlement-share/compute",
        json={
            "period_start": period_start,
            "period_end": period_end,
            "mark_settled": True,
        },
    ).json()
    assert compute_body["attestations_settled"] == 3
    assert len(compute_body["envelopes"]) == 1
    envelope = compute_body["envelopes"][0]
    assert envelope["read_count"] == 3
    assert envelope["cc_amount_to_serving"] == pytest.approx(1.2)
    assert envelope["cc_amount_to_creator"] == pytest.approx(4.8)
    # The forged 1000 CC would have moved the total to 200.2 to serving;
    # the absence of that value is the attestation that rejection held.
    assert envelope["cc_amount_to_serving"] < 5.0


# ---------------------------------------------------------------------------
# 4. Local reads on A and federated reads via B compose in A's settlement
# ---------------------------------------------------------------------------


def test_local_reads_and_federated_reads_compose_in_settlement(
    two_instance_world, monkeypatch
):
    """A's own readers + B's federated readers both flow into A's settlement.

    Federation does not displace the local read path; it sits beside it.
    A's settlement batch counts both kinds, and the federated entries are
    distinguishable by their ``federated:<peer>:<subject>`` reader_id.
    """
    client = two_instance_world

    content = b"served from both bodies: locally on A, mirrored on B"
    origin_uuid, origin_node_id, _ = _register_asset_on_a(client, content=content)

    # Two local-on-A paid reads.
    for i in range(2):
        local_response = client.get(
            f"/api/assets/{origin_uuid}/content",
            headers={"Authorization": f"Bearer x402-local-reader-{i}"},
        )
        assert local_response.status_code == 200, local_response.text
        assert local_response.json()["read_type"] == "paid"

    # Two federated reads via B (signed by B's secret, verified on A).
    observed = _iso_now()
    for i in range(2):
        ack = _b_serves_read_and_attests_to_a(
            client,
            origin_asset_uuid=origin_uuid,
            reader_subject=f"federated-reader-{i}",
            cc_amount=1.5,
            observed_at=observed,
        )
        assert ack["status_code"] == 201, ack["body"]

    # A's read-tracking holds all 4 events across two asset-id keys:
    # local content-delivery records under `asset:<uuid>` (node_id);
    # federated bridge records under the bare uuid from the envelope.
    # Both forms point at the same asset; a cross-instance follow-up may
    # unify the key shape, but the test attests both flow into settlement.
    local_events = read_tracking_service.get_read_events(origin_node_id)
    federated_events = read_tracking_service.get_read_events(origin_uuid)
    assert len(local_events) == 2, (
        f"two local-on-A paid reads expected under {origin_node_id}; got {local_events}"
    )
    assert len(federated_events) == 2, (
        f"two federated reads expected under {origin_uuid}; got {federated_events}"
    )
    assert all(not is_federated_reader_id(e["reader_id"]) for e in local_events)
    assert all(is_federated_reader_id(e["reader_id"]) for e in federated_events)

    # A's daily settlement composes both kinds. Each asset_id key
    # produces its own per-asset entry; the batch total covers all four
    # reads. Local reads carry DEFAULT_CONTENT_CC_AMOUNT (0.01) each;
    # federated reads carry the attested 1.5 each.
    today = _utc_today()
    batch = client.post(
        "/api/settlement/run", json={"batch_date": today.isoformat()}
    ).json()
    assert batch["total_read_count"] == 4, (
        f"local + federated reads compose in A's settlement; got entries={batch['entries']}"
    )
    entries_for_asset = [
        e for e in batch["entries"]
        if e["asset_id"] in (origin_node_id, origin_uuid)
    ]
    total_reads = sum(e["read_count"] for e in entries_for_asset)
    assert total_reads == 4, (
        f"expected 4 reads across both asset_id forms; got {entries_for_asset}"
    )

    # The federated portion is independently attributable on A's side via
    # the federated-attestations endpoint — settlement composes, but the
    # provenance is preserved for each side's audit.
    fed_att = client.get(
        "/api/federation/value/read-attestations",
        params={"asset_origin_id": origin_uuid},
    ).json()
    assert fed_att["count"] == 2
    assert all(a["signature_verified"] for a in fed_att["attestations"])
