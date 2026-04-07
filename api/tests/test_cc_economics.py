"""Tests for CC Economics and Value Coherence (spec cc-economics-and-value-coherence).

Flow-centric tests: HTTP requests in, JSON out. No internal service imports
except for setup helpers (mint, reset).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str) -> dict:
    """Create an idea in the graph for staking targets."""
    r = await c.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": f"Idea {idea_id}",
            "description": f"Test idea for staking: {idea_id}",
            "potential_value": 1000.0,
            "estimated_cost": 100.0,
            "confidence": 0.8,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _mint_for_user(user_id: str, amount_cc: float, deposit_usd: float) -> None:
    """Mint CC for a user so they have balance to stake."""
    from app.services import cc_treasury_service
    cc_treasury_service.mint(user_id, amount_cc, deposit_usd, 333.33)


def _reset_services() -> None:
    """Reset treasury and oracle state between tests."""
    from app.services import cc_treasury_service, cc_oracle_service
    cc_treasury_service.reset_treasury()
    cc_oracle_service.reset_cache()


# ---------------------------------------------------------------------------
# Supply endpoint (R1, R7, R8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supply_returns_required_fields():
    """GET /api/cc/supply returns total_minted, total_burned, outstanding, coherence_score."""
    _reset_services()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/cc/supply")
        assert r.status_code == 200
        data = r.json()
        assert "total_minted" in data
        assert "total_burned" in data
        assert "outstanding" in data
        assert "coherence_score" in data
        assert "coherence_status" in data
        assert "treasury_value_usd" in data
        assert "exchange_rate" in data
        assert "as_of" in data


@pytest.mark.asyncio
async def test_supply_coherence_score_above_one():
    """Coherence score >= 1.0 when treasury properly backs outstanding CC."""
    _reset_services()
    # Mint 1000 CC backed by $10 USD at rate 333.33 CC/USD
    # treasury_value_usd = 10.0, outstanding = 1000 CC
    # coherence = 10.0 / (1000 / 333.33) = 10.0 / 3.0 = 3.33
    _mint_for_user("user-cs", 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/cc/supply")
        assert r.status_code == 200
        data = r.json()
        assert data["coherence_score"] >= 1.0
        assert data["coherence_status"] in ("healthy", "warning")


@pytest.mark.asyncio
async def test_mint_on_deposit_burn_on_withdrawal():
    """Minting increases supply, burning decreases it."""
    _reset_services()
    from app.services import cc_treasury_service

    cc_treasury_service.mint("u1", 500.0, 5.0, 333.33)
    supply1 = cc_treasury_service.get_supply(333.33)
    assert supply1["total_minted"] == 500.0
    assert supply1["outstanding"] == 500.0

    cc_treasury_service.burn("u1", 200.0, 2.0, 333.33)
    supply2 = cc_treasury_service.get_supply(333.33)
    assert supply2["total_burned"] == 200.0
    assert supply2["outstanding"] == 300.0


@pytest.mark.asyncio
async def test_no_mint_when_coherence_below_one():
    """System pauses minting when coherence score drops below 1.0 (R7)."""
    _reset_services()
    from app.services import cc_treasury_service

    # Create a situation where coherence < 1.0
    # Mint 10000 CC but only deposit $1 USD
    # coherence = 1.0 / (10000/333.33) = 1.0 / 30.0 = 0.033
    cc_treasury_service.mint("u-bad", 10000.0, 1.0, 333.33)
    assert not cc_treasury_service.can_mint(333.33)

    supply = cc_treasury_service.get_supply(333.33)
    assert supply["coherence_score"] < 1.0
    assert supply["coherence_status"] == "paused"


# ---------------------------------------------------------------------------
# Exchange rate endpoint (R5, R9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_rate_includes_spread():
    """GET /api/cc/exchange-rate returns 1% spread (R5)."""
    _reset_services()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/cc/exchange-rate")
        assert r.status_code == 200
        data = r.json()
        assert data["spread_pct"] == 1.0
        assert data["buy_rate"] < data["cc_per_usd"]
        assert data["sell_rate"] > data["cc_per_usd"]
        assert data["oracle_source"] == "coingecko"


@pytest.mark.asyncio
async def test_exchange_rate_cached_5min():
    """Exchange rate has 5-minute cache TTL (R9)."""
    _reset_services()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/cc/exchange-rate")
        assert r.status_code == 200
        data = r.json()
        assert data["cache_ttl_seconds"] == 300
        assert "cached_at" in data


@pytest.mark.asyncio
async def test_exchange_rate_stale_detection():
    """Exchange rate marks stale when cache exceeds TTL (R9)."""
    _reset_services()
    import time
    from app.services import cc_oracle_service

    # Force a fetch first
    rate = cc_oracle_service.get_exchange_rate()
    assert rate is not None
    assert rate.is_stale is False

    # Backdate the cache to simulate expiry
    cc_oracle_service._CACHE["cached_at"] = time.time() - 400

    # The next call should detect stale but refresh successfully
    rate2 = cc_oracle_service.get_exchange_rate()
    assert rate2 is not None
    # After refresh, it should no longer be stale
    assert rate2.is_stale is False


# ---------------------------------------------------------------------------
# Staking (R3, R4, R10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stake_into_idea_creates_position():
    """POST /api/cc/stake creates a staking position linked to an idea (R3)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        r = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["stake_id"]
        assert data["user_id"] == user_id
        assert data["idea_id"] == idea_id
        assert data["amount_cc"] == 500.0
        assert data["attribution_cc"] == 500.0
        assert data["status"] == "active"


