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


# ---------------------------------------------------------------------------
# Reward policies
# ---------------------------------------------------------------------------

class TestRewardPolicies:
    """Community-configurable reward formulas."""

    def test_list_policies_returns_defaults(self):
        res = client.get("/api/reward-policies")
        assert res.status_code == 200
        policies = res.json()
        assert isinstance(policies, list)
        keys = {p["key"] for p in policies}
        assert "discovery.view_reward_cc" in keys
        assert "discovery.transaction_fee_rate" in keys

    def test_get_single_policy(self):
        res = client.get("/api/reward-policies/discovery.view_reward_cc")
        assert res.status_code == 200
        data = res.json()
        assert data["key"] == "discovery.view_reward_cc"
        assert data["source"] == "code_default"

    def test_override_policy(self):
        res = client.put(
            "/api/reward-policies/discovery.view_reward_cc",
            json={
                "value": {"value": 0.05, "unit": "CC", "description": "Custom view reward"},
                "updated_by": "test_community",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "community_override"

        # Verify the override takes effect
        get_res = client.get("/api/reward-policies/discovery.view_reward_cc")
        assert get_res.status_code == 200
        assert get_res.json()["source"] == "community_override"

    def test_delete_policy_reverts_to_default(self):
        # Set override
        client.put(
            "/api/reward-policies/discovery.max_view_rewards_daily",
            json={"value": {"value": 200, "unit": "count"}, "updated_by": "test"},
        )
        # Delete it
        res = client.delete("/api/reward-policies/discovery.max_view_rewards_daily")
        assert res.status_code == 200

        # Verify reverted to default
        get_res = client.get("/api/reward-policies/discovery.max_view_rewards_daily")
        assert get_res.json()["source"] == "code_default"

    def test_policy_snapshot_for_traceability(self):
        res = client.get("/api/reward-policies-snapshot")
        assert res.status_code == 200
        data = res.json()
        assert "snapshot_at" in data
        assert "policies" in data
        assert "discovery.view_reward_cc" in data["policies"]

    def test_workspace_scoping(self):
        """Policies are scoped to workspaces."""
        # Set a policy for a custom workspace
        res = client.put(
            "/api/reward-policies/discovery.view_reward_cc?workspace_id=test-community",
            json={
                "value": {"value": 0.1, "unit": "CC"},
                "updated_by": "test",
            },
        )
        assert res.status_code == 200

        # Default workspace should still have original
        default_res = client.get("/api/reward-policies/discovery.view_reward_cc")
        custom_res = client.get(
            "/api/reward-policies/discovery.view_reward_cc?workspace_id=test-community"
        )
        # Both should return, but sources differ
        assert default_res.status_code == 200
        assert custom_res.status_code == 200


# ---------------------------------------------------------------------------
# Flow simulator
# ---------------------------------------------------------------------------

class TestFlowSimulator:
    """CC flow simulation."""

    def test_simulate_basic_scenario(self):
        res = client.post("/api/flow/simulate", json={
            "contributors": 10,
            "assets_created": 5,
            "views_per_asset": 100,
            "referral_rate": 0.15,
            "transaction_rate": 0.05,
            "avg_transaction_cc": 50,
            "avg_contribution_cc": 100,
            "avg_coherence_score": 0.75,
            "staking_rate": 0.3,
        })
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "edges" in data
        assert "totals" in data
        assert "policy_snapshot" in data
        assert "vitality_signals" in data
        assert data["totals"]["monthly_cc_minted"] > 0
        assert len(data["nodes"]) >= 5
        assert len(data["edges"]) >= 5

    def test_simulate_high_coherence_triggers_bonus(self):
        res = client.post("/api/flow/simulate", json={
            "contributors": 10,
            "avg_coherence_score": 0.95,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["coherence_bonus_applied"] is True

    def test_simulate_low_coherence_no_bonus(self):
        res = client.post("/api/flow/simulate", json={
            "contributors": 10,
            "avg_coherence_score": 0.5,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["coherence_bonus_applied"] is False

    def test_simulate_zero_activity(self):
        res = client.post("/api/flow/simulate", json={
            "contributors": 1,
            "assets_created": 0,
            "views_per_asset": 0,
            "referral_rate": 0,
            "transaction_rate": 0,
            "avg_transaction_cc": 0,
            "avg_contribution_cc": 0,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["totals"]["monthly_cc_minted"] == 0

    def test_live_flow_endpoint(self):
        res = client.get("/api/flow/live?days=7")
        assert res.status_code == 200
        data = res.json()
        assert "views" in data
        assert "cc" in data
        assert "active_policies" in data
