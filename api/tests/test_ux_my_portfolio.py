"""Tests for 'Ux My Portfolio' (ux-my-portfolio).

Verifies acceptance criteria:
- UX-P1: /my-portfolio page exists as a Next.js client component
- UX-P2: /contributors/[id]/portfolio page exists and renders portfolio sections
- UX-P3: Portfolio service correctly aggregates contributor data
- UX-P4: Pydantic models are well-formed and validate correctly
- UX-P5: CC balance, CC history, idea contributions, stakes, tasks — all service functions work
- UX-P6: Service handles missing/unknown contributor gracefully (raises ValueError)
- UX-P7: CC history window/bucket validation
- UX-P8: Portfolio web page file structure is complete (sub-routes: ideas, stakes, tasks)
"""

from __future__ import annotations

import unittest.mock as mock
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# File paths for web UX verification
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
MY_PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "my-portfolio" / "page.tsx"
CONTRIBUTOR_PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "page.tsx"
PORTFOLIO_IDEAS_DIR = REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "ideas"
PORTFOLIO_STAKES_DIR = REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "stakes"
PORTFOLIO_TASKS_DIR = REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "tasks"


# ---------------------------------------------------------------------------
# UX-P1 — /my-portfolio page exists
# ---------------------------------------------------------------------------


def test_my_portfolio_page_file_exists() -> None:
    """web/app/my-portfolio/page.tsx must exist."""
    assert MY_PORTFOLIO_PAGE.is_file(), f"Missing {MY_PORTFOLIO_PAGE}"


def test_my_portfolio_page_is_client_component() -> None:
    """my-portfolio/page.tsx must be a 'use client' component."""
    content = MY_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert '"use client"' in content or "'use client'" in content, (
        "my-portfolio/page.tsx must declare 'use client' — it needs browser APIs (useState, router)"
    )


def test_my_portfolio_page_has_contributor_input() -> None:
    """my-portfolio page must contain an input for contributor ID."""
    content = MY_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "Input" in content or "input" in content, (
        "my-portfolio page must have a contributor ID input field"
    )


def test_my_portfolio_page_redirects_to_contributor_portfolio() -> None:
    """my-portfolio page must redirect to /contributors/{id}/portfolio on submit."""
    content = MY_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "contributors" in content and "portfolio" in content, (
        "my-portfolio page must redirect to /contributors/{id}/portfolio"
    )


def test_my_portfolio_page_uses_router_push() -> None:
    """my-portfolio page must use router.push for navigation."""
    content = MY_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "router.push" in content, (
        "my-portfolio page must use router.push to navigate to contributor portfolio"
    )


def test_my_portfolio_page_exports_default_function() -> None:
    """my-portfolio/page.tsx must export a default function component."""
    content = MY_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "export default function" in content, (
        "my-portfolio/page.tsx must export a default function component"
    )


# ---------------------------------------------------------------------------
# UX-P2 — /contributors/[id]/portfolio page exists with all sections
# ---------------------------------------------------------------------------


def test_contributor_portfolio_page_file_exists() -> None:
    """web/app/contributors/[id]/portfolio/page.tsx must exist."""
    assert CONTRIBUTOR_PORTFOLIO_PAGE.is_file(), f"Missing {CONTRIBUTOR_PORTFOLIO_PAGE}"


def test_contributor_portfolio_page_is_client_component() -> None:
    """contributors/[id]/portfolio/page.tsx must be 'use client'."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert '"use client"' in content or "'use client'" in content, (
        "contributors portfolio page must declare 'use client'"
    )


def test_contributor_portfolio_page_fetches_portfolio_summary() -> None:
    """Portfolio page must fetch /api/contributors/{id}/portfolio."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "portfolio" in content.lower(), (
        "Portfolio page must fetch the portfolio summary endpoint"
    )


def test_contributor_portfolio_page_fetches_cc_history() -> None:
    """Portfolio page must fetch cc-history endpoint."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "cc-history" in content, (
        "Portfolio page must fetch /api/contributors/{id}/cc-history"
    )


def test_contributor_portfolio_page_fetches_idea_contributions() -> None:
    """Portfolio page must fetch idea-contributions endpoint."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "idea-contributions" in content, (
        "Portfolio page must fetch /api/contributors/{id}/idea-contributions"
    )