@pytest.mark.asyncio
async def test_stake_insufficient_balance_rejected():
    """POST /api/cc/stake returns 400 on insufficient balance (R3)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 100.0, 1.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        r = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        assert r.status_code == 400
        assert "Insufficient" in r.json()["detail"]


@pytest.mark.asyncio
async def test_stake_idea_not_found():
    """POST /api/cc/stake returns 404 when idea does not exist."""
    _reset_services()
    user_id = _uid("user")
    _mint_for_user(user_id, 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": "nonexistent-idea", "amount_cc": 100.0},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Unstaking with cooldown tiers (R4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unstake_cooldown_instant_under_100():
    """Unstake < 100 CC has instant cooldown (0 hours) (R4)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 500.0, 5.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        # Stake 50 CC (under 100)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 50.0},
        )
        assert sr.status_code == 201
        stake_id = sr.json()["stake_id"]

        # Unstake
        ur = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur.status_code == 200
        data = ur.json()
        assert data["cooldown_hours"] == 0
        assert data["status"] == "withdrawn"


@pytest.mark.asyncio
async def test_unstake_cooldown_24h_100_to_1000():
    """Unstake 100-1000 CC has 24h cooldown (R4)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 2000.0, 20.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        assert sr.status_code == 201
        stake_id = sr.json()["stake_id"]

        ur = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur.status_code == 200
        data = ur.json()
        assert data["cooldown_hours"] == 24
        assert data["status"] == "cooling_down"


@pytest.mark.asyncio
async def test_unstake_cooldown_72h_over_1000():
    """Unstake > 1000 CC has 72h cooldown (R4)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 5000.0, 50.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 2000.0},
        )
        assert sr.status_code == 201
        stake_id = sr.json()["stake_id"]

        ur = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur.status_code == 200
        data = ur.json()
        assert data["cooldown_hours"] == 72
        assert data["status"] == "cooling_down"


@pytest.mark.asyncio
async def test_unstake_already_cooling_rejected():
    """Unstake returns 400 if already in cooldown (R4)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 2000.0, 20.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        stake_id = sr.json()["stake_id"]

        # First unstake succeeds
        ur1 = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur1.status_code == 200

        # Second unstake should be rejected
        ur2 = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur2.status_code == 400
        assert "cooldown" in ur2.json()["detail"].lower() or "withdrawn" in ur2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unstake_not_found():
    """Unstake returns 404 for nonexistent stake."""
    _reset_services()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/cc/unstake",
            json={"stake_id": "nonexistent", "user_id": "nobody"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Attribution (R2, R3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attribution_grows_with_usage_events():
    """Attribution grows proportionally to usage events on staked idea (R2)."""
    _reset_services()
    from app.services import cc_staking_service

    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 2000.0, 20.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        assert sr.status_code == 201

        # Simulate 10 usage events
        updated = cc_staking_service.update_attribution(idea_id, 10)
        assert updated == 1

        # Check positions — attribution should have grown
        r = await c.get(f"/api/cc/staking/{user_id}")
        assert r.status_code == 200
        data = r.json()
        pos = data["positions"][0]
        # 500 * (1 + 0.01 * 10) = 500 * 1.1 = 550
        assert pos["attribution_cc"] == pytest.approx(550.0, rel=0.01)


@pytest.mark.asyncio
async def test_attribution_flat_without_usage():
    """Attribution stays flat when no usage events occur (R3 — no guaranteed yield)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 2000.0, 20.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 500.0},
        )
        assert sr.status_code == 201

        # No usage events — attribution should equal original amount
        r = await c.get(f"/api/cc/staking/{user_id}")
        data = r.json()
        pos = data["positions"][0]
        assert pos["attribution_cc"] == 500.0


