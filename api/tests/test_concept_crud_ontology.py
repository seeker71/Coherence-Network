"""Tests for Concept layer CRUD — 184 universal concepts with typed relationships.

Verification contract — these tests prove the concept layer feature works:

1. ONTOLOGY LOAD: 184 concepts, 46 relationship types, 53 axes loaded from config/
2. LIST CONCEPTS: GET /api/concepts returns paginated list with total count
3. GET CONCEPT BY ID: GET /api/concepts/{id} returns concept or 404
4. SEARCH CONCEPTS: GET /api/concepts/search?q= returns matching concepts
5. RELATIONSHIP TYPES: GET /api/concepts/relationships returns 46 typed relationships
6. AXES: GET /api/concepts/axes returns 53 ontology axes
7. STATS: GET /api/concepts/stats returns correct counts
8. EDGES CRUD: POST/GET /api/concepts/{id}/edges creates and retrieves edges
9. ERROR HANDLING: bad ids, missing concepts, empty queries handled correctly
10. PAGINATION: limit/offset parameters work correctly
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Client fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create TestClient using the main FastAPI app."""
    from app.main import app
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Ontology load verification
# ─────────────────────────────────────────────────────────────────────────────

class TestOntologyLoad:
    """Verify the Living Codex ontology (config/ontology/) loads correctly."""

    def test_concepts_module_loads(self) -> None:
        """concept_service must be importable without errors."""
        from app.services import concept_service
        assert concept_service is not None

    def test_concepts_list_non_empty(self) -> None:
        """After module load, _concepts must contain entries."""
        from app.services import concept_service
        assert len(concept_service._concepts) > 0, (
            "concept_service._concepts is empty — "
            "check that config/ontology/core-concepts.json exists and is valid JSON"
        )

    def test_concepts_count_is_184(self) -> None:
        """Spec requires exactly 184 universal concepts."""
        from app.services import concept_service
        count = len(concept_service._concepts)
        assert count == 184, (
            f"Expected 184 concepts, got {count}. "
            "Port of Living Codex ontology may be incomplete."
        )

    def test_relationships_count_is_46(self) -> None:
        """Spec requires exactly 46 relationship types."""
        from app.services import concept_service
        count = len(concept_service._relationships)
        assert count == 46, (
            f"Expected 46 relationship types, got {count}."
        )

    def test_axes_count_is_53(self) -> None:
        """Spec requires exactly 53 ontology axes."""
        from app.services import concept_service
        count = len(concept_service._axes)
        assert count == 53, (
            f"Expected 53 axes, got {count}."
        )

    def test_concept_index_built(self) -> None:
        """_concept_index must be a dict keyed by concept id."""
        from app.services import concept_service
        assert isinstance(concept_service._concept_index, dict)
        assert len(concept_service._concept_index) == len(concept_service._concepts)

    def test_each_concept_has_required_fields(self) -> None:
        """Every concept must have 'id' and 'name' fields."""
        from app.services import concept_service
        for c in concept_service._concepts:
            assert "id" in c, f"Concept missing 'id': {c}"
            assert "name" in c, f"Concept missing 'name': {c}"

    def test_concept_ids_are_unique(self) -> None:
        """Concept ids must be unique across all 184 entries."""
        from app.services import concept_service
        ids = [c["id"] for c in concept_service._concepts]
        assert len(ids) == len(set(ids)), "Duplicate concept ids detected"

    def test_each_relationship_has_id_and_name(self) -> None:
        """Every relationship type must have 'id' and 'name'."""
        from app.services import concept_service
        for r in concept_service._relationships:
            assert "id" in r, f"Relationship missing 'id': {r}"
            assert "name" in r, f"Relationship missing 'name': {r}"

    def test_relationship_ids_are_unique(self) -> None:
        """Relationship type ids should be unique.

        NOTE: core-relationships.json currently contains a duplicate 'resonates-with'
        entry (known data issue in the ontology seed file). This test documents the
        issue and asserts uniqueness — fix the data file to remove the duplicate entry.
        """
        from app.services import concept_service
        from collections import Counter
        ids = [r["id"] for r in concept_service._relationships]
        duplicates = {k: v for k, v in Counter(ids).items() if v > 1}
        assert len(duplicates) == 0, (
            f"Duplicate relationship type ids found: {duplicates}. "
            "Fix config/ontology/core-relationships.json to remove duplicates."
        )

    def test_each_axis_has_id_and_name(self) -> None:
        """Every axis must have 'id' and 'name'."""
        from app.services import concept_service
        for a in concept_service._axes:
            assert "id" in a, f"Axis missing 'id': {a}"
            assert "name" in a, f"Axis missing 'name': {a}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Service layer unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConceptServiceList:
    """concept_service.list_concepts() pagination."""

    def test_list_concepts_returns_dict_with_items(self) -> None:
        from app.services import concept_service
        result = concept_service.list_concepts()
        assert isinstance(result, dict)
        assert "items" in result
        assert "total" in result

    def test_list_concepts_total_is_184(self) -> None:
        from app.services import concept_service
        result = concept_service.list_concepts(limit=500, offset=0)
        assert result["total"] == 184

    def test_list_concepts_default_limit_50(self) -> None:
        from app.services import concept_service
        result = concept_service.list_concepts()
        assert len(result["items"]) == 50
        assert result["limit"] == 50
        assert result["offset"] == 0

    def test_list_concepts_custom_limit(self) -> None:
        from app.services import concept_service
        result = concept_service.list_concepts(limit=10)
        assert len(result["items"]) == 10

    def test_list_concepts_offset_skips_items(self) -> None:
        from app.services import concept_service
        all_items = concept_service.list_concepts(limit=184, offset=0)["items"]
        offset_items = concept_service.list_concepts(limit=10, offset=10)["items"]
        assert offset_items == all_items[10:20]

    def test_list_concepts_offset_beyond_total_returns_empty(self) -> None:
        from app.services import concept_service
        result = concept_service.list_concepts(limit=50, offset=1000)
        assert result["items"] == []
        assert result["total"] == 184