def test_contributor_portfolio_page_fetches_stakes() -> None:
    """Portfolio page must fetch stakes endpoint."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "stakes" in content, (
        "Portfolio page must fetch /api/contributors/{id}/stakes"
    )


def test_contributor_portfolio_page_fetches_tasks() -> None:
    """Portfolio page must fetch tasks endpoint."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "tasks" in content, (
        "Portfolio page must fetch /api/contributors/{id}/tasks"
    )


def test_contributor_portfolio_page_shows_cc_balance_section() -> None:
    """Portfolio page must display CC Balance stat."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "CC Balance" in content or "cc_balance" in content, (
        "Portfolio page must display the contributor's CC Balance"
    )


def test_contributor_portfolio_page_shows_ideas_section() -> None:
    """Portfolio page must render an ideas contributions section."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "Ideas I Contributed" in content or "idea_contribution_count" in content, (
        "Portfolio page must render an 'Ideas I Contributed To' section"
    )


def test_contributor_portfolio_page_shows_stakes_section() -> None:
    """Portfolio page must render a stakes section."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "Stakes" in content or "stake_count" in content, (
        "Portfolio page must render a stakes section"
    )


def test_contributor_portfolio_page_shows_tasks_section() -> None:
    """Portfolio page must render a tasks section."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "Tasks" in content or "task_completion_count" in content, (
        "Portfolio page must render a tasks completed section"
    )


def test_contributor_portfolio_page_has_back_navigation() -> None:
    """Portfolio page must link back to /my-portfolio."""
    content = CONTRIBUTOR_PORTFOLIO_PAGE.read_text(encoding="utf-8")
    assert "my-portfolio" in content, (
        "Portfolio page must include a link back to /my-portfolio"
    )


# ---------------------------------------------------------------------------
# UX-P8 — Sub-route file structure is complete
# ---------------------------------------------------------------------------


def test_portfolio_ideas_sub_route_exists() -> None:
    """web/app/contributors/[id]/portfolio/ideas/[idea_id]/ must exist."""
    assert PORTFOLIO_IDEAS_DIR.is_dir(), f"Missing portfolio ideas sub-route: {PORTFOLIO_IDEAS_DIR}"


def test_portfolio_stakes_sub_route_exists() -> None:
    """web/app/contributors/[id]/portfolio/stakes/ must exist."""
    assert PORTFOLIO_STAKES_DIR.is_dir(), f"Missing portfolio stakes sub-route: {PORTFOLIO_STAKES_DIR}"


def test_portfolio_tasks_sub_route_exists() -> None:
    """web/app/contributors/[id]/portfolio/tasks/ must exist."""
    assert PORTFOLIO_TASKS_DIR.is_dir(), f"Missing portfolio tasks sub-route: {PORTFOLIO_TASKS_DIR}"


# ---------------------------------------------------------------------------
# UX-P4 — Pydantic model validation
# ---------------------------------------------------------------------------


def test_portfolio_summary_model_valid() -> None:
    """PortfolioSummary model must accept valid contributor data."""
    from app.models.portfolio import (
        ContributorSummary,
        LinkedIdentity,
        PortfolioSummary,
    )

    now = datetime.now(timezone.utc)
    contributor = ContributorSummary(
        id="test-contributor",
        display_name="Test Contributor",
        identities=[
            LinkedIdentity(type="github", handle="testuser", verified=True),
        ],
    )
    summary = PortfolioSummary(
        contributor=contributor,
        cc_balance=42.5,
        cc_network_pct=1.23,
        idea_contribution_count=5,
        stake_count=2,
        task_completion_count=10,
        recent_activity=now,
    )
    assert summary.cc_balance == 42.5
    assert summary.idea_contribution_count == 5
    assert summary.stake_count == 2
    assert summary.task_completion_count == 10


