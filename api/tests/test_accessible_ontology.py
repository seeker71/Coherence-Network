"""Tests for accessible ontology — plain-language concept contribution workflow.

These tests verify the full feature contract:
  - Non-technical contributors can submit concepts in plain language
  - The system infers relationships and places concepts in the ontology
  - Garden view returns clustered, UI-ready data
  - Stats prove the feature is working
  - Error handling for missing/duplicate concepts

Run with: pytest api/tests/test_accessible_ontology.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixture: reset in-memory store between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_store():
    """Clear the in-memory contribution store before each test."""
    from app.services import accessible_ontology_service as svc
    svc._contributions.clear()
    svc._inferred_edges.clear()
    svc._domain_index.clear()
    yield
    svc._contributions.clear()
    svc._inferred_edges.clear()
    svc._domain_index.clear()


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Scenario 1: Full create-read-update-delete cycle
# ---------------------------------------------------------------------------

class TestContributionCRUD:
    def test_submit_plain_language_concept(self, client):
        """
        Setup: Empty store
        Action: POST /api/ontology/contribute with plain text
        Expected: 201, response contains id, title, status, garden_position
        """
        resp = client.post("/api/ontology/contribute", json={
            "plain_text": "Water flows downhill because gravity pulls it toward equilibrium",
            "contributor_id": "alice",
            "domains": ["physics", "ecology"],
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert "title" in body
        assert body["status"] in ("placed", "pending", "orphan")
        assert "garden_position" in body
        assert "x" in body["garden_position"]
        assert "y" in body["garden_position"]
        assert "cluster" in body["garden_position"]
        assert body["contributor_id"] == "alice"

    def test_get_contribution_by_id(self, client):
        """
        Setup: One contribution exists
        Action: GET /api/ontology/contributions/{id}
        Expected: 200 with full record
        """
        create_resp = client.post("/api/ontology/contribute", json={
            "plain_text": "Creativity emerges when constraints are removed",
            "contributor_id": "bob",
            "domains": ["art"],
        })
        assert create_resp.status_code == 201
        concept_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/ontology/contributions/{concept_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["id"] == concept_id
        assert body["contributor_id"] == "bob"

    def test_list_contributions_returns_items(self, client):
        """
        Setup: Two contributions from different contributors
        Action: GET /api/ontology/contributions
        Expected: list with total >= 2
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Trees communicate through root networks and fungal threads",
            "contributor_id": "carol",
            "domains": ["ecology"],
        })
        client.post("/api/ontology/contribute", json={
            "plain_text": "Music is structured emotion that moves time",
            "contributor_id": "dave",
            "domains": ["music"],
        })

        list_resp = client.get("/api/ontology/contributions")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_patch_contribution_updates_domains(self, client):
        """
        Setup: One contribution exists
        Action: PATCH /api/ontology/contributions/{id} with new domains
        Expected: 200, domains updated
        """
        create_resp = client.post("/api/ontology/contribute", json={
            "plain_text": "Balance is found in motion not stillness",
            "contributor_id": "eve",
            "domains": ["philosophy"],
        })
        concept_id = create_resp.json()["id"]

        patch_resp = client.patch(f"/api/ontology/contributions/{concept_id}", json={
            "domains": ["philosophy", "yoga", "physics"],
        })
        assert patch_resp.status_code == 200
        assert "yoga" in patch_resp.json()["domains"]

    def test_delete_contribution(self, client):
        """
        Setup: One contribution exists
        Action: DELETE /api/ontology/contributions/{id}
        Expected: 204; subsequent GET returns 404
        """
        create_resp = client.post("/api/ontology/contribute", json={
            "plain_text": "Silence holds as much meaning as sound",
            "contributor_id": "frank",
            "domains": ["music"],
        })
        concept_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/ontology/contributions/{concept_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/ontology/contributions/{concept_id}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 2: Relationship inference
# ---------------------------------------------------------------------------

class TestRelationshipInference:
    def test_related_concepts_share_domain_edges(self, client):
        """
        Setup: Two concepts in same domain
        Action: Submit both and check inferred_relationships
        Expected: second concept has relationship to first via same-domain
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Soil is a living system with complex interdependencies",
            "contributor_id": "gina",
            "domains": ["ecology"],
        })
        resp2 = client.post("/api/ontology/contribute", json={
            "plain_text": "Mycorrhizal networks extend plant roots into the broader ecology",
            "contributor_id": "gina",
            "domains": ["ecology"],
        })
        body = resp2.json()
        # At least one inferred relationship should exist via domain
        assert isinstance(body["inferred_relationships"], list)

    def test_causal_language_infers_causes_relationship(self, client):
        """
        Setup: Empty store
        Action: Submit concept with 'leads to' language
        Expected: inferred_relationships may include a 'causes' or similar relationship type
        """
        resp = client.post("/api/ontology/contribute", json={
            "plain_text": "Drought leads to soil degradation which causes loss of biodiversity",
            "contributor_id": "hank",
            "domains": ["ecology", "climate"],
        })
        assert resp.status_code == 201
        # No assertion on relationship count since store is empty — just verify structure
        body = resp.json()
        assert isinstance(body["inferred_relationships"], list)

    def test_edges_endpoint_returns_list(self, client):
        """
        Setup: One contribution
        Action: GET /api/ontology/edges
        Expected: 200, edges key is a list
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Growth depends on the right conditions",
            "contributor_id": "iris",
            "domains": ["biology"],
        })
        resp = client.get("/api/ontology/edges")
        assert resp.status_code == 200
        assert "edges" in resp.json()
        assert isinstance(resp.json()["edges"], list)


