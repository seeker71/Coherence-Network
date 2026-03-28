"""Comprehensive tests for My Portfolio — personal contributor view.

Covers:
  - Linked identities at top of portfolio
  - CC balance (absolute) and CC % of network
  - CC earning history as time-series chart data
  - Ideas contributed to: status, contribution types, current value
  - Ideas staked on: ROI since staking
  - Tasks completed: provider, outcome
  - Drill-down: idea → contributions → value lineage
  - Authentication / identity-link access pattern
  - Error handling: unknown contributor, bad params, forbidden drilldown
  - Pagination on all list endpoints
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
import unittest.mock as mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service


# ─── helpers ──────────────────────────────────────────────────────────────────


def _uid() -> str:
    """Short random suffix to guarantee uniqueness across test runs."""
    return uuid.uuid4().hex[:8]


def _unique_email(label: str) -> str:
    return f"portfolio-{label}-{_uid()}@coherence.network"


def _make_contributor_node(
    contributor_id: str,
    name: str = "TestUser",
    github: str | None = None,
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
    idea_id: str,
    amount: float,
    contribution_type: str,
    ts: str,
    coherence_score: float = 0.8,
) -> dict[str, Any]:
    cid = f"contrib-{contributor_id[:6]}-{idea_id[:6]}-{contribution_type}-{_uid()}"
    return {
        "id": cid,
        "type": "contribution",
        "name": f"{contribution_type} on {idea_id}",
        "description": "",
        "phase": "water",
        "created_at": ts,
        "updated_at": ts,
        "properties": {
            "contributor_id": contributor_id,
            "idea_id": idea_id,
            "cost_amount": amount,
            "contribution_type": contribution_type,
            "coherence_score": coherence_score,
        },
    }


# ─── 1. Model shape tests (no DB required) ────────────────────────────────────


class TestPortfolioModelShapes:
    def test_portfolio_summary_requires_contributor_block(self) -> None:
        from app.models.portfolio import ContributorSummary, PortfolioSummary

        s = PortfolioSummary(
            contributor=ContributorSummary(id="alice", display_name="Alice", identities=[]),
        )
        assert s.contributor.id == "alice"
        assert s.cc_balance is None
        assert s.stake_count == 0
        assert s.task_completion_count == 0
        assert s.idea_contribution_count == 0

    def test_linked_identity_model_accepts_github_telegram_wallet(self) -> None:
        from app.models.portfolio import LinkedIdentity

        for identity_type in ("github", "telegram", "wallet"):
            li = LinkedIdentity(type=identity_type, handle="test-handle", verified=True)
            assert li.type == identity_type
            assert li.verified is True

    def test_linked_identity_unverified_default(self) -> None:
        from app.models.portfolio import LinkedIdentity

        li = LinkedIdentity(type="github", handle="gh-user", verified=False)
        assert li.verified is False

    def test_cc_history_bucket_model(self) -> None:
        from app.models.portfolio import CCHistoryBucket

        now = datetime.now(timezone.utc)
        b = CCHistoryBucket(
            period_start=now - timedelta(days=7),
            period_end=now,
            cc_earned=3.5,
            running_total=10.0,
            network_pct_at_period_end=0.012345,
        )
        assert b.cc_earned == 3.5
        assert b.running_total == 10.0
        assert b.network_pct_at_period_end == pytest.approx(0.012345)

    def test_cc_history_model_empty_series_allowed(self) -> None:
        from app.models.portfolio import CCHistory

        h = CCHistory(contributor_id="alice", window="90d", bucket="7d")
        assert h.series == []

    def test_stake_summary_roi_optional(self) -> None:
        from app.models.portfolio import StakeSummary

        s = StakeSummary(stake_id="s1", idea_id="i1", idea_title="Idea One", cc_staked=10.0)
        assert s.roi_pct is None
        assert s.cc_valuation is None

    def test_stake_summary_roi_computed_inline(self) -> None:
        from app.models.portfolio import StakeSummary

        s = StakeSummary(
            stake_id="s2",
            idea_id="i2",
            idea_title="Idea Two",
            cc_staked=20.0,
            cc_valuation=26.0,
            roi_pct=30.0,
        )
        assert s.roi_pct == pytest.approx(30.0)

    def test_task_summary_outcome_values(self) -> None:
        from app.models.portfolio import TaskSummary

        for outcome in ("passed", "failed", "partial"):
            t = TaskSummary(
                task_id="t1",
                description="test task",
                provider="openclaw",
                outcome=outcome,
                cc_earned=1.0,
            )
            assert t.outcome == outcome

    def test_idea_contribution_summary_health_defaults(self) -> None:
        from app.models.portfolio import HealthSignal, IdeaContributionSummary

        s = IdeaContributionSummary(idea_id="x", idea_title="X")
        assert s.health.activity_signal == "unknown"
        assert s.health.evidence_count == 0

    def test_value_lineage_summary_defaults(self) -> None:
        from app.models.portfolio import ValueLineageSummary

        v = ValueLineageSummary()
        assert v.total_value == 0.0
        assert v.lineage_id is None
        assert v.roi_ratio is None


# ─── 2. Service unit tests (mocked graph_service) ─────────────────────────────


class TestPortfolioServiceUnit:
    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_portfolio_summary_aggregates_identities(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-alice"
        contributor = _make_contributor_node(cid, name="Alice", github="alice-gh")
        contrib = _make_contribution_node(cid, "idea-x", 5.0, "code", "2026-03-01T10:00:00+00:00")

        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": [contrib], "total": 1} if type == "contribution" else {"items": [], "total": 0}
        )

        summary = portfolio_service.get_portfolio_summary(cid)

        assert summary.contributor.id == cid
        assert summary.contributor.display_name == "Alice"
        assert summary.cc_balance == pytest.approx(5.0)
        assert summary.idea_contribution_count == 1

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_portfolio_summary_counts_unique_ideas(
        self, mock_gs: mock.MagicMock
    ) -> None:
        """Multiple contributions to the same idea count as 1 idea, not 2."""
        from app.services import portfolio_service

        cid = "svc-bob"
        contributor = _make_contributor_node(cid, name="Bob")
        ts = "2026-03-10T12:00:00+00:00"
        contributions = [
            _make_contribution_node(cid, "idea-1", 3.0, "code", ts),
            _make_contribution_node(cid, "idea-1", 2.0, "spec", ts),  # same idea
            _make_contribution_node(cid, "idea-2", 1.0, "task", ts),
        ]

        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": contributions, "total": len(contributions)}
            if type == "contribution"
            else {"items": [], "total": 0}
        )

        summary = portfolio_service.get_portfolio_summary(cid)

        assert summary.idea_contribution_count == 2  # 2 unique ideas
        assert summary.cc_balance == pytest.approx(6.0)  # 3 + 2 + 1

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_portfolio_summary_task_count_includes_code_impl_task_types(
        self, mock_gs: mock.MagicMock
    ) -> None:
        """Contributions with type='task', 'code', or 'impl' count as task completions.
        Spec contributions do NOT count as task completions."""
        from app.services import portfolio_service

        cid = "svc-carol"
        contributor = _make_contributor_node(cid, name="Carol")
        ts = "2026-03-15T09:00:00+00:00"
        contributions = [
            _make_contribution_node(cid, "idea-a", 4.0, "code", ts),   # counts
            _make_contribution_node(cid, "idea-a", 2.0, "task", ts),   # counts
            _make_contribution_node(cid, "idea-b", 1.0, "spec", ts),   # does NOT count
        ]

        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": contributions, "total": len(contributions)}
            if type == "contribution"
            else {"items": [], "total": 0}
        )

        summary = portfolio_service.get_portfolio_summary(cid)

        # code + task = 2 task completions, spec is excluded
        assert summary.task_completion_count == 2

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_portfolio_summary_include_cc_false_omits_balance(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-dave"
        contributor = _make_contributor_node(cid, name="Dave")
        contrib = _make_contribution_node(cid, "idea-y", 7.0, "spec", "2026-03-20T08:00:00+00:00")

        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": [contrib], "total": 1} if type == "contribution" else {"items": [], "total": 0}
        )

        summary = portfolio_service.get_portfolio_summary(cid, include_cc=False)

        assert summary.cc_balance is None
        assert summary.cc_network_pct is None
        # Non-CC counts still populated
        assert summary.idea_contribution_count == 1

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_portfolio_summary_raises_for_unknown_contributor(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        mock_gs.get_node.return_value = None
        mock_gs.list_nodes.return_value = {"items": [], "total": 0}

        with pytest.raises(ValueError, match="Contributor not found"):
            portfolio_service.get_portfolio_summary("no-such-person")

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_cc_balance_raises_for_unknown_contributor(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        mock_gs.get_node.return_value = None
        mock_gs.list_nodes.return_value = {"items": [], "total": 0}

        with pytest.raises(ValueError, match="Contributor not found"):
            portfolio_service.get_cc_balance("ghost")

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_cc_history_rejects_invalid_bucket(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-eve"
        contributor = _make_contributor_node(cid, name="Eve")
        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.return_value = {"items": [], "total": 0}

        with pytest.raises(ValueError, match="[Bb]ucket"):
            portfolio_service.get_cc_history(cid, window="90d", bucket="2d")

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_cc_history_returns_correct_number_of_buckets(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-frank"
        contributor = _make_contributor_node(cid, name="Frank")
        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.return_value = {"items": [], "total": 0}

        hist = portfolio_service.get_cc_history(cid, window="30d", bucket="7d")

        assert hist.window == "30d"
        assert hist.bucket == "7d"
        assert len(hist.series) == 4  # 30 / 7 = ~4 buckets

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_cc_history_running_total_is_cumulative(
        self, mock_gs: mock.MagicMock
    ) -> None:
        """Ensure running_total accumulates across buckets."""
        from app.services import portfolio_service

        cid = "svc-grace"
        contributor = _make_contributor_node(cid, name="Grace")

        now = datetime.now(timezone.utc)
        ts1 = (now - timedelta(days=20)).isoformat()
        ts2 = (now - timedelta(days=6)).isoformat()
        contributions = [
            _make_contribution_node(cid, "idea-z", 4.0, "code", ts1),
            _make_contribution_node(cid, "idea-z", 3.0, "spec", ts2),
        ]

        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": contributions, "total": 2}
            if type == "contribution"
            else {"items": [], "total": 0}
        )

        hist = portfolio_service.get_cc_history(cid, window="30d", bucket="7d")

        totals = [b.running_total for b in hist.series]
        # Running total must be non-decreasing
        for i in range(1, len(totals)):
            assert totals[i] >= totals[i - 1]

        # Final total equals sum of all contributions in window
        assert hist.series[-1].running_total == pytest.approx(7.0)

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_idea_contributions_groups_by_idea(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-henry"
        contributor = _make_contributor_node(cid, name="Henry")
        ts = "2026-03-22T11:00:00+00:00"
        contributions = [
            _make_contribution_node(cid, "idea-alpha", 3.0, "code", ts),
            _make_contribution_node(cid, "idea-alpha", 1.0, "spec", ts),
            _make_contribution_node(cid, "idea-beta", 5.0, "task", ts),
        ]
        idea_alpha = {
            "id": "idea:idea-alpha",
            "name": "Idea Alpha",
            "properties": {"status": "active", "coherence_score": 0.85},
        }
        idea_beta = {
            "id": "idea:idea-beta",
            "name": "Idea Beta",
            "properties": {"status": "completed", "coherence_score": 0.9},
        }

        def get_node(node_id: str) -> dict | None:
            if "idea-alpha" in node_id:
                return idea_alpha
            if "idea-beta" in node_id:
                return idea_beta
            return contributor

        mock_gs.get_node.side_effect = get_node
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": contributions, "total": len(contributions)}
            if type == "contribution"
            else {"items": [], "total": 0}
        )

        result = portfolio_service.get_idea_contributions(cid)

        assert result.total == 2
        ids = {item.idea_id for item in result.items}
        assert "idea-alpha" in ids
        assert "idea-beta" in ids
        alpha_item = next(i for i in result.items if i.idea_id == "idea-alpha")
        assert alpha_item.cc_attributed == pytest.approx(4.0)
        assert set(alpha_item.contribution_types) == {"code", "spec"}

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_idea_contribution_detail_raises_permission_when_no_contributions(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-ivan"
        contributor = _make_contributor_node(cid, name="Ivan")
        mock_gs.get_node.return_value = contributor
        mock_gs.list_nodes.return_value = {"items": [], "total": 0}

        with pytest.raises(PermissionError):
            portfolio_service.get_idea_contribution_detail(cid, "ghost-idea")

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_stakes_computes_roi_pct(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-julia"
        contributor = _make_contributor_node(cid, name="Julia")
        stake_node = {
            "id": "stake-j1",
            "type": "stake",
            "name": "stake on idea-s",
            "description": "",
            "phase": "water",
            "properties": {
                "contributor_id": cid,
                "idea_id": "idea-s",
                "cc_staked": 10.0,
                "cc_valuation": 13.0,
                "staked_at": "2026-01-01T00:00:00+00:00",
            },
        }
        idea_node = {
            "id": "idea:idea-s",
            "name": "Staked Idea",
            "properties": {"status": "active"},
        }

        def get_node(node_id: str) -> dict | None:
            if "idea-s" in node_id:
                return idea_node
            return contributor

        mock_gs.get_node.side_effect = get_node
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": [stake_node], "total": 1}
            if type == "stake"
            else {"items": [], "total": 0}
        )

        result = portfolio_service.get_stakes(cid)

        assert result.total == 1
        assert result.items[0].cc_staked == 10.0
        # ROI = (13 - 10) / 10 * 100 = 30%
        assert result.items[0].roi_pct == pytest.approx(30.0)

    @mock.patch("app.services.portfolio_service.graph_service")
    def test_get_tasks_filters_by_status(
        self, mock_gs: mock.MagicMock
    ) -> None:
        from app.services import portfolio_service

        cid = "svc-kate"
        contributor = _make_contributor_node(cid, name="Kate")
        tasks = [
            {
                "id": "task-k1",
                "type": "task",
                "name": "Completed task",
                "description": "",
                "phase": "water",
                "properties": {
                    "contributor_id": cid,
                    "idea_id": "idea-t",
                    "status": "completed",
                    "provider": "openclaw",
                    "outcome": "passed",
                    "cc_earned": 2.0,
                    "completed_at": "2026-03-25T14:00:00+00:00",
                },
            },
            {
                "id": "task-k2",
                "type": "task",
                "name": "In-progress task",
                "description": "",
                "phase": "water",
                "properties": {
                    "contributor_id": cid,
                    "idea_id": "idea-t",
                    "status": "in_progress",
                    "provider": "cursor",
                    "outcome": None,
                    "cc_earned": 0.0,
                },
            },
        ]
        idea_node = {
            "id": "idea:idea-t",
            "name": "Task Idea",
            "properties": {"status": "active"},
        }

        def get_node(node_id: str) -> dict | None:
            if "idea-t" in node_id:
                return idea_node
            return contributor

        mock_gs.get_node.side_effect = get_node
        mock_gs.list_nodes.side_effect = lambda type, limit=100: (
            {"items": tasks, "total": len(tasks)}
            if type == "task"
            else {"items": [], "total": 0}
        )

        result = portfolio_service.get_tasks(cid, status="completed")

        assert result.total == 1
        assert result.items[0].provider == "openclaw"
        assert result.items[0].outcome == "passed"
        assert result.items[0].cc_earned == pytest.approx(2.0)


# ─── 3. Web page structure tests ──────────────────────────────────────────────


class TestPortfolioWebPages:
    """Verify Next.js page files wire the expected sections and API routes."""

    def _read(self, path: Any) -> str:
        return path.read_text(encoding="utf-8")

    def test_my_portfolio_page_exists_and_is_client_component(self) -> None:
        from pathlib import Path

        page = Path(__file__).resolve().parents[2] / "web" / "app" / "my-portfolio" / "page.tsx"
        assert page.is_file(), f"Missing: {page}"
        content = self._read(page)
        assert '"use client"' in content or "'use client'" in content

    def test_my_portfolio_page_redirects_to_contributor_portfolio(self) -> None:
        from pathlib import Path

        page = Path(__file__).resolve().parents[2] / "web" / "app" / "my-portfolio" / "page.tsx"
        content = self._read(page)
        assert "router.push" in content
        assert "/contributors/${encodeURIComponent(id)}/portfolio" in content

    def test_contributor_portfolio_page_exists(self) -> None:
        from pathlib import Path

        page = (
            Path(__file__).resolve().parents[2]
            / "web"
            / "app"
            / "contributors"
            / "[id]"
            / "portfolio"
            / "page.tsx"
        )
        assert page.is_file(), f"Missing: {page}"

    def test_contributor_portfolio_page_shows_core_sections(self) -> None:
        from pathlib import Path

        page = (
            Path(__file__).resolve().parents[2]
            / "web"
            / "app"
            / "contributors"
            / "[id]"
            / "portfolio"
            / "page.tsx"
        )
        content = self._read(page)
        assert "CC Balance" in content
        assert "Ideas I Contributed To" in content
        assert "Ideas I Staked On" in content
        assert "Tasks I Completed" in content

    def test_contributor_portfolio_page_fetches_all_api_sub_resources(self) -> None:
        from pathlib import Path

        page = (
            Path(__file__).resolve().parents[2]
            / "web"
            / "app"
            / "contributors"
            / "[id]"
            / "portfolio"
            / "page.tsx"
        )
        content = self._read(page)
        # All five sub-resource endpoints must be referenced
        assert "/portfolio" in content
        assert "/cc-history" in content
        assert "/idea-contributions" in content
        assert "/stakes" in content
        assert "/tasks" in content

    def test_contributor_portfolio_page_links_back_to_my_portfolio(self) -> None:
        from pathlib import Path

        page = (
            Path(__file__).resolve().parents[2]
            / "web"
            / "app"
            / "contributors"
            / "[id]"
            / "portfolio"
            / "page.tsx"
        )
        content = self._read(page)
        assert "/my-portfolio" in content


# ─── 4. API integration tests (ASGI, in-process SQLite) ───────────────────────


def _seed_portfolio_nodes(contributor_uuid: str, idea_key: str) -> None:
    """Insert idea, 2 contributions (spec+task), 1 stake, 1 completed task node."""
    graph_service.create_node(
        id=f"idea:{idea_key}",
        type="idea",
        name=f"Portfolio Idea {idea_key}",
        description="Integration test idea",
        phase="gas",
        properties={"status": "active", "coherence_score": 0.75},
    )
    graph_service.create_node(
        id=f"contrib-spec-{idea_key}",
        type="contribution",
        name="spec contribution",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cost_amount": 6.0,
            "contribution_type": "spec",
            "coherence_score": 0.88,
        },
    )
    graph_service.create_node(
        id=f"contrib-task-{idea_key}",
        type="contribution",
        name="task contribution",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cost_amount": 4.0,
            "contribution_type": "task",
            "coherence_score": 0.72,
        },
    )
    graph_service.create_node(
        id=f"stake-{idea_key}",
        type="stake",
        name=f"stake on {idea_key}",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cc_staked": 15.0,
            "cc_valuation": 18.0,
            "staked_at": "2026-02-01T00:00:00+00:00",
        },
    )
    graph_service.create_node(
        id=f"task-completed-{idea_key}",
        type="task",
        name="Portfolio task",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "status": "completed",
            "provider": "openclaw",
            "outcome": "passed",
            "cc_earned": 4.0,
            "completed_at": "2026-03-26T10:00:00+00:00",
        },
    )


@pytest.mark.asyncio
async def test_portfolio_api_summary_returns_correct_aggregates() -> None:
    """Full round-trip: create contributor → seed nodes → GET /portfolio summary."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Alice-{suffix}", "email": _unique_email("alice")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"pv-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["contributor"]["id"] == str(cid)
        assert body["idea_contribution_count"] == 1
        assert body["stake_count"] == 1
        assert body["task_completion_count"] == 1
        # CC balance = sum of spec(6) + task(4) = 10
        assert body["cc_balance"] == pytest.approx(10.0)
        # Network % is present
        assert body["cc_network_pct"] is not None


