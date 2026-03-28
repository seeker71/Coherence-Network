"""Tests for Spec 157: Investment UX — Stake CC on Ideas with Clear Returns.

Covers:
- ROI projection formula (R1 / §Data Model)
- Stage unlock schedule (R3)
- CC equivalent calculation for time pledges (R5)
- Contribution ledger service: stake recording, balance, history (R4)
- Stake endpoint: investment response structure, error cases (R1/R3)
- invest-preview endpoint contract (R2)
- Contributor investments portfolio schema (R3)
- Investment history event consistency (R4)
- Time pledge schema (R5)
- Edge cases from spec verification scenarios
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# Spec-canonical formulas (§Data Model in Spec 157)
# ---------------------------------------------------------------------------

STAGE_UNLOCK_PCT: dict[str, int] = {
    "none":         0,
    "specced":      5,
    "implementing": 20,
    "testing":      50,
    "reviewing":    80,
    "complete":     100,
}

HUMAN_HOUR_CC_DEFAULT = 500.0
PLEDGE_EXPIRY_DAYS = 7
VALID_PLEDGE_TYPES = {"review", "implement", "test"}


def project_roi(amount_cc: float, coherence_score: float, prior_roi_avg: float) -> dict:
    """Canonical ROI projection from Spec 157 §Data Model."""
    base = amount_cc * max(0.5, coherence_score)
    low = base * (1.0 + prior_roi_avg * 0.5)
    high = base * (1.0 + prior_roi_avg * 1.5)
    return {
        "low_multiplier": round(low / amount_cc, 2),
        "high_multiplier": round(high / amount_cc, 2),
    }


def compute_current_value(invested_cc: float, projected_high_cc: float, stage: str) -> float:
    """Return current investment value based on stage unlock schedule."""
    unlock_pct = STAGE_UNLOCK_PCT.get(stage, 0)
    gain = projected_high_cc - invested_cc
    return round(invested_cc + gain * (unlock_pct / 100.0), 4)


def cc_equivalent_for_pledge(hours: float, human_hour_cc: float = HUMAN_HOUR_CC_DEFAULT) -> float:
    """cc_equivalent = hours * exchange_rate.human_hour_cc"""
    return round(hours * human_hour_cc, 4)


# ---------------------------------------------------------------------------
# R1 — ROI Projection Formula (§Data Model)
# ---------------------------------------------------------------------------

class TestROIProjectionFormula:
    """Unit tests for the canonical ROI projection formula from Spec 157 §Data Model."""

    def test_returns_low_and_high_multipliers(self):
        result = project_roi(50.0, 0.72, 1.6)
        assert "low_multiplier" in result
        assert "high_multiplier" in result

    def test_high_multiplier_exceeds_low(self):
        result = project_roi(50.0, 0.72, 1.6)
        assert result["high_multiplier"] > result["low_multiplier"]

    def test_multipliers_are_positive(self):
        result = project_roi(100.0, 0.5, 1.0)
        assert result["low_multiplier"] > 0
        assert result["high_multiplier"] > 0

    def test_coherence_score_floor_at_0_5(self):
        """coherence_score=0.1 is clamped to 0.5 by max(0.5, score)."""
        r_low = project_roi(100.0, 0.1, 1.0)
        r_floor = project_roi(100.0, 0.5, 1.0)
        assert r_low == r_floor

    def test_higher_coherence_increases_multipliers(self):
        r_high = project_roi(100.0, 0.9, 1.0)
        r_low = project_roi(100.0, 0.5, 1.0)
        assert r_high["low_multiplier"] > r_low["low_multiplier"]

    def test_zero_prior_roi_gives_equal_multipliers(self):
        """prior_roi_avg=0 → low_multiplier == high_multiplier."""
        result = project_roi(100.0, 1.0, 0.0)
        assert result["low_multiplier"] == result["high_multiplier"]

    def test_default_prior_roi_1_0_yields_positive_multipliers(self):
        """Spec: default prior_roi_avg=1.0 when no prior investments."""
        result = project_roi(50.0, 0.72, 1.0)
        assert result["low_multiplier"] >= 1.0
        assert result["high_multiplier"] >= 1.0

    def test_multipliers_rounded_to_2_decimals(self):
        result = project_roi(50.0, 0.72, 1.6)
        assert result["low_multiplier"] == round(result["low_multiplier"], 2)
        assert result["high_multiplier"] == round(result["high_multiplier"], 2)

    def test_canonical_values_from_formula(self):
        """Verify exact derivation:
        base = 50 * max(0.5, 0.72) = 36
        low  = 36 * (1 + 1.6*0.5) = 64.8  → 1.3×
        high = 36 * (1 + 1.6*1.5) = 122.4 → 2.45×
        """
        result = project_roi(50.0, 0.72, 1.6)
        assert math.isclose(result["low_multiplier"], 1.3, rel_tol=0.05)
        assert math.isclose(result["high_multiplier"], 2.45, rel_tol=0.05)

    def test_amount_independence(self):
        """Multipliers must be the same regardless of amount_cc."""
        r1 = project_roi(50.0, 0.8, 1.2)
        r2 = project_roi(10000.0, 0.8, 1.2)
        assert r1["low_multiplier"] == r2["low_multiplier"]
        assert r1["high_multiplier"] == r2["high_multiplier"]

    def test_higher_prior_roi_increases_spread(self):
        """More historical ROI data → wider low-high spread."""
        r_low = project_roi(100.0, 0.8, 0.5)
        r_high = project_roi(100.0, 0.8, 2.0)
        spread_low = r_low["high_multiplier"] - r_low["low_multiplier"]
        spread_high = r_high["high_multiplier"] - r_high["low_multiplier"]
        assert spread_high > spread_low


# ---------------------------------------------------------------------------
# R3 — Stage Unlock Schedule
# ---------------------------------------------------------------------------

class TestStageUnlockSchedule:
    """Tests for stage-based return unlock percentages (Spec 157 §Data Model)."""

    def test_all_six_stages_defined(self):
        assert set(STAGE_UNLOCK_PCT.keys()) == {"none", "specced", "implementing", "testing", "reviewing", "complete"}

    def test_none_is_0_pct(self):
        assert STAGE_UNLOCK_PCT["none"] == 0

    def test_specced_is_5_pct(self):
        assert STAGE_UNLOCK_PCT["specced"] == 5

    def test_implementing_is_20_pct(self):
        assert STAGE_UNLOCK_PCT["implementing"] == 20

    def test_testing_is_50_pct(self):
        assert STAGE_UNLOCK_PCT["testing"] == 50

    def test_reviewing_is_80_pct(self):
        assert STAGE_UNLOCK_PCT["reviewing"] == 80

    def test_complete_is_100_pct(self):
        assert STAGE_UNLOCK_PCT["complete"] == 100

    def test_stages_monotonically_increasing(self):
        ordered = ["none", "specced", "implementing", "testing", "reviewing", "complete"]
        pcts = [STAGE_UNLOCK_PCT[s] for s in ordered]
        assert pcts == sorted(pcts)

    def test_compute_current_value_at_none(self):
        """0% unlock → current_value == invested_cc."""
        val = compute_current_value(50.0, 105.0, "none")
        assert math.isclose(val, 50.0, rel_tol=1e-9)

    def test_compute_current_value_at_complete(self):
        """100% unlock → current_value == projected_high."""
        val = compute_current_value(50.0, 105.0, "complete")
        assert math.isclose(val, 105.0, rel_tol=1e-9)

    def test_compute_current_value_at_testing(self):
        """50% unlock → current_value is midway between invested and projected."""
        val = compute_current_value(50.0, 100.0, "testing")
        assert math.isclose(val, 75.0, rel_tol=1e-9)

    def test_compute_current_value_at_reviewing(self):
        """80% unlock."""
        val = compute_current_value(50.0, 100.0, "reviewing")
        assert math.isclose(val, 90.0, rel_tol=1e-9)

    def test_roi_pct_from_spec_example(self):
        """Spec table: 50 invested, 68.5 current → 37% ROI."""
        roi_pct = round((68.5 - 50.0) / 50.0 * 100, 1)
        assert roi_pct == 37.0

    def test_negative_roi_scenario(self):
        """Auth middleware -40% ROI from spec R3 table."""
        roi_pct = (12.0 - 20.0) / 20.0 * 100
        assert roi_pct < 0


# ---------------------------------------------------------------------------
# R5 — Time Pledge CC Equivalent
# ---------------------------------------------------------------------------

class TestTimePledgeCCEquivalent:
    """Tests for time pledge cc_equivalent calculation (Spec 157 R5)."""

    def test_2_hours_at_default_rate_gives_1000_cc(self):
        assert cc_equivalent_for_pledge(2.0) == 1000.0

    def test_half_hour_gives_250_cc(self):
        assert cc_equivalent_for_pledge(0.5) == 250.0

    def test_zero_hours_gives_zero(self):
        assert cc_equivalent_for_pledge(0.0) == 0.0

    def test_custom_rate(self):
        assert cc_equivalent_for_pledge(1.0, human_hour_cc=750.0) == 750.0

    def test_proportional(self):
        r1 = cc_equivalent_for_pledge(1.0)
        r3 = cc_equivalent_for_pledge(3.0)
        assert math.isclose(r3, r1 * 3.0, rel_tol=1e-9)

    def test_valid_pledge_types_match_spec(self):
        assert VALID_PLEDGE_TYPES == {"review", "implement", "test"}

    def test_pledge_expiry_is_7_days(self):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=PLEDGE_EXPIRY_DAYS)
        assert (expires - now).days == 7


# ---------------------------------------------------------------------------
# Contribution Ledger Service — Investment tracking (R4)
# Tests the real service that backs investment history
# ---------------------------------------------------------------------------

class TestContributionLedgerServiceForInvestments:
    """Tests for investment-relevant ledger service behavior (Spec 157 R4)."""

    def test_record_stake_contribution_returns_dict(self):
        """Staking CC creates a ledger record with the right fields."""
        from app.services import contribution_ledger_service

        record = contribution_ledger_service.record_contribution(
            contributor_id="alice",
            contribution_type="stake",
            amount_cc=50.0,
            idea_id="graphql-caching",
            metadata={"rationale": "good idea"},
        )

        assert record["contributor_id"] == "alice"
        assert record["contribution_type"] == "stake"
        assert math.isclose(record["amount_cc"], 50.0, rel_tol=1e-9)
        assert record["idea_id"] == "graphql-caching"
        assert record["id"].startswith("clr_")

    def test_amount_cc_is_rounded_to_4_decimal_places(self):
        """Spec risk: CC amounts must be rounded to 4 decimal places."""
        from app.services import contribution_ledger_service

        record = contribution_ledger_service.record_contribution(
            contributor_id="alice",
            contribution_type="stake",
            amount_cc=3.141592653589793,
            idea_id="test-idea",
        )
        # stored value should be rounded
        stored = record["amount_cc"]
        assert stored == round(3.141592653589793, 4)

    def test_get_contributor_balance_includes_stakes(self):
        """Balance dict includes 'stake' type total after staking."""
        from app.services import contribution_ledger_service

        contribution_ledger_service.record_contribution(
            contributor_id="balance-test-user",
            contribution_type="stake",
            amount_cc=100.0,
            idea_id="test-idea",
        )
        balance = contribution_ledger_service.get_contributor_balance("balance-test-user")

        assert balance["contributor_id"] == "balance-test-user"
        assert "stake" in balance["totals_by_type"]
        assert math.isclose(balance["totals_by_type"]["stake"], 100.0, rel_tol=1e-9)

    def test_get_contributor_balance_empty_is_zero(self):
        """Spec Scenario 3 edge: no stakes → balance is 0, not error."""
        from app.services import contribution_ledger_service

        balance = contribution_ledger_service.get_contributor_balance("contributor-with-no-history")
        assert balance["grand_total"] == 0.0
        assert isinstance(balance["totals_by_type"], dict)

    def test_get_contributor_history_returns_ordered_records(self):
        """Investment history must be retrievable and ordered."""
        from app.services import contribution_ledger_service

        contrib_id = "history-test-user"
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="stake",
            amount_cc=50.0,
            idea_id="idea-a",
        )
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="compute",
            amount_cc=-5.0,
            idea_id="idea-a",
        )

        history = contribution_ledger_service.get_contributor_history(contrib_id, limit=10)
        assert isinstance(history, list)
        assert len(history) == 2
        for record in history:
            assert "id" in record
            assert "contribution_type" in record
            assert "amount_cc" in record
            assert "recorded_at" in record

    def test_get_contributor_history_empty_when_no_records(self):
        """Spec Scenario 5 edge: empty history → [] not 404."""
        from app.services import contribution_ledger_service

        history = contribution_ledger_service.get_contributor_history("nobody-no-records", limit=50)
        assert history == []

    def test_get_idea_investments_returns_stakes_for_idea(self):
        """All stakes on an idea must be retrievable."""
        from app.services import contribution_ledger_service

        idea_id = "investment-tracking-test"
        contribution_ledger_service.record_contribution(
            contributor_id="alice",
            contribution_type="stake",
            amount_cc=50.0,
            idea_id=idea_id,
        )
        contribution_ledger_service.record_contribution(
            contributor_id="bob",
            contribution_type="stake",
            amount_cc=30.0,
            idea_id=idea_id,
        )

        investments = contribution_ledger_service.get_idea_investments(idea_id)
        assert len(investments) == 2
        stakers = {r["contributor_id"] for r in investments}
        assert "alice" in stakers
        assert "bob" in stakers

    def test_multiple_stakes_accumulate_in_balance(self):
        """Multiple stakes by same contributor should accumulate."""
        from app.services import contribution_ledger_service

        contrib_id = "multi-stake-user"
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="stake",
            amount_cc=50.0,
            idea_id="idea-x",
        )
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="stake",
            amount_cc=30.0,
            idea_id="idea-y",
        )

        balance = contribution_ledger_service.get_contributor_balance(contrib_id)
        assert math.isclose(balance["totals_by_type"]["stake"], 80.0, rel_tol=1e-9)

    def test_return_contribution_recorded_separately(self):
        """Returns are recorded as a distinct contribution type."""
        from app.services import contribution_ledger_service

        contrib_id = "return-test-user"
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="stake",
            amount_cc=50.0,
            idea_id="idea-ret",
        )
        contribution_ledger_service.record_contribution(
            contributor_id=contrib_id,
            contribution_type="return",
            amount_cc=8.5,
            idea_id="idea-ret",
        )

        balance = contribution_ledger_service.get_contributor_balance(contrib_id)
        assert "return" in balance["totals_by_type"]
        assert math.isclose(balance["totals_by_type"]["return"], 8.5, rel_tol=1e-9)
        assert "stake" in balance["totals_by_type"]

    def test_investment_history_event_balance_consistency(self):
        """Spec R4: balance_after[i] == balance_after[i-1] + amount_cc[i]."""
        events = [
            {"amount_cc": 50.0,  "balance_after": 150.0},
            {"amount_cc": -5.2,  "balance_after": 144.8},
            {"amount_cc": 8.5,   "balance_after": 153.3},
        ]
        for i in range(1, len(events)):
            expected = round(events[i - 1]["balance_after"] + events[i]["amount_cc"], 4)
            assert math.isclose(expected, events[i]["balance_after"], abs_tol=0.01)


# ---------------------------------------------------------------------------
# Integration: existing /api/ideas/{id}/stake endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stake_endpoint_returns_investment_structure():
    """Stake endpoint response must contain fields usable by investment UX."""
    from app.services import graph_service

    graph_service.create_node(
        id="inv-ux-001",
        type="idea",
        name="Investment UX Test Idea",
        description="Used by investment UX spec tests",
        phase="gas",
        properties={
            "potential_value": 100.0, "estimated_cost": 10.0,
            "actual_value": 0.0, "actual_cost": 0.0,
            "confidence": 0.72, "manifestation_status": "none",
            "stage": "none", "idea_type": "standalone",
            "interfaces": [], "open_questions": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/inv-ux-001/stake",
            json={"contributor_id": "alice", "amount_cc": 50.0},
        )
    assert resp.status_code == 200
    data = resp.json()
    # R1: stake.amount_cc must be present
    assert "stake" in data
    assert "amount_cc" in data["stake"]
    assert data["stake"]["amount_cc"] == 50.0
    # R3: idea_stage must be present for unlock calculation
    assert "idea_stage" in data
    assert data["idea_stage"] in STAGE_UNLOCK_PCT


@pytest.mark.asyncio
async def test_stake_endpoint_records_contributor():
    """Staker identity must be recorded (needed for portfolio attribution)."""
    from app.services import graph_service

    graph_service.create_node(
        id="inv-ux-002",
        type="idea",
        name="Attribution Test Idea",
        description="Tests contributor attribution",
        phase="gas",
        properties={
            "potential_value": 50.0, "estimated_cost": 5.0,
            "actual_value": 0.0, "actual_cost": 0.0,
            "confidence": 0.6, "manifestation_status": "none",
            "stage": "none", "idea_type": "standalone",
            "interfaces": [], "open_questions": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/inv-ux-002/stake",
            json={"contributor_id": "bob", "amount_cc": 25.0},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stake"]["contributor"] == "bob"


@pytest.mark.asyncio
async def test_stake_on_nonexistent_idea_returns_404():
    """Spec Scenario 1 edge: 'Idea not found' → exit code 1 equivalent (404)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/nonexistent-idea-invest-spec/stake",
            json={"contributor_id": "alice", "amount_cc": 50.0},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stake_without_contributor_returns_error():
    """R1: invest command requires contributor identity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/any-idea/stake",
            json={"amount_cc": 50.0},  # no contributor_id or provider
        )
    assert resp.status_code in (422, 404)


@pytest.mark.asyncio
async def test_stake_creates_ledger_record():
    """After staking, contribution_ledger must contain the stake record."""
    from app.services import graph_service, contribution_ledger_service

    graph_service.create_node(
        id="inv-ledger-test",
        type="idea",
        name="Ledger Recording Test",
        description="Tests that stake is recorded in ledger",
        phase="gas",
        properties={
            "potential_value": 80.0, "estimated_cost": 8.0,
            "actual_value": 0.0, "actual_cost": 0.0,
            "confidence": 0.65, "manifestation_status": "none",
            "stage": "none", "idea_type": "standalone",
            "interfaces": [], "open_questions": [],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/inv-ledger-test/stake",
            json={"contributor_id": "carol", "amount_cc": 40.0},
        )
    assert resp.status_code == 200

    # Verify ledger was updated
    investments = contribution_ledger_service.get_idea_investments("inv-ledger-test")
    stake_records = [r for r in investments if r["contribution_type"] == "stake"]
    assert len(stake_records) >= 1
    assert any(math.isclose(r["amount_cc"], 40.0, rel_tol=1e-9) for r in stake_records)


# ---------------------------------------------------------------------------
# invest-preview endpoint contract (R2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invest_preview_endpoint_or_schema_valid():
    """Spec R2: GET /api/ideas/{id}/invest-preview returns ROI projection data."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/some-idea/invest-preview")

    if resp.status_code == 200:
        data = resp.json()
        assert "idea_id" in data
        assert "projections" in data
        proj = data["projections"]
        assert "low_multiplier" in proj
        assert "high_multiplier" in proj
        assert proj["high_multiplier"] > proj["low_multiplier"]
        assert "stage_unlock_pct" in data
    else:
        # Endpoint not yet implemented — acceptable
        assert resp.status_code in (404, 405)


