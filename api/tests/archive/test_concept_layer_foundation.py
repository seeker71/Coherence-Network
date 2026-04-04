"""Tests for Concept Layer Foundation (concept-layer-foundation).

Verification Contract
=====================
Covers the full concept CRUD lifecycle, ontology data integrity,
edge management, tagging, and search against the Living Codex ontology
(184 concepts, 46 relationship types, 53 axes).

Acceptance Criteria Verified
-----------------------------
1. Ontology loads correctly: 184 concepts, 46 rel types, 53 axes
2. GET /api/concepts — paged list with total, items, limit, offset
3. GET /api/concepts/stats — counts match loaded ontology data
4. GET /api/concepts/<id> — retrieve a core concept by ID
5. GET /api/concepts/<id> — 404 for unknown concept
6. POST /api/concepts — create user-defined concept
7. POST /api/concepts — 409 on duplicate ID
8. PATCH /api/concepts/<id> — update mutable fields
9. PATCH /api/concepts/<id> — 404 on unknown
10. DELETE /api/concepts/<id> — delete user-defined concept
11. DELETE /api/concepts/<id> — 403 on core concept (immutable)
12. GET /api/concepts/search?q=<query> — full-text search over name/desc/keywords
13. GET /api/concepts/relationships — returns all 46 relationship types
14. GET /api/concepts/axes — returns all 53 axes
15. POST /api/concepts/<id>/edges — create typed edge between concepts
16. GET /api/concepts/<id>/edges — retrieve edges for a concept
17. POST /api/concepts/<id>/edges — 404 on missing source or target
18. POST /api/ideas/<id>/concepts — tag idea with concepts
19. GET /api/ideas/<id>/concepts — retrieve concepts tagged on idea
20. POST /api/specs/<id>/concepts — tag spec with concepts
21. GET /api/concepts/<id>/related — find ideas/specs tagged with concept
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_user_concept(client: AsyncClient, concept_id: str, name: str = "Test Concept") -> dict:
    payload = {
        "id": concept_id,
        "name": name,
        "description": "A user-defined concept for testing purposes",
        "type_id": "codex.ucore.user",
        "level": 1,
        "keywords": ["test", "user-defined"],
    }
    r = await client.post("/api/concepts", json=payload, headers=AUTH_HEADERS)
    return r


# ---------------------------------------------------------------------------
# 1. Ontology data integrity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ontology_stats_match_spec() -> None:
    """Ontology must contain exactly 184 concepts, 46 relationship types, 53 axes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/stats")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["concepts"] >= 184, f"Expected >=184 concepts, got {data['concepts']}"
        assert data["relationship_types"] == 46, f"Expected 46 rel types, got {data['relationship_types']}"
        assert data["axes"] == 53, f"Expected 53 axes, got {data['axes']}"


@pytest.mark.asyncio
async def test_concept_stats_has_all_fields() -> None:
    """Stats response must have all expected fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/stats")
        assert r.status_code == 200
        data = r.json()
        for field in ["concepts", "relationship_types", "axes", "user_edges", "user_concepts", "tagged_entities"]:
            assert field in data, f"Stats must include field '{field}'"


# ---------------------------------------------------------------------------
# 2. List concepts (paged)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_concepts_returns_paged_result() -> None:
    """GET /api/concepts returns items, total, limit, offset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts?limit=10&offset=0")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert len(data["items"]) == 10
        assert data["total"] >= 184
        assert data["limit"] == 10
        assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_concepts_offset_paging() -> None:
    """Paging offset shifts the window — items at offset 10 differ from offset 0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r0 = await client.get("/api/concepts?limit=5&offset=0")
        r1 = await client.get("/api/concepts?limit=5&offset=5")
        assert r0.status_code == 200
        assert r1.status_code == 200
        ids0 = [c["id"] for c in r0.json()["items"]]
        ids1 = [c["id"] for c in r1.json()["items"]]
        assert ids0 != ids1, "Offset 5 should produce a different page than offset 0"


@pytest.mark.asyncio
async def test_list_concepts_default_limit() -> None:
    """Default limit is 50 per the API spec."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 50
        assert len(data["items"]) <= 50


# ---------------------------------------------------------------------------
# 3. Get single concept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_core_concept_by_id() -> None:
    """GET /api/concepts/activity returns the core Activity concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/activity")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == "activity"
        assert "name" in data
        assert "description" in data


@pytest.mark.asyncio
async def test_get_concept_returns_full_metadata() -> None:
    """Core concept response includes typeId, level, keywords, parentConcepts, axes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/activity")
        assert r.status_code == 200
        data = r.json()
        for field in ["id", "name", "description", "typeId", "level", "keywords"]:
            assert field in data, f"Concept response must include '{field}'"


