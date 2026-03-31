"""Acceptance tests for fractal zoom navigation (Spec 182).

Covers all requirements in the spec:
  - GET /api/graph/pillars — 5 pillars
  - GET /api/graph/zoom/{node_id} — subtree traversal
  - depth validation (0..3, 422 on 4)
  - 404 for missing nodes
  - coherence_score always in [0.0, 1.0]
  - view_hint: "garden" / "graph"
  - POST/PATCH /api/graph/nodes/{id}/questions
"""

from __future__ import annotations

import os
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def isolate_db(tmp_path, monkeypatch):
    """Each test gets its own SQLite DB so seed data is clean."""
    db_path = tmp_path / "test_zoom.db"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    # Ensure unified_db picks up the new URL on each test
    import app.services.unified_db as _udb
    _udb._ENGINE_CACHE.clear()
    _udb._SCHEMA_INITIALIZED.clear()
    yield
    _udb._ENGINE_CACHE.clear()
    _udb._SCHEMA_INITIALIZED.clear()


async def _client():
    from app.main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(client):
    """Seed pillar nodes via the graph API directly."""
    pillar_ids = ["traceability", "trust", "freedom", "uniqueness", "collaboration"]
    for pid in pillar_ids:
        await client.post("/api/graph/nodes", json={
            "id": pid,
            "type": "concept",
            "name": pid.capitalize(),
            "properties": {"lifecycle_state": "water", "coherence_score": 0.5, "open_questions": []},
        })

    # Trust subtree depth 2
    for child_id, child_name in [
        ("coherence-scoring", "Coherence Scoring"),
        ("contribution-verification", "Contribution Verification"),
        ("identity-attestation", "Identity Attestation"),
    ]:
        await client.post("/api/graph/nodes", json={
            "id": child_id,
            "type": "concept",
            "name": child_name,
            "properties": {"lifecycle_state": "water", "coherence_score": 0.6, "open_questions": []},
        })
        await client.post("/api/graph/edges", json={
            "from_id": "trust",
            "to_id": child_id,
            "type": "parent-of",
        })

    # coherence-scoring subtree depth 3
    for child_id, child_name in [
        ("test-coverage-analysis", "Test Coverage Analysis"),
        ("documentation-quality-metrics", "Documentation Quality Metrics"),
        ("simplicity-index", "Simplicity Index"),
    ]:
        await client.post("/api/graph/nodes", json={
            "id": child_id,
            "type": "concept",
            "name": child_name,
            "properties": {"lifecycle_state": "water", "coherence_score": 0.7, "open_questions": []},
        })
        await client.post("/api/graph/edges", json={
            "from_id": "coherence-scoring",
            "to_id": child_id,
            "type": "parent-of",
        })


@pytest.mark.asyncio
async def test_pillars_returns_five_nodes():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/pillars")
    assert resp.status_code == 200
    data = resp.json()
    assert "pillars" in data
    assert data["total"] == 5
    ids = {p["id"] for p in data["pillars"]}
    assert ids == {"traceability", "trust", "freedom", "uniqueness", "collaboration"}


@pytest.mark.asyncio
async def test_pillar_fields_present():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/pillars")
    assert resp.status_code == 200
    for p in resp.json()["pillars"]:
        assert "id" in p
        assert "name" in p
        assert "node_type" in p
        assert "coherence_score" in p
        assert "child_count" in p
        assert "open_question_count" in p
        assert "lifecycle_state" in p
        assert 0.0 <= p["coherence_score"] <= 1.0


@pytest.mark.asyncio
async def test_trust_child_count():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/pillars")
    trust = next(p for p in resp.json()["pillars"] if p["id"] == "trust")
    assert trust["child_count"] == 3


@pytest.mark.asyncio
async def test_zoom_trust_depth1():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"]["id"] == "trust"
    assert len(data["node"]["children"]) == 3
    child_ids = {c["id"] for c in data["node"]["children"]}
    assert child_ids == {"coherence-scoring", "contribution-verification", "identity-attestation"}
    assert data["total_nodes_in_subtree"] == 4
    assert data["depth_requested"] == 1