@pytest.mark.asyncio
async def test_portfolio_api_cc_history_returns_time_series() -> None:
    """CC earning history must return a valid time-series with window/bucket metadata."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-HistUser-{suffix}", "email": _unique_email("hist")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        _seed_portfolio_nodes(str(cid), f"hist-idea-{suffix}")

        r = await client.get(f"/api/contributors/{cid}/cc-history?window=30d&bucket=7d")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["contributor_id"] == str(cid)
        assert body["window"] == "30d"
        assert body["bucket"] == "7d"
        series = body["series"]
        assert isinstance(series, list)
        assert len(series) >= 1
        # Each bucket must have required fields
        for bucket in series:
            assert "period_start" in bucket
            assert "period_end" in bucket
            assert "cc_earned" in bucket
            assert "running_total" in bucket
        # Running total must be non-decreasing
        running_totals = [b["running_total"] for b in series]
        for i in range(1, len(running_totals)):
            assert running_totals[i] >= running_totals[i - 1]


@pytest.mark.asyncio
async def test_portfolio_api_cc_history_default_window_90d() -> None:
    """Default cc-history window is 90d with 7d buckets."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Def90-{suffix}", "email": _unique_email("def90")},
        )
        cid = create.json()["id"]
        r = await client.get(f"/api/contributors/{cid}/cc-history")
        assert r.status_code == 200
        body = r.json()
        assert body["window"] == "90d"
        assert body["bucket"] == "7d"