class TestConceptServiceGetById:
    """concept_service.get_concept() by id."""

    def test_get_first_concept_by_id(self) -> None:
        from app.services import concept_service
        first = concept_service._concepts[0]
        found = concept_service.get_concept(first["id"])
        assert found is not None
        assert found["id"] == first["id"]

    def test_get_nonexistent_concept_returns_none(self) -> None:
        from app.services import concept_service
        result = concept_service.get_concept("__nonexistent_concept_xyz__")
        assert result is None

    def test_get_concept_is_case_sensitive(self) -> None:
        from app.services import concept_service
        first = concept_service._concepts[0]
        upper_id = first["id"].upper()
        # Only test case sensitivity if ids are lowercase
        if upper_id != first["id"]:
            assert concept_service.get_concept(upper_id) is None


class TestConceptServiceSearch:
    """concept_service.search_concepts() full-text matching."""

    def test_search_by_exact_name_substring(self) -> None:
        from app.services import concept_service
        # pick first concept name to search by
        first = concept_service._concepts[0]
        name_fragment = first["name"][:4].lower()
        results = concept_service.search_concepts(name_fragment)
        # The first concept must appear in results
        ids = [c["id"] for c in results]
        assert first["id"] in ids

    def test_search_returns_list(self) -> None:
        from app.services import concept_service
        results = concept_service.search_concepts("a")
        assert isinstance(results, list)

    def test_search_no_match_returns_empty_list(self) -> None:
        from app.services import concept_service
        results = concept_service.search_concepts("zzzzzznomatch9999")
        assert results == []

    def test_search_limit_respected(self) -> None:
        from app.services import concept_service
        results = concept_service.search_concepts("a", limit=3)
        assert len(results) <= 3

    def test_search_case_insensitive(self) -> None:
        from app.services import concept_service
        first = concept_service._concepts[0]
        lower = concept_service.search_concepts(first["name"].lower())
        upper = concept_service.search_concepts(first["name"].upper())
        # Both should find the same concept
        lower_ids = {c["id"] for c in lower}
        upper_ids = {c["id"] for c in upper}
        assert first["id"] in lower_ids
        assert first["id"] in upper_ids