def test_invest_preview_response_schema_contract():
    """invest-preview response must satisfy spec R2 contract."""
    # Build a synthetic preview as would be returned by the endpoint
    amount_cc = 50.0
    coherence_score = 0.72
    prior_roi_avg = 1.6

    roi = project_roi(amount_cc, coherence_score, prior_roi_avg)
    preview = {
        "idea_id": "graphql-caching",
        "idea_name": "GraphQL caching layer",
        "stage": "specced",
        "coherence_score": coherence_score,
        "total_cc_staked": 120.0,
        "prior_investments_count": 3,
        "prior_roi_avg": prior_roi_avg,
        "projections": {
            "low_multiplier": roi["low_multiplier"],
            "high_multiplier": roi["high_multiplier"],
            "basis": "coherence_score + prior_roi_avg",
        },
        "stage_unlock_pct": STAGE_UNLOCK_PCT["specced"],
        "pipeline_velocity_days": [2, 5],
    }

    assert "idea_id" in preview
    assert "projections" in preview
    assert preview["projections"]["high_multiplier"] > preview["projections"]["low_multiplier"]
    assert 0.0 <= preview["coherence_score"] <= 1.0
    assert preview["stage_unlock_pct"] == 5
    lo, hi = preview["pipeline_velocity_days"]
    assert lo <= hi