@pytest.mark.asyncio
async def test_portfolio_api_idea_contributions_list() -> None:
    """GET /idea-contributions returns correct idea list with types and CC."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Ideas-{suffix}", "email": _unique_email("ideas")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"ideas-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/idea-contributions")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["idea_id"] == idea_key
        assert item["cc_attributed"] == pytest.approx(10.0)
        assert "spec" in item["contribution_types"]
        assert "task" in item["contribution_types"]
        assert item["idea_status"] == "active"


@pytest.mark.asyncio
async def test_portfolio_api_idea_contributions_drilldown() -> None:
    """GET /idea-contributions/{idea_id} returns per-contribution details and lineage."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Drill-{suffix}", "email": _unique_email("drill")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"drill-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/idea-contributions/{idea_key}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["idea_id"] == idea_key
        assert body["idea_title"] == f"Portfolio Idea {idea_key}"
        assert len(body["contributions"]) == 2
        assert body["value_lineage_summary"]["total_value"] == pytest.approx(10.0)

        # Drilldown must include contribution types
        types = {c["type"] for c in body["contributions"]}
        assert "spec" in types
        assert "task" in types


@pytest.mark.asyncio
async def test_portfolio_api_stakes_list_with_roi() -> None:
    """GET /stakes returns stakes with ROI correctly computed."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Stakes-{suffix}", "email": _unique_email("stakes")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"stakes-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/stakes")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        stake = body["items"][0]
        assert stake["cc_staked"] == 15.0
        # ROI = (18 - 15) / 15 * 100 = 20%
        assert stake["roi_pct"] == pytest.approx(20.0)
        assert stake["idea_id"] == idea_key


@pytest.mark.asyncio
async def test_portfolio_api_tasks_list_with_provider_and_outcome() -> None:
    """GET /tasks returns completed tasks with provider and outcome fields."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Tasks-{suffix}", "email": _unique_email("tasks")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"tasks-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/tasks?status=completed")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        task = body["items"][0]
        assert task["provider"] == "openclaw"
        assert task["outcome"] == "passed"
        assert task["cc_earned"] == pytest.approx(4.0)
        assert task["idea_id"] == idea_key