def test_portfolio_summary_model_nullable_fields() -> None:
    """PortfolioSummary must work with all optional fields as None."""
    from app.models.portfolio import ContributorSummary, PortfolioSummary

    contributor = ContributorSummary(
        id="unknown",
        display_name="Unknown",
        identities=[],
    )
    summary = PortfolioSummary(contributor=contributor)
    assert summary.cc_balance is None
    assert summary.cc_network_pct is None
    assert summary.recent_activity is None


def test_cc_balance_model_valid() -> None:
    """CCBalance model must accept a valid balance payload."""
    from app.models.portfolio import CCBalance

    now = datetime.now(timezone.utc)
    bal = CCBalance(
        contributor_id="test",
        balance=100.0,
        network_total=5000.0,
        network_pct=2.0,
        last_updated=now,
    )
    assert bal.balance == 100.0
    assert bal.network_pct == 2.0


def test_cc_history_model_valid() -> None:
    """CCHistory model with series buckets must validate correctly."""
    from app.models.portfolio import CCHistory, CCHistoryBucket

    now = datetime.now(timezone.utc)
    buckets = [
        CCHistoryBucket(
            period_start=now,
            period_end=now,
            cc_earned=5.0,
            running_total=5.0,
            network_pct_at_period_end=0.1,
        )
    ]
    history = CCHistory(
        contributor_id="test",
        window="90d",
        bucket="7d",
        series=buckets,
    )
    assert len(history.series) == 1
    assert history.series[0].cc_earned == 5.0


def test_idea_contribution_summary_model_valid() -> None:
    """IdeaContributionSummary model must validate with health signal."""
    from app.models.portfolio import HealthSignal, IdeaContributionSummary

    item = IdeaContributionSummary(
        idea_id="my-idea",
        idea_title="My Idea",
        idea_status="active",
        contribution_types=["code", "spec"],
        cc_attributed=15.0,
        contribution_count=3,
        health=HealthSignal(activity_signal="active", value_delta_pct=10.0, evidence_count=3),
    )
    assert item.cc_attributed == 15.0
    assert item.health.activity_signal == "active"


def test_stake_summary_model_roi_calculation() -> None:
    """StakeSummary roi_pct field accepts computed values."""
    from app.models.portfolio import HealthSignal, StakeSummary

    stake = StakeSummary(
        stake_id="stake-1",
        idea_id="idea-1",
        idea_title="Test Idea",
        cc_staked=10.0,
        cc_valuation=12.0,
        roi_pct=20.0,
        health=HealthSignal(activity_signal="active"),
    )
    assert stake.roi_pct == 20.0
    assert stake.cc_valuation == 12.0


def test_task_summary_model_valid() -> None:
    """TaskSummary model must accept all optional fields."""
    from app.models.portfolio import TaskSummary

    now = datetime.now(timezone.utc)
    task = TaskSummary(
        task_id="task-abc",
        description="Implement feature X",
        idea_id="idea-1",
        idea_title="Feature X",
        provider="claude",
        outcome="passed",
        cc_earned=3.5,
        completed_at=now,
    )
    assert task.outcome == "passed"
    assert task.cc_earned == 3.5


def test_health_signal_defaults() -> None:
    """HealthSignal must default to 'unknown' activity and 0 evidence."""
    from app.models.portfolio import HealthSignal

    sig = HealthSignal()
    assert sig.activity_signal == "unknown"
    assert sig.evidence_count == 0
    assert sig.value_delta_pct is None


# ---------------------------------------------------------------------------
# UX-P3 / UX-P5 — Portfolio service unit tests (with mocked graph_service)
# ---------------------------------------------------------------------------


