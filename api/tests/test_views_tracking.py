"""Flow-centric tests for view tracking, wallet integration, and discovery rewards.

These tests verify the full flow:
  1. Connect wallet → verify ownership
  2. View an asset → view event recorded
  3. View with referrer → discovery chain tracked
  4. Stats reflect views correctly
  5. Trending calculates correctly
  6. Discovery rewards flow CC to referrers
"""
from __future__ import annotations

import uuid

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contributor_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def _wallet_address() -> str:
    return f"0x{uuid.uuid4().hex[:40]}"


def _asset_id() -> str:
    return f"test-asset-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Wallet integration
# ---------------------------------------------------------------------------

class TestViewTracking:
    """View events, stats, trending, discovery chain."""

    def test_view_stats_empty(self):
        asset_id = _asset_id()
        res = client.get(f"/api/views/stats/{asset_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["total_views"] == 0
        assert data["unique_contributors"] == 0
        assert data["anonymous_views"] == 0

    def test_concept_read_creates_view_event(self):
        """Reading a concept via GET creates a view event in the middleware."""
        # First create a concept node so the GET returns 200
        from app.services import graph_service
        concept_id = f"lc-test-{uuid.uuid4().hex[:6]}"
        graph_service.create_node(
            id=concept_id,
            type="concept",
            name=f"Test Concept {concept_id}",
            description="A test concept for view tracking",
        )

        # Read it with contributor headers
        cid = _contributor_id()
        res = client.get(
            f"/api/concepts/{concept_id}",
            headers={
                "X-Contributor-Id": cid,
                "X-Session-Fingerprint": "test-session-123",
                "X-Page-Route": f"/vision/{concept_id}",
            },
        )
        assert res.status_code == 200

        # View stats should show the read
        stats_res = client.get(f"/api/views/stats/{concept_id}")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_views"] >= 1

    def test_view_with_referrer_creates_discovery_chain(self):
        """Views with referrer headers build a discovery chain."""
        from app.services import read_tracking_service

        asset_id = _asset_id()
        referrer = _contributor_id()
        viewer = _contributor_id()

        # Record a view with referrer
        read_tracking_service.record_view(
            asset_id=asset_id,
            contributor_id=viewer,
            referrer_contributor_id=referrer,
        )

        # Discovery chain should show the referral
        res = client.get(f"/api/views/discovery/{asset_id}")
        assert res.status_code == 200
        chain = res.json()
        assert len(chain) >= 1
        assert chain[0]["referrer"] == referrer
        assert chain[0]["viewer"] == viewer

    def test_trending_returns_results(self):
        """Trending endpoint returns assets ranked by view velocity."""
        from app.services import read_tracking_service

        asset_id = _asset_id()
        for _ in range(5):
            read_tracking_service.record_view(asset_id=asset_id)

        res = client.get("/api/views/trending?days=7&limit=10")
        assert res.status_code == 200
        trending = res.json()
        assert isinstance(trending, list)
        # Our asset should appear
        asset_ids = [t["asset_id"] for t in trending]
        assert asset_id in asset_ids

    def test_contributor_view_history(self):
        """Contributor view history shows what they viewed."""
        from app.services import read_tracking_service

        cid = _contributor_id()
        asset1 = _asset_id()
        asset2 = _asset_id()

        read_tracking_service.record_view(asset_id=asset1, contributor_id=cid)
        read_tracking_service.record_view(asset_id=asset2, contributor_id=cid)

        res = client.get(f"/api/views/contributor/{cid}")
        assert res.status_code == 200
        history = res.json()
        assert len(history) == 2
        viewed_assets = {h["asset_id"] for h in history}
        assert asset1 in viewed_assets
        assert asset2 in viewed_assets

    def test_view_summary(self):
        """Summary endpoint returns aggregate stats."""
        res = client.get("/api/views/summary?days=7")
        assert res.status_code == 200
        data = res.json()
        assert "total_views" in data
        assert "unique_contributors" in data
        assert "assets_viewed" in data

    def test_ping_records_attributed_view(self):
        """POST /api/views/ping records a view tied to X-Contributor-Id."""
        cid = _contributor_id()
        concept_id = f"lc-test-{uuid.uuid4().hex[:6]}"
        res = client.post(
            "/api/views/ping",
            json={"asset_id": concept_id, "source_page": f"/vision/{concept_id}"},
            headers={
                "X-Contributor-Id": cid,
                "X-Session-Fingerprint": f"sess-{uuid.uuid4().hex[:8]}",
            },
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True

        # The ping attached the contributor — it should show in history
        history = client.get(f"/api/views/contributor/{cid}").json()
        assert any(h["asset_id"] == concept_id for h in history)

    def test_ping_anonymous_still_tracks(self):
        """A ping without X-Contributor-Id still records by session."""
        concept_id = f"lc-anon-{uuid.uuid4().hex[:6]}"
        res = client.post(
            "/api/views/ping",
            json={"asset_id": concept_id},
            headers={"X-Session-Fingerprint": f"sess-{uuid.uuid4().hex[:8]}"},
        )
        assert res.status_code == 200
        stats = client.get(f"/api/views/stats/{concept_id}").json()
        assert stats["total_views"] >= 1

    def test_trail_aggregates_per_concept(self):
        """Trail groups a contributor's reads by concept, ranked by count."""
        cid = _contributor_id()
        a = f"lc-a-{uuid.uuid4().hex[:6]}"
        b = f"lc-b-{uuid.uuid4().hex[:6]}"

        # a read 3 times, b read once — a should rank first
        for _ in range(3):
            client.post(
                "/api/views/ping",
                json={"asset_id": a},
                headers={"X-Contributor-Id": cid},
            )
        client.post(
            "/api/views/ping",
            json={"asset_id": b},
            headers={"X-Contributor-Id": cid},
        )

        trail = client.get(f"/api/views/trail/{cid}").json()
        assert trail["total_reads"] == 4
        assert trail["concept_count"] == 2
        ids = [c["concept_id"] for c in trail["concepts"]]
        assert ids[0] == a  # highest count ranks first
        assert b in ids


# ---------------------------------------------------------------------------
# Discovery rewards
# ---------------------------------------------------------------------------

class TestDiscoveryRewards:
    """Discovery reward flow — referrer earns from bringing attention."""

    def test_earnings_endpoint_empty(self):
        cid = _contributor_id()
        res = client.get(f"/api/views/earnings/{cid}")
        assert res.status_code == 200
        data = res.json()
        assert data["total_referrals"] == 0
        assert data["estimated_view_rewards_cc"] == 0

    def test_referral_accumulates_earnings(self):
        """Referrals show up in earnings query."""
        from app.services import read_tracking_service

        referrer = _contributor_id()
        asset_id = _asset_id()

        for _ in range(3):
            viewer = _contributor_id()
            read_tracking_service.record_view(
                asset_id=asset_id,
                contributor_id=viewer,
                referrer_contributor_id=referrer,
            )

        res = client.get(f"/api/views/earnings/{referrer}")
        assert res.status_code == 200
        data = res.json()
        assert data["total_referrals"] == 3
        assert data["unique_viewers_referred"] == 3
        assert data["unique_assets_shared"] == 1
        assert data["estimated_view_rewards_cc"] > 0


# ---------------------------------------------------------------------------
# Reward policies
# ---------------------------------------------------------------------------