# ─── 5. CC display: absolute numbers vs network percentage ────────────────────


@pytest.mark.asyncio
async def test_portfolio_cc_shows_both_absolute_and_network_pct_by_default() -> None:
    """By default, portfolio shows cc_balance (absolute) AND cc_network_pct (% of network)."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-CCDisp-{suffix}", "email": _unique_email("ccdisp")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        idea_key = f"cc-disp-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["cc_balance"] is not None
        assert body["cc_network_pct"] is not None
        # cc_network_pct must be a valid percentage (0–100)
        assert 0.0 <= body["cc_network_pct"] <= 100.0


@pytest.mark.asyncio
async def test_portfolio_include_cc_false_omits_both_fields() -> None:
    """When include_cc=false, both cc_balance and cc_network_pct must be null."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-NoCCDisp-{suffix}", "email": _unique_email("noccd")},
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        _seed_portfolio_nodes(str(cid), f"nocc-idea-{suffix}")

        r = await client.get(f"/api/contributors/{cid}/portfolio?include_cc=false")
        assert r.status_code == 200
        body = r.json()
        assert body["cc_balance"] is None
        assert body["cc_network_pct"] is None


# ─── 6. Authentication & identity-link pattern ────────────────────────────────


@pytest.mark.asyncio
async def test_portfolio_accessible_by_contributor_id() -> None:
    """Portfolio is accessible via contributor UUID — no session cookie required in API mode."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Auth-{suffix}", "email": _unique_email("auth")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        # Should return 200 without any auth header — contributor ID is the identity key
        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200
        assert r.json()["contributor"]["id"] == str(cid)


@pytest.mark.asyncio
async def test_portfolio_linked_identities_appear_in_contributor_block() -> None:
    """Contributor block in portfolio summary includes linked identities."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Identity-{suffix}", "email": _unique_email("ident")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200
        body = r.json()
        # identities list must be present (may be empty for a brand-new contributor)
        assert "identities" in body["contributor"]
        assert isinstance(body["contributor"]["identities"], list)