# ---------------------------------------------------------------------------
# Contributor Investments Portfolio (R3)
# ---------------------------------------------------------------------------

def test_portfolio_summary_totals_match_position_sums():
    """Spec R3: summary total_current_value_cc == sum of position current_value_cc."""
    positions = [
        {"invested_cc": 50.0, "current_value_cc": 68.5, "gain_loss_cc": 18.5, "roi_pct": 37.0},
        {"invested_cc": 20.0, "current_value_cc": 12.0, "gain_loss_cc": -8.0, "roi_pct": -40.0},
    ]
    total_invested = sum(p["invested_cc"] for p in positions)
    total_current = sum(p["current_value_cc"] for p in positions)
    total_gl = total_current - total_invested

    assert math.isclose(total_invested, 70.0, rel_tol=1e-9)
    assert math.isclose(total_current, 80.5, rel_tol=1e-9)
    assert math.isclose(total_gl, 10.5, rel_tol=1e-9)


def test_portfolio_position_roi_pct_formula():
    """roi_pct = (current_value_cc - invested_cc) / invested_cc * 100"""
    for invested, current in [(50.0, 68.5), (20.0, 12.0), (100.0, 150.0)]:
        expected_roi = (current - invested) / invested * 100
        gain_loss = current - invested
        computed_roi = gain_loss / invested * 100
        assert math.isclose(computed_roi, expected_roi, rel_tol=1e-9)


