"""Tests for creator-economy endpoints — spec R1, R2, R3, R4.

Covers stats aggregation (R1), proof card shape (R2), featured list
ordering/filtering/pagination (R3), AssetType enum extension (R4).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.asset import AssetType
from app.routers import creator_economy as ce_router
from app.routers.render_events import _EVENTS as _RENDER_EVENTS
from app.routers.render_events import _reset_events_for_tests
from app.models.renderer import RenderEvent
from app.services.creator_economy_service import AssetRow


@pytest.fixture
def client():
    ce_router._reset_for_tests()
    _reset_events_for_tests()
    return TestClient(app)


def _seed_event(asset_id: str, asset_share: Decimal = Decimal("0.80")) -> None:
    pool = Decimal("0.1")
    e = RenderEvent(
        asset_id=asset_id,
        renderer_id="r1",
        reader_id="u1",
        timestamp=datetime.now(timezone.utc),
        duration_ms=10000,
        cc_pool=pool,
        cc_asset_creator=pool * asset_share,
        cc_renderer_creator=pool * Decimal("0.15"),
        cc_host_node=pool * Decimal("0.05"),
    )
    _RENDER_EVENTS[e.id] = e


# ---------- R4 AssetType enum extension ----------


def test_asset_type_enum_includes_new_creator_types():
    assert AssetType.BLUEPRINT.value == "BLUEPRINT"
    assert AssetType.DESIGN.value == "DESIGN"
    assert AssetType.RESEARCH.value == "RESEARCH"


def test_asset_type_legacy_values_preserved():
    assert AssetType.CODE.value == "CODE"
    assert AssetType.MODEL.value == "MODEL"
    assert AssetType.CONTENT.value == "CONTENT"
    assert AssetType.DATA.value == "DATA"


# ---------- R1 stats ----------


def test_stats_empty_returns_zeros(client):
    response = client.get("/api/creator-economy/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_creators"] == 0
    assert body["total_blueprints"] == 0
    assert Decimal(body["total_cc_distributed"]) == Decimal("0")
    assert body["total_uses"] == 0


def test_stats_aggregates_creator_economy_types(client):
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp1",
            name="Cob Wall Blueprint",
            asset_type="BLUEPRINT",
            creator_id="contributor:alice",
            creator_handle="alice",
            community_tags=["permaculture"],
        )
    )
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:de1",
            name="Village Layout",
            asset_type="DESIGN",
            creator_id="contributor:bob",
            creator_handle="bob",
        )
    )
    # A legacy CODE asset should not count toward blueprint totals
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:code1",
            name="Not creator-economy",
            asset_type="CODE",
            creator_id="contributor:alice",
        )
    )
    _seed_event("asset:bp1")
    _seed_event("asset:bp1")
    _seed_event("asset:de1")

    response = client.get("/api/creator-economy/stats")
    body = response.json()
    assert body["total_creators"] == 2  # alice + bob; CODE asset doesn't count
    assert body["total_blueprints"] == 2
    assert body["total_uses"] == 3
    # each event = 0.1 * 0.8 = 0.08, three events on creator-economy assets = 0.24
    assert Decimal(body["total_cc_distributed"]) == Decimal("0.240000")


def test_stats_caches_for_5_minutes(client):
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp1",
            name="v1",
            asset_type="BLUEPRINT",
            creator_id="c1",
        )
    )
    first = client.get("/api/creator-economy/stats").json()
    # Add another asset — should NOT appear until cache expires
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp2",
            name="v2",
            asset_type="BLUEPRINT",
            creator_id="c2",
        )
    )
    second = client.get("/api/creator-economy/stats").json()
    assert first["total_blueprints"] == second["total_blueprints"] == 1


# ---------- R2 proof card ----------


def test_proof_card_returns_canonical_shape(client):
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp1",
            name="Cob Wall Blueprint",
            asset_type="BLUEPRINT",
            creator_id="contributor:alice",
            creator_handle="alice",
            community_tags=["permaculture", "natural-building"],
        )
    )
    _seed_event("asset:bp1")
    _seed_event("asset:bp1")
    response = client.get("/api/assets/asset:bp1/proof-card")
    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == "asset:bp1"
    assert body["name"] == "Cob Wall Blueprint"
    assert body["creator_handle"] == "alice"
    assert body["asset_type"] == "BLUEPRINT"
    assert body["use_count"] == 2
    assert Decimal(body["cc_earned"]) == Decimal("0.160000")
    assert body["arweave_url"] is None
    assert body["verification_url"] == "/api/verification/chain/asset:bp1"
    assert body["community_tags"] == ["permaculture", "natural-building"]


def test_proof_card_404_for_unknown_asset(client):
    response = client.get("/api/assets/asset:nope/proof-card")
    assert response.status_code == 404


# ---------- R3 featured ----------


def test_featured_ordered_by_use_count_desc(client):
    for i in range(3):
        ce_router.register_creator_asset(
            AssetRow(
                id=f"asset:bp{i}",
                name=f"bp{i}",
                asset_type="BLUEPRINT",
                creator_id=f"c{i}",
            )
        )
    # bp0 gets 1 use, bp1 gets 3, bp2 gets 2
    _seed_event("asset:bp0")
    _seed_event("asset:bp1")
    _seed_event("asset:bp1")
    _seed_event("asset:bp1")
    _seed_event("asset:bp2")
    _seed_event("asset:bp2")

    response = client.get("/api/creator-economy/featured")
    body = response.json()
    ids = [i["asset_id"] for i in body["items"]]
    assert ids == ["asset:bp1", "asset:bp2", "asset:bp0"]


def test_featured_filters_by_asset_type(client):
    ce_router.register_creator_asset(
        AssetRow(id="asset:bp", name="bp", asset_type="BLUEPRINT", creator_id="a")
    )
    ce_router.register_creator_asset(
        AssetRow(id="asset:de", name="de", asset_type="DESIGN", creator_id="b")
    )
    response = client.get(
        "/api/creator-economy/featured", params={"asset_type": "DESIGN"}
    )
    body = response.json()
    assert [i["asset_id"] for i in body["items"]] == ["asset:de"]


def test_featured_filters_by_community_tag(client):
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp1",
            name="bp1",
            asset_type="BLUEPRINT",
            creator_id="a",
            community_tags=["permaculture"],
        )
    )
    ce_router.register_creator_asset(
        AssetRow(
            id="asset:bp2",
            name="bp2",
            asset_type="BLUEPRINT",
            creator_id="b",
            community_tags=["3d-printing"],
        )
    )
    response = client.get(
        "/api/creator-economy/featured",
        params={"community_tag": "permaculture"},
    )
    body = response.json()
    assert [i["asset_id"] for i in body["items"]] == ["asset:bp1"]


def test_featured_pagination(client):
    for i in range(5):
        ce_router.register_creator_asset(
            AssetRow(
                id=f"asset:bp{i}",
                name=f"bp{i}",
                asset_type="BLUEPRINT",
                creator_id=f"c{i}",
            )
        )
    body = client.get(
        "/api/creator-economy/featured", params={"limit": 2, "offset": 0}
    ).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    page2 = client.get(
        "/api/creator-economy/featured", params={"limit": 2, "offset": 2}
    ).json()
    assert len(page2["items"]) == 2


def test_featured_excludes_non_creator_economy_types(client):
    ce_router.register_creator_asset(
        AssetRow(id="asset:code", name="code", asset_type="CODE", creator_id="a")
    )
    ce_router.register_creator_asset(
        AssetRow(id="asset:bp", name="bp", asset_type="BLUEPRINT", creator_id="b")
    )
    body = client.get("/api/creator-economy/featured").json()
    assert [i["asset_id"] for i in body["items"]] == ["asset:bp"]