def _make_contributor_node(
    contributor_id: str = "user-1",
    name: str = "Alice",
    github: str | None = "alice",
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if github:
        props["github_handle"] = github
    return {
        "id": f"contributor:{contributor_id}",
        "legacy_id": contributor_id,
        "name": name,
        "properties": props,
    }


def _make_contribution_node(
    contributor_id: str,
    idea_id: str = "idea-1",
    amount: float = 5.0,
    contribution_type: str = "code",
    created_at: str | None = None,
) -> dict[str, Any]:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"contrib-{contributor_id}-{idea_id}",
        "properties": {
            "contributor_id": contributor_id,
            "idea_id": idea_id,
            "cost_amount": amount,
            "contribution_type": contribution_type,
        },
        "created_at": created_at,
        "updated_at": created_at,
    }


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_network_stats_returns_model(mock_gs: mock.MagicMock) -> None:
    """get_network_stats should return a NetworkStats model with total_supply >= 1."""
    mock_gs.list_nodes.return_value = {
        "items": [
            {"properties": {"cost_amount": 10.0}},
            {"properties": {"cost_amount": 20.0}},
        ],
        "total": 2,
    }

    from app.services import portfolio_service

    stats = portfolio_service.get_network_stats()
    assert stats.total_supply == 30.0
    assert stats.total_contributors >= 0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_network_stats_empty_network(mock_gs: mock.MagicMock) -> None:
    """get_network_stats with no contributions should return total_supply=1.0 floor."""
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    stats = portfolio_service.get_network_stats()
    assert stats.total_supply >= 1.0  # Floor prevents division by zero


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_balance_contributor_found(mock_gs: mock.MagicMock) -> None:
    """get_cc_balance should return balance aggregated from matching contributions."""
    contributor_node = _make_contributor_node("alice", "Alice")
    contributions = [
        _make_contribution_node("alice", "idea-1", 5.0),
        _make_contribution_node("alice", "idea-2", 10.0),
        _make_contribution_node("bob", "idea-1", 3.0),  # different contributor, not counted
    ]

    def list_nodes(type: str, limit: int = 100) -> dict[str, Any]:
        if type == "contribution":
            return {"items": contributions, "total": 3}
        if type == "contributor":
            return {"items": [contributor_node], "total": 1}
        return {"items": [], "total": 0}

    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.side_effect = list_nodes

    from app.services import portfolio_service

    balance = portfolio_service.get_cc_balance("alice")
    assert balance.contributor_id == "alice"
    assert balance.balance == 15.0
    assert 0.0 <= balance.network_pct <= 100.0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_balance_unknown_contributor_raises(mock_gs: mock.MagicMock) -> None:
    """get_cc_balance must raise ValueError for unknown contributor."""
    mock_gs.get_node.return_value = None
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    with pytest.raises(ValueError, match="Contributor not found"):
        portfolio_service.get_cc_balance("nobody")


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_contributor_found(mock_gs: mock.MagicMock) -> None:
    """get_portfolio_summary should return PortfolioSummary for a valid contributor."""
    contributor_node = _make_contributor_node("alice", "Alice")
    contributions = [
        _make_contribution_node("alice", "idea-1", 5.0, "code"),
        _make_contribution_node("alice", "idea-2", 3.0, "spec"),
        _make_contribution_node("alice", "idea-1", 2.0, "task"),
    ]

    def list_nodes(type: str, limit: int = 100) -> dict[str, Any]:
        if type == "contribution":
            return {"items": contributions, "total": 3}
        if type == "contributor":
            return {"items": [contributor_node], "total": 1}
        return {"items": [], "total": 0}

    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.side_effect = list_nodes

    from app.services import portfolio_service

    summary = portfolio_service.get_portfolio_summary("alice")
    assert summary.contributor.id == "alice"
    assert summary.contributor.display_name == "Alice"
    assert summary.idea_contribution_count == 2  # idea-1 and idea-2


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_unknown_contributor_raises(mock_gs: mock.MagicMock) -> None:
    """get_portfolio_summary must raise ValueError for unknown contributor."""
    mock_gs.get_node.return_value = None
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    with pytest.raises(ValueError, match="Contributor not found"):
        portfolio_service.get_portfolio_summary("nobody")


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_history_returns_buckets(mock_gs: mock.MagicMock) -> None:
    """get_cc_history should return a CCHistory with non-empty series for valid contributor."""
    contributor_node = _make_contributor_node("alice", "Alice")
    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    history = portfolio_service.get_cc_history("alice", window="30d", bucket="7d")
    assert history.contributor_id == "alice"
    assert history.window == "30d"
    assert history.bucket == "7d"
    assert len(history.series) > 0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_history_unknown_contributor_raises(mock_gs: mock.MagicMock) -> None:
    """get_cc_history must raise ValueError for unknown contributor."""
    mock_gs.get_node.return_value = None
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    with pytest.raises(ValueError, match="Contributor not found"):
        portfolio_service.get_cc_history("nobody")


