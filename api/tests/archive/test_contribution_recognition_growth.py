"""Tests for visible contribution recognition and growth tracking.

Spec: Every contribution — a question, a spec, a review, a share — should be
immediately visible to the contributor and the community. Show growth over time.
Make the invisible labor of thinking, connecting, and caring visible and valued.

Verification Scenarios:
1. Contribution immediately appears in recognition snapshot after creation
2. Growth delta is positive when current-window contributions exceed prior-window
3. Multiple contribution types (question, review, spec, share) all count and are visible
4. Ledger history shows all recorded contribution types immediately
5. Community-visible endpoint lists all contributions with pagination
6. Missing contributor returns 404 (not 500)
7. Contributor with no contributions returns zero metrics (visible 'clean slate')
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.graph import Edge
from app.services import contributor_recognition_service, graph_service
from app.services.unified_db import session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_contributor_node(contributor_id, name: str) -> str:
    """Create a contributor graph node and return its node_id."""
    node_id = f"contributor:visibility-{contributor_id}"
    graph_service.create_node(
        id=node_id,
        type="contributor",
        name=name,
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"{name.lower().replace(' ', '-')}-{contributor_id}@coherence.network",
            "legacy_id": str(contributor_id),
        },
    )
    return node_id


def _add_contribution_edge(
    contributor_node_id: str,
    contributor_id,
    *,
    cost: str = "5.00",
    score: float = 0.7,
    days_ago: float = 5,
    contribution_type: str = "code",
    fixed_now: datetime,
) -> None:
    """Attach a contribution edge to a contributor node, backdated by days_ago."""
    asset_id = uuid4()
    asset_node_id = f"asset:visibility-{asset_id}"
    graph_service.create_node(
        id=asset_node_id,
        type="asset",
        name=f"{contribution_type}-asset-{asset_id}",
        description=f"Asset for {contribution_type} contribution",
        phase="water",
        properties={"legacy_id": str(asset_id)},
    )
    edge = graph_service.create_edge(
        from_id=contributor_node_id,
        to_id=asset_node_id,
        type="contribution",
        properties={
            "contribution_id": str(uuid4()),
            "contributor_id": str(contributor_id),
            "asset_id": str(asset_id),
            "cost_amount": cost,
            "coherence_score": score,
            "metadata": {"contribution_type": contribution_type},
        },
        strength=score,
        created_by="test_contribution_recognition_growth",
    )
    # Backdate the edge so window calculations work correctly
    backdate = fixed_now - timedelta(days=days_ago)
    with session() as s:
        row = s.get(Edge, edge["id"])
        assert row is not None
        row.created_at = backdate
        s.commit()


# ---------------------------------------------------------------------------
# Scenario 1: Contribution immediately visible after creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_contribution_is_immediately_visible_in_recognition_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario 1 — Immediate Visibility
    Setup:   Contributor exists with no contributions
    Action:  POST /api/contributions to record one contribution
    Expected: GET /api/contributors/{id}/recognition returns total_contributions=1
    Proof:   The recognition snapshot updates instantly — no caching delay
    """
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = _create_contributor_node(contributor_id, "Immediate Visibility User")

    # Verify zero contributions before
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pre = await client.get(f"/api/contributors/{contributor_id}/recognition")
    assert pre.status_code == 200
    assert pre.json()["total_contributions"] == 0

    # Add one contribution
    _add_contribution_edge(
        contributor_node_id,
        contributor_id,
        cost="15.00",
        score=0.8,
        days_ago=2,
        contribution_type="question",
        fixed_now=fixed_now,
    )

    # Recognition snapshot must now reflect that contribution
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post = await client.get(f"/api/contributors/{contributor_id}/recognition")
    assert post.status_code == 200
    payload = post.json()
    assert payload["total_contributions"] == 1
    assert Decimal(str(payload["total_cost"])) == Decimal("15.00")
    assert payload["average_coherence_score"] == 0.8
    assert payload["current_window_contributions"] == 1