# ─── 7. Error handling ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_portfolio_routes_return_404_for_unknown_contributor() -> None:
    """All five portfolio sub-resources return 404 for unknown contributor UUID."""
    fake_id = "00000000-0000-0000-0000-deadbeef0099"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        endpoints = [
            f"/api/contributors/{fake_id}/portfolio",
            f"/api/contributors/{fake_id}/cc-history",
            f"/api/contributors/{fake_id}/idea-contributions",
            f"/api/contributors/{fake_id}/stakes",
            f"/api/contributors/{fake_id}/tasks",
        ]
        for path in endpoints:
            r = await client.get(path)
            assert r.status_code == 404, f"Expected 404, got {r.status_code} for {path}"
            detail = r.json().get("detail", "")
            assert detail, f"Missing detail message for {path}"


@pytest.mark.asyncio
async def test_portfolio_idea_drilldown_returns_403_when_contributor_has_no_contributions() -> None:
    """Drilldown for an idea the contributor never touched must return 403 (not 404)."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-ForbDrill-{suffix}", "email": _unique_email("forb")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r = await client.get(f"/api/contributors/{cid}/idea-contributions/nobody-worked-on-this")
        assert r.status_code == 403
        assert r.json()["detail"]


@pytest.mark.asyncio
async def test_cc_history_returns_404_for_invalid_bucket_param() -> None:
    """Unsupported bucket value (e.g., 2d) must produce a 404 with 'bucket' in detail."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-BadBucket-{suffix}", "email": _unique_email("badbt")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r = await client.get(f"/api/contributors/{cid}/cc-history?bucket=2d")
        assert r.status_code == 404
        assert "bucket" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tasks_pagination_limit_zero_returns_422() -> None:
    """limit=0 must be rejected as invalid by FastAPI validation (422)."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Pager-{suffix}", "email": _unique_email("pager")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r = await client.get(f"/api/contributors/{cid}/tasks?limit=0")
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_idea_contributions_pagination_limit_above_max_returns_422() -> None:
    """limit > 100 must be rejected (422) to prevent oversized responses."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-MaxLim-{suffix}", "email": _unique_email("maxlim")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r = await client.get(f"/api/contributors/{cid}/idea-contributions?limit=200")
        assert r.status_code == 422


