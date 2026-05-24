"""Acceptance tests for self-sovereign capability manifests.

Each instance is the source-of-truth for its own capabilities. The
signature lets others verify "this came from this instance" without
making any instance authoritative over others. The fleet is the union
of self-declared capabilities, not a coerced aggregate.

Endpoints under test:
  - GET  /api/federation/capabilities/self
  - POST /api/federation/capabilities/sign
  - POST /api/federation/capabilities/{instance_id}/verify
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.federation import (
    CapabilityManifest,
    FederatedInstance,
    SignedCapabilityManifest,
)
from app.services import federation_service

BASE = "http://test"


@pytest.fixture
def instance_secret(monkeypatch):
    """Set a stable instance secret + id for the duration of a test."""
    secret = "test-secret-" + uuid4().hex
    monkeypatch.setenv("FEDERATION_INSTANCE_SECRET", secret)
    monkeypatch.setenv("FEDERATION_INSTANCE_ID", "self-test")
    monkeypatch.setenv("FEDERATION_INSTANCE_URL", "http://self.test")
    return secret


# ---------------------------------------------------------------------------
# 1. Self manifest carries the full declaration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_capabilities_returns_complete_manifest(instance_secret):
    """GET /capabilities/self returns providers, languages, substrate
    canonicals, and economics — each field present, each self-declared."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/federation/capabilities/self")
        assert r.status_code == 200, r.text
        body = r.json()

    # Required keys must all be present (empty list is honest absence,
    # missing key is a contract break).
    assert "providers" in body
    assert "language_coverage" in body
    assert "substrate_canonicals" in body
    assert "economics" in body
    assert "declared_at" in body
    assert "instance_id" in body
    assert "instance_url" in body

    # Providers come from model_routing.json tiers_by_executor — at minimum
    # the catalog should carry a few entries on a working instance.
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1, "expected at least one provider"

    # Languages come from SUPPORTED_LOCALES — at minimum en is always there.
    assert "en" in body["language_coverage"]

    # Substrate canonicals come from canonical_shape_names() — at least
    # one shape interned in the production lattice.
    assert isinstance(body["substrate_canonicals"], list)
    assert len(body["substrate_canonicals"]) >= 1

    # Economics gates the CC question — keys present whether or not CC is on.
    assert "cc_accepted" in body["economics"]
    assert "staking_enabled" in body["economics"]