# ---------------------------------------------------------------------------
# Scenario 2: Growth tracking — positive delta signals positive growth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_growth_delta_positive_when_current_window_exceeds_prior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario 2 — Growth Tracking
    Setup:   Contributor has 1 contribution in prior window (31-60 days ago),
             3 contributions in current window (0-30 days ago)
    Action:  GET /api/contributors/{id}/recognition
    Expected: delta_contributions == 2 (3 - 1), showing positive growth
    Edge:    delta == 0 means stagnation; negative delta means declining activity
    """
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = _create_contributor_node(contributor_id, "Growth Tracker")

    # 1 prior-window contribution (40 days ago)
    _add_contribution_edge(
        contributor_node_id, contributor_id,
        cost="5.00", score=0.6, days_ago=40,
        contribution_type="review", fixed_now=fixed_now,
    )
    # 3 current-window contributions
    for days_ago, ctype in [(5, "spec"), (10, "question"), (20, "share")]:
        _add_contribution_edge(
            contributor_node_id, contributor_id,
            cost="8.00", score=0.75, days_ago=days_ago,
            contribution_type=ctype, fixed_now=fixed_now,
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_window_contributions"] == 3
    assert payload["prior_window_contributions"] == 1
    assert payload["delta_contributions"] == 2  # positive growth
    assert payload["window_days"] == 30


# ---------------------------------------------------------------------------
# Scenario 3: All contribution types count and are visible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_contribution_types_are_visible_and_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario 3 — Contribution Type Visibility
    Setup:   Contributor makes contributions of types: question, spec, review, share
    Action:  GET /api/contributors/{id}/recognition
    Expected: total_contributions == 4, all types count toward total
    Proof:   No contribution type is silently excluded from recognition
    """
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = _create_contributor_node(contributor_id, "All Types User")

    contribution_types = [
        ("question", "3.00", 0.6),
        ("spec", "12.00", 0.9),
        ("review", "7.00", 0.8),
        ("share", "2.00", 0.5),
    ]
    for i, (ctype, cost, score) in enumerate(contribution_types):
        _add_contribution_edge(
            contributor_node_id, contributor_id,
            cost=cost, score=score, days_ago=i + 1,
            contribution_type=ctype, fixed_now=fixed_now,
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_contributions"] == 4
    # All in current window (all within 30 days)
    assert payload["current_window_contributions"] == 4
    expected_total_cost = Decimal("3.00") + Decimal("12.00") + Decimal("7.00") + Decimal("2.00")
    assert Decimal(str(payload["total_cost"])) == expected_total_cost
    # Average coherence: (0.6 + 0.9 + 0.8 + 0.5) / 4 = 0.7
    assert abs(payload["average_coherence_score"] - 0.70) < 0.01


# ---------------------------------------------------------------------------
# Scenario 4: Ledger records are immediately visible after record_contribution
# ---------------------------------------------------------------------------


def test_ledger_contribution_visible_immediately_after_recording() -> None:
    """
    Scenario 4 — Ledger Immediate Visibility
    Setup:   Empty ledger for a new contributor_id
    Action:  record_contribution(contributor_id='carol', type='question', amount_cc=3.0)
    Expected: get_contributor_history('carol') returns 1 record with type='question'
    Edge:    recording same type twice shows both records (ledger is append-only)
    """
    from app.services import contribution_ledger_service

    contributor_id = f"carol-{uuid4().hex[:8]}"

    # Empty before
    history = contribution_ledger_service.get_contributor_history(contributor_id)
    assert history == []

    # Record a question contribution
    result = contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="question",
        amount_cc=3.0,
        idea_id=None,
        metadata={"source": "community_forum"},
    )

    # Must be immediately visible
    history = contribution_ledger_service.get_contributor_history(contributor_id)
    assert len(history) == 1
    assert history[0]["id"] == result["id"]
    assert history[0]["contribution_type"] == "question"
    assert history[0]["amount_cc"] == 3.0

    # Record again (ledger is append-only, both records must exist)
    contribution_ledger_service.record_contribution(
        contributor_id=contributor_id,
        contribution_type="question",
        amount_cc=3.0,
        idea_id=None,
        metadata={"source": "community_forum_round2"},
    )
    history2 = contribution_ledger_service.get_contributor_history(contributor_id)
    assert len(history2) == 2  # both records present, no deduplication


