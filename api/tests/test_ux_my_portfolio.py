"""Minimal tests for the my-portfolio UX flow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any
import unittest.mock as mock
import uuid

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MY_PORTFOLIO_PAGE = REPO_ROOT / "web" / "app" / "my-portfolio" / "page.tsx"
CONTRIBUTOR_PORTFOLIO_PAGE = (
    REPO_ROOT / "web" / "app" / "contributors" / "[id]" / "portfolio" / "page.tsx"
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_contributor_node(
    contributor_id: str = "alice",
    name: str = "Alice",
    github: str | None = "alice-gh",
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    if github:
        properties["github_handle"] = github
    return {
        "id": f"contributor:{contributor_id}",
        "legacy_id": contributor_id,
        "name": name,
        "properties": properties,
    }


def _make_contribution(
    *,
    contributor_id: str,
    contributor_name: str = "Alice",
    idea_id: str,
    amount: float,
    contribution_type: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "id": f"{contributor_id}-{idea_id}-{contribution_type}",
        "properties": {
            "contributor_id": contributor_id,
            "contributor_name": contributor_name,
            "idea_id": idea_id,
            "cost_amount": amount,
            "contribution_type": contribution_type,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


@pytest.fixture
def tmp_path() -> Path:
    path = REPO_ROOT / ".task-pytest-fixtures" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_service_caches_between_tests() -> None:
    yield


def test_my_portfolio_page_routes_to_contributor_portfolio() -> None:
    content = _read_text(MY_PORTFOLIO_PAGE)

    assert MY_PORTFOLIO_PAGE.is_file()
    assert '"use client"' in content or "'use client'" in content
    assert "router.push" in content
    assert "/contributors/${encodeURIComponent(id)}/portfolio" in content
    assert "View Portfolio" in content


def test_contributor_portfolio_page_wires_core_sections_and_requests() -> None:
    content = _read_text(CONTRIBUTOR_PORTFOLIO_PAGE)

    assert CONTRIBUTOR_PORTFOLIO_PAGE.is_file()
    assert '"use client"' in content or "'use client'" in content
    assert "/portfolio" in content
    assert "/cc-history" in content
    assert "/idea-contributions" in content
    assert "/stakes" in content
    assert "/tasks" in content
    assert "CC Balance" in content
    assert "Ideas I Contributed To" in content
    assert "Ideas I Staked On" in content
    assert "Tasks I Completed" in content
    assert "/my-portfolio" in content


def test_portfolio_summary_model_accepts_core_fields() -> None:
    from app.models.portfolio import ContributorSummary, LinkedIdentity, PortfolioSummary

    summary = PortfolioSummary(
        contributor=ContributorSummary(
            id="alice",
            display_name="Alice",
            identities=[LinkedIdentity(type="github", handle="alice-gh", verified=True)],
        ),
        cc_balance=12.5,
        cc_network_pct=5.0,
        idea_contribution_count=2,
        task_completion_count=3,
    )

    assert summary.contributor.id == "alice"
    assert summary.contributor.identities[0].handle == "alice-gh"
    assert summary.cc_balance == 12.5
    assert summary.idea_contribution_count == 2
    assert summary.task_completion_count == 3


def test_portfolio_summary_model_defaults_optional_fields() -> None:
    from app.models.portfolio import ContributorSummary, PortfolioSummary

    summary = PortfolioSummary(
        contributor=ContributorSummary(id="unknown", display_name="Unknown", identities=[]),
    )

    assert summary.cc_balance is None
    assert summary.cc_network_pct is None
    assert summary.recent_activity is None
    assert summary.stake_count == 0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_aggregates_core_counts(
    mock_graph_service: mock.MagicMock,
) -> None:
    from app.services import portfolio_service

    contributor = _make_contributor_node()
    earlier = "2026-03-20T10:00:00+00:00"
    later = "2026-03-25T15:30:00+00:00"
    contributions = [
        _make_contribution(
            contributor_id="alice",
            idea_id="idea-1",
            amount=5.0,
            contribution_type="code",
            timestamp=earlier,
        ),
        _make_contribution(
            contributor_id="alice",
            idea_id="idea-2",
            amount=3.0,
            contribution_type="spec",
            timestamp=later,
        ),
        _make_contribution(
            contributor_id="alice",
            idea_id="idea-1",
            amount=2.0,
            contribution_type="task",
            timestamp=later,
        ),
    ]

    def list_nodes(type: str, limit: int = 100) -> dict[str, Any]:
        if type == "contribution":
            return {"items": contributions, "total": len(contributions)}
        if type == "contributor":
            return {"items": [contributor], "total": 1}
        return {"items": [], "total": 0}

    mock_graph_service.get_node.return_value = contributor
    mock_graph_service.list_nodes.side_effect = list_nodes

    summary = portfolio_service.get_portfolio_summary("alice")

    assert summary.contributor.id == "alice"
    assert summary.contributor.display_name == "Alice"
    assert [identity.handle for identity in summary.contributor.identities] == ["alice-gh"]
    assert summary.cc_balance == 10.0
    assert summary.idea_contribution_count == 2
    assert summary.task_completion_count == 2
    assert summary.recent_activity == datetime.fromisoformat(later)


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_can_skip_cc_balance(
    mock_graph_service: mock.MagicMock,
) -> None:
    from app.services import portfolio_service

    contributor = _make_contributor_node(github=None)
    contribution = _make_contribution(
        contributor_id="alice",
        idea_id="idea-1",
        amount=5.0,
        contribution_type="spec",
        timestamp="2026-03-20T10:00:00+00:00",
    )

    def list_nodes(type: str, limit: int = 100) -> dict[str, Any]:
        if type == "contribution":
            return {"items": [contribution], "total": 1}
        if type == "contributor":
            return {"items": [contributor], "total": 1}
        return {"items": [], "total": 0}

    mock_graph_service.get_node.return_value = contributor
    mock_graph_service.list_nodes.side_effect = list_nodes

    summary = portfolio_service.get_portfolio_summary("alice", include_cc=False)

    assert summary.cc_balance is None
    assert summary.cc_network_pct is None
    assert summary.idea_contribution_count == 1
    assert summary.task_completion_count == 0


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_portfolio_summary_rejects_unknown_contributor(
    mock_graph_service: mock.MagicMock,
) -> None:
    from app.services import portfolio_service

    mock_graph_service.get_node.return_value = None
    mock_graph_service.list_nodes.return_value = {"items": [], "total": 0}

    with pytest.raises(ValueError, match="Contributor not found"):
        portfolio_service.get_portfolio_summary("missing-user")


@mock.patch("app.services.portfolio_service.graph_service")
def test_get_cc_balance_rejects_unknown_contributor(
    mock_graph_service: mock.MagicMock,
) -> None:
    from app.services import portfolio_service

    mock_graph_service.get_node.return_value = None
    mock_graph_service.list_nodes.return_value = {"items": [], "total": 0}

    with pytest.raises(ValueError, match="Contributor not found"):
        portfolio_service.get_cc_balance("missing-user")