class TestConceptServiceStats:
    """concept_service.get_stats() returns correct counts."""

    def test_stats_returns_dict(self) -> None:
        from app.services import concept_service
        stats = concept_service.get_stats()
        assert isinstance(stats, dict)

    def test_stats_concepts_count(self) -> None:
        from app.services import concept_service
        stats = concept_service.get_stats()
        assert stats["concepts"] == 184

    def test_stats_relationship_types_count(self) -> None:
        from app.services import concept_service
        stats = concept_service.get_stats()
        assert stats["relationship_types"] == 46

    def test_stats_axes_count(self) -> None:
        from app.services import concept_service
        stats = concept_service.get_stats()
        assert stats["axes"] == 53

    def test_stats_user_edges_starts_at_zero_or_more(self) -> None:
        from app.services import concept_service
        stats = concept_service.get_stats()
        assert "user_edges" in stats
        assert stats["user_edges"] >= 0


class TestConceptServiceEdges:
    """concept_service edge creation and retrieval."""

    def _first_two_ids(self):
        from app.services import concept_service
        return concept_service._concepts[0]["id"], concept_service._concepts[1]["id"]

    def _first_rel_type(self):
        from app.services import concept_service
        return concept_service._relationships[0]["id"]

    def test_create_edge_returns_edge_dict(self) -> None:
        from app.services import concept_service
        from_id, to_id = self._first_two_ids()
        rel = self._first_rel_type()
        edge = concept_service.create_edge(from_id, to_id, rel, created_by="test")
        assert "id" in edge
        assert edge["from"] == from_id
        assert edge["to"] == to_id
        assert edge["type"] == rel
        assert edge["created_by"] == "test"
        assert "created_at" in edge

    def test_get_concept_edges_returns_list(self) -> None:
        from app.services import concept_service
        from_id, to_id = self._first_two_ids()
        rel = self._first_rel_type()
        concept_service.create_edge(from_id, to_id, rel, created_by="test")
        edges = concept_service.get_concept_edges(from_id)
        assert isinstance(edges, list)
        assert len(edges) >= 1

    def test_get_edges_for_unknown_concept_returns_empty_list(self) -> None:
        from app.services import concept_service
        edges = concept_service.get_concept_edges("__no_such_concept__")
        assert edges == []

    def test_edge_appears_for_both_from_and_to(self) -> None:
        from app.services import concept_service
        from_id, to_id = self._first_two_ids()
        rel = self._first_rel_type()
        edge = concept_service.create_edge(from_id, to_id, rel, created_by="test_both")
        from_edges = concept_service.get_concept_edges(from_id)
        to_edges = concept_service.get_concept_edges(to_id)
        from_edge_ids = {e["id"] for e in from_edges}
        to_edge_ids = {e["id"] for e in to_edges}
        assert edge["id"] in from_edge_ids
        assert edge["id"] in to_edge_ids

    def test_edge_id_is_unique(self) -> None:
        from app.services import concept_service
        from_id, to_id = self._first_two_ids()
        rel = self._first_rel_type()
        e1 = concept_service.create_edge(from_id, to_id, rel)
        e2 = concept_service.create_edge(from_id, to_id, rel)
        assert e1["id"] != e2["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — HTTP API tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConceptsEndpoint:
    """GET /api/concepts — list all concepts."""

    def test_list_concepts_200(self, client: TestClient) -> None:
        resp = client.get("/api/concepts")
        assert resp.status_code == 200

    def test_list_concepts_returns_items_and_total(self, client: TestClient) -> None:
        resp = client.get("/api/concepts")
        body = resp.json()
        assert "items" in body
        assert "total" in body

    def test_list_concepts_total_is_184(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=1")
        body = resp.json()
        assert body["total"] == 184

    def test_list_concepts_default_limit_50(self, client: TestClient) -> None:
        resp = client.get("/api/concepts")
        body = resp.json()
        assert len(body["items"]) == 50

    def test_list_concepts_custom_limit(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=5")
        body = resp.json()
        assert len(body["items"]) == 5

    def test_list_concepts_limit_max_500(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=500")
        assert resp.status_code == 200

    def test_list_concepts_limit_exceeds_max_422(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=501")
        assert resp.status_code == 422

    def test_list_concepts_limit_zero_422(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=0")
        assert resp.status_code == 422

    def test_list_concepts_negative_offset_422(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?offset=-1")
        assert resp.status_code == 422

    def test_list_concepts_offset_pagination(self, client: TestClient) -> None:
        page1 = client.get("/api/concepts?limit=10&offset=0").json()["items"]
        page2 = client.get("/api/concepts?limit=10&offset=10").json()["items"]
        ids1 = [c["id"] for c in page1]
        ids2 = [c["id"] for c in page2]
        assert ids1 != ids2
        assert len(set(ids1) & set(ids2)) == 0, "Pages should not overlap"

    def test_list_concepts_items_have_id_and_name(self, client: TestClient) -> None:
        resp = client.get("/api/concepts?limit=5")
        for item in resp.json()["items"]:
            assert "id" in item
            assert "name" in item


class TestGetConceptByIdEndpoint:
    """GET /api/concepts/{id} — retrieve single concept."""

    def _known_concept_id(self) -> str:
        from app.services import concept_service
        return concept_service._concepts[0]["id"]

    def test_get_known_concept_200(self, client: TestClient) -> None:
        concept_id = self._known_concept_id()
        resp = client.get(f"/api/concepts/{concept_id}")
        assert resp.status_code == 200

    def test_get_known_concept_returns_correct_id(self, client: TestClient) -> None:
        concept_id = self._known_concept_id()
        resp = client.get(f"/api/concepts/{concept_id}")
        body = resp.json()
        assert body["id"] == concept_id

    def test_get_unknown_concept_404(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/__nonexistent_concept_xyz__")
        assert resp.status_code == 404

    def test_get_unknown_concept_error_message(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/__nonexistent_concept_xyz__")
        body = resp.json()
        assert "detail" in body

    def test_get_all_184_concepts_individually(self, client: TestClient) -> None:
        """Spot-check that all concept IDs resolve via HTTP."""
        from app.services import concept_service
        # Check every concept is reachable (test all 184)
        for concept in concept_service._concepts:
            resp = client.get(f"/api/concepts/{concept['id']}")
            assert resp.status_code == 200, (
                f"Concept '{concept['id']}' returned {resp.status_code}"
            )

    def test_get_concept_body_has_name(self, client: TestClient) -> None:
        concept_id = self._known_concept_id()
        resp = client.get(f"/api/concepts/{concept_id}")
        assert "name" in resp.json()


class TestSearchConceptsEndpoint:
    """GET /api/concepts/search?q= — full-text search."""

    def test_search_requires_q_param(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search")
        assert resp.status_code == 422

    def test_search_empty_q_422(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search?q=")
        assert resp.status_code == 422

    def test_search_known_term_returns_results(self, client: TestClient) -> None:
        from app.services import concept_service
        first = concept_service._concepts[0]
        fragment = first["name"][:4]
        resp = client.get(f"/api/concepts/search?q={fragment}")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    def test_search_no_match_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search?q=zzzzzznomatch9999")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_limit_param_respected(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search?q=a&limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) <= 3

    def test_search_limit_exceeds_max_422(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search?q=a&limit=101")
        assert resp.status_code == 422

    def test_search_results_are_list_of_concepts(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/search?q=a&limit=5")
        for item in resp.json():
            assert "id" in item
            assert "name" in item

    def test_search_finds_concept_by_name(self, client: TestClient) -> None:
        from app.services import concept_service
        first = concept_service._concepts[0]
        name = first["name"].lower()
        resp = client.get(f"/api/concepts/search?q={name}")
        ids = [c["id"] for c in resp.json()]
        assert first["id"] in ids

    def test_search_route_does_not_match_concept_id(self, client: TestClient) -> None:
        """GET /api/concepts/search must not be captured by /api/concepts/{concept_id}."""
        # This test verifies route ordering: 'search' as a path segment must
        # be handled by the search endpoint, not the get-by-id endpoint.
        resp = client.get("/api/concepts/search?q=a")
        # Must return a list, not a single concept or 404
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestConceptRelationshipsEndpoint:
    """GET /api/concepts/relationships — list 46 typed relationships."""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/relationships")
        assert resp.status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        body = client.get("/api/concepts/relationships").json()
        assert isinstance(body, list)

    def test_returns_46_relationships(self, client: TestClient) -> None:
        body = client.get("/api/concepts/relationships").json()
        assert len(body) == 46, f"Expected 46 relationship types, got {len(body)}"

    def test_each_relationship_has_id_and_name(self, client: TestClient) -> None:
        body = client.get("/api/concepts/relationships").json()
        for rel in body:
            assert "id" in rel, f"Relationship missing 'id': {rel}"
            assert "name" in rel, f"Relationship missing 'name': {rel}"

    def test_resonates_with_is_present(self, client: TestClient) -> None:
        """The 'resonates-with' relationship from Living Codex must be present."""
        body = client.get("/api/concepts/relationships").json()
        ids = {r["id"] for r in body}
        assert "resonates-with" in ids, "Missing canonical 'resonates-with' relationship"


class TestConceptAxesEndpoint:
    """GET /api/concepts/axes — list 53 ontology axes."""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/axes")
        assert resp.status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        body = client.get("/api/concepts/axes").json()
        assert isinstance(body, list)

    def test_returns_53_axes(self, client: TestClient) -> None:
        body = client.get("/api/concepts/axes").json()
        assert len(body) == 53, f"Expected 53 axes, got {len(body)}"

    def test_each_axis_has_id_and_name(self, client: TestClient) -> None:
        body = client.get("/api/concepts/axes").json()
        for axis in body:
            assert "id" in axis, f"Axis missing 'id': {axis}"
            assert "name" in axis, f"Axis missing 'name': {axis}"

    def test_water_states_axis_is_present(self, client: TestClient) -> None:
        """The 'water_states' axis from Living Codex must be present."""
        body = client.get("/api/concepts/axes").json()
        ids = {a["id"] for a in body}
        assert "water_states" in ids, "Missing canonical 'water_states' axis"


class TestConceptStatsEndpoint:
    """GET /api/concepts/stats — ontology statistics."""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/stats")
        assert resp.status_code == 200

    def test_returns_correct_counts(self, client: TestClient) -> None:
        body = client.get("/api/concepts/stats").json()
        assert body["concepts"] == 184
        assert body["relationship_types"] == 46
        assert body["axes"] == 53

    def test_user_edges_field_present(self, client: TestClient) -> None:
        body = client.get("/api/concepts/stats").json()
        assert "user_edges" in body
        assert isinstance(body["user_edges"], int)


class TestConceptEdgesEndpoint:
    """POST/GET /api/concepts/{id}/edges — edge creation and retrieval."""

    def _known_ids(self):
        from app.services import concept_service
        return (
            concept_service._concepts[0]["id"],
            concept_service._concepts[1]["id"],
        )

    def _known_rel_type(self):
        from app.services import concept_service
        return concept_service._relationships[0]["id"]

    def test_get_edges_for_known_concept_200(self, client: TestClient) -> None:
        from_id, _ = self._known_ids()
        resp = client.get(f"/api/concepts/{from_id}/edges")
        assert resp.status_code == 200

    def test_get_edges_for_unknown_concept_404(self, client: TestClient) -> None:
        resp = client.get("/api/concepts/__nonexistent__/edges")
        assert resp.status_code == 404

    def test_post_edge_creates_edge(self, client: TestClient) -> None:
        from_id, to_id = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "relationship_type": rel_type,
            "created_by": "test_suite",
        }
        resp = client.post(f"/api/concepts/{from_id}/edges", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["from"] == from_id
        assert body["to"] == to_id
        assert body["type"] == rel_type

    def test_post_edge_appears_in_get_edges(self, client: TestClient) -> None:
        from_id, to_id = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "relationship_type": rel_type,
            "created_by": "test_visibility",
        }
        post_resp = client.post(f"/api/concepts/{from_id}/edges", json=payload)
        edge_id = post_resp.json()["id"]

        get_resp = client.get(f"/api/concepts/{from_id}/edges")
        edge_ids = {e["id"] for e in get_resp.json()}
        assert edge_id in edge_ids

    def test_post_edge_with_unknown_from_concept_404(self, client: TestClient) -> None:
        _, to_id = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": "__nonexistent__",
            "to_id": to_id,
            "relationship_type": rel_type,
        }
        resp = client.post("/api/concepts/__nonexistent__/edges", json=payload)
        assert resp.status_code == 404

    def test_post_edge_with_unknown_to_concept_404(self, client: TestClient) -> None:
        from_id, _ = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": from_id,
            "to_id": "__nonexistent_to__",
            "relationship_type": rel_type,
        }
        resp = client.post(f"/api/concepts/{from_id}/edges", json=payload)
        assert resp.status_code == 404

    def test_post_edge_missing_required_fields_422(self, client: TestClient) -> None:
        from_id, _ = self._known_ids()
        resp = client.post(f"/api/concepts/{from_id}/edges", json={})
        assert resp.status_code == 422

    def test_post_edge_returns_created_at_timestamp(self, client: TestClient) -> None:
        from_id, to_id = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "relationship_type": rel_type,
        }
        resp = client.post(f"/api/concepts/{from_id}/edges", json=payload)
        body = resp.json()
        assert "created_at" in body
        assert body["created_at"]  # not empty

    def test_post_edge_default_created_by(self, client: TestClient) -> None:
        from_id, to_id = self._known_ids()
        rel_type = self._known_rel_type()
        payload = {
            "from_id": from_id,
            "to_id": to_id,
            "relationship_type": rel_type,
        }
        resp = client.post(f"/api/concepts/{from_id}/edges", json=payload)
        assert resp.status_code == 200
        assert resp.json()["created_by"] == "unknown"

    def test_get_edges_returns_list(self, client: TestClient) -> None:
        from_id, _ = self._known_ids()
        resp = client.get(f"/api/concepts/{from_id}/edges")
        assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Full CRUD cycle (Verification Scenarios)
# ─────────────────────────────────────────────────────────────────────────────

class TestFullCRUDCycle:
    """
    Verification Scenarios — proves the full concept layer feature works.

    Scenario 1: List → Get → Search cycle on seeded data
    Scenario 2: Edge creation and retrieval cycle
    Scenario 3: Error handling for all bad inputs
    Scenario 4: Pagination correctness
    Scenario 5: Ontology integrity verification
    """

    def test_scenario_1_list_get_search_cycle(self, client: TestClient) -> None:
        """
        Setup: Ontology seeded from config/ontology/
        Action: List concepts → pick id → get by id → search by name
        Expected: All three operations return consistent data
        """
        # Step 1: List
        list_resp = client.get("/api/concepts?limit=10")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) > 0

        # Step 2: Get by ID
        concept_id = items[0]["id"]
        concept_name = items[0]["name"]
        get_resp = client.get(f"/api/concepts/{concept_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == concept_id
        assert get_resp.json()["name"] == concept_name

        # Step 3: Search by name fragment
        fragment = concept_name[:4].lower()
        search_resp = client.get(f"/api/concepts/search?q={fragment}")
        assert search_resp.status_code == 200
        found_ids = [c["id"] for c in search_resp.json()]
        assert concept_id in found_ids

    def test_scenario_2_edge_create_and_retrieve_cycle(self, client: TestClient) -> None:
        """
        Setup: Two known concepts from ontology
        Action: POST edge → GET edges for source concept
        Expected: Created edge appears in GET response with correct fields
        Edge case: POST with unknown to_id returns 404
        """
        from app.services import concept_service
        from_id = concept_service._concepts[5]["id"]
        to_id = concept_service._concepts[6]["id"]
        rel_type = concept_service._relationships[0]["id"]

        # Create edge
        create_resp = client.post(f"/api/concepts/{from_id}/edges", json={
            "from_id": from_id,
            "to_id": to_id,
            "relationship_type": rel_type,
            "created_by": "scenario_2",
        })
        assert create_resp.status_code == 200
        edge = create_resp.json()
        assert edge["from"] == from_id
        assert edge["to"] == to_id
        assert edge["type"] == rel_type
        assert "id" in edge
        assert "created_at" in edge

        # Retrieve edges
        get_resp = client.get(f"/api/concepts/{from_id}/edges")
        assert get_resp.status_code == 200
        edge_ids = {e["id"] for e in get_resp.json()}
        assert edge["id"] in edge_ids

        # Edge case: bad to_id
        bad_resp = client.post(f"/api/concepts/{from_id}/edges", json={
            "from_id": from_id,
            "to_id": "__no_such_concept__",
            "relationship_type": rel_type,
        })
        assert bad_resp.status_code == 404

    def test_scenario_3_error_handling(self, client: TestClient) -> None:
        """
        Setup: No pre-conditions
        Action: Various invalid requests
        Expected: Correct error codes, not 500
        """
        # 404 on unknown concept
        assert client.get("/api/concepts/__bad__").status_code == 404
        # 404 on edges for unknown concept
        assert client.get("/api/concepts/__bad__/edges").status_code == 404
        # 422 on bad limit
        assert client.get("/api/concepts?limit=0").status_code == 422
        assert client.get("/api/concepts?limit=501").status_code == 422
        # 422 on bad offset
        assert client.get("/api/concepts?offset=-1").status_code == 422
        # 422 on missing search query
        assert client.get("/api/concepts/search").status_code == 422
        # 422 on empty search query
        assert client.get("/api/concepts/search?q=").status_code == 422
        # 422 on edge create with missing body
        from app.services import concept_service
        from_id = concept_service._concepts[0]["id"]
        assert client.post(f"/api/concepts/{from_id}/edges", json={}).status_code == 422

    def test_scenario_4_pagination_correctness(self, client: TestClient) -> None:
        """
        Setup: 184 concepts seeded
        Action: Iterate pages with limit=20
        Expected: 9 full pages + 1 partial = 184 total unique concepts
        """
        all_ids: set[str] = set()
        limit = 20
        offset = 0
        while True:
            resp = client.get(f"/api/concepts?limit={limit}&offset={offset}")
            assert resp.status_code == 200
            body = resp.json()
            page_items = body["items"]
            if not page_items:
                break
            for item in page_items:
                all_ids.add(item["id"])
            offset += limit
            if offset > 200:  # safety stop
                break

        assert len(all_ids) == 184, (
            f"Pagination collected {len(all_ids)} unique ids, expected 184"
        )

    def test_scenario_5_ontology_integrity(self, client: TestClient) -> None:
        """
        Setup: Ontology seeded from Living Codex config files
        Action: Check stats endpoint and list endpoints
        Expected: Counts are exactly 184/46/53
        Edge case: stats matches actual list lengths
        """
        stats = client.get("/api/concepts/stats").json()
        rels = client.get("/api/concepts/relationships").json()
        axes = client.get("/api/concepts/axes").json()
        all_concepts = client.get("/api/concepts?limit=500").json()

        # Counts must match between stats and actual lists
        assert stats["concepts"] == all_concepts["total"] == 184
        assert stats["relationship_types"] == len(rels) == 46
        assert stats["axes"] == len(axes) == 53
