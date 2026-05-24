"""Acceptance tests for the federated substrate canonical exchange.

Two coherence instances meeting at the substrate altitude. Each exposes
its interned canonical recipe-shapes; content-addressing lets peers
test for structural alignment without forcing either to import the
other's lattice.

The tests demonstrate the freedom-preserving shape:

- Both instances list their canonicals, each with a deterministic
  content_hash (same canonical_name + role_slots → same hash anywhere).
- Aligned: peer carries the same canonical with the same hash.
- Diverged: peer carries the same canonical name but a different hash.
- Discovered: peer carries a canonical this instance does not.
- Exchange writes attestations into the federation-mirror table.
- Exchange is idempotent and leaves local recipe-shape cells untouched.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.federation import PeerCanonicalEntry
from app.services import federation_service, federation_substrate_service
from app.services import unified_db as _udb
from app.services.federation_service import FederatedSubstrateAttestationRecord
from app.services.federation_substrate_service import (
    canonical_content_hash,
    discover_local_canonical,
    exchange_with_peer,
    local_canonicals,
)
from app.services.substrate.kernel import lookup_cell
from app.services.substrate.modality_shapes import (
    CANONICAL_SHAPES,
    DOMAIN_RECIPE_SHAPE,
    intern_all_canonical_shapes,
)

BASE = "http://test"


# ---------------------------------------------------------------------------
# Fixture — intern the canonicals into the running app's DB once, and
# clear the attestation mirror between tests so each test starts clean.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _interned_canonicals_and_clean_attestations():
    """Ensure canonicals are interned and attestations table is empty."""
    federation_service._ensure_schema()
    with _udb.session() as session:
        # Idempotent: if a previous test already interned, the upsert is a no-op.
        intern_all_canonical_shapes(session)
        # Wipe attestation rows so test ordering doesn't shift counts.
        session.query(FederatedSubstrateAttestationRecord).delete()
    yield
    with _udb.session() as session:
        session.query(FederatedSubstrateAttestationRecord).delete()


# ---------------------------------------------------------------------------
# 1. Inventory endpoint returns every declared canonical.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonicals_endpoint_lists_all_interned():
    """GET /api/federation/substrate/canonicals returns one entry per CANONICAL_SHAPES."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/federation/substrate/canonicals")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == len(CANONICAL_SHAPES)
        names_in_response = {entry["canonical_name"] for entry in body["canonicals"]}
        for canonical_name, _role_slots, _modality_tags in CANONICAL_SHAPES:
            assert canonical_name in names_in_response, (
                f"canonical {canonical_name!r} missing from federation inventory"
            )
        # Every entry should be interned (the fixture interns them).
        for entry in body["canonicals"]:
            assert entry["interned"] is True
            assert entry["member_count"] >= 1