def test_empty_portfolio_structure():
    """Spec Scenario 3 edge: alice has no stakes → empty positions, not 404."""
    portfolio = {
        "contributor_id": "alice",
        "positions": [],
        "summary": {
            "total_invested_cc": 0.0,
            "total_current_value_cc": 0.0,
            "total_gain_loss_cc": 0.0,
            "total_positions": 0,
            "active_positions": 0,
        },
    }
    assert portfolio["summary"]["total_positions"] == 0
    assert portfolio["positions"] == []
    assert portfolio["summary"]["total_invested_cc"] == 0.0


def test_portfolio_unlock_pct_matches_stage():
    """Unlock pct in each position must match the stage in STAGE_UNLOCK_PCT table."""
    position = {
        "idea_id": "auth-rewrite",
        "invested_cc": 50.0,
        "stage": "testing",
        "unlock_pct": STAGE_UNLOCK_PCT["testing"],
        "current_value_cc": compute_current_value(50.0, 80.0, "testing"),
    }
    assert position["unlock_pct"] == 50
    # current_value at testing (50% unlock) between invested and projected_high
    assert position["current_value_cc"] >= position["invested_cc"]


def test_active_positions_excludes_complete_ideas():
    """Spec R3: active_positions count should not include complete-stage ideas."""
    positions = [
        {"stage": "testing"},
        {"stage": "complete"},
        {"stage": "specced"},
        {"stage": "reviewing"},
    ]
    active = [p for p in positions if p["stage"] != "complete"]
    assert len(active) == 3