# ─── 8. Pagination and offset tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_idea_contributions_pagination_with_offset() -> None:
    """Offset parameter shifts the result window correctly."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-PagOff-{suffix}", "email": _unique_email("pagoff")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        r_all = await client.get(f"/api/contributors/{cid}/idea-contributions?limit=20&offset=0")
        assert r_all.status_code == 200
        total = r_all.json()["total"]

        r_offset = await client.get(
            f"/api/contributors/{cid}/idea-contributions?limit=20&offset={total + 100}"
        )
        assert r_offset.status_code == 200
        # Offset past the end must return empty items list
        assert r_offset.json()["items"] == []


@pytest.mark.asyncio
async def test_stakes_pagination_default_limit_is_20() -> None:
    """Default limit for stakes is 20 items per page."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-StPag-{suffix}", "email": _unique_email("stpag")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]

        # No limit param — should default to 20 and return valid response
        r = await client.get(f"/api/contributors/{cid}/stakes")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert len(body["items"]) <= 20


# ─── 9. Recent activity timestamp ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_portfolio_recent_activity_reflects_latest_contribution() -> None:
    """recent_activity in portfolio summary matches the latest contribution timestamp."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-RecAct-{suffix}", "email": _unique_email("recact")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]
        idea_key = f"recact-idea-{suffix}"
        _seed_portfolio_nodes(str(cid), idea_key)

        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200
        body = r.json()
        # recent_activity should be set given we have contributions
        assert body["recent_activity"] is not None
        # Must be a valid ISO 8601 datetime string
        dt = datetime.fromisoformat(body["recent_activity"].replace("Z", "+00:00"))
        assert isinstance(dt, datetime)


# ─── 10. Multi-idea contributor scenario ──────────────────────────────────────


@pytest.mark.asyncio
async def test_portfolio_contributor_with_multiple_ideas_and_stakes() -> None:
    """A contributor with 3 ideas, 2 stakes, 4 tasks — all aggregated correctly."""
    suffix = _uid()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": f"PV-Multi-{suffix}", "email": _unique_email("multi")},
        )
        assert create.status_code == 201
        cid = create.json()["id"]
        cid_str = str(cid)

        # Seed 3 ideas with contributions
        for i in range(3):
            key = f"multi-idea-{i}-{suffix}"
            graph_service.create_node(
                id=f"idea:{key}",
                type="idea",
                name=f"Multi Idea {i} {suffix}",
                description="",
                phase="gas",
                properties={"status": "active"},
            )
            graph_service.create_node(
                id=f"multi-contrib-{i}-{suffix}",
                type="contribution",
                name=f"code for idea {i}",
                description="",
                phase="water",
                properties={
                    "contributor_id": cid_str,
                    "idea_id": key,
                    "cost_amount": float(i + 1),
                    "contribution_type": "code",
                },
            )
            graph_service.create_node(
                id=f"multi-task-{i}-{suffix}",
                type="task",
                name=f"task for idea {i}",
                description="",
                phase="water",
                properties={
                    "contributor_id": cid_str,
                    "idea_id": key,
                    "status": "completed",
                    "provider": "cursor",
                    "outcome": "passed",
                    "cc_earned": 1.0,
                },
            )

        # Add 2 stakes on ideas 0 and 1
        for i in range(2):
            key = f"multi-idea-{i}-{suffix}"
            graph_service.create_node(
                id=f"multi-stake-{i}-{suffix}",
                type="stake",
                name=f"stake {i}",
                description="",
                phase="water",
                properties={
                    "contributor_id": cid_str,
                    "idea_id": key,
                    "cc_staked": 5.0,
                    "cc_valuation": 6.0,
                    "staked_at": "2026-02-15T00:00:00+00:00",
                },
            )

        r = await client.get(f"/api/contributors/{cid}/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["idea_contribution_count"] == 3
        assert body["stake_count"] == 2
        assert body["task_completion_count"] == 3
        # CC = 1 + 2 + 3 = 6
        assert body["cc_balance"] == pytest.approx(6.0)

        ideas_r = await client.get(f"/api/contributors/{cid}/idea-contributions")
        assert ideas_r.status_code == 200
        assert ideas_r.json()["total"] == 3

        stakes_r = await client.get(f"/api/contributors/{cid}/stakes")
        assert stakes_r.status_code == 200
        assert stakes_r.json()["total"] == 2
        # All stakes should have ROI = (6-5)/5*100 = 20%
        for s in stakes_r.json()["items"]:
            assert s["roi_pct"] == pytest.approx(20.0)

        tasks_r = await client.get(f"/api/contributors/{cid}/tasks?status=completed")
        assert tasks_r.status_code == 200
        assert tasks_r.json()["total"] == 3
