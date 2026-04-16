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

class TestWalletConnect:
    """Wallet connect, list, disconnect flow."""

    def test_connect_wallet(self):
        cid = _contributor_id()
        addr = _wallet_address()
        res = client.post("/api/wallets/connect", json={
            "contributor_id": cid,
            "address": addr,
            "chain": "ethereum",
            "label": "Test Wallet",
        })
        assert res.status_code == 201
        data = res.json()
        assert data["contributor_id"] == cid
        assert data["address"] == addr.lower()
        assert data["chain"] == "ethereum"
        assert data["verified"] is False

    def test_connect_same_wallet_same_contributor_idempotent(self):
        cid = _contributor_id()
        addr = _wallet_address()
        res1 = client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr,
        })
        assert res1.status_code == 201
        res2 = client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr,
        })
        # Idempotent — returns existing wallet
        assert res2.status_code == 201
        assert res1.json()["id"] == res2.json()["id"]

    def test_connect_same_wallet_different_contributor_409(self):
        addr = _wallet_address()
        cid1 = _contributor_id()
        cid2 = _contributor_id()
        client.post("/api/wallets/connect", json={
            "contributor_id": cid1, "address": addr,
        })
        res = client.post("/api/wallets/connect", json={
            "contributor_id": cid2, "address": addr,
        })
        assert res.status_code == 409

    def test_list_wallets(self):
        cid = _contributor_id()
        addr1 = _wallet_address()
        addr2 = _wallet_address()
        client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr1, "chain": "ethereum",
        })
        client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr2, "chain": "base",
        })
        res = client.get(f"/api/wallets/{cid}")
        assert res.status_code == 200
        wallets = res.json()
        assert len(wallets) == 2
        chains = {w["chain"] for w in wallets}
        assert chains == {"ethereum", "base"}

    def test_disconnect_wallet(self):
        cid = _contributor_id()
        addr = _wallet_address()
        create_res = client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr,
        })
        wallet_id = create_res.json()["id"]
        res = client.delete(f"/api/wallets/{wallet_id}")
        assert res.status_code == 200
        assert res.json()["deleted"] is True

        # Wallet no longer listed
        list_res = client.get(f"/api/wallets/{cid}")
        assert list_res.status_code == 200
        assert len(list_res.json()) == 0

    def test_disconnect_nonexistent_404(self):
        res = client.delete("/api/wallets/nonexistent-id")
        assert res.status_code == 404

    def test_lookup_by_address(self):
        cid = _contributor_id()
        addr = _wallet_address()
        client.post("/api/wallets/connect", json={
            "contributor_id": cid, "address": addr,
        })
        res = client.get(f"/api/wallets/lookup/{addr}")
        assert res.status_code == 200
        assert res.json()["contributor_id"] == cid

    def test_lookup_nonexistent_404(self):
        res = client.get("/api/wallets/lookup/0xnonexistent")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# View tracking
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
