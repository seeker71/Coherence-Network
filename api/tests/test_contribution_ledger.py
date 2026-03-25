"""Tests for contribution ledger and CC staking."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


def _isolate_db(tmp_path, monkeypatch):
    """Point unified_db at a temp SQLite database for test isolation."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    from app.services import unified_db
    unified_db.reset_engine()
    unified_db.ensure_schema()


def _seed_idea(tmp_path, monkeypatch):
    """Create a test idea in the portfolio."""
    _isolate_db(tmp_path, monkeypatch)
    from app.services import idea_service
    idea_service.create_idea(
        idea_id="test-stake-idea",
        name="Test Stake Idea",
        description="An idea for staking tests",
        potential_value=100.0,
        estimated_cost=50.0,
        confidence=0.7,
    )


def test_record_contribution_persists(tmp_path, monkeypatch):
    """Record a contribution and verify it persists in history."""
    _isolate_db(tmp_path, monkeypatch)
    from app.services import contribution_ledger_service

    result = contribution_ledger_service.record_contribution(
        contributor_id="alice",
        contribution_type="compute",
        amount_cc=10.0,
        idea_id=None,
        metadata={"task": "test-task"},
    )
    assert result["id"].startswith("clr_")
    assert result["contributor_id"] == "alice"
    assert result["amount_cc"] == 10.0

    history = contribution_ledger_service.get_contributor_history("alice")
    assert len(history) == 1
    assert history[0]["id"] == result["id"]


def test_get_balance_totals(tmp_path, monkeypatch):
    """Get balance and verify totals by type and grand total."""
    _isolate_db(tmp_path, monkeypatch)
    from app.services import contribution_ledger_service

    contribution_ledger_service.record_contribution("bob", "compute", 10.0)
    contribution_ledger_service.record_contribution("bob", "compute", 5.0)
    contribution_ledger_service.record_contribution("bob", "code", 20.0)

    balance = contribution_ledger_service.get_contributor_balance("bob")
    assert balance["contributor_id"] == "bob"
    assert balance["totals_by_type"]["compute"] == 15.0
    assert balance["totals_by_type"]["code"] == 20.0
    assert balance["grand_total"] == 35.0


def test_stake_on_idea_increases_potential_value(tmp_path, monkeypatch):
    """Stake on an idea and verify potential_value increases by amount * 0.5."""
    _seed_idea(tmp_path, monkeypatch)
    from app.services import idea_service

    original_idea = idea_service.get_idea("test-stake-idea")
    assert original_idea is not None
    original_pv = original_idea.potential_value

    result = idea_service.stake_on_idea(
        idea_id="test-stake-idea",
        contributor_id="charlie",
        amount_cc=20.0,
        rationale="I believe in this idea",
    )

    assert result["stake_record"]["amount_cc"] == 20.0
    updated_idea = idea_service.get_idea("test-stake-idea")
    assert updated_idea is not None
    assert updated_idea.potential_value == pytest.approx(original_pv + 10.0)


def test_stake_on_idea_creates_lineage_investment(tmp_path, monkeypatch):
    """Stake on an idea and verify a value lineage investment is created."""
    _seed_idea(tmp_path, monkeypatch)
    from app.services import idea_service, value_lineage_service

    result = idea_service.stake_on_idea(
        idea_id="test-stake-idea",
        contributor_id="dave",
        amount_cc=15.0,
    )

    lineage_id = result["lineage_id"]
    assert lineage_id is not None

    link = value_lineage_service.get_link(lineage_id)
    assert link is not None
    staker_investments = [i for i in link.investments if i.stage == "staker"]
    assert len(staker_investments) >= 1
    assert staker_investments[0].contributor == "dave"
    assert staker_investments[0].energy_units == 15.0


def test_get_idea_investments_shows_stake(tmp_path, monkeypatch):
    """Stake on an idea and verify it appears in get_idea_investments."""
    _seed_idea(tmp_path, monkeypatch)
    from app.services import idea_service, contribution_ledger_service

    idea_service.stake_on_idea(
        idea_id="test-stake-idea",
        contributor_id="eve",
        amount_cc=25.0,
    )

    investments = contribution_ledger_service.get_idea_investments("test-stake-idea")
    assert len(investments) == 1
    assert investments[0]["contribution_type"] == "stake"
    assert investments[0]["contributor_id"] == "eve"
    assert investments[0]["amount_cc"] == 25.0


@pytest.mark.asyncio
async def test_stake_endpoint(tmp_path, monkeypatch):
    """Test the POST /api/ideas/{idea_id}/stake endpoint."""
    _seed_idea(tmp_path, monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas/test-stake-idea/stake",
            json={"contributor_id": "frank", "amount_cc": 10.0, "rationale": "looks promising"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stake"]["contributor"] == "frank"
        assert data["stake"]["amount_cc"] == 10.0
        assert "tasks_created" in data


@pytest.mark.asyncio
async def test_ledger_endpoint(tmp_path, monkeypatch):
    """Test the GET /api/contributions/ledger/{contributor_id} endpoint."""
    _isolate_db(tmp_path, monkeypatch)
    from app.services import contribution_ledger_service

    contribution_ledger_service.record_contribution("grace", "compute", 12.0)
    contribution_ledger_service.record_contribution("grace", "code", 8.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/contributions/ledger/grace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"]["grand_total"] == 20.0
        assert len(data["history"]) == 2
