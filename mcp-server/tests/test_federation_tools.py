"""Tests for the federation sovereign-instance MCP tools.

Mirrors what test_cross_modal_tools.py did for the cross-modal substrate
query surface (PR #1960). The federation tissue shipped in PRs #1974
(instance pulse), #1975 (substrate exchange), #1976 (capability
declarations), #1977 (value flow). These six MCP tools expose the
read-only query windows so any agent (Claude Desktop, Codex, Cursor,
A2A) can ask:

  - what is this instance breathing now? (self_pulse)
  - what have we observed from watched peers? (peer_pulses)
  - what does this instance claim it carries? (self_capabilities)
  - what do we attest about peer X? (substrate_alignment)
  - what is the structural inventory we hold? (substrate_canonicals)
  - who are the registered peers? (known_peers)

Write-paths (mirror-asset, read-attribution, settlement-share,
sign-capability) are deliberately not exposed via MCP — those are state
changes that warrant explicit HTTP-level intent.

The tests assert two layers:

1. Registration + dispatch contract — the tool joins TOOL_MAP and
   `dispatch` routes to the documented REST path. Same monkeypatch
   pattern as test_cross_modal_tools.py.
2. Service-backed integration — the same federation/pulse services that
   power the REST routes answer these queries when called via the
   router functions directly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPO_ROOT = ROOT.parent
API_DIR = REPO_ROOT / "api"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for extra in (API_DIR, SCRIPTS_DIR):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from coherence_mcp_server import server as mcp_server  # noqa: E402


SIX_FEDERATION_TOOLS = {
    "coherence_federation_self_pulse",
    "coherence_federation_peer_pulses",
    "coherence_federation_self_capabilities",
    "coherence_federation_substrate_alignment",
    "coherence_federation_substrate_canonicals",
    "coherence_federation_known_peers",
}


# ---------------------------------------------------------------------------
# Registration + dispatch contract
# ---------------------------------------------------------------------------


def test_all_six_federation_tools_are_registered() -> None:
    """All six federation tools join the MCP surface."""
    assert SIX_FEDERATION_TOOLS <= set(mcp_server.TOOL_MAP)


def test_self_pulse_routes_to_pulse_self(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"overall": "breathing", "organs": [], "instance_id": "local"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch("coherence_federation_self_pulse", {})
    assert result["overall"] == "breathing"
    assert calls == [("/api/pulse/self", None)]


def test_peer_pulses_routes_to_pulse_peers(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"instance_id": "local", "peers": [], "count": 0}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch("coherence_federation_peer_pulses", {})
    assert result == {"instance_id": "local", "peers": [], "count": 0}
    assert calls == [("/api/pulse/peers", None)]


def test_self_capabilities_routes_to_capabilities_self(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"truth_source": "self", "instance_id": "local"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch("coherence_federation_self_capabilities", {})
    assert result["truth_source"] == "self"
    assert calls == [("/api/federation/capabilities/self", None)]


def test_substrate_alignment_routes_to_attestations(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"peer_instance_id": "node-b", "attestations": [], "count": 0}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_federation_substrate_alignment", {"peer_id": "node-b"}
    )
    assert result["peer_instance_id"] == "node-b"
    assert calls == [
        ("/api/federation/substrate/attestations/node-b", None)
    ]


def test_substrate_alignment_quotes_peer_id_with_special_chars(monkeypatch) -> None:
    """Peer IDs with slashes / spaces must be URL-quoted on the way in."""
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"path": path}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    mcp_server.dispatch(
        "coherence_federation_substrate_alignment",
        {"peer_id": "ns/with slash"},
    )
    # urllib.parse.quote with safe='' encodes both '/' and ' '
    assert calls == [
        ("/api/federation/substrate/attestations/ns%2Fwith%20slash", None)
    ]


def test_substrate_alignment_rejects_empty_peer_id() -> None:
    result = mcp_server.dispatch(
        "coherence_federation_substrate_alignment", {}
    )
    assert "error" in result
    assert "peer_id" in result["error"]


def test_substrate_canonicals_routes_to_canonicals(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"instance_id": None, "canonicals": [], "count": 0}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_federation_substrate_canonicals", {}
    )
    assert "canonicals" in result
    assert calls == [("/api/federation/substrate/canonicals", None)]


def test_known_peers_routes_to_instances(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return []

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch("coherence_federation_known_peers", {})
    assert result == []
    assert calls == [("/api/federation/instances", None)]


# ---------------------------------------------------------------------------
# Service-backed integration: the routes the tools wrap answer from the
# same federation/pulse services that power production.
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_federation_db(tmp_path, monkeypatch):
    """Point unified_db at a fresh SQLite file so router calls don't hit prod.

    Mirrors the api/tests/conftest.py isolation pattern: write the test
    DB url into config_loader, reset the unified-db engine, ensure schema.
    """
    from app import config_loader
    import app.services.config_service as cs_module
    from app.services import unified_db
    from app.services import unified_models  # noqa: F401 — register tables

    db_file = tmp_path / "federation_test.db"
    cs_module.reset_config_cache()
    config_loader._CONFIG.setdefault("database", {})["url"] = (
        f"sqlite+pysqlite:///{db_file}"
    )
    cs_module._CACHE = dict(cs_module.get_config())

    unified_db.reset_engine()
    unified_db.ensure_schema()

    yield db_file

    unified_db.reset_engine()
    cs_module.reset_config_cache()


@pytest.mark.asyncio
async def test_self_pulse_returns_breath_state(isolated_federation_db, monkeypatch) -> None:
    """The router that backs coherence_federation_self_pulse answers with
    overall + organs, the shape the MCP tool surfaces."""
    monkeypatch.delenv("FEDERATION_PULSE_DISABLED", raising=False)
    from app.routers.pulse import get_self_pulse

    result = await get_self_pulse()
    assert "overall" in result
    assert "organs" in result
    # Organs is iterable; each one has a name/status pair.
    organs = result["organs"]
    assert isinstance(organs, list)
    if organs:
        for o in organs:
            assert "name" in o
            assert "status" in o


@pytest.mark.asyncio
async def test_peer_pulses_returns_observed_list(isolated_federation_db) -> None:
    """Seed a PeerPulseRecord and confirm /pulse/peers reads it.

    This is the same query path the MCP tool calls — service-backed, no
    HTTP layer. Validates that the tool's response shape carries
    instance_id + peers + count."""
    from datetime import datetime, timezone
    from app.services import instance_pulse_service  # registers PeerPulseRecord
    from app.services import unified_db
    from app.routers.pulse import get_peer_pulses

    # Re-run ensure_schema now that instance_pulse_service has imported,
    # binding its PeerPulseRecord table to the unified Base metadata.
    unified_db.reset_engine()
    unified_db.ensure_schema()
    with unified_db.session() as s:
        s.add(
            instance_pulse_service.PeerPulseRecord(
                peer_instance_id="peer-alpha",
                last_pulse_json='{"overall": "breathing"}',
                observed_at=datetime.now(timezone.utc),
            )
        )
        s.commit()

    result = await get_peer_pulses()
    assert "instance_id" in result
    assert "peers" in result
    assert "count" in result
    assert result["count"] == len(result["peers"])
    peer_ids = {p.get("peer_instance_id") for p in result["peers"]}
    assert "peer-alpha" in peer_ids


@pytest.mark.asyncio
async def test_self_capabilities_returns_manifest_with_truth_source(
    isolated_federation_db,
) -> None:
    """Self-capability manifest carries truth_source == 'self' — the
    invariant that makes the federation sovereign."""
    from app.routers.federation import get_self_capabilities

    manifest = await get_self_capabilities()
    # CapabilityManifest is a pydantic model; the truth_source field is
    # the load-bearing claim.
    assert manifest.truth_source == "self"
    assert manifest.instance_id  # non-empty


@pytest.mark.asyncio
async def test_substrate_alignment_returns_per_peer_attestations(
    isolated_federation_db,
) -> None:
    """Seed a FederatedSubstrateAttestationRecord; confirm the router
    returns it under attestations[] keyed by peer."""
    from app.services import federation_service
    from app.services import unified_db
    from app.routers.federation import list_substrate_attestations

    federation_service._ensure_schema()
    with unified_db.session() as s:
        s.add(
            federation_service.FederatedSubstrateAttestationRecord(
                peer_instance_id="peer-beta",
                canonical_name="R_Recovery",
                peer_content_hash="a" * 64,
                local_content_hash="a" * 64,
                alignment_status="aligned",
                observed_at="2026-05-24T00:00:00Z",
            )
        )
        s.commit()

    result = await list_substrate_attestations("peer-beta")
    assert result["peer_instance_id"] == "peer-beta"
    assert result["count"] >= 1
    canonicals = {a["canonical_name"] for a in result["attestations"]}
    assert "R_Recovery" in canonicals


@pytest.mark.asyncio
async def test_substrate_canonicals_returns_content_hashed_inventory(
    isolated_federation_db,
) -> None:
    """Every canonical entry carries a content_hash — the structural
    handle peers compare against, regardless of interning state."""
    from app.routers.federation import list_substrate_canonicals

    response = await list_substrate_canonicals()
    assert response.count == len(response.canonicals)
    assert response.count > 0
    for c in response.canonicals:
        assert c.content_hash  # non-empty
        assert len(c.content_hash) == 64  # SHA-256 hex
        assert c.canonical_name


@pytest.mark.asyncio
async def test_known_peers_returns_registered_instances(
    isolated_federation_db,
) -> None:
    """Register two peers; the list endpoint returns both."""
    from app.models.federation import FederatedInstance
    from app.routers.federation import list_instances, register_instance

    await register_instance(
        FederatedInstance(
            instance_id="peer-gamma",
            name="Gamma",
            endpoint_url="https://gamma.example",
        )
    )
    await register_instance(
        FederatedInstance(
            instance_id="peer-delta",
            name="Delta",
            endpoint_url="https://delta.example",
        )
    )

    peers = await list_instances()
    ids = {p.instance_id for p in peers}
    assert {"peer-gamma", "peer-delta"} <= ids
