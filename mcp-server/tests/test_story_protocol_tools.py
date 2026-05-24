"""Tests for the story-protocol MCP tools.

Mirrors test_federation_tools.py (PR #1979) and test_cross_modal_tools.py
(PR #1960). The story-protocol tissue shipped across PRs #1931, #1934,
#1940, #1942, #1943, #1953. These seven MCP tools surface the
read-only query windows so any agent (Claude Desktop, Codex, Cursor,
A2A) can ask:

  - asset detail (asset_get)
  - content integrity (asset_verification)
  - IP registration state (ip_status)
  - per-asset evidence with applicable multiplier (evidence_for_asset)
  - recent settlement batches (settlement_batches)
  - settlement for a specific date (settlement_for_date)
  - aggregate render-event analytics (asset_analytics)

Write paths (asset registration, evidence submission, settlement run)
are deliberately not exposed via MCP — those are state changes that
warrant explicit HTTP intent.

The tests assert two layers:

1. Registration + dispatch contract — each tool joins TOOL_MAP and
   dispatch routes to the documented REST path. Same monkeypatch
   pattern as test_federation_tools.py.
2. Service-backed integration — the same services that power the REST
   routes answer these queries when called via the router functions
   directly.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

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


SEVEN_STORY_PROTOCOL_TOOLS = {
    "coherence_asset_get",
    "coherence_asset_verification",
    "coherence_ip_status",
    "coherence_evidence_for_asset",
    "coherence_settlement_batches",
    "coherence_settlement_for_date",
    "coherence_asset_analytics",
}


# ---------------------------------------------------------------------------
# Registration + dispatch contract
# ---------------------------------------------------------------------------


def test_all_seven_story_protocol_tools_are_registered() -> None:
    """All seven story-protocol tools join the MCP surface."""
    assert SEVEN_STORY_PROTOCOL_TOOLS <= set(mcp_server.TOOL_MAP)


def test_asset_get_routes_to_assets_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"id": "abc-123", "description": "an asset"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_asset_get", {"asset_id": "abc-123"}
    )
    assert result["id"] == "abc-123"
    assert calls == [("/api/assets/abc-123", None)]


def test_asset_get_rejects_empty_asset_id() -> None:
    result = mcp_server.dispatch("coherence_asset_get", {})
    assert "error" in result
    assert "asset_id" in result["error"]


def test_asset_verification_routes_to_verification_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"asset_id": "abc-123", "integrity": "verified"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_asset_verification", {"asset_id": "abc-123"}
    )
    assert result["integrity"] == "verified"
    assert calls == [("/api/assets/abc-123/verification", None)]


def test_asset_verification_quotes_asset_id_with_special_chars(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"path": path}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    mcp_server.dispatch(
        "coherence_asset_verification", {"asset_id": "ns/with space"}
    )
    assert calls == [
        ("/api/assets/ns%2Fwith%20space/verification", None)
    ]


def test_asset_verification_rejects_empty_asset_id() -> None:
    result = mcp_server.dispatch("coherence_asset_verification", {})
    assert "error" in result


def test_ip_status_narrows_asset_payload(monkeypatch) -> None:
    """The IP-status tool reads /api/assets/{id} and narrows the payload
    to just the IP registration fields, giving callers a focused view."""
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {
            "id": "abc-123",
            "description": "irrelevant",
            "sp_ip_id": "sp:mock:abc-123",
            "ip_status": "registered",
            "ip_reason": None,
            "ipfs_cid": "Qm-noise",
        }

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_ip_status", {"asset_id": "abc-123"}
    )
    # Wraps /api/assets, narrows the response.
    assert calls == [("/api/assets/abc-123", None)]
    assert result == {
        "asset_id": "abc-123",
        "sp_ip_id": "sp:mock:abc-123",
        "ip_status": "registered",
        "ip_reason": None,
    }


def test_ip_status_propagates_upstream_error(monkeypatch) -> None:
    def fake_get(path: str, params: dict | None = None):
        return {"error": "404 Not Found"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_ip_status", {"asset_id": "missing"}
    )
    assert "error" in result


def test_ip_status_rejects_empty_asset_id() -> None:
    result = mcp_server.dispatch("coherence_ip_status", {})
    assert "error" in result


def test_evidence_for_asset_routes_to_evidence_asset(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"asset_id": "abc-123", "submissions": [], "verifications": []}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_evidence_for_asset", {"asset_id": "abc-123"}
    )
    assert result["asset_id"] == "abc-123"
    assert calls == [("/api/evidence/asset/abc-123", None)]


def test_evidence_for_asset_rejects_empty_asset_id() -> None:
    result = mcp_server.dispatch("coherence_evidence_for_asset", {})
    assert "error" in result


def test_settlement_batches_routes_to_settlement(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return []

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch("coherence_settlement_batches", {})
    assert result == []
    assert calls == [("/api/settlement", {"limit": 20})]


def test_settlement_batches_respects_limit(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return []

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    mcp_server.dispatch("coherence_settlement_batches", {"limit": 5})
    assert calls == [("/api/settlement", {"limit": 5})]


def test_settlement_for_date_routes_to_dated_path(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"batch_date": "2026-05-24"}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_settlement_for_date", {"batch_date": "2026-05-24"}
    )
    assert result["batch_date"] == "2026-05-24"
    assert calls == [("/api/settlement/2026-05-24", None)]


def test_settlement_for_date_rejects_empty_date() -> None:
    result = mcp_server.dispatch("coherence_settlement_for_date", {})
    assert "error" in result
    assert "batch_date" in result["error"]


def test_asset_analytics_routes_to_render_events_analytics(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"asset_id": "abc-123", "total_renders": 0}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)
    result = mcp_server.dispatch(
        "coherence_asset_analytics", {"asset_id": "abc-123"}
    )
    assert result["total_renders"] == 0
    assert calls == [("/api/render-events/analytics/abc-123", None)]


def test_asset_analytics_rejects_empty_asset_id() -> None:
    result = mcp_server.dispatch("coherence_asset_analytics", {})
    assert "error" in result


# ---------------------------------------------------------------------------
# Service-backed integration: each tool routes to a path that the existing
# story-protocol services answer. Confirms the wrapper composes with the
# real underlying flow (no parallel implementation).
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_story_protocol_db(tmp_path, monkeypatch):
    """Point unified_db at a fresh SQLite file and reset all
    story-protocol module-level state so each test starts on fresh
    ground. Mirrors the isolation pattern in test_federation_tools.py.
    """
    from app import config_loader
    import app.services.config_service as cs_module
    from app.services import unified_db
    from app.services import unified_models  # noqa: F401 — register tables

    db_file = tmp_path / "story_protocol_test.db"
    cs_module.reset_config_cache()
    config_loader._CONFIG.setdefault("database", {})["url"] = (
        f"sqlite+pysqlite:///{db_file}"
    )
    cs_module._CACHE = dict(cs_module.get_config())

    unified_db.reset_engine()
    unified_db.ensure_schema()

    # Reset module-level state for evidence, settlement, render-events,
    # and IP registration so each test starts clean.
    from app.routers import render_events as render_events_router
    from app.services import evidence_service, ip_registration_service
    from app.services import settlement_service

    render_events_router._reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()

    yield db_file

    render_events_router._reset_events_for_tests()
    evidence_service._reset_for_tests()
    settlement_service._reset_for_tests()
    ip_registration_service._reset_for_tests()
    unified_db.reset_engine()
    cs_module.reset_config_cache()


@pytest.mark.asyncio
async def test_asset_verification_returns_integrity_passed_for_intact_content(
    isolated_story_protocol_db,
) -> None:
    """Seed an asset with content, call the verification router directly,
    confirm integrity reads 'verified' for unmodified bytes."""
    import base64

    from app.models.asset import AssetCreate
    from app.routers.assets import create_asset, get_asset_verification
    from app.services import graph_service
    from app.services.story_protocol_bridge import compute_content_hash

    content = b"a sample asset payload"
    content_hash = compute_content_hash(content)

    created = await create_asset(
        AssetCreate(type="DATA", description="test asset")
    )
    # Attach content bytes + matching hash to the underlying node so
    # verification has bytes to recompute. The asset router reads
    # content_base64 from node["metadata"], and mime_type +
    # content_hash from top-level node fields (which `to_dict` merges
    # from properties).
    node_id = f"asset:{created.id}"
    graph_service.update_node(
        node_id,
        properties={
            "metadata": {
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
            "mime_type": "application/octet-stream",
            "content_hash": content_hash,
        },
    )

    result = await get_asset_verification(created.id)
    assert result["integrity"] == "verified"
    assert result["content_hash"] == content_hash
    assert result["recomputed_hash"] == content_hash


@pytest.mark.asyncio
async def test_evidence_for_asset_returns_submission_list(
    isolated_story_protocol_db,
) -> None:
    """Seed an evidence submission; confirm the per-asset list endpoint
    returns it under submissions[]."""
    from app.models.evidence import EvidenceCreate
    from app.routers.evidence import list_for_asset, submit_evidence

    asset_id = "asset:" + str(uuid4())
    await submit_evidence(
        EvidenceCreate(
            asset_id=asset_id,
            submitter_id="contrib-alpha",
            photo_urls=["https://example.com/photo.jpg"],
            attestation_count=2,
            description="proof of build",
        )
    )

    result = await list_for_asset(asset_id)
    assert result.asset_id == asset_id
    assert len(result.submissions) == 1
    assert result.submissions[0].submitter_id == "contrib-alpha"
    # No verification yet, so multiplier is the baseline.
    assert result.cc_multiplier_applicable in {"1", "1.0", "1.00"}


def test_settlement_for_date_returns_specific_batch(
    isolated_story_protocol_db,
) -> None:
    """Store a batch for a date; confirm the dated GET reads it back."""
    from app.models.settlement import SettlementBatch
    from app.services import settlement_service

    target_date = date(2026, 5, 24)
    batch = SettlementBatch(batch_date=target_date)
    settlement_service.store_batch(batch)

    # The router is a thin wrapper around settlement_service.get_batch.
    fetched = settlement_service.get_batch(target_date)
    assert fetched is not None
    assert fetched.batch_date == target_date


def test_settlement_batches_returns_recent_most_recent_first(
    isolated_story_protocol_db,
) -> None:
    """Store batches across three dates; list_batches returns them
    most-recent-first."""
    from app.models.settlement import SettlementBatch
    from app.services import settlement_service

    today = date(2026, 5, 24)
    for d in (today, today - timedelta(days=1), today - timedelta(days=2)):
        settlement_service.store_batch(SettlementBatch(batch_date=d))

    batches = settlement_service.list_batches()
    assert len(batches) >= 3
    dates = [b.batch_date for b in batches[:3]]
    assert dates == sorted(dates, reverse=True)


def test_ip_status_reflects_register_then_query_flow(
    isolated_story_protocol_db,
) -> None:
    """Register an IP asset directly through the service, then confirm
    the status the MCP tool reads back matches what was minted."""
    from app.services import ip_registration_service

    asset_id = "asset:" + str(uuid4())
    record = ip_registration_service.register_ip_asset(
        asset_id, metadata={"title": "test"}
    )
    assert record["ip_status"] == "registered"
    assert record["sp_ip_id"] is not None

    # The MCP tool reads /api/assets/{id} and narrows to the IP fields.
    # Here we exercise the service layer that backs that response.
    status = ip_registration_service.get_ip_status(asset_id)
    assert status["ip_status"] == "registered"
    assert status["sp_ip_id"] == record["sp_ip_id"]


@pytest.mark.asyncio
async def test_asset_analytics_returns_aggregates_for_seeded_events(
    isolated_story_protocol_db,
) -> None:
    """Seed two render events for one asset; the analytics router returns
    total_renders=2 and the matching unique-reader count."""
    from app.routers.render_events import (
        RenderEventCreate,
        get_asset_analytics,
        log_render_event,
    )

    asset_id = "asset:" + str(uuid4())
    await log_render_event(
        RenderEventCreate(
            asset_id=asset_id,
            renderer_id="renderer-text",
            reader_id="reader-a",
            duration_ms=5000,
        )
    )
    await log_render_event(
        RenderEventCreate(
            asset_id=asset_id,
            renderer_id="renderer-text",
            reader_id="reader-b",
            duration_ms=10000,
        )
    )

    result = await get_asset_analytics(asset_id)
    assert result.total_renders == 2
    assert result.unique_readers == 2
    assert result.total_cc_earned > Decimal("0")


@pytest.mark.asyncio
async def test_asset_analytics_returns_zero_for_asset_with_no_events(
    isolated_story_protocol_db,
) -> None:
    """An asset with no render events returns a zero-valued analytics
    record (not a 404). The MCP wrapper preserves that shape."""
    from app.routers.render_events import get_asset_analytics

    result = await get_asset_analytics("asset:no-events-" + str(uuid4()))
    assert result.total_renders == 0
    assert result.unique_readers == 0
    assert result.total_cc_earned == Decimal("0")
