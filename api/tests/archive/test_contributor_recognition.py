from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.contribution import Contribution
from app.models.contributor import Contributor, ContributorType
from app.models.graph import Edge
from app.services import contributor_recognition_service, graph_service
from app.services.unified_db import session

@pytest.fixture
def tmp_path() -> Path:
    path = Path.cwd() / ".task-pytest-fixtures" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_recognition_snapshot_returns_lifetime_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = f"contributor:seed-lifetime-{contributor_id}"
    graph_service.create_node(
        id=contributor_node_id,
        type="contributor",
        name="Alice Lifetime",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"alice-{contributor_id}@coherence.network",
            "legacy_id": str(contributor_id),
        },
    )

    for suffix, cost, score, days_ago in (
        ("current-a", "10.00", 0.8, 5),
        ("current-b", "20.00", 0.6, 10),
        ("prior-a", "5.50", 1.0, 40),
    ):
        asset_id = uuid4()
        asset_node_id = f"asset:{suffix}-{asset_id}"
        graph_service.create_node(
            id=asset_node_id,
            type="asset",
            name=suffix,
            description=f"Asset {suffix}",
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
                "metadata": {},
            },
            strength=score,
            created_by="test_contributor_recognition",
        )
        with session() as s:
            row = s.get(Edge, edge["id"])
            assert row is not None
            row.created_at = fixed_now - timedelta(days=days_ago)
            s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["contributor_id"] == str(contributor_id)
    assert payload["name"] == "Alice Lifetime"
    assert payload["total_contributions"] == 3
    assert Decimal(str(payload["total_cost"])) == Decimal("35.50")
    assert payload["average_coherence_score"] == 0.8
    assert payload["current_window_contributions"] == 2
    assert payload["prior_window_contributions"] == 1
    assert payload["delta_contributions"] == 1
    assert payload["window_days"] == 30


def test_get_recognition_snapshot_merges_store_contributions_for_graph_contributor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    graph_node = {
        "id": f"contributor:hybrid-{contributor_id}",
        "type": "contributor",
        "name": "Hybrid User",
        "description": "HUMAN contributor",
        "phase": "water",
        "legacy_id": str(contributor_id),
        "contributor_type": "HUMAN",
        "email": f"hybrid-{contributor_id}@coherence.network",
        "created_at": fixed_now.isoformat(),
    }

    class StubStore:
        def get_contributor(self, contributor_key):
            if contributor_key != contributor_id:
                return None
            return Contributor(
                id=contributor_id,
                name="Store User",
                type=ContributorType.HUMAN,
                email=f"store-{contributor_id}@coherence.network",
                created_at=fixed_now - timedelta(days=90),
            )

        def get_contributor_contributions(self, contributor_key):
            if contributor_key != contributor_id:
                return []
            return [
                Contribution(
                    contributor_id=contributor_id,
                    asset_id=uuid4(),
                    cost_amount=Decimal("12.50"),
                    coherence_score=0.5,
                    timestamp=fixed_now - timedelta(days=3),
                    metadata={},
                ),
                Contribution(
                    contributor_id=contributor_id,
                    asset_id=uuid4(),
                    cost_amount=Decimal("3.50"),
                    coherence_score=1.0,
                    timestamp=fixed_now - timedelta(days=40),
                    metadata={},
                ),
            ]

    monkeypatch.setattr(graph_service, "get_node", lambda node_id: None)
    monkeypatch.setattr(
        graph_service,
        "list_nodes",
        lambda type=None, limit=50, offset=0, phase=None, search=None: {
            "items": [graph_node] if type == "contributor" else [],
            "total": 1 if type == "contributor" else 0,
            "limit": limit,
            "offset": offset,
        },
    )
    monkeypatch.setattr(graph_service, "get_edges", lambda node_id, direction="both", edge_type=None: [])

    snapshot = contributor_recognition_service.get_contributor_recognition_snapshot(
        contributor_id,
        store=StubStore(),
    )

    assert snapshot is not None
    assert snapshot.name == "Hybrid User"
    assert snapshot.total_contributions == 2
    assert snapshot.total_cost == Decimal("16.00")
    assert snapshot.average_coherence_score == 0.75
    assert snapshot.current_window_contributions == 1
    assert snapshot.prior_window_contributions == 1
    assert snapshot.delta_contributions == 0


@pytest.mark.asyncio
async def test_get_recognition_snapshot_returns_window_growth_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(contributor_recognition_service, "_utc_now", lambda: fixed_now)

    contributor_id = uuid4()
    contributor_node_id = f"contributor:seed-boundary-{contributor_id}"
    graph_service.create_node(
        id=contributor_node_id,
        type="contributor",
        name="Boundary User",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"boundary-{contributor_id}@coherence.network",
            "legacy_id": str(contributor_id),
        },
    )

    timestamps = (
        ("current-edge", fixed_now - timedelta(days=30)),
        ("prior-edge", fixed_now - timedelta(days=60)),
        ("excluded-now", fixed_now),
    )
    for suffix, created_at in timestamps:
        asset_id = uuid4()
        asset_node_id = f"asset:{suffix}-{asset_id}"
        graph_service.create_node(
            id=asset_node_id,
            type="asset",
            name=suffix,
            description=f"Asset {suffix}",
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
                "cost_amount": "1.00",
                "coherence_score": 0.5,
                "metadata": {},
            },
            strength=0.5,
            created_by="test_contributor_recognition",
        )
        with session() as s:
            row = s.get(Edge, edge["id"])
            assert row is not None
            row.created_at = created_at
            s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current_window_contributions"] == 1
    assert payload["prior_window_contributions"] == 1
    assert payload["delta_contributions"] == 0
    assert payload["total_contributions"] == 3


@pytest.mark.asyncio
async def test_get_recognition_snapshot_returns_zero_metrics_for_existing_contributor_without_contributions() -> None:
    contributor_id = uuid4()
    graph_service.create_node(
        id=f"contributor:seed-empty-{contributor_id}",
        type="contributor",
        name="Zero User",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"zero-{contributor_id}@coherence.network",
            "legacy_id": str(contributor_id),
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{contributor_id}/recognition")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["name"] == "Zero User"
    assert payload["total_contributions"] == 0
    assert Decimal(str(payload["total_cost"])) == Decimal("0")
    assert payload["average_coherence_score"] == 0.0
    assert payload["current_window_contributions"] == 0
    assert payload["prior_window_contributions"] == 0
    assert payload["delta_contributions"] == 0


@pytest.mark.asyncio
async def test_get_recognition_snapshot_returns_404_for_missing_contributor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/contributors/{uuid4()}/recognition")

    assert response.status_code == 404
    assert response.json()["detail"] == "Contributor not found"