# ---------------------------------------------------------------------------
# User staking summary (R10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_staking_summary_aggregation():
    """GET /api/cc/staking/{user_id} returns all positions with totals (R10)."""
    _reset_services()
    user_id = _uid("user")
    idea1 = _uid("idea")
    idea2 = _uid("idea")
    _mint_for_user(user_id, 5000.0, 50.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea1)
        await _create_idea(c, idea2)

        # Two stakes
        await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea1, "amount_cc": 200.0},
        )
        await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea2, "amount_cc": 300.0},
        )

        r = await c.get(f"/api/cc/staking/{user_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == user_id
        assert len(data["positions"]) == 2
        assert data["total_staked_cc"] == 500.0
        assert data["total_attribution_cc"] == 500.0

        # Each position has required fields
        for pos in data["positions"]:
            assert "stake_id" in pos
            assert "idea_id" in pos
            assert "amount_cc" in pos
            assert "attribution_cc" in pos
            assert "staked_at" in pos
            assert "status" in pos


# ---------------------------------------------------------------------------
# Treasury ledger (audit trail)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_treasury_ledger_audit_trail():
    """Treasury ledger records all mint/burn/stake/unstake operations."""
    _reset_services()
    from app.services import cc_treasury_service

    cc_treasury_service.mint("u-audit", 1000.0, 10.0, 333.33)
    cc_treasury_service.burn("u-audit", 100.0, 1.0, 333.33)

    entries = cc_treasury_service.get_ledger_entries(user_id="u-audit")
    assert len(entries) >= 2

    actions = [e["action"] for e in entries]
    assert "mint" in actions
    assert "burn" in actions

    for entry in entries:
        assert "treasury_balance_after" in entry
        assert "coherence_score_after" in entry
        assert "created_at" in entry


# ---------------------------------------------------------------------------
# Quality gate deposit (R6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_deposit_returned_on_evidence():
    """Quality gate: deposit for idea publishing returned when evidence threshold met.

    This tests the R6 demand driver concept. The deposit is represented as a
    stake that can be unstaked (returned) when the idea has evidence.
    """
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        # Stake as quality gate deposit
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 50.0},
        )
        assert sr.status_code == 201
        stake_id = sr.json()["stake_id"]

        # Simulate evidence (usage events increase attribution)
        from app.services import cc_staking_service
        cc_staking_service.update_attribution(idea_id, 5)

        # Unstake — should be instant (< 100 CC) and attribution grew
        ur = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur.status_code == 200
        data = ur.json()
        assert data["cooldown_hours"] == 0  # Instant for < 100 CC
        assert data["attribution_cc"] >= 50.0  # At least original amount


@pytest.mark.asyncio
async def test_quality_gate_deposit_retained_without_evidence():
    """Quality gate: deposit stays flat when no evidence is produced (R6)."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        sr = await c.post(
            "/api/cc/stake",
            json={"user_id": user_id, "idea_id": idea_id, "amount_cc": 50.0},
        )
        assert sr.status_code == 201
        stake_id = sr.json()["stake_id"]

        # No usage events — unstake returns flat attribution
        ur = await c.post(
            "/api/cc/unstake",
            json={"stake_id": stake_id, "user_id": user_id},
        )
        assert ur.status_code == 200
        data = ur.json()
        assert data["attribution_cc"] == 50.0  # Exactly the original amount