# ---------------------------------------------------------------------------
# Scenario 5: Community-visible list of all contributions (paginated)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contributions_list_endpoint_shows_all_contributions() -> None:
    """
    Scenario 5 — Community Visibility
    Setup:   Two contributors each record one contribution
    Action:  GET /api/contributions
    Expected: Response contains both contributions, total >= 2
    Edge:    limit/offset pagination parameters respected
    """
    contributor_a_id = uuid4()
    contributor_b_id = uuid4()
    node_a = _create_contributor_node(contributor_a_id, "Community Alice")
    node_b = _create_contributor_node(contributor_b_id, "Community Bob")

    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    _add_contribution_edge(node_a, contributor_a_id, cost="10.00", score=0.7,
                           days_ago=2, contribution_type="spec", fixed_now=fixed_now)
    _add_contribution_edge(node_b, contributor_b_id, cost="5.00", score=0.6,
                           days_ago=3, contribution_type="review", fixed_now=fixed_now)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/contributions?limit=100&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
    assert payload["total"] >= 2

    contributor_ids_seen = {item["contributor_id"] for item in payload["items"]}
    assert str(contributor_a_id) in contributor_ids_seen
    assert str(contributor_b_id) in contributor_ids_seen

    # Edge: offset=0 limit=1 returns exactly 1 item
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        paginated = await client.get("/api/contributions?limit=1&offset=0")
    assert paginated.status_code == 200
    paginated_payload = paginated.json()
    assert len(paginated_payload["items"]) == 1
    assert paginated_payload["total"] >= 2  # total is the full count


# ---------------------------------------------------------------------------
# Scenario 6: Missing contributor returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognition_snapshot_returns_404_for_nonexistent_contributor() -> None:
    """
    Scenario 6 — Missing Contributor Edge Case
    Setup:   No contributor with the given UUID exists
    Action:  GET /api/contributors/{random_uuid}/recognition
    Expected: HTTP 404 with detail='Contributor not found'
    Edge:    Must not return 500 — missing data should be a clean 404
    """
    random_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{random_id}/recognition")

    assert response.status_code == 404
    body = response.json()
    assert body.get("detail") == "Contributor not found"


# ---------------------------------------------------------------------------
# Scenario 7: Contributor with no contributions shows zero metrics (clean slate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_contributions_shows_clean_slate_not_error() -> None:
    """
    Scenario 7 — Clean Slate Visibility
    Setup:   Contributor exists in the graph but has no contribution edges
    Action:  GET /api/contributors/{id}/recognition
    Expected: HTTP 200 with all numeric fields at zero — visible 'clean slate'
    Proof:   New contributors can see themselves in the system immediately on join
    """
    contributor_id = uuid4()
    _create_contributor_node(contributor_id, "Brand New User")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Brand New User"
    assert payload["total_contributions"] == 0
    assert Decimal(str(payload["total_cost"])) == Decimal("0")
    assert payload["average_coherence_score"] == 0.0
    assert payload["current_window_contributions"] == 0
    assert payload["prior_window_contributions"] == 0
    assert payload["delta_contributions"] == 0


