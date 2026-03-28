from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_beliefs_get_defaults_patch_resonance() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "BeliefTester", "email": "belief-tester@coherence.network"},
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]

        g = await client.get(f"/api/contributors/{cid}/beliefs")
        assert g.status_code == 200
        body = g.json()
        assert body["contributor_id"] == cid
        assert body["worldview"] == "pragmatic"
        assert "rigor" in body["axes"]

        p = await client.patch(
            f"/api/contributors/{cid}/beliefs",
            json={
                "worldview": "scientific",
                "axes": {"rigor": 0.9},
                "concepts": {"graph": 0.8, "pipeline": 0.6},
            },
        )
        assert p.status_code == 200
        assert p.json()["worldview"] == "scientific"
        assert p.json()["axes"]["rigor"] == 0.9
        assert "graph" in p.json()["concepts"]

        r = await client.get(
            "/api/contributors/{}/beliefs/resonance".format(cid),
            params={"idea_id": "coherence-network-agent-pipeline"},
        )
        assert r.status_code == 200
        res = r.json()
        assert res["idea_id"] == "coherence-network-agent-pipeline"
        assert "scores" in res
        assert 0.0 <= res["scores"]["overall"] <= 1.0


@pytest.mark.asyncio
async def test_beliefs_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = await client.get("/api/contributors/00000000-0000-0000-0000-000000000001/beliefs")
        assert bad.status_code == 404