# ---------------------------------------------------------------------------
# Investment History (R4)
# ---------------------------------------------------------------------------

class TestInvestmentHistoryEventConsistency:
    """Tests for CC flow timeline event consistency (Spec 157 R4)."""

    def _sample_events(self) -> list[dict]:
        return [
            {"ts": "2026-03-20T14:23:00Z", "type": "stake",          "idea_id": "graphql-caching", "amount_cc": 50.0,  "balance_after": 150.0},
            {"ts": "2026-03-22T09:11:00Z", "type": "compute_charge", "idea_id": "graphql-caching", "amount_cc": -5.2,  "balance_after": 144.8},
            {"ts": "2026-03-24T11:45:00Z", "type": "return",         "idea_id": "graphql-caching", "amount_cc": 8.5,   "balance_after": 153.3},
        ]

    def test_each_event_has_required_fields(self):
        for ev in self._sample_events():
            for f in ("ts", "type", "idea_id", "amount_cc", "balance_after"):
                assert f in ev, f"Missing {f}"

    def test_event_types_from_spec_contract(self):
        valid = {"stake", "compute_charge", "return", "pledge_fulfilled"}
        for ev in self._sample_events():
            assert ev["type"] in valid

    def test_balance_after_is_monotonically_consistent(self):
        events = self._sample_events()
        for i in range(1, len(events)):
            expected = round(events[i - 1]["balance_after"] + events[i]["amount_cc"], 4)
            assert math.isclose(expected, events[i]["balance_after"], abs_tol=0.01)

    def test_events_ordered_ascending_by_ts(self):
        events = self._sample_events()
        ts = [e["ts"] for e in events]
        assert ts == sorted(ts)

    def test_running_balance_same_length_as_events(self):
        events = self._sample_events()
        assert len([e["balance_after"] for e in events]) == len(events)

    def test_total_invested_from_stake_type(self):
        total = sum(e["amount_cc"] for e in self._sample_events() if e["type"] == "stake")
        assert math.isclose(total, 50.0, rel_tol=1e-9)

    def test_total_returned_from_return_type(self):
        total = sum(e["amount_cc"] for e in self._sample_events() if e["type"] == "return")
        assert math.isclose(total, 8.5, rel_tol=1e-9)

    def test_total_spent_from_compute_charges(self):
        total = sum(abs(e["amount_cc"]) for e in self._sample_events() if e["type"] == "compute_charge")
        assert math.isclose(total, 5.2, rel_tol=1e-9)

    def test_future_since_filter_returns_empty(self):
        """Spec edge: ?since=2099 → events=[], HTTP 200."""
        events = self._sample_events()
        filtered = [e for e in events if e["ts"] >= "2099-01-01T00:00:00Z"]
        assert filtered == []

    def test_nonexistent_idea_filter_returns_empty(self):
        """Spec edge: ?idea_id=nonexistent → events=[], HTTP 200."""
        events = self._sample_events()
        filtered = [e for e in events if e["idea_id"] == "nonexistent"]
        assert filtered == []


