"""Acceptance tests for federation_peer_poll_service — the heartbeat.

The federation now has a heartbeat. Each instance chooses its peers and
polls their public read-only surfaces (pulse, capabilities, canonicals).
These tests demonstrate the freedom-preserving shape:

  - A successful poll records pulse, capability manifest, and substrate
    alignment (one PeerPulseRecord, one PeerCapabilityRecord, one row per
    canonical in the federation-mirror table).
  - A peer that refuses (401/403/404) is honored — recorded as
    "not_sharing" with no retry.
  - A peer that times out is honored — recorded as "unreachable".
  - A failing peer never breaks the rest of the loop.
  - The poll never writes to the peer — every outbound is a GET.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.models.federation import FederatedInstance
from app.services import (
    federation_peer_poll_service,
    federation_service,
    instance_pulse_service,
)
from app.services import unified_db as _udb
from app.services.federation_peer_poll_service import (
    PeerCapabilityRecord,
    PeerPollResult,
    poll_all_peers,
    poll_peer,
)
from app.services.federation_service import (
    FederatedSubstrateAttestationRecord,
)
from app.services.instance_pulse_service import PeerPulseRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_peer_poll_tissue():
    """Each test starts from clean ground."""
    federation_peer_poll_service._reset_for_tests()
    yield
    federation_peer_poll_service._reset_for_tests()


def _register_peer(
    instance_id: str = "peer-a",
    endpoint_url: str = "https://peer-a.example.test",
) -> FederatedInstance:
    """Register a peer the poll loop can find."""
    return federation_service.register_instance(
        FederatedInstance(
            instance_id=instance_id,
            name=instance_id,
            endpoint_url=endpoint_url,
            public_key=None,
            registered_at=datetime.now(timezone.utc).isoformat(),
            last_sync_at=None,
            trust_level="pending",
        )
    )


# ---------------------------------------------------------------------------
# Mock transports — each test scripts exactly the HTTP responses it needs
# ---------------------------------------------------------------------------


def _ok_pulse_body() -> dict:
    return {
        "instance_id": "peer-a",
        "overall": "breathing",
        "organs": [{"name": "api", "status": "breathing", "score": 1.0}],
        "silences": 0,
        "uptime_seconds": 42,
        "as_of": "2026-05-24T00:00:00Z",
        "sample_duration_ms": 3,
    }


def _ok_capabilities_body() -> dict:
    return {
        "instance_id": "peer-a",
        "instance_url": "https://peer-a.example.test",
        "providers": ["claude", "openai"],
        "language_coverage": ["en"],
        "substrate_canonicals": ["R_Recovery"],
        "economics": {"cc_accepted": True},
        "extensions": {},
        "declared_at": "2026-05-24T00:00:00Z",
        "truth_source": "self",
    }


def _ok_canonicals_body() -> dict:
    return {
        "instance_id": "peer-a",
        "canonicals": [
            {
                "canonical_name": "R_Recovery",
                "role_slots": ["from", "to"],
                "modality_tags": ["narrative"],
                "content_hash": "a" * 64,
                "blueprint": None,
                "interned": True,
                "member_count": 3,
            },
            {
                "canonical_name": "R_PeerDiscoveredOnly",
                "role_slots": ["only_on_peer"],
                "modality_tags": [],
                "content_hash": "b" * 64,
                "blueprint": None,
                "interned": True,
                "member_count": 1,
            },
        ],
    }


def _route_handler(routes: dict[str, httpx.Response]):
    """Build an MockTransport handler that dispatches by URL suffix."""

    def handler(request: httpx.Request) -> httpx.Response:
        for suffix, response in routes.items():
            if request.url.path.endswith(suffix):
                # Sovereignty discipline: every outbound MUST be a GET.
                assert request.method == "GET", (
                    f"peer-poll attempted {request.method} on {request.url} — "
                    "the service is read-only by contract"
                )
                return response
        return httpx.Response(status_code=404, json={"detail": "no route"})

    return handler


def _mock_client(routes: dict[str, httpx.Response]) -> httpx.AsyncClient:
    transport = httpx.MockTransport(_route_handler(routes))
    return httpx.AsyncClient(transport=transport, timeout=5.0)


# ---------------------------------------------------------------------------
# 1. Pulse is recorded on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_records_pulse():
    """A successful pulse GET upserts a PeerPulseRecord."""
    _register_peer("peer-a")
    routes = {
        "/api/pulse/now": httpx.Response(200, json=_ok_pulse_body()),
        "/api/federation/capabilities/self": httpx.Response(200, json=_ok_capabilities_body()),
        "/api/federation/substrate/canonicals": httpx.Response(200, json=_ok_canonicals_body()),
    }
    async with _mock_client(routes) as client:
        result = await poll_peer("peer-a", client=client)

    assert result.pulse_status == "ok"
    pulses = instance_pulse_service.list_peer_pulses()
    assert len(pulses) == 1
    assert pulses[0]["peer_instance_id"] == "peer-a"
    assert pulses[0]["pulse"]["overall"] == "breathing"


# ---------------------------------------------------------------------------
# 2. Capability manifest is recorded on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_records_capabilities():
    """A successful capabilities GET upserts a PeerCapabilityRecord."""
    _register_peer("peer-a")
    routes = {
        "/api/pulse/now": httpx.Response(200, json=_ok_pulse_body()),
        "/api/federation/capabilities/self": httpx.Response(200, json=_ok_capabilities_body()),
        "/api/federation/substrate/canonicals": httpx.Response(200, json=_ok_canonicals_body()),
    }
    async with _mock_client(routes) as client:
        result = await poll_peer("peer-a", client=client)

    assert result.capabilities_status == "ok"
    with _udb.session() as session:
        row = session.get(PeerCapabilityRecord, "peer-a")
        assert row is not None
        manifest = json.loads(row.manifest_json)
        assert manifest["providers"] == ["claude", "openai"]
        assert manifest["substrate_canonicals"] == ["R_Recovery"]


# ---------------------------------------------------------------------------
# 3. Substrate alignment attestations are written
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_records_substrate_alignment():
    """A successful canonicals GET drives federation_substrate_service.exchange_with_peer."""
    _register_peer("peer-a")
    routes = {
        "/api/pulse/now": httpx.Response(200, json=_ok_pulse_body()),
        "/api/federation/capabilities/self": httpx.Response(200, json=_ok_capabilities_body()),
        "/api/federation/substrate/canonicals": httpx.Response(200, json=_ok_canonicals_body()),
    }
    async with _mock_client(routes) as client:
        result = await poll_peer("peer-a", client=client)

    assert result.substrate_status == "ok"
    # Two canonicals shared: R_Recovery (we carry it, but hash differs from
    # our deterministic hash → diverged) and R_PeerDiscoveredOnly (peer-only
    # → discovered). Both record attestations; neither imports into our
    # lattice.
    assert result.aligned + result.diverged + result.discovered == 2

    with _udb.session() as session:
        rows = (
            session.query(FederatedSubstrateAttestationRecord)
            .filter_by(peer_instance_id="peer-a")
            .all()
        )
    canonical_names = {row.canonical_name for row in rows}
    assert "R_Recovery" in canonical_names
    assert "R_PeerDiscoveredOnly" in canonical_names


# ---------------------------------------------------------------------------
# 4. Timeout is honored — no exception escapes, no record written
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_handles_timeout_gracefully():
    """A timeout on any endpoint marks 'unreachable' and continues."""
    _register_peer("peer-a")

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        result = await poll_peer("peer-a", client=client)

    assert result.pulse_status == "unreachable"
    assert result.capabilities_status == "unreachable"
    assert result.substrate_status == "unreachable"
    # No silent crash — the result is structured and tells us why.
    assert any("timeout" in n.lower() for n in result.notes)
    # No tissue written for an unreachable peer.
    assert instance_pulse_service.list_peer_pulses() == []
    with _udb.session() as session:
        assert session.get(PeerCapabilityRecord, "peer-a") is None


# ---------------------------------------------------------------------------
# 5. 403 is honored as sovereign refusal — no retry, no record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_handles_403_gracefully():
    """A peer that refuses is recorded as 'not_sharing'; nothing is forced."""
    _register_peer("peer-a")
    routes = {
        "/api/pulse/now": httpx.Response(403, json={"detail": "not shared"}),
        "/api/federation/capabilities/self": httpx.Response(404, json={"detail": "not shared"}),
        "/api/federation/substrate/canonicals": httpx.Response(401, json={"detail": "not shared"}),
    }
    async with _mock_client(routes) as client:
        result = await poll_peer("peer-a", client=client)

    assert result.pulse_status == "not_sharing"
    assert result.capabilities_status == "not_sharing"
    assert result.substrate_status == "not_sharing"
    # Nothing recorded — the peer named a boundary; we honor it.
    assert instance_pulse_service.list_peer_pulses() == []
    with _udb.session() as session:
        assert session.get(PeerCapabilityRecord, "peer-a") is None
        rows = (
            session.query(FederatedSubstrateAttestationRecord)
            .filter_by(peer_instance_id="peer-a")
            .all()
        )
        assert rows == []


# ---------------------------------------------------------------------------
# 6. Per-peer isolation — one failing peer doesn't break the others
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_all_peers_continues_after_individual_failure(monkeypatch):
    """Three peers, one fails internally — the other two still get polled."""
    _register_peer("peer-ok-1", endpoint_url="https://peer-ok-1.example.test")
    _register_peer("peer-bad", endpoint_url="https://peer-bad.example.test")
    _register_peer("peer-ok-2", endpoint_url="https://peer-ok-2.example.test")

    real_poll_peer = federation_peer_poll_service.poll_peer

    async def poll_peer_with_boom(instance_id, **kwargs):
        if instance_id == "peer-bad":
            raise RuntimeError("simulated mid-poll crash")
        # The good peers get a fully-mocked client.
        routes = {
            "/api/pulse/now": httpx.Response(200, json=_ok_pulse_body()),
            "/api/federation/capabilities/self": httpx.Response(
                200, json=_ok_capabilities_body()
            ),
            "/api/federation/substrate/canonicals": httpx.Response(
                200, json=_ok_canonicals_body()
            ),
        }
        async with _mock_client(routes) as client:
            return await real_poll_peer(instance_id, client=client)

    monkeypatch.setattr(
        federation_peer_poll_service, "poll_peer", poll_peer_with_boom
    )

    results = await poll_all_peers()

    assert set(results.keys()) == {"peer-ok-1", "peer-bad", "peer-ok-2"}
    assert results["peer-ok-1"].pulse_status == "ok"
    assert results["peer-ok-2"].pulse_status == "ok"
    # The crashing peer gets a structured fallback, not an exception.
    assert any("RuntimeError" in n for n in results["peer-bad"].notes)


# ---------------------------------------------------------------------------
# 7. Sovereignty discipline — the poll never POSTs / PUTs / DELETEs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_does_not_write_to_peer():
    """Every outbound request the service makes is a GET.

    The MockTransport asserts request.method == 'GET' on every call; if
    the service ever tries to POST/PUT/DELETE, the assert fires and the
    test fails. The contract is enforced at the wire.
    """
    _register_peer("peer-a")
    seen_methods: list[str] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen_methods.append(request.method)
        assert request.method == "GET", (
            f"peer-poll attempted {request.method} on {request.url} — "
            "the service is read-only by contract"
        )
        if request.url.path.endswith("/api/pulse/now"):
            return httpx.Response(200, json=_ok_pulse_body())
        if request.url.path.endswith("/api/federation/capabilities/self"):
            return httpx.Response(200, json=_ok_capabilities_body())
        if request.url.path.endswith("/api/federation/substrate/canonicals"):
            return httpx.Response(200, json=_ok_canonicals_body())
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(recording_handler)
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        await poll_peer("peer-a", client=client)

    assert seen_methods == ["GET", "GET", "GET"]
    assert all(m == "GET" for m in seen_methods)


# ---------------------------------------------------------------------------
# 8. Unregistered peer yields a clean PeerPollResult, never raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_peer_unregistered_returns_structured_result():
    """Polling a peer we never registered is a noop with a clear note."""
    result = await poll_peer("not-registered-anywhere")
    assert isinstance(result, PeerPollResult)
    assert result.pulse_status == "skipped"
    assert any("not registered" in n for n in result.notes)