# ---------------------------------------------------------------------------
# Scenario 8: Decline detection — negative delta is visible (not hidden)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_negative_delta_visible_when_activity_is_declining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario 8 — Decline Detection
    Setup:   3 contributions in prior window, 1 in current window
    Action:  GET /api/contributors/{id}/recognition
    Expected: delta_contributions == -2 (visible decline, not hidden or clipped to 0)
    Proof:   Declining contributors need honest feedback, not false positivity
    """
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = _create_contributor_node(contributor_id, "Declining User")

    # 3 prior-window contributions
    for days_ago in [35, 45, 55]:
        _add_contribution_edge(
            contributor_node_id, contributor_id,
            cost="10.00", score=0.7, days_ago=days_ago,
            contribution_type="code", fixed_now=fixed_now,
        )
    # 1 current-window contribution
    _add_contribution_edge(
        contributor_node_id, contributor_id,
        cost="5.00", score=0.5, days_ago=5,
        contribution_type="review", fixed_now=fixed_now,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_window_contributions"] == 1
    assert payload["prior_window_contributions"] == 3
    assert payload["delta_contributions"] == -2  # decline is visible


# ---------------------------------------------------------------------------
# Scenario 9: Ledger balance aggregates all contribution types into grand total
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_balance_endpoint_shows_per_type_and_grand_total() -> None:
    """
    Scenario 9 — Ledger Balance Visibility via API
    Setup:   Contributor records question (2 CC), spec (5 CC), review (3 CC)
    Action:  GET /api/contributions/ledger/{contributor_id}
    Expected: balance.totals_by_type has question=2, spec=5, review=3; grand_total=10
    Edge:    GET with unknown contributor_id returns empty totals, not 404
    """
    from app.services import contribution_ledger_service

    contributor_id = f"dave-{uuid4().hex[:8]}"
    contribution_ledger_service.record_contribution(contributor_id, "question", 2.0)
    contribution_ledger_service.record_contribution(contributor_id, "spec", 5.0)
    contribution_ledger_service.record_contribution(contributor_id, "review", 3.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributions/ledger/{contributor_id}")

    assert response.status_code == 200
    payload = response.json()
    assert "balance" in payload
    balance = payload["balance"]
    assert balance["totals_by_type"]["question"] == pytest.approx(2.0)
    assert balance["totals_by_type"]["spec"] == pytest.approx(5.0)
    assert balance["totals_by_type"]["review"] == pytest.approx(3.0)
    assert balance["grand_total"] == pytest.approx(10.0)

    # Edge: unknown contributor returns empty (not 404)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        empty_response = await client.get(f"/api/contributions/ledger/unknown-{uuid4().hex[:8]}")
    assert empty_response.status_code == 200
    empty_balance = empty_response.json()["balance"]
    assert empty_balance["grand_total"] == 0.0
    assert empty_balance["totals_by_type"] == {}


# ---------------------------------------------------------------------------
# Scenario 10: Contributor contributions endpoint lists their work by ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contributor_contributions_endpoint_lists_their_work() -> None:
    """
    Scenario 10 — Per-Contributor Contribution Listing
    Setup:   Contributor has 2 contributions; another contributor has 1
    Action:  GET /api/contributors/{id}/contributions
    Expected: Returns only that contributor's contributions (not others')
    Edge:    GET for nonexistent contributor returns 404
    """
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)

    contributor_a_id = uuid4()
    contributor_b_id = uuid4()
    node_a = _create_contributor_node(contributor_a_id, "Listing Alice")
    node_b = _create_contributor_node(contributor_b_id, "Listing Bob")

    _add_contribution_edge(node_a, contributor_a_id, cost="10.00", score=0.7,
                           days_ago=2, contribution_type="spec", fixed_now=fixed_now)
    _add_contribution_edge(node_a, contributor_a_id, cost="5.00", score=0.8,
                           days_ago=5, contribution_type="question", fixed_now=fixed_now)
    _add_contribution_edge(node_b, contributor_b_id, cost="7.00", score=0.6,
                           days_ago=3, contribution_type="review", fixed_now=fixed_now)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_a_id}/contributions")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    for item in items:
        assert item["contributor_id"] == str(contributor_a_id)

    # Edge: nonexistent contributor -> 404
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get(f"/api/contributors/{uuid4()}/contributions")
    assert missing.status_code == 404