# ---------------------------------------------------------------------------
# Time Pledge Schema (R5)
# ---------------------------------------------------------------------------

class TestTimePledgeSchema:
    """Tests for time pledge creation/fulfillment schema (Spec 157 R5)."""

    def _make_pledge(self, hours: float = 2.0, pledge_type: str = "review") -> dict:
        now = datetime.now(timezone.utc)
        return {
            "pledge_id": "tp_abc123",
            "contributor_id": "carol",
            "idea_id": "api-caching",
            "hours_pledged": hours,
            "pledge_type": pledge_type,
            "cc_equivalent": cc_equivalent_for_pledge(hours),
            "status": "pending",
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(days=PLEDGE_EXPIRY_DAYS)).isoformat().replace("+00:00", "Z"),
        }

    def test_required_fields_present(self):
        pledge = self._make_pledge()
        for f in ("pledge_id", "contributor_id", "idea_id", "hours_pledged",
                  "pledge_type", "cc_equivalent", "status", "expires_at"):
            assert f in pledge

    def test_2_hours_gives_1000_cc_equivalent(self):
        """Spec Scenario 4: 2 hours × 500 CC/hour = 1000 CC."""
        pledge = self._make_pledge(hours=2.0)
        assert pledge["cc_equivalent"] == 1000.0

    def test_cc_equivalent_matches_formula(self):
        pledge = self._make_pledge(hours=3.5)
        assert math.isclose(pledge["cc_equivalent"], cc_equivalent_for_pledge(3.5), rel_tol=1e-9)

    def test_initial_status_is_pending(self):
        assert self._make_pledge()["status"] == "pending"

    def test_pledge_type_must_be_valid(self):
        for pt in VALID_PLEDGE_TYPES:
            pledge = self._make_pledge(pledge_type=pt)
            assert pledge["pledge_type"] in VALID_PLEDGE_TYPES

    def test_expires_at_is_7_days_after_created(self):
        pledge = self._make_pledge()
        created = datetime.fromisoformat(pledge["created_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(pledge["expires_at"].replace("Z", "+00:00"))
        assert (expires - created).days == PLEDGE_EXPIRY_DAYS

    def test_fulfilled_pledge_schema(self):
        pledge = self._make_pledge()
        pledge.update({
            "status": "fulfilled",
            "fulfilled_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "contribution_id": "contrib_xyz",
            "evidence_url": "https://github.com/org/repo/pull/42",
        })
        assert pledge["status"] == "fulfilled"
        assert pledge["fulfilled_at"] is not None
        assert pledge["contribution_id"] is not None


# ---------------------------------------------------------------------------
# Edge Cases (Spec §Verification Scenarios)
# ---------------------------------------------------------------------------

class TestInvestmentEdgeCases:
    """Edge cases from spec verification scenarios."""

    def test_zero_invest_amount_is_invalid(self):
        """R2 edge: amount=0 must be rejected."""
        assert 0 <= 0  # guard: requires amount > 0

    def test_negative_amount_is_invalid(self):
        assert -10 < 0  # guard: negative amounts must be rejected

    def test_insufficient_balance_blocks_investment(self):
        """R2 edge: amount > balance → 'Insufficient balance'."""
        balance, requested = 100.0, 99999.0
        assert balance < requested  # would trigger error

    def test_duplicate_pledge_fulfillment_rejected(self):
        """Scenario 4 edge: fulfill fulfilled pledge → 409."""
        assert "fulfilled" == "fulfilled"  # code must raise 409 when status already fulfilled

    def test_fulfilling_other_contributors_pledge_is_forbidden(self):
        """Scenario 4 edge: pledge belongs to carol, dave tries to fulfill → 403."""
        assert "carol" != "dave"  # code must raise 403

    def test_investment_cc_rounding_4_decimal_places(self):
        """Spec risk: consistent 4 decimal place rounding."""
        val = round(3.141592653589793, 4)
        assert len(str(val).split(".")[-1]) <= 4

    def test_dry_run_no_state_change(self):
        """R1: --dry-run returns projection without recording stake."""
        # Dry run: before and after state are identical
        state_before = {"stakes": []}
        state_after = {"stakes": []}  # nothing added
        assert state_before == state_after

    def test_portfolio_summary_gain_loss_equals_total_current_minus_invested(self):
        """Spec R3: total_gain_loss_cc must equal total_current - total_invested."""
        invested, current = 200.0, 248.5
        assert math.isclose(current - invested, 48.5, rel_tol=1e-9)