# ---------------------------------------------------------------------------
# 2. truth_source is always "self"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_capabilities_truth_source_is_self(instance_secret):
    """The truth_source field is always 'self' — no third-party assertion."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/federation/capabilities/self")
        assert r.status_code == 200
        assert r.json()["truth_source"] == "self"


# ---------------------------------------------------------------------------
# 3. Signature round-trips with the same secret
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signed_capabilities_signature_verifies(instance_secret):
    """Sign with secret, verify with same secret — passes."""
    manifest = federation_service.get_self_capability_manifest()
    signed = federation_service.sign_capability_manifest(manifest, secret=instance_secret)
    assert signed.signature
    assert len(signed.signature) == 64  # HMAC-SHA256 hex digest length
    assert federation_service.verify_capability_signature(signed, instance_secret) is True


# ---------------------------------------------------------------------------
# 4. Tampered/wrong secret fails verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signed_capabilities_signature_fails_with_wrong_secret(instance_secret):
    """Verification fails when the secret differs OR the manifest was tampered."""
    manifest = federation_service.get_self_capability_manifest()
    signed = federation_service.sign_capability_manifest(manifest, secret=instance_secret)

    # Wrong secret — verification fails.
    assert federation_service.verify_capability_signature(signed, "wrong-secret") is False

    # Empty secret — verification fails (refuses to verify against nothing).
    assert federation_service.verify_capability_signature(signed, "") is False

    # Tampered manifest with correct secret — fails (signature was over
    # the original manifest, not the mutated one).
    tampered = SignedCapabilityManifest(
        manifest=manifest.model_copy(update={"providers": [*manifest.providers, "evil-injected-provider"]}),
        signature=signed.signature,
        signed_at=signed.signed_at,
    )
    assert federation_service.verify_capability_signature(tampered, instance_secret) is False


# ---------------------------------------------------------------------------
# 5. Verify-endpoint aligns overlapping capabilities between two instances
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_peer_aligns_overlapping_capabilities(instance_secret):
    """Two instances with overlapping capabilities — alignment surfaces shared set."""
    peer_id = "peer-" + uuid4().hex[:8]
    peer_secret = "peer-secret-" + uuid4().hex

    # Register the peer with us (we hold their secret).
    federation_service.register_instance(
        FederatedInstance(
            instance_id=peer_id,
            name=peer_id,
            endpoint_url="http://peer.example",
            public_key=peer_secret,
        )
    )

    # Build a peer manifest with deliberate overlap and a unique extra.
    self_manifest = federation_service.get_self_capability_manifest()
    peer_manifest = CapabilityManifest(
        instance_id=peer_id,
        instance_url="http://peer.example",
        providers=[*self_manifest.providers[:1], "peer-only-provider"],
        language_coverage=["en", "fr"],  # en overlaps, fr is peer-unique
        substrate_canonicals=self_manifest.substrate_canonicals[:1] + ["R_PeerOnlyShape"],
        economics={"cc_accepted": False},
    )
    signed_peer = federation_service.sign_capability_manifest(peer_manifest, secret=peer_secret)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            f"/api/federation/capabilities/{peer_id}/verify",
            json=signed_peer.model_dump(mode="json"),
        )
        assert r.status_code == 200, r.text
        body = r.json()

    assert body["verified"] is True, body.get("verification_note")
    assert body["peer_instance_id"] == peer_id

    # Overlap surfaces in shared lists.
    if self_manifest.providers:
        assert self_manifest.providers[0] in body["shared_providers"]
    assert "en" in body["shared_languages"]


# ---------------------------------------------------------------------------
# 6. Peer-unique capabilities surface as unique_to_peer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_peer_marks_unique_capabilities(instance_secret):
    """A peer carrying capabilities we lack surfaces in unique_to_peer."""
    peer_id = "peer-" + uuid4().hex[:8]
    peer_secret = "peer-secret-" + uuid4().hex
    federation_service.register_instance(
        FederatedInstance(
            instance_id=peer_id,
            name=peer_id,
            endpoint_url="http://peer.example",
            public_key=peer_secret,
        )
    )

    peer_manifest = CapabilityManifest(
        instance_id=peer_id,
        instance_url="http://peer.example",
        providers=["uniquely-peer-provider"],
        language_coverage=["zh", "ja"],  # neither in self
        substrate_canonicals=["R_PeerOnlyCanonical"],
        economics={},
    )
    signed_peer = federation_service.sign_capability_manifest(peer_manifest, secret=peer_secret)

    alignment = federation_service.align_with_peer(signed_peer)

    assert alignment.verified is True
    assert "uniquely-peer-provider" in alignment.unique_to_peer["providers"]
    assert "zh" in alignment.unique_to_peer["languages"]
    assert "ja" in alignment.unique_to_peer["languages"]
    assert "R_PeerOnlyCanonical" in alignment.unique_to_peer["substrate_canonicals"]

    # The peer-only providers do NOT appear in our shared set.
    assert "uniquely-peer-provider" not in alignment.shared_providers


# ---------------------------------------------------------------------------
# 7. Unsigned peer (or peer not registered with a secret) yields alignment
#    without erroring — sovereignty includes the choice not to sign.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsigned_peer_returns_unverified_alignment_not_error(instance_secret):
    """A peer with no registered secret yields verified=False, not 404/422."""
    peer_id = "unregistered-peer-" + uuid4().hex[:8]

    # Build a peer manifest. We never register the peer — we don't hold
    # their secret. Their signature could be anything; verification will
    # fail, but alignment is still returned.
    peer_manifest = CapabilityManifest(
        instance_id=peer_id,
        instance_url="http://unknown.example",
        providers=["claude"],
        language_coverage=["en", "de"],
        substrate_canonicals=[],
        economics={},
    )
    signed_peer = SignedCapabilityManifest(
        manifest=peer_manifest,
        signature="0" * 64,  # placeholder — no secret to verify against
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            f"/api/federation/capabilities/{peer_id}/verify",
            json=signed_peer.model_dump(mode="json"),
        )
        # Sovereignty: still 200, alignment surfaces, verified=False with a note.
        assert r.status_code == 200, r.text
        body = r.json()

    assert body["verified"] is False
    assert "not registered" in body["verification_note"].lower() or "unsigned" in body["verification_note"].lower()
    # Alignment still computes — we can still see what the peer carries.
    assert "shared_languages" in body
    assert "unique_to_peer" in body


# ---------------------------------------------------------------------------
# 8. Sign endpoint refuses to ship a forgeable signature
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sign_endpoint_returns_503_without_secret(monkeypatch):
    """Without a configured secret, /sign returns 503 rather than producing
    an unverifiable signature."""
    monkeypatch.delenv("FEDERATION_INSTANCE_SECRET", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/capabilities/sign")
        assert r.status_code == 503
        # Self-declaration without signature still works — sovereignty
        # includes the choice not to sign.
        r2 = await c.get("/api/federation/capabilities/self")
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# 9. Sign endpoint returns a verifiable signed manifest when secret is set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sign_endpoint_produces_verifiable_signature(instance_secret):
    """When the secret is configured, /sign produces a manifest whose
    signature verifies against that same secret."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/federation/capabilities/sign")
        assert r.status_code == 200, r.text
        body = r.json()

    signed = SignedCapabilityManifest(**body)
    assert federation_service.verify_capability_signature(signed, instance_secret) is True