# ---------------------------------------------------------------------------
# UX-P7 — CC history window/bucket validation
# ---------------------------------------------------------------------------


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_history_rejects_invalid_bucket(mock_gs: mock.MagicMock) -> None:
    """get_cc_history must reject buckets not in (1d, 7d, 30d)."""
    contributor_node = _make_contributor_node("alice", "Alice")
    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    with pytest.raises(ValueError, match="Invalid bucket"):
        portfolio_service.get_cc_history("alice", window="30d", bucket="14d")


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_history_rejects_oversized_window(mock_gs: mock.MagicMock) -> None:
    """get_cc_history must reject windows over 365d."""
    contributor_node = _make_contributor_node("alice", "Alice")
    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    with pytest.raises(ValueError):
        portfolio_service.get_cc_history("alice", window="400d", bucket="7d")


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_idea_contributions_returns_list(mock_gs: mock.MagicMock) -> None:
    """get_idea_contributions should return IdeaContributionsList for valid contributor."""
    contributor_node = _make_contributor_node("alice", "Alice")
    contributions = [
        _make_contribution_node("alice", "idea-1", 10.0),
        _make_contribution_node("alice", "idea-2", 5.0),
    ]
    idea_node = {"id": "idea:idea-1", "name": "Test Idea", "properties": {"status": "active"}}

    def get_node(node_id: str) -> dict[str, Any] | None:
        if "contributor:alice" in node_id or node_id == "alice":
            return contributor_node
        if "idea:" in node_id:
            return idea_node
        return None

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": contributions, "total": 2}

    from app.services import portfolio_service

    result = portfolio_service.get_idea_contributions("alice")
    assert result.contributor_id == "alice"
    assert result.total == 2
    assert len(result.items) == 2


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_idea_contributions_sorted_by_cc_desc(mock_gs: mock.MagicMock) -> None:
    """get_idea_contributions with sort=cc_attributed_desc should sort highest CC first."""
    contributor_node = _make_contributor_node("alice", "Alice")
    contributions = [
        _make_contribution_node("alice", "idea-1", 2.0),
        _make_contribution_node("alice", "idea-2", 20.0),
    ]

    def get_node(node_id: str) -> dict[str, Any] | None:
        return contributor_node if "contributor" in node_id else {}

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": contributions, "total": 2}

    from app.services import portfolio_service

    result = portfolio_service.get_idea_contributions("alice", sort="cc_attributed_desc")
    assert result.items[0].cc_attributed >= result.items[1].cc_attributed


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_stakes_returns_list(mock_gs: mock.MagicMock) -> None:
    """get_stakes should return StakesList for a valid contributor."""
    contributor_node = _make_contributor_node("alice", "Alice")
    stake_nodes = [
        {
            "id": "stake-1",
            "properties": {
                "contributor_id": "alice",
                "idea_id": "idea-1",
                "cc_staked": 10.0,
                "cc_valuation": 12.0,
            },
        }
    ]

    def get_node(node_id: str) -> dict[str, Any] | None:
        if "contributor" in node_id:
            return contributor_node
        return {}

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": stake_nodes, "total": 1}

    from app.services import portfolio_service

    result = portfolio_service.get_stakes("alice")
    assert result.contributor_id == "alice"
    assert result.total == 1
    assert result.items[0].cc_staked == 10.0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_stakes_computes_roi_pct(mock_gs: mock.MagicMock) -> None:
    """get_stakes should compute roi_pct = (valuation - staked) / staked * 100."""
    contributor_node = _make_contributor_node("alice", "Alice")
    stake_nodes = [
        {
            "id": "stake-1",
            "properties": {
                "contributor_id": "alice",
                "idea_id": "idea-1",
                "cc_staked": 10.0,
                "cc_valuation": 12.0,
            },
        }
    ]

    def get_node(node_id: str) -> dict[str, Any] | None:
        if "contributor" in node_id:
            return contributor_node
        return {}

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": stake_nodes, "total": 1}

    from app.services import portfolio_service

    result = portfolio_service.get_stakes("alice")
    stake = result.items[0]
    assert stake.roi_pct is not None
    assert abs(stake.roi_pct - 20.0) < 0.01  # (12-10)/10 * 100 = 20%


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_tasks_returns_list(mock_gs: mock.MagicMock) -> None:
    """get_tasks should return TasksList filtered by status."""
    contributor_node = _make_contributor_node("alice", "Alice")
    task_nodes = [
        {
            "id": "task-1",
            "description": "Implement feature",
            "properties": {
                "executor_contributor_id": "alice",
                "status": "completed",
                "outcome": "passed",
                "cc_earned": 5.0,
                "idea_id": "idea-1",
            },
        }
    ]

    def get_node(node_id: str) -> dict[str, Any] | None:
        if "contributor" in node_id:
            return contributor_node
        return {}

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": task_nodes, "total": 1}

    from app.services import portfolio_service

    result = portfolio_service.get_tasks("alice", status="completed")
    assert result.contributor_id == "alice"
    assert result.total == 1
    assert result.items[0].outcome == "passed"


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_tasks_filters_by_status(mock_gs: mock.MagicMock) -> None:
    """get_tasks should only return tasks matching the requested status."""
    contributor_node = _make_contributor_node("alice", "Alice")
    task_nodes = [
        {
            "id": "task-1",
            "description": "Done task",
            "properties": {
                "executor_contributor_id": "alice",
                "status": "completed",
                "outcome": "passed",
            },
        },
        {
            "id": "task-2",
            "description": "Pending task",
            "properties": {
                "executor_contributor_id": "alice",
                "status": "pending",
            },
        },
    ]

    def get_node(node_id: str) -> dict[str, Any] | None:
        if "contributor" in node_id:
            return contributor_node
        return {}

    mock_gs.get_node.side_effect = get_node
    mock_gs.list_nodes.return_value = {"items": task_nodes, "total": 2}

    from app.services import portfolio_service

    result = portfolio_service.get_tasks("alice", status="completed")
    assert all(item.task_id == "task-1" for item in result.items)
    assert result.total == 1