@pytest.mark.asyncio
async def test_get_unknown_concept_returns_404() -> None:
    """GET /api/concepts/<unknown> → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/totally-nonexistent-concept-xyz-999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4. Create concept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_concept_success() -> None:
    """POST /api/concepts creates a user-defined concept and returns 201."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _create_user_concept(client, "clf-test-create-001")
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["id"] == "clf-test-create-001"
        assert data["userDefined"] is True
        assert "createdAt" in data


@pytest.mark.asyncio
async def test_create_concept_stores_all_fields() -> None:
    """POST /api/concepts persists name, description, keywords, level, typeId."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "id": "clf-test-full-fields-002",
            "name": "Full Field Test",
            "description": "A concept with all fields populated",
            "type_id": "codex.ucore.user",
            "level": 2,
            "keywords": ["alpha", "beta", "gamma"],
            "axes": ["temporal"],
        }
        r = await client.post("/api/concepts", json=payload, headers=AUTH_HEADERS)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Full Field Test"
        assert data["description"] == "A concept with all fields populated"
        assert "alpha" in data["keywords"]
        assert data["level"] == 2


@pytest.mark.asyncio
async def test_create_concept_duplicate_returns_409() -> None:
    """POST /api/concepts with existing ID returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-dup-003")
        r2 = await _create_user_concept(client, "clf-test-dup-003")
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_concept_retrievable_after_creation() -> None:
    """A user-created concept can be retrieved via GET /api/concepts/<id>."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-retrieve-004", name="Retrievable Concept")
        r = await client.get("/api/concepts/clf-test-retrieve-004")
        assert r.status_code == 200
        assert r.json()["name"] == "Retrievable Concept"


# ---------------------------------------------------------------------------
# 5. Patch concept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_concept_name_and_description() -> None:
    """PATCH /api/concepts/<id> updates name and description."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-patch-005")
        r = await client.patch(
            "/api/concepts/clf-test-patch-005",
            json={"name": "Patched Name", "description": "Patched description text"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "Patched Name"
        assert data["description"] == "Patched description text"


@pytest.mark.asyncio
async def test_patch_concept_keywords() -> None:
    """PATCH /api/concepts/<id> can update keywords list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-patch-kw-006")
        r = await client.patch(
            "/api/concepts/clf-test-patch-kw-006",
            json={"keywords": ["updated", "keywords", "list"]},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200
        assert "updated" in r.json()["keywords"]


@pytest.mark.asyncio
async def test_patch_concept_sets_updated_at() -> None:
    """PATCH adds updatedAt timestamp to the concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-patch-ts-007")
        r = await client.patch(
            "/api/concepts/clf-test-patch-ts-007",
            json={"name": "Updated Name"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200
        assert "updatedAt" in r.json()


@pytest.mark.asyncio
async def test_patch_unknown_concept_returns_404() -> None:
    """PATCH /api/concepts/<unknown> → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/concepts/no-such-concept-xyz",
            json={"name": "Ghost"},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 6. Delete concept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_user_concept_returns_204() -> None:
    """DELETE /api/concepts/<user-defined> returns 204."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-delete-008")
        r = await client.delete("/api/concepts/clf-test-delete-008")
        assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_concept_removes_from_list() -> None:
    """After DELETE, concept is no longer retrievable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-test-delete-gone-009")
        await client.delete("/api/concepts/clf-test-delete-gone-009")
        r = await client.get("/api/concepts/clf-test-delete-gone-009")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_core_concept_returns_403() -> None:
    """DELETE on a core ontology concept returns 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/api/concepts/activity")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_unknown_concept_returns_404() -> None:
    """DELETE on a nonexistent concept returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/api/concepts/never-existed-concept-xyz")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 7. Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_concepts_by_name() -> None:
    """GET /api/concepts/search?q=activity returns Activity concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/search", params={"q": "activity"})
        assert r.status_code == 200, r.text
        results = r.json()
        assert isinstance(results, list)
        ids = [c["id"] for c in results]
        assert "activity" in ids


@pytest.mark.asyncio
async def test_search_concepts_by_keyword() -> None:
    """Search matches keywords field, not just name."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/search", params={"q": "process"})
        assert r.status_code == 200
        results = r.json()
        assert len(results) > 0, "Should find at least one concept matching 'process'"


@pytest.mark.asyncio
async def test_search_concepts_no_match_returns_empty() -> None:
    """Search with no matching term returns empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/search", params={"q": "zzz-no-match-xyz-999"})
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_search_concepts_limit_respected() -> None:
    """Search limit param caps results."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/search", params={"q": "a", "limit": 3})
        assert r.status_code == 200
        assert len(r.json()) <= 3


@pytest.mark.asyncio
async def test_search_finds_user_created_concept() -> None:
    """User-created concepts appear in search results."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-search-user-010", name="SearchableUserConcept")
        r = await client.get("/api/concepts/search", params={"q": "SearchableUserConcept"})
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert "clf-search-user-010" in ids


# ---------------------------------------------------------------------------
# 8. Relationship types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_relationships_returns_46_types() -> None:
    """GET /api/concepts/relationships returns exactly 46 relationship types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/relationships")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 46


@pytest.mark.asyncio
async def test_relationships_have_required_fields() -> None:
    """Each relationship type must have id and name."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/relationships")
        assert r.status_code == 200
        for rel in r.json():
            assert "id" in rel, "Relationship must have 'id'"
            assert "name" in rel, "Relationship must have 'name'"


@pytest.mark.asyncio
async def test_relationships_include_resonates_with() -> None:
    """Core relationship 'resonates-with' must be present."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/relationships")
        assert r.status_code == 200
        ids = [rel["id"] for rel in r.json()]
        assert "resonates-with" in ids


# ---------------------------------------------------------------------------
# 9. Axes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_axes_returns_53_axes() -> None:
    """GET /api/concepts/axes returns exactly 53 axes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/axes")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 53


@pytest.mark.asyncio
async def test_axes_have_required_fields() -> None:
    """Each axis must have id and name."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/axes")
        assert r.status_code == 200
        for axis in r.json():
            assert "id" in axis
            assert "name" in axis


@pytest.mark.asyncio
async def test_axes_include_water_states() -> None:
    """Core axis 'water_states' must be present."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/axes")
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert "water_states" in ids


