"""Cross-instance identity — recognition by shared pubkey, not central registry.

Identity belongs to the contributor, not the instance. Each contributor
holds an ed25519 keypair; their identity IS the public key. An instance
links a pubkey to a contributor only after the contributor proves
possession by signing a canonical claim payload. Cross-instance
recognition is signature verification, not deference to a central
issuer — when two instances independently verify that the same pubkey
belongs to someone on each side, they can record an alias without
either claiming authority over who the person "really is."

The tests below walk that arc:

  1. Valid signature → pubkey claimed.
  2. Invalid signature → 401, nothing stored.
  3. Re-claim of the same pubkey → idempotent, no error.
  4. Pubkey rotation requires a counter-signature from the OLD pubkey.
  5. Peer recognition envelope records an alias when our pubkey matches.
  6. Peer envelope with no local match → no record (we do not speculate).
  7. Aliases endpoint returns what we've recognized.
  8. Two instances recognize the same person via the same pubkey — both
     sides record an alias pointing at the other.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import cross_instance_identity_service
from app.services.identity_signing import (
    generate_keypair,
    sign_payload,
)

BASE = "http://test"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _fresh_identity_state():
    cross_instance_identity_service._reset_for_tests()
    yield
    cross_instance_identity_service._reset_for_tests()


def _signed_claim(
    contributor_id: str,
    *,
    private_key_hex: str | None = None,
    public_key_hex: str | None = None,
) -> dict:
    """Generate a fresh keypair (if not provided) and sign a claim with it."""
    if private_key_hex is None or public_key_hex is None:
        private_key_hex, public_key_hex = generate_keypair()
    payload = cross_instance_identity_service.claim_payload(
        contributor_id=contributor_id,
        public_key_hex=public_key_hex,
        issued_at=_iso_now(),
    )
    signature = sign_payload(payload, private_key_hex)
    return {
        "contributor_id": contributor_id,
        "public_key_hex": public_key_hex,
        "claim_signature": signature,
        "claim_payload": payload,
        "_private_key_hex": private_key_hex,
    }


# ---------------------------------------------------------------------------
# 1. Valid signature → claim succeeds and pubkey is linked.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_with_valid_signature_succeeds():
    claim = _signed_claim("alice")
    body = {k: v for k, v in claim.items() if not k.startswith("_")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/identity/claim", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["contributor_id"] == "alice"
        assert data["public_key_hex"] == claim["public_key_hex"]
        assert data["claimed"] is True
        assert data["rotated"] is False

    # Stored: lookup by pubkey returns the local contributor.
    assert (
        cross_instance_identity_service.find_contributor_by_pubkey(
            claim["public_key_hex"]
        )
        == "alice"
    )


# ---------------------------------------------------------------------------
# 2. Invalid signature → 401, nothing stored.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_with_invalid_signature_rejected():
    claim = _signed_claim("bob")
    # Tamper with the signature.
    bad_signature = "00" * 64
    body = {
        "contributor_id": claim["contributor_id"],
        "public_key_hex": claim["public_key_hex"],
        "claim_signature": bad_signature,
        "claim_payload": claim["claim_payload"],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/identity/claim", json=body)
        assert r.status_code == 401, r.text

    # Nothing was stored — pubkey is still free.
    assert (
        cross_instance_identity_service.find_contributor_by_pubkey(
            claim["public_key_hex"]
        )
        is None
    )


# ---------------------------------------------------------------------------
# 3. Re-claim of the same pubkey is idempotent.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_is_idempotent_for_same_pubkey():
    claim = _signed_claim("carol")
    body = {k: v for k, v in claim.items() if not k.startswith("_")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r1 = await c.post("/api/identity/claim", json=body)
        assert r1.status_code == 200

        # A fresh signature over a fresh payload, but the SAME pubkey.
        # Idempotent: no error, no change.
        claim2 = _signed_claim(
            "carol",
            private_key_hex=claim["_private_key_hex"],
            public_key_hex=claim["public_key_hex"],
        )
        body2 = {k: v for k, v in claim2.items() if not k.startswith("_")}
        r2 = await c.post("/api/identity/claim", json=body2)
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["claimed"] is True
        assert data2.get("idempotent") is True


# ---------------------------------------------------------------------------
# 4. Pubkey rotation requires a counter-signature from the OLD pubkey.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pubkey_rotation_requires_old_key_signature():
    # First claim establishes the original pubkey.
    first = _signed_claim("dora")
    first_body = {k: v for k, v in first.items() if not k.startswith("_")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/identity/claim", json=first_body)
        assert r.status_code == 200

        # Generate a NEW keypair and try to swap without rotation_signature.
        new_priv, new_pub = generate_keypair()
        new_payload = cross_instance_identity_service.claim_payload(
            contributor_id="dora",
            public_key_hex=new_pub,
            issued_at=_iso_now(),
        )
        new_sig = sign_payload(new_payload, new_priv)
        no_rotation_body = {
            "contributor_id": "dora",
            "public_key_hex": new_pub,
            "claim_signature": new_sig,
            "claim_payload": new_payload,
        }
        r_fail = await c.post("/api/identity/claim", json=no_rotation_body)
        assert r_fail.status_code == 409, r_fail.text

        # Now include a rotation signature from the OLD key over a payload
        # that names the old pubkey in `rotates_from`. Identity continuity
        # is the contributor's choice — proven by their own old key.
        rotation_payload = cross_instance_identity_service.claim_payload(
            contributor_id="dora",
            public_key_hex=new_pub,
            issued_at=_iso_now(),
            rotates_from=first["public_key_hex"],
        )
        rotation_sig = sign_payload(rotation_payload, first["_private_key_hex"])
        with_rotation_body = {
            "contributor_id": "dora",
            "public_key_hex": new_pub,
            "claim_signature": new_sig,
            "claim_payload": new_payload,
            "rotation_signature": rotation_sig,
            "rotation_payload": rotation_payload,
        }
        r_ok = await c.post("/api/identity/claim", json=with_rotation_body)
        assert r_ok.status_code == 200, r_ok.text
        data = r_ok.json()
        assert data["public_key_hex"] == new_pub
        assert data["rotated"] is True

    # The pubkey now in store is the new one, and the old pubkey no
    # longer resolves to "dora".
    assert cross_instance_identity_service.get_pubkey("dora") == new_pub
    assert (
        cross_instance_identity_service.find_contributor_by_pubkey(
            first["public_key_hex"]
        )
        is None
    )


# ---------------------------------------------------------------------------
# 5. Peer recognition envelope → alias recorded when pubkey matches.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognize_cross_instance_identity_records_alias():
    claim = _signed_claim("eve")
    body = {k: v for k, v in claim.items() if not k.startswith("_")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/identity/claim", json=body)
        assert r.status_code == 200

        envelope = {
            "peer_instance_id": "peer-a",
            "peer_contributor_id": "eve-on-peer-a",
            "public_key_hex": claim["public_key_hex"],
        }
        r_rec = await c.post("/api/federation/identity/recognize", json=envelope)
        assert r_rec.status_code == 200, r_rec.text
        rec = r_rec.json()
        assert rec["recognized"] is True
        assert rec["local_contributor_id"] == "eve"
        assert rec["peer_instance_id"] == "peer-a"
        assert rec["peer_contributor_id"] == "eve-on-peer-a"

        # Re-sending the same envelope is idempotent.
        r_again = await c.post("/api/federation/identity/recognize", json=envelope)
        assert r_again.status_code == 200
        again = r_again.json()
        assert again["recognized"] is True
        assert again.get("idempotent") is True

    aliases = cross_instance_identity_service.list_aliases("eve")
    assert len(aliases) == 1
    assert aliases[0]["peer_instance_id"] == "peer-a"
    assert aliases[0]["peer_contributor_id"] == "eve-on-peer-a"


# ---------------------------------------------------------------------------
# 6. Peer envelope with no local pubkey match → no record (no speculation).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognize_without_matching_local_pubkey_skips():
    _, orphan_pubkey = generate_keypair()
    envelope = {
        "peer_instance_id": "peer-z",
        "peer_contributor_id": "stranger",
        "public_key_hex": orphan_pubkey,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/identity/recognize", json=envelope)
        assert r.status_code == 200
        data = r.json()
        assert data["recognized"] is False
        assert "no local contributor" in data["reason"]


# ---------------------------------------------------------------------------
# 7. Aliases endpoint returns known cross-instance links.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aliases_endpoint_returns_known_cross_instance_links():
    claim = _signed_claim("frank")
    body = {k: v for k, v in claim.items() if not k.startswith("_")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post("/api/identity/claim", json=body)
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-a",
                "peer_contributor_id": "frank-on-a",
                "public_key_hex": claim["public_key_hex"],
            },
        )
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-b",
                "peer_contributor_id": "frankie-on-b",
                "public_key_hex": claim["public_key_hex"],
            },
        )

        r = await c.get("/api/federation/identity/aliases/frank")
        assert r.status_code == 200, r.text
        body_out = r.json()
        assert body_out["contributor_id"] == "frank"
        peers = {(a["peer_instance_id"], a["peer_contributor_id"]) for a in body_out["aliases"]}
        assert peers == {("peer-a", "frank-on-a"), ("peer-b", "frankie-on-b")}


# ---------------------------------------------------------------------------
# 7b. Recognition-summary endpoint reports fleet-level counts only.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognition_summary_aggregates_without_exposing_identities():
    """Summary endpoint reports counts + per-peer breakdown without leaking
    contributor names. The federation page reads this; per-contributor
    detail lives behind /aliases/{id}.
    """
    # Two local contributors, each with a pubkey claim.
    claim_a = _signed_claim("hank")
    claim_b = _signed_claim("ingrid")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await c.post(
            "/api/identity/claim",
            json={k: v for k, v in claim_a.items() if not k.startswith("_")},
        )
        await c.post(
            "/api/identity/claim",
            json={k: v for k, v in claim_b.items() if not k.startswith("_")},
        )
        # Recognitions on two peers.
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-a",
                "peer_contributor_id": "hank-on-a",
                "public_key_hex": claim_a["public_key_hex"],
            },
        )
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-a",
                "peer_contributor_id": "ingrid-on-a",
                "public_key_hex": claim_b["public_key_hex"],
            },
        )
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-b",
                "peer_contributor_id": "hank-on-b",
                "public_key_hex": claim_a["public_key_hex"],
            },
        )
        # Re-send one — idempotency keeps the count honest.
        await c.post(
            "/api/federation/identity/recognize",
            json={
                "peer_instance_id": "peer-a",
                "peer_contributor_id": "hank-on-a",
                "public_key_hex": claim_a["public_key_hex"],
            },
        )

        r = await c.get("/api/federation/identity/recognition-summary")
        assert r.status_code == 200, r.text
        summary = r.json()
        assert summary["local_contributors_with_pubkey"] == 2
        assert summary["cross_instance_recognitions"] == 3
        by_peer = {p["peer_instance_id"]: p["count"] for p in summary["per_peer_counts"]}
        assert by_peer == {"peer-a": 2, "peer-b": 1}
        # No identities anywhere in the payload.
        payload_text = r.text
        assert "hank" not in payload_text
        assert "ingrid" not in payload_text


# ---------------------------------------------------------------------------
# 8. Two instances recognize the same person via shared pubkey.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_instances_recognize_same_person_via_shared_pubkey():
    """End-to-end: the same person holds one keypair, two instances each
    claim it locally, then exchange recognition envelopes. Both sides
    record an alias — neither defers; both recognize."""
    private_hex, public_hex = generate_keypair()

    # On instance "A" the person is known as "grace-a".
    payload_a = cross_instance_identity_service.claim_payload(
        contributor_id="grace-a",
        public_key_hex=public_hex,
        issued_at=_iso_now(),
    )
    sig_a = sign_payload(payload_a, private_hex)

    # On instance "B" the same person is known as "grace-b".
    payload_b = cross_instance_identity_service.claim_payload(
        contributor_id="grace-b",
        public_key_hex=public_hex,
        issued_at=_iso_now(),
    )
    sig_b = sign_payload(payload_b, private_hex)

    # Both claims pass — pubkey is the same, signatures verify against it.
    # (We use the local service directly here to simulate "two instances"
    # sharing the same in-process DB. The body of the test is the
    # symmetric recognition that follows.)
    cross_instance_identity_service.claim_pubkey(
        contributor_id="grace-a",
        public_key_hex=public_hex,
        claim_signature=sig_a,
        claim_payload_dict=payload_a,
    )
    # We can only have one local contributor per pubkey in a single DB,
    # so simulate the second instance by clearing local state and
    # re-claiming under the OTHER name to model side B.
    cross_instance_identity_service._reset_for_tests()
    cross_instance_identity_service.claim_pubkey(
        contributor_id="grace-b",
        public_key_hex=public_hex,
        claim_signature=sig_b,
        claim_payload_dict=payload_b,
    )

    # Now model side B receiving "grace-a on instance-A shares this pubkey":
    result_b = cross_instance_identity_service.recognize_peer_identity(
        peer_instance_id="instance-A",
        peer_contributor_id="grace-a",
        public_key_hex=public_hex,
    )
    assert result_b["recognized"] is True
    assert result_b["local_contributor_id"] == "grace-b"

    aliases_b = cross_instance_identity_service.list_aliases("grace-b")
    assert len(aliases_b) == 1
    assert aliases_b[0]["peer_instance_id"] == "instance-A"
    assert aliases_b[0]["peer_contributor_id"] == "grace-a"

    # Now switch to side A and have A recognize grace-b on instance-B.
    cross_instance_identity_service._reset_for_tests()
    cross_instance_identity_service.claim_pubkey(
        contributor_id="grace-a",
        public_key_hex=public_hex,
        claim_signature=sig_a,
        claim_payload_dict=payload_a,
    )
    result_a = cross_instance_identity_service.recognize_peer_identity(
        peer_instance_id="instance-B",
        peer_contributor_id="grace-b",
        public_key_hex=public_hex,
    )
    assert result_a["recognized"] is True
    assert result_a["local_contributor_id"] == "grace-a"

    aliases_a = cross_instance_identity_service.list_aliases("grace-a")
    assert len(aliases_a) == 1
    assert aliases_a[0]["peer_instance_id"] == "instance-B"
    assert aliases_a[0]["peer_contributor_id"] == "grace-b"
