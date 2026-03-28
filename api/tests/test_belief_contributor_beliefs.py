from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_get_patch_beliefs_and_resonance() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "BeliefTester", "email": "belief-tester@coherence.network"},
        )
        assert c.status_code == 201, c.json()
        contributor_id = c.json()["id"]

        g = await client.get(f"/api/contributors/{contributor_id}/beliefs")
        assert g.status_code == 200
        body = g.json()
        assert body["worldview"] == "pragmatic"
        assert "empirical" in body["axis_weights"]

        p = await client.patch(
            f"/api/contributors/{contributor_id}/beliefs",
            headers=AUTH_HEADERS,
            json={
                "worldview": "scientific",
                "concept_weights": {"api": 0.9, "graph": 0.7},
                "axis_weights": {"empirical": 0.9, "technical": 0.85},
            },
        )
        assert p.status_code == 200, p.json()
        patched = p.json()
        assert patched["worldview"] == "scientific"
        assert patched["concept_weights"]["api"] == 0.9

        idea_id = f"test-belief-resonance-{uuid.uuid4().hex[:12]}"
        idea = await client.post(
            "/api/ideas",
            json={
                "id": idea_id,
                "name": "API graph coherence",
                "description": "Measure evidence and deploy the graph api with data metrics.",
                "potential_value": 10.0,
                "estimated_cost": 2.0,
                "interfaces": ["api", "graph"],
            },
        )
        assert idea.status_code == 201, idea.json()

        r = await client.get(
            f"/api/contributors/{contributor_id}/beliefs/resonance",
            params={"idea_id": idea_id},
        )
        assert r.status_code == 200
        res = r.json()
        assert res["idea_id"] == idea_id
        assert 0.0 <= res["resonance_score"] <= 1.0
        assert "matching_concepts" in res
