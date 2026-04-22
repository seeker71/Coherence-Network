"""Tests for CC Economics and Value Coherence.

Five flows cover the surface:

  · Supply + coherence (mint/burn, pause-below-1.0, healthy-empty)
  · Exchange rate (spread, 5-min TTL, stale detection/refresh)
  · Staking lifecycle (stake → attribution growth → unstake with
    cooldown tiers 0/24/72 h → cooldown re-reject, 404 paths, summary)
  · Treasury ledger audit trail
  · Quality gate deposit (attribution grows with evidence, flat
    without evidence)
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str) -> dict:
    r = await c.post("/api/ideas", json={
        "id": idea_id, "name": f"Idea {idea_id}",
        "description": f"Test idea for staking: {idea_id}",
        "potential_value": 1000.0, "estimated_cost": 100.0, "confidence": 0.8,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _mint(user_id: str, amount_cc: float, deposit_usd: float) -> None:
    from app.services import cc_treasury_service
    cc_treasury_service.mint(user_id, amount_cc, deposit_usd, 333.33)


def _reset() -> None:
    from app.services import cc_treasury_service, cc_oracle_service
    cc_treasury_service.reset_treasury()
    cc_oracle_service.reset_cache()


@pytest.mark.asyncio
async def test_supply_and_coherence_flow():
    """Supply endpoint returns the full shape; empty treasury is
    healthy (regression — 1.0 used to show 'warning'); mint/burn
    moves outstanding; coherence < 1.0 pauses minting."""
    _reset()
    from app.services import cc_treasury_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Empty treasury — score 1.0, status healthy, full shape.
        r = await c.get("/api/cc/supply")
        assert r.status_code == 200
        d = r.json()
        for field in ("total_minted", "total_burned", "outstanding", "coherence_score",
                      "coherence_status", "treasury_value_usd", "exchange_rate", "as_of"):
            assert field in d
        assert d["outstanding"] == 0.0
        assert d["coherence_score"] == 1.0
        assert d["coherence_status"] == "healthy"

    # Mint/burn directly via service for deterministic state.
    cc_treasury_service.mint("u1", 500.0, 5.0, 333.33)
    s1 = cc_treasury_service.get_supply(333.33)
    assert s1["total_minted"] == 500.0 and s1["outstanding"] == 500.0
    cc_treasury_service.burn("u1", 200.0, 2.0, 333.33)
    s2 = cc_treasury_service.get_supply(333.33)
    assert s2["total_burned"] == 200.0 and s2["outstanding"] == 300.0

    # Over-mint → coherence < 1.0 → paused, can_mint False.
    _reset()
    cc_treasury_service.mint("u-bad", 10000.0, 1.0, 333.33)
    assert not cc_treasury_service.can_mint(333.33)
    paused = cc_treasury_service.get_supply(333.33)
    assert paused["coherence_score"] < 1.0 and paused["coherence_status"] == "paused"

    # Healthy coherence above 1.0 when treasury properly backs supply.
    _reset()
    _mint("user-cs", 1000.0, 10.0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        d = (await c.get("/api/cc/supply")).json()
        assert d["coherence_score"] >= 1.0
        assert d["coherence_status"] in ("healthy", "warning")


@pytest.mark.asyncio
async def test_exchange_rate_flow():
    """Spread is 1%, 5-minute cache, stale is detected and refreshes."""
    _reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        d = (await c.get("/api/cc/exchange-rate")).json()
        assert d["spread_pct"] == 1.0
        assert d["buy_rate"] < d["cc_per_usd"] < d["sell_rate"]
        assert d["oracle_source"] == "coingecko"
        assert d["cache_ttl_seconds"] == 300
        assert "cached_at" in d

    # Stale detection via direct service — backdate cache, refresh clears stale.
    from app.services import cc_oracle_service
    rate = cc_oracle_service.get_exchange_rate()
    assert rate is not None and rate.is_stale is False
    cc_oracle_service._CACHE["cached_at"] = time.time() - 400
    refreshed = cc_oracle_service.get_exchange_rate()
    assert refreshed is not None and refreshed.is_stale is False


@pytest.mark.asyncio
async def test_staking_lifecycle_flow():
    """Stake → attribution grows with usage events → unstake with
    cooldown tiers (0/24/72 h depending on amount) → second unstake
    rejected → missing stake/idea return 404 → summary aggregates
    positions."""
    _reset()
    from app.services import cc_staking_service

    user = _uid("user")
    idea_small = _uid("idea")       # <100 CC stake → instant
    idea_medium = _uid("idea")      # 100-1000 CC stake → 24h
    idea_large = _uid("idea")       # >1000 CC stake → 72h
    _mint(user, 10000.0, 100.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create ideas.
        for iid in (idea_small, idea_medium, idea_large):
            await _create_idea(c, iid)

        # Staking 404 on unknown idea.
        unknown = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": "nonexistent-idea", "amount_cc": 100.0,
        })
        assert unknown.status_code == 404

        # Stake creates position with attribution == amount initially.
        s_small = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": idea_small, "amount_cc": 50.0,
        })
        assert s_small.status_code == 201
        small_data = s_small.json()
        assert small_data["attribution_cc"] == 50.0 and small_data["status"] == "active"
        small_stake_id = small_data["stake_id"]

        s_medium = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": idea_medium, "amount_cc": 500.0,
        })
        medium_stake_id = s_medium.json()["stake_id"]

        s_large = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": idea_large, "amount_cc": 2000.0,
        })
        large_stake_id = s_large.json()["stake_id"]

        # Insufficient-balance reject.
        broke = _uid("broke")
        _mint(broke, 10.0, 0.1)
        reject = await c.post("/api/cc/stake", json={
            "user_id": broke, "idea_id": idea_small, "amount_cc": 500.0,
        })
        assert reject.status_code == 400
        assert "Insufficient" in reject.json()["detail"]

        # Attribution grows when usage events fire on the idea.
        cc_staking_service.update_attribution(idea_medium, 10)
        summary = (await c.get(f"/api/cc/staking/{user}")).json()
        medium_pos = next(p for p in summary["positions"] if p["idea_id"] == idea_medium)
        # 500 * (1 + 0.01 * 10) = 550
        assert medium_pos["attribution_cc"] == pytest.approx(550.0, rel=0.01)

        # Attribution flat without usage.
        small_pos = next(p for p in summary["positions"] if p["idea_id"] == idea_small)
        assert small_pos["attribution_cc"] == 50.0

        # Summary aggregates all positions.
        assert len(summary["positions"]) == 3
        for pos in summary["positions"]:
            for field in ("stake_id", "idea_id", "amount_cc",
                          "attribution_cc", "staked_at", "status"):
                assert field in pos

        # Unstake cooldown tiers.
        u_small = (await c.post("/api/cc/unstake", json={
            "stake_id": small_stake_id, "user_id": user,
        })).json()
        assert u_small["cooldown_hours"] == 0 and u_small["status"] == "withdrawn"

        u_medium = (await c.post("/api/cc/unstake", json={
            "stake_id": medium_stake_id, "user_id": user,
        })).json()
        assert u_medium["cooldown_hours"] == 24 and u_medium["status"] == "cooling_down"

        u_large = (await c.post("/api/cc/unstake", json={
            "stake_id": large_stake_id, "user_id": user,
        })).json()
        assert u_large["cooldown_hours"] == 72 and u_large["status"] == "cooling_down"

        # Second unstake on the cooling-down stake is rejected.
        second = await c.post("/api/cc/unstake", json={
            "stake_id": medium_stake_id, "user_id": user,
        })
        assert second.status_code == 400
        body = second.json()["detail"].lower()
        assert "cooldown" in body or "withdrawn" in body

        # Unknown stake → 404.
        unknown_unstake = await c.post("/api/cc/unstake", json={
            "stake_id": "nonexistent", "user_id": "nobody",
        })
        assert unknown_unstake.status_code == 404


@pytest.mark.asyncio
async def test_treasury_ledger_audit_trail():
    """Every mint/burn lands on the ledger with balance + coherence
    snapshots, queryable by user_id for audit."""
    _reset()
    from app.services import cc_treasury_service

    cc_treasury_service.mint("u-audit", 1000.0, 10.0, 333.33)
    cc_treasury_service.burn("u-audit", 100.0, 1.0, 333.33)

    entries = cc_treasury_service.get_ledger_entries(user_id="u-audit")
    assert len(entries) >= 2
    actions = [e["action"] for e in entries]
    assert "mint" in actions and "burn" in actions
    for entry in entries:
        for field in ("treasury_balance_after", "coherence_score_after", "created_at"):
            assert field in entry


@pytest.mark.asyncio
async def test_quality_gate_deposit_flow():
    """R6 demand driver: deposit (stake) grows with evidence (usage
    events), stays flat without. Unstake returns the grown or flat
    attribution accordingly."""
    _reset()
    from app.services import cc_staking_service

    user = _uid("user")
    idea_with_evidence = _uid("idea")
    idea_without = _uid("idea")
    _mint(user, 2000.0, 20.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        for iid in (idea_with_evidence, idea_without):
            await _create_idea(c, iid)

        # With evidence — attribution >= original.
        s1 = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": idea_with_evidence, "amount_cc": 50.0,
        })
        sid1 = s1.json()["stake_id"]
        cc_staking_service.update_attribution(idea_with_evidence, 5)
        r1 = (await c.post("/api/cc/unstake", json={
            "stake_id": sid1, "user_id": user,
        })).json()
        assert r1["cooldown_hours"] == 0  # <100 CC = instant
        assert r1["attribution_cc"] >= 50.0

        # Without evidence — attribution stays flat.
        s2 = await c.post("/api/cc/stake", json={
            "user_id": user, "idea_id": idea_without, "amount_cc": 50.0,
        })
        sid2 = s2.json()["stake_id"]
        r2 = (await c.post("/api/cc/unstake", json={
            "stake_id": sid2, "user_id": user,
        })).json()
        assert r2["attribution_cc"] == 50.0