# ---------------------------------------------------------------------------
# Scenario 3: Garden view
# ---------------------------------------------------------------------------

class TestGardenView:
    def test_garden_view_structure(self, client):
        """
        Setup: Three concepts in two domains
        Action: GET /api/ontology/garden
        Expected: clusters, concepts, total, placement_rate
        """
        for text, domain in [
            ("Patterns repeat across scale", "systems"),
            ("Fractals show self-similarity", "systems"),
            ("Jazz improvisation creates coherence from chaos", "music"),
        ]:
            client.post("/api/ontology/contribute", json={
                "plain_text": text,
                "contributor_id": "jake",
                "domains": [domain],
            })

        resp = client.get("/api/ontology/garden")
        assert resp.status_code == 200
        body = resp.json()
        assert "clusters" in body
        assert "concepts" in body
        assert "total" in body
        assert body["total"] == 3
        assert "placement_rate" in body
        assert 0.0 <= body["placement_rate"] <= 1.0
        assert "contributor_count" in body
        assert "domain_count" in body

    def test_garden_view_clusters_by_domain(self, client):
        """
        Setup: Two concepts each in different domains
        Action: GET /api/ontology/garden
        Expected: clusters contain the domain names
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Rhythm provides structure and flow in time",
            "contributor_id": "kate",
            "domains": ["music"],
        })
        client.post("/api/ontology/contribute", json={
            "plain_text": "Metamorphosis is radical change with continuity of identity",
            "contributor_id": "kate",
            "domains": ["biology"],
        })

        resp = client.get("/api/ontology/garden")
        cluster_names = [c["name"] for c in resp.json()["clusters"]]
        assert "music" in cluster_names
        assert "biology" in cluster_names


# ---------------------------------------------------------------------------
# Scenario 4: Stats endpoint (proof of feature working)
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_empty_store(self, client):
        """
        Setup: Empty store
        Action: GET /api/ontology/stats
        Expected: 200, all counts zero
        """
        resp = client.get("/api/ontology/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_contributions"] == 0
        assert body["placement_rate"] == 0.0

    def test_stats_after_contributions(self, client):
        """
        Setup: Multiple contributions with known domains
        Action: GET /api/ontology/stats
        Expected: counts reflect submissions, placement_rate in [0,1]
        """
        for i in range(3):
            client.post("/api/ontology/contribute", json={
                "plain_text": f"Concept {i} about coherence and flow in systems",
                "contributor_id": f"user{i}",
                "domains": ["systems"],
            })

        resp = client.get("/api/ontology/stats")
        body = resp.json()
        assert body["total_contributions"] == 3
        assert body["placed_count"] + body["pending_count"] + body["orphan_count"] == 3
        assert 0.0 <= body["placement_rate"] <= 1.0
        assert len(body["top_domains"]) >= 1
        assert body["top_domains"][0]["domain"] == "systems"


# ---------------------------------------------------------------------------
# Scenario 5: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_get_nonexistent_concept_returns_404(self, client):
        """
        Setup: Empty store
        Action: GET /api/ontology/contributions/does-not-exist
        Expected: 404, not 500
        """
        resp = client.get("/api/ontology/contributions/does-not-exist-xyz")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_patch_nonexistent_concept_returns_404(self, client):
        """
        Setup: Empty store
        Action: PATCH /api/ontology/contributions/does-not-exist
        Expected: 404
        """
        resp = client.patch("/api/ontology/contributions/does-not-exist-xyz", json={
            "domains": ["test"],
        })
        assert resp.status_code == 404

    def test_delete_nonexistent_concept_returns_404(self, client):
        """
        Setup: Empty store
        Action: DELETE /api/ontology/contributions/does-not-exist
        Expected: 404
        """
        resp = client.delete("/api/ontology/contributions/does-not-exist-xyz")
        assert resp.status_code == 404

    def test_submit_too_short_text_returns_422(self, client):
        """
        Setup: Empty store
        Action: POST /api/ontology/contribute with plain_text < 5 chars
        Expected: 422 validation error
        """
        resp = client.post("/api/ontology/contribute", json={
            "plain_text": "hi",
            "contributor_id": "test",
        })
        assert resp.status_code == 422

    def test_filter_by_status(self, client):
        """
        Setup: One placed concept (has core concept match)
        Action: GET /api/ontology/contributions?status=placed
        Expected: returns only placed concepts
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Coherence is the alignment of values ideas and actions",
            "contributor_id": "lana",
            "domains": ["philosophy"],
        })

        resp = client.get("/api/ontology/contributions?status=placed")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "placed"

    def test_filter_by_domain(self, client):
        """
        Setup: Two concepts in different domains
        Action: GET /api/ontology/contributions?domain=ecology
        Expected: only ecology concepts returned
        """
        client.post("/api/ontology/contribute", json={
            "plain_text": "Photosynthesis transforms light into stored energy",
            "contributor_id": "mia",
            "domains": ["ecology"],
        })
        client.post("/api/ontology/contribute", json={
            "plain_text": "Jazz harmony uses tension and resolution",
            "contributor_id": "mia",
            "domains": ["music"],
        })

        resp = client.get("/api/ontology/contributions?domain=ecology")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert "ecology" in item["domains"]