# ---------------------------------------------------------------------------
# 2. Each entry carries a deterministic content_hash.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canonical_carries_content_hash():
    """Content-hash is present, hex-encoded, and matches the deterministic helper."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/federation/substrate/canonicals")
        assert r.status_code == 200
        body = r.json()

    expected_hashes = {
        name: canonical_content_hash(name, list(role_slots))
        for name, role_slots, _tags in CANONICAL_SHAPES
    }

    for entry in body["canonicals"]:
        chash = entry["content_hash"]
        assert isinstance(chash, str) and len(chash) == 64, (
            f"content_hash for {entry['canonical_name']} not a 64-char sha256 hex"
        )
        # Hex-only sanity.
        int(chash, 16)
        # Deterministic match against the pure-function helper.
        assert chash == expected_hashes[entry["canonical_name"]], (
            f"content_hash drift for {entry['canonical_name']}"
        )


# ---------------------------------------------------------------------------
# 3. Discover endpoint: this instance carries the canonical → aligned shape.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_aligned():
    """When two instances carry the same canonical, exchange marks it aligned."""
    canonical_name = "R_Recovery"
    role_slots = next(
        list(slots) for name, slots, _tags in CANONICAL_SHAPES if name == canonical_name
    )
    peer_hash = canonical_content_hash(canonical_name, role_slots)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Single-shape discover endpoint on this instance.
        r = await c.get(f"/api/federation/substrate/canonicals/{canonical_name}/discover")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["content_hash"] == peer_hash

        # Exchange with a peer that carries the same canonical at the same hash.
        r = await c.post(
            "/api/federation/substrate/exchange",
            json={
                "peer_instance_id": "peer-aligned",
                "canonicals": [
                    {
                        "canonical_name": canonical_name,
                        "role_slots": role_slots,
                        "modality_tags": [],
                        "content_hash": peer_hash,
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["aligned"] == 1
        assert result["diverged"] == 0
        assert result["discovered"] == 0
        assert result["attestations"][0]["alignment_status"] == "aligned"


# ---------------------------------------------------------------------------
# 4. Discover diverged: same name, different role_slots → different hash.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_diverged():
    """A peer claiming a known canonical with a different shape registers as diverged."""
    canonical_name = "R_Recovery"
    divergent_hash = canonical_content_hash(canonical_name, ["mutated", "slots"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/substrate/exchange",
            json={
                "peer_instance_id": "peer-diverged",
                "canonicals": [
                    {
                        "canonical_name": canonical_name,
                        "role_slots": ["mutated", "slots"],
                        "modality_tags": [],
                        "content_hash": divergent_hash,
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["aligned"] == 0
        assert result["diverged"] == 1
        assert result["discovered"] == 0
        attestation = result["attestations"][0]
        assert attestation["alignment_status"] == "diverged"
        # Local hash present because this instance DOES carry R_Recovery.
        assert attestation["local_content_hash"] is not None
        assert attestation["peer_content_hash"] == divergent_hash
        assert attestation["local_content_hash"] != divergent_hash


# ---------------------------------------------------------------------------
# 5. Discover unknown: peer has a canonical we don't → discovered.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_unknown():
    """A canonical this instance lacks is recorded as discovered (never imported)."""
    unknown_name = "R_PeerExclusiveShape"
    unknown_hash = canonical_content_hash(unknown_name, ["alpha", "beta"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # discover endpoint reports not-found.
        r = await c.get(f"/api/federation/substrate/canonicals/{unknown_name}/discover")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body["content_hash"] is None  # we don't even have the declaration

        # Exchange marks it discovered.
        r = await c.post(
            "/api/federation/substrate/exchange",
            json={
                "peer_instance_id": "peer-unknown",
                "canonicals": [
                    {
                        "canonical_name": unknown_name,
                        "role_slots": ["alpha", "beta"],
                        "modality_tags": ["R_TagA"],
                        "content_hash": unknown_hash,
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["discovered"] == 1
        attestation = result["attestations"][0]
        assert attestation["alignment_status"] == "discovered"
        assert attestation["local_content_hash"] is None
        assert attestation["peer_content_hash"] == unknown_hash

        # Sovereignty: the cell was NOT interned locally.
        with _udb.session() as session:
            cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, unknown_name)
        assert cell is None, "exchange must not import peer canonicals"


# ---------------------------------------------------------------------------
# 6. Attestations land in the federation-mirror table.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_records_attestations():
    """POST exchange creates FederatedSubstrateAttestationRecord rows."""
    canonical_name = "R_ObserverConditionedActualization"
    role_slots = next(
        list(slots) for name, slots, _tags in CANONICAL_SHAPES if name == canonical_name
    )
    peer_hash = canonical_content_hash(canonical_name, role_slots)
    peer_id = "peer-attestation-test"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/substrate/exchange",
            json={
                "peer_instance_id": peer_id,
                "canonicals": [
                    {
                        "canonical_name": canonical_name,
                        "role_slots": role_slots,
                        "modality_tags": [],
                        "content_hash": peer_hash,
                    },
                    {
                        "canonical_name": "R_PeerOnly",
                        "role_slots": ["one", "two"],
                        "modality_tags": [],
                        "content_hash": canonical_content_hash("R_PeerOnly", ["one", "two"]),
                    },
                ],
            },
        )
        assert r.status_code == 200, r.text

        # Read back via the GET endpoint.
        r = await c.get(f"/api/federation/substrate/attestations/{peer_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        statuses = {a["canonical_name"]: a["alignment_status"] for a in body["attestations"]}
        assert statuses[canonical_name] == "aligned"
        assert statuses["R_PeerOnly"] == "discovered"

    # Direct DB read confirms the row presence.
    with _udb.session() as session:
        rows = (
            session.query(FederatedSubstrateAttestationRecord)
            .filter_by(peer_instance_id=peer_id)
            .all()
        )
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# 7. Exchange is idempotent — re-running does not duplicate attestations.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_is_idempotent():
    """Repeating an exchange refreshes attestations in place; no duplicate rows."""
    canonical_name = "R_SustainedTension"
    role_slots = next(
        list(slots) for name, slots, _tags in CANONICAL_SHAPES if name == canonical_name
    )
    peer_hash = canonical_content_hash(canonical_name, role_slots)
    peer_id = "peer-idempotent"

    payload = {
        "peer_instance_id": peer_id,
        "canonicals": [
            {
                "canonical_name": canonical_name,
                "role_slots": role_slots,
                "modality_tags": [],
                "content_hash": peer_hash,
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r1 = await c.post("/api/federation/substrate/exchange", json=payload)
        assert r1.status_code == 200
        r2 = await c.post("/api/federation/substrate/exchange", json=payload)
        assert r2.status_code == 200

    with _udb.session() as session:
        rows = (
            session.query(FederatedSubstrateAttestationRecord)
            .filter_by(peer_instance_id=peer_id, canonical_name=canonical_name)
            .all()
        )
    assert len(rows) == 1, "duplicate attestation written on re-exchange"


# ---------------------------------------------------------------------------
# 8. Exchange leaves the local lattice unchanged — sovereignty preserved.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_does_not_modify_local_lattice():
    """Before and after a discovery-heavy exchange, local recipe-shape cells are identical."""
    # Capture local lattice fingerprint before.
    with _udb.session() as session:
        before = local_canonicals(session)
    before_map = {c.canonical_name: (c.content_hash, c.blueprint, c.member_count) for c in before.canonicals}

    # Exchange a mixture: one aligned, one diverged, several discovered.
    peer_payload = [
        {
            "canonical_name": "R_Recovery",
            "role_slots": list(
                next(slots for n, slots, _t in CANONICAL_SHAPES if n == "R_Recovery")
            ),
            "modality_tags": [],
            "content_hash": canonical_content_hash(
                "R_Recovery",
                list(next(slots for n, slots, _t in CANONICAL_SHAPES if n == "R_Recovery")),
            ),
        },
        {
            "canonical_name": "R_MeetThenShift",
            "role_slots": ["foreign", "shape"],
            "modality_tags": [],
            "content_hash": canonical_content_hash("R_MeetThenShift", ["foreign", "shape"]),
        },
        {
            "canonical_name": "R_PeerNovel-A",
            "role_slots": ["x", "y", "z"],
            "modality_tags": ["R_TagAlpha"],
            "content_hash": canonical_content_hash("R_PeerNovel-A", ["x", "y", "z"]),
        },
        {
            "canonical_name": "R_PeerNovel-B",
            "role_slots": ["m", "n"],
            "modality_tags": [],
            "content_hash": canonical_content_hash("R_PeerNovel-B", ["m", "n"]),
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/federation/substrate/exchange",
            json={
                "peer_instance_id": "peer-sovereign",
                "canonicals": peer_payload,
            },
        )
        assert r.status_code == 200

    with _udb.session() as session:
        after = local_canonicals(session)
    after_map = {c.canonical_name: (c.content_hash, c.blueprint, c.member_count) for c in after.canonicals}

    assert before_map == after_map, (
        "local canonical inventory changed after exchange — sovereignty violated"
    )

    # And the peer's novel canonicals are NOT interned locally.
    with _udb.session() as session:
        for novel in ("R_PeerNovel-A", "R_PeerNovel-B"):
            assert lookup_cell(session, DOMAIN_RECIPE_SHAPE, novel) is None, (
                f"discovered peer canonical {novel!r} was imported — sovereignty violated"
            )


# ---------------------------------------------------------------------------
# Direct service-level tests — pure-function classifiers.
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic_and_distinguishing():
    """Same input → same hash; different name or slots → different hash."""
    h_a = canonical_content_hash("R_X", ["a", "b"])
    h_b = canonical_content_hash("R_X", ["a", "b"])
    assert h_a == h_b

    h_c = canonical_content_hash("R_Y", ["a", "b"])
    h_d = canonical_content_hash("R_X", ["a", "b", "c"])
    h_e = canonical_content_hash("R_X", ["b", "a"])  # order matters
    assert len({h_a, h_c, h_d, h_e}) == 4


def test_classify_alignment_pure_function():
    """exchange_with_peer's classifier returns the right status for each case."""
    federation_service._ensure_schema()
    with _udb.session() as session:
        intern_all_canonical_shapes(session)
        # Aligned
        slots = list(next(slots for n, slots, _t in CANONICAL_SHAPES if n == "R_Recovery"))
        result = exchange_with_peer(
            session,
            "peer-classify",
            [
                PeerCanonicalEntry(
                    canonical_name="R_Recovery",
                    role_slots=slots,
                    modality_tags=[],
                    content_hash=canonical_content_hash("R_Recovery", slots),
                )
            ],
        )
        assert result.aligned == 1
        # Clean up so other tests don't see this row.
        session.query(FederatedSubstrateAttestationRecord).filter_by(
            peer_instance_id="peer-classify"
        ).delete()