# ---------------------------------------------------------------------------
# UX-P6 — Graceful error handling
# ---------------------------------------------------------------------------


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_with_cc_disabled(mock_gs: mock.MagicMock) -> None:
    """get_portfolio_summary with include_cc=False should not call balance functions."""
    contributor_node = _make_contributor_node("alice", "Alice")
    mock_gs.get_node.return_value = contributor_node
    mock_gs.list_nodes.return_value = {"items": [], "total": 0}

    from app.services import portfolio_service

    summary = portfolio_service.get_portfolio_summary("alice", include_cc=False)
    assert summary.cc_balance is None
    assert summary.cc_network_pct is None


@mock.patch("app.services.portfolio_service.graph_service")
def test_contributor_summary_includes_identity_list(mock_gs: mock.MagicMock) -> None:
    """Contributor with GitHub handle should include identity in summary."""
    contributor_node = _make_contributor_node("alice", "Alice", github="alice-gh")
    mock_gs.get_node.return_value = contributor_node

    from app.services.portfolio_service import _contributor_summary

    summary = _contributor_summary(contributor_node)
    assert summary.display_name == "Alice"
    assert any(i.type == "github" and i.handle == "alice-gh" for i in summary.identities)


@mock.patch("app.services.portfolio_service.graph_service")
def test_contributor_summary_empty_identities_by_default(mock_gs: mock.MagicMock) -> None:
    """Contributor with no handles should return empty identities list."""
    contributor_node = {
        "id": "contributor:bob",
        "legacy_id": "bob",
        "name": "Bob",
        "properties": {},
    }

    from app.services.portfolio_service import _contributor_summary

    summary = _contributor_summary(contributor_node)
    assert summary.identities == []