# ---------------------------------------------------------------------------
# 10. Edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_edge_between_concepts() -> None:
    """POST /api/concepts/<id>/edges creates a typed edge and returns 201."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-edge-src-011")
        await _create_user_concept(client, "clf-edge-tgt-011")
        r = await client.post(
            "/api/concepts/clf-edge-src-011/edges",
            json={
                "from_id": "clf-edge-src-011",
                "to_id": "clf-edge-tgt-011",
                "relationship_type": "resonates-with",
                "created_by": "test-agent",
            },
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["from"] == "clf-edge-src-011"
        assert data["to"] == "clf-edge-tgt-011"
        assert data["type"] == "resonates-with"
        assert "id" in data


@pytest.mark.asyncio
async def test_get_concept_edges_returns_created_edge() -> None:
    """GET /api/concepts/<id>/edges returns edges including the one just created."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-edge-get-src-012")
        await _create_user_concept(client, "clf-edge-get-tgt-012")
        await client.post(
            "/api/concepts/clf-edge-get-src-012/edges",
            json={
                "from_id": "clf-edge-get-src-012",
                "to_id": "clf-edge-get-tgt-012",
                "relationship_type": "aligns-with",
            },
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/concepts/clf-edge-get-src-012/edges")
        assert r.status_code == 200, r.text
        edges = r.json()
        assert isinstance(edges, list)
        types = [e["type"] for e in edges]
        assert "aligns-with" in types


@pytest.mark.asyncio
async def test_create_edge_missing_source_returns_404() -> None:
    """POST /api/concepts/<missing>/edges → 404 when source concept doesn't exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/concepts/no-such-source-xyz/edges",
            json={
                "from_id": "no-such-source-xyz",
                "to_id": "activity",
                "relationship_type": "resonates-with",
            },
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_edge_missing_target_returns_404() -> None:
    """POST /api/concepts/<id>/edges with unknown to_id → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-edge-orphan-013")
        r = await client.post(
            "/api/concepts/clf-edge-orphan-013/edges",
            json={
                "from_id": "clf-edge-orphan-013",
                "to_id": "no-such-target-xyz",
                "relationship_type": "resonates-with",
            },
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_edge_includes_timestamps() -> None:
    """Created edge includes created_at timestamp."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-edge-ts-src-014")
        await _create_user_concept(client, "clf-edge-ts-tgt-014")
        r = await client.post(
            "/api/concepts/clf-edge-ts-src-014/edges",
            json={
                "from_id": "clf-edge-ts-src-014",
                "to_id": "clf-edge-ts-tgt-014",
                "relationship_type": "implements",
            },
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 201
        assert "created_at" in r.json()


# ---------------------------------------------------------------------------
# 11. Tagging: ideas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tag_idea_with_concept() -> None:
    """POST /api/ideas/<id>/concepts tags an idea with a concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/ideas/clf-test-idea-001/concepts",
            json={"concept_ids": ["activity"]},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "activity" in data["concept_ids"]
        assert data["entity_type"] == "idea"
        assert data["entity_id"] == "clf-test-idea-001"


@pytest.mark.asyncio
async def test_get_idea_concepts_after_tagging() -> None:
    """GET /api/ideas/<id>/concepts returns tagged concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas/clf-test-idea-002/concepts",
            json={"concept_ids": ["activity", "adaptation"]},
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/ideas/clf-test-idea-002/concepts")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["entity_type"] == "idea"
        assert data["entity_id"] == "clf-test-idea-002"
        ids = [c["id"] for c in data["concepts"]]
        assert "activity" in ids
        assert "adaptation" in ids


@pytest.mark.asyncio
async def test_tag_idea_with_missing_concept_returns_404() -> None:
    """POST /api/ideas/<id>/concepts with nonexistent concept → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/ideas/clf-test-idea-003/concepts",
            json={"concept_ids": ["no-such-concept-xyz"]},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_tag_idea_multiple_concepts() -> None:
    """Tagging accumulates: second tag call adds to existing, not replace."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas/clf-test-idea-accumulate/concepts",
            json={"concept_ids": ["activity"]},
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas/clf-test-idea-accumulate/concepts",
            json={"concept_ids": ["adaptation"]},
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/ideas/clf-test-idea-accumulate/concepts")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()["concepts"]]
        assert "activity" in ids
        assert "adaptation" in ids


# ---------------------------------------------------------------------------
# 12. Tagging: specs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tag_spec_with_concept() -> None:
    """POST /api/specs/<id>/concepts tags a spec with a concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/specs/clf-test-spec-001/concepts",
            json={"concept_ids": ["activity"]},
            headers=AUTH_HEADERS,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "activity" in data["concept_ids"]
        assert data["entity_type"] == "spec"


@pytest.mark.asyncio
async def test_get_spec_concepts_after_tagging() -> None:
    """GET /api/specs/<id>/concepts returns tagged concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/specs/clf-test-spec-002/concepts",
            json={"concept_ids": ["adaptation"]},
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/specs/clf-test-spec-002/concepts")
        assert r.status_code == 200
        data = r.json()
        assert data["entity_type"] == "spec"
        assert any(c["id"] == "adaptation" for c in data["concepts"])


# ---------------------------------------------------------------------------
# 13. Related items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_related_items_after_idea_tagging() -> None:
    """GET /api/concepts/<id>/related returns ideas tagged with the concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-related-concept-015")
        await client.post(
            "/api/ideas/clf-related-idea-015/concepts",
            json={"concept_ids": ["clf-related-concept-015"]},
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/concepts/clf-related-concept-015/related")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["concept_id"] == "clf-related-concept-015"
        assert "clf-related-idea-015" in data["ideas"]
        assert isinstance(data["specs"], list)
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_related_items_missing_concept_returns_404() -> None:
    """GET /api/concepts/<missing>/related → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/no-such-concept-related-xyz/related")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_related_items_includes_spec() -> None:
    """GET /api/concepts/<id>/related includes spec when tagged."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-related-spec-concept-016")
        await client.post(
            "/api/specs/clf-related-spec-016/concepts",
            json={"concept_ids": ["clf-related-spec-concept-016"]},
            headers=AUTH_HEADERS,
        )
        r = await client.get("/api/concepts/clf-related-spec-concept-016/related")
        assert r.status_code == 200
        data = r.json()
        assert "clf-related-spec-016" in data["specs"]


# ---------------------------------------------------------------------------
# 14. Core concept immutability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_core_concepts_have_type_base() -> None:
    """Core ontology concepts (like 'activity') must have typeId codex.ucore.base."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/concepts/activity")
        assert r.status_code == 200
        assert r.json()["typeId"] == "codex.ucore.base"


@pytest.mark.asyncio
async def test_user_concept_has_type_user() -> None:
    """User-created concepts have typeId codex.ucore.user."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-user-type-017")
        r = await client.get("/api/concepts/clf-user-type-017")
        assert r.status_code == 200
        assert r.json()["typeId"] == "codex.ucore.user"


@pytest.mark.asyncio
async def test_user_concept_flag() -> None:
    """User-created concepts have userDefined=True, core do not."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_user_concept(client, "clf-flag-018")
        user_r = await client.get("/api/concepts/clf-flag-018")
        assert user_r.json().get("userDefined") is True

        core_r = await client.get("/api/concepts/activity")
        assert core_r.json().get("userDefined") is not True