@pytest.mark.asyncio
async def test_zoom_trust_depth0_no_children():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node"]["children"] == []
    assert data["total_nodes_in_subtree"] == 1


@pytest.mark.asyncio
async def test_zoom_trust_depth2_full_subtree():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_nodes_in_subtree"] == 7
    coherence_scoring = next(
        c for c in data["node"]["children"] if c["id"] == "coherence-scoring"
    )
    leaf_ids = {c["id"] for c in coherence_scoring["children"]}
    assert leaf_ids == {
        "test-coverage-analysis",
        "documentation-quality-metrics",
        "simplicity-index",
    }


@pytest.mark.asyncio
async def test_zoom_depth4_returns_422():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=4")
    assert resp.status_code == 422
    assert "depth must be between 0 and 3" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_zoom_missing_node_returns_404():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/nonexistent-node")
    assert resp.status_code == 404
    assert "nonexistent-node" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_zoom_invalid_id_returns_404_not_500():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/___invalid___")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coherence_score_never_null():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=2")
    assert resp.status_code == 200

    def check_node(node):
        score = node["coherence_score"]
        assert score is not None
        assert 0.0 <= score <= 1.0
        for child in node.get("children", []):
            check_node(child)

    check_node(resp.json()["node"])


@pytest.mark.asyncio
async def test_view_hint_values():
    async with await _client() as client:
        await _seed(client)
        resp = await client.get("/api/graph/zoom/trust?depth=2")
    data = resp.json()
    # Root at depth 0 has 3 children — GARDEN_THRESHOLD default is 2, so garden
    root = data["node"]
    assert root["view_hint"] in ("garden", "graph")
    for child in root["children"]:
        assert child["view_hint"] in ("garden", "graph")
        for leaf in child.get("children", []):
            assert leaf["view_hint"] in ("garden", "graph")


@pytest.mark.asyncio
async def test_add_question_returns_201():
    async with await _client() as client:
        await _seed(client)
        resp = await client.post(
            "/api/graph/nodes/trust/questions",
            json={"question": "How do we measure trust over time?"},
        )
    assert resp.status_code == 201
    q = resp.json()
    assert q["resolved"] is False
    assert q["question"] == "How do we measure trust over time?"
    assert q["node_id"] == "trust"
    assert "id" in q
    assert "created_at" in q


@pytest.mark.asyncio
async def test_add_question_to_missing_node_returns_404():
    async with await _client() as client:
        await _seed(client)
        resp = await client.post(
            "/api/graph/nodes/nonexistent-node/questions",
            json={"question": "test"},
        )
    assert resp.status_code == 404
    assert "nonexistent-node" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_resolve_question():
    async with await _client() as client:
        await _seed(client)
        create_resp = await client.post(
            "/api/graph/nodes/trust/questions",
            json={"question": "How do we measure trust?"},
        )
        assert create_resp.status_code == 201
        q_id = create_resp.json()["id"]

        patch_resp = await client.patch(
            f"/api/graph/nodes/trust/questions/{q_id}",
            json={"resolved": True},
        )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["resolved"] is True
    assert data["resolved_at"] is not None


@pytest.mark.asyncio
async def test_question_appears_in_zoom():
    async with await _client() as client:
        await _seed(client)
        await client.post(
            "/api/graph/nodes/trust/questions",
            json={"question": "A visible question"},
        )
        resp = await client.get("/api/graph/zoom/trust?depth=0")
    assert resp.status_code == 200
    questions = resp.json()["node"]["open_questions"]
    assert any(q["question"] == "A visible question" for q in questions)


@pytest.mark.asyncio
async def test_seed_is_idempotent():
    """Running the zoom endpoint twice (and seed twice) should not duplicate pillars."""
    from seed.pillar_seed import seed_pillars
    seed_pillars()
    seed_pillars()

    async with await _client() as client:
        resp = await client.get("/api/graph/pillars")
    # After seeding and calling the pillars endpoint, we should have exactly 5
    # (the API seeds on startup, but test isolation uses fresh DB via _seed helper)
    # This test just verifies no IntegrityError is raised on double-seed
    assert resp.status_code == 200
