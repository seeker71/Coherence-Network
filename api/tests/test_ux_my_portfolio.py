"""Tests for the My Portfolio UX flow — web wiring, models, service aggregation, and API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any
import unittest.mock as mock
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service


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


# ── HTTP API integration (ASGI) — portfolio sub-resources per spec 174 ─────


def _seed_portfolio_graph(*, contributor_uuid: str) -> None:
    """Insert idea, contribution, stake, and completed task nodes for one contributor."""
    idea_key = "pf-seed-idea"
    graph_service.create_node(
        id=f"idea:{idea_key}",
        type="idea",
        name="Seeded Portfolio Idea",
        description="Test idea for portfolio API",
        phase="gas",
        properties={"status": "active", "coherence_score": 0.72},
    )
    graph_service.create_node(
        id=f"contrib-{contributor_uuid[:8]}",
        type="contribution",
        name="spec contribution",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cost_amount": 5.0,
            "contribution_type": "spec",
            "coherence_score": 0.9,
        },
    )
    graph_service.create_node(
        id=f"contrib-task-{contributor_uuid[:8]}",
        type="contribution",
        name="task completion",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cost_amount": 3.0,
            "contribution_type": "task",
            "coherence_score": 0.5,
        },
    )
    graph_service.create_node(
        id=f"stake-{contributor_uuid[:8]}",
        type="stake",
        name="stake on idea",
        description="",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "cc_staked": 20.0,
            "cc_valuation": 24.0,
            "staked_at": "2026-01-15T12:00:00+00:00",
        },
    )
    graph_service.create_node(
        id=f"task-{contributor_uuid[:8]}",
        type="task",
        name="Implement portfolio section",
        description="Portfolio task",
        phase="water",
        properties={
            "contributor_id": contributor_uuid,
            "idea_id": idea_key,
            "status": "completed",
            "provider": "openclaw",
            "outcome": "passed",
            "cc_earned": 3.0,
            "completed_at": "2026-03-27T18:00:00+00:00",
        },
    )


@pytest.mark.asyncio
async def test_portfolio_api_full_cycle_seeded_graph() -> None:
    """Create contributor, seed graph CC/ideas/stakes/tasks, exercise all portfolio GET routes."""
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"PortfolioSeedUser_{suffix}",
                "email": f"portfolioseed_{suffix}@coherence.network",
            },
        )
        assert create.status_code == 201, create.text
        cid = create.json()["id"]
        _seed_portfolio_graph(contributor_uuid=str(cid))

        sum_res = await client.get(f"/api/contributors/{cid}/portfolio")
        assert sum_res.status_code == 200
        body = sum_res.json()
        assert body["contributor"]["id"] == str(cid)
        assert body["idea_contribution_count"] == 1
        assert body["stake_count"] == 1
        assert body["task_completion_count"] == 1
        assert body["cc_balance"] is not None
        assert float(body["cc_balance"]) == pytest.approx(8.0)
        assert body["cc_network_pct"] is not None

        hist = await client.get(f"/api/contributors/{cid}/cc-history?window=90d&bucket=7d")
        assert hist.status_code == 200
        hist_j = hist.json()
        assert hist_j["contributor_id"] == str(cid)
        assert hist_j["window"] == "90d"
        assert isinstance(hist_j["series"], list)
        assert len(hist_j["series"]) >= 1

        ideas = await client.get(f"/api/contributors/{cid}/idea-contributions")
        assert ideas.status_code == 200
        ij = ideas.json()
        assert ij["total"] == 1
        assert ij["items"][0]["idea_id"] == "pf-seed-idea"
        assert ij["items"][0]["cc_attributed"] == pytest.approx(8.0)
        assert "spec" in ij["items"][0]["contribution_types"]
        assert "task" in ij["items"][0]["contribution_types"]
        assert ij["items"][0]["idea_status"] == "active"

        drill = await client.get(
            f"/api/contributors/{cid}/idea-contributions/pf-seed-idea",
        )
        assert drill.status_code == 200
        dj = drill.json()
        assert dj["idea_id"] == "pf-seed-idea"
        assert dj["idea_title"] == "Seeded Portfolio Idea"
        assert len(dj["contributions"]) == 2
        assert dj["value_lineage_summary"]["total_value"] == pytest.approx(8.0)

        stakes = await client.get(f"/api/contributors/{cid}/stakes")
        assert stakes.status_code == 200
        sj = stakes.json()
        assert sj["total"] == 1
        assert sj["items"][0]["cc_staked"] == 20.0
        assert sj["items"][0]["roi_pct"] == pytest.approx(20.0)

        tasks = await client.get(f"/api/contributors/{cid}/tasks?status=completed")
        assert tasks.status_code == 200
        tj = tasks.json()
        assert tj["total"] == 1
        assert tj["items"][0]["provider"] == "openclaw"
        assert tj["items"][0]["outcome"] == "passed"
        assert tj["items"][0]["cc_earned"] == 3.0


@pytest.mark.asyncio
async def test_portfolio_api_unknown_contributor_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in (
            "/api/contributors/00000000-0000-0000-0000-000000000099/portfolio",
            "/api/contributors/00000000-0000-0000-0000-000000000099/cc-history",
            "/api/contributors/00000000-0000-0000-0000-000000000099/idea-contributions",
            "/api/contributors/00000000-0000-0000-0000-000000000099/stakes",
            "/api/contributors/00000000-0000-0000-0000-000000000099/tasks",
        ):
            r = await client.get(path)
            assert r.status_code == 404, path
            assert "not found" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portfolio_idea_drilldown_forbidden_when_no_matching_contributions() -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"NoDrillUser_{suffix}",
                "email": f"nodrill_{suffix}@coherence.network",
            },
        )
        assert create.status_code == 201
        cid = create.json()["id"]
        r = await client.get(f"/api/contributors/{cid}/idea-contributions/ghost-idea-id")
        assert r.status_code == 403
        assert r.json()["detail"]


@pytest.mark.asyncio
async def test_portfolio_summary_include_cc_false() -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"NoCCUser_{suffix}",
                "email": f"nocc_{suffix}@coherence.network",
            },
        )
        assert create.status_code == 201
        cid = create.json()["id"]
        graph_service.create_node(
            id=f"idea:nocc_{suffix}",
            type="idea",
            name="I",
            description="",
            phase="gas",
            properties={"status": "unknown"},
        )
        graph_service.create_node(
            id=f"contrib-nocc_{suffix}",
            type="contribution",
            name="c",
            description="",
            phase="water",
            properties={
                "contributor_id": str(cid),
                "idea_id": f"nocc_{suffix}",
                "cost_amount": 1.0,
                "contribution_type": "code",
            },
        )
        r = await client.get(f"/api/contributors/{cid}/portfolio?include_cc=false")
        assert r.status_code == 200
        j = r.json()
        assert j["cc_balance"] is None
        assert j["cc_network_pct"] is None


@pytest.mark.asyncio
async def test_cc_history_invalid_bucket_returns_404() -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"BucketUser_{suffix}",
                "email": f"bucket_{suffix}@coherence.network",
            },
        )
        cid = create.json()["id"]
        r = await client.get(f"/api/contributors/{cid}/cc-history?bucket=2d")
        assert r.status_code == 404
        assert "bucket" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portfolio_pagination_invalid_limit_returns_422() -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"PageUser_{suffix}",
                "email": f"pageuser_{suffix}@coherence.network",
            },
        )
        cid = create.json()["id"]
        r = await client.get(f"/api/contributors/{cid}/tasks?limit=0")
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_contribution_lineage_endpoint() -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"LineageUser_{suffix}",
                "email": f"lineage_{suffix}@coherence.network",
            },
        )
        assert create.status_code == 201
        cid = create.json()["id"]
        graph_service.create_node(
            id=f"idea:lineage-test_{suffix}",
            type="idea",
            name="Lineage Idea",
            description="",
            phase="gas",
            properties={"status": "active"},
        )
        graph_service.create_node(
            id=f"contrib-lineage-1_{suffix}",
            type="contribution",
            name="c1",
            description="",
            phase="water",
            properties={
                "contributor_id": str(cid),
                "idea_id": f"lineage-test_{suffix}",
                "cost_amount": 2.5,
                "contribution_type": "code",
                "lineage_chain_id": "vl-nonexistent-999",
            },
        )
        r = await client.get(f"/api/contributors/{cid}/contributions/contrib-lineage-1_{suffix}/lineage")
        assert r.status_code == 200
        j = r.json()
        assert j["contribution_id"] == f"contrib-lineage-1_{suffix}"
        assert j["cc_attributed"] == pytest.approx(2.5)
        assert j["lineage_chain_id"] == "vl-nonexistent-999"
        assert j["lineage_resolution_note"] is not None

        r404 = await client.get(f"/api/contributors/{cid}/contributions/does-not-exist/lineage")
        assert r404.status_code == 404


@pytest.mark.asyncio
@mock.patch("app.routers.me_portfolio.verify_contributor_key")
async def test_me_portfolio_requires_valid_api_key(mock_verify: mock.MagicMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/me/portfolio")
        assert r.status_code == 401

        mock_verify.return_value = None
        r2 = await client.get("/api/me/portfolio", headers={"X-API-Key": "bad"})
        assert r2.status_code == 401

        mock_verify.return_value = {"contributor_id": "not-a-real-contributor-uuid-99"}
        r3 = await client.get("/api/me/portfolio", headers={"X-API-Key": "k"})
        assert r3.status_code == 404


@pytest.mark.asyncio
@mock.patch("app.routers.me_portfolio.verify_contributor_key")
async def test_me_portfolio_ok_when_key_matches_contributor(mock_verify: mock.MagicMock) -> None:
    suffix = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": f"MePortfolioUser_{suffix}",
                "email": f"meport_{suffix}@coherence.network",
            },
        )
        cid = str(create.json()["id"])
        mock_verify.return_value = {"contributor_id": cid}
        r = await client.get("/api/me/portfolio", headers={"X-API-Key": "test-key"})
        assert r.status_code == 200
        assert r.json()["contributor"]["id"] == cid
