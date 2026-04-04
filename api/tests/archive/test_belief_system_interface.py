"""Supplementary integration tests for belief-system-interface — spec-169.

These tests extend test_belief_system.py with additional acceptance-criteria coverage:
 1. AC#3 — resonance endpoint: idea not found returns 404
 2. AC#4 — PATCH non-existent contributor returns 404
 3. AC#4 — resonance for non-existent contributor returns 404
 4. AC#6 — concept_resonance weight exactly 0.0 and 1.0 are valid
 5. AC#6 — concept_resonance weight below 0.0 returns 422
 6. AC#7 — PATCH concept_resonances additive merge (no replace)
 7. AC#7 — PATCH concept_resonances replace=true replaces list
 8. AC#8 — ROI with zero contributors returns 200 + profile_adoption_rate=0.0
 9. resonance_score weights sum to 1.0 (0.4+0.4+0.2) verified via neutral inputs
10. concept_resonances in GET profile match patched values
11. PATCH with only interest_tags leaves worldview_axes unchanged
12. PATCH with empty interest_tags list is valid (no-op additive)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contributor(name: str = "belief_user", props: dict | None = None):
    return {
        "id": f"contributor:{name}",
        "type": "contributor",
        "name": name,
        "properties": props or {},
    }


def _idea(idea_id: str = "idea_001", tags: list | None = None, axes: dict | None = None):
    return {
        "id": idea_id,
        "type": "idea",
        "name": "Test Idea",
        "properties": {
            "tags": tags or [],
            "worldview_axes": axes or {},
        },
    }


# ---------------------------------------------------------------------------
# AC#3 — resonance idea not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resonance_idea_not_found_returns_404():
    """GET /api/contributors/{id}/beliefs/resonance?idea_id=bad — 404 when idea missing."""
    node = _contributor()

    def _get_node(nid: str):
        if "contributor" in nid or nid == "belief_user":
            return node
        return None  # idea not found

    with patch("app.services.belief_service.graph_service.get_node", side_effect=_get_node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/belief_user/beliefs/resonance?idea_id=nonexistent")
    assert r.status_code == 404, r.text
    assert "not found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# AC#4 — non-existent contributor on PATCH and resonance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_beliefs_nonexistent_contributor_returns_404():
    """PATCH /api/contributors/ghost/beliefs — 404 when contributor missing."""
    with patch("app.services.belief_service.graph_service.get_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/ghost/beliefs",
                json={"interest_tags": ["entropy"]},
            )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Contributor not found"


@pytest.mark.asyncio
async def test_resonance_nonexistent_contributor_returns_404():
    """GET resonance for non-existent contributor → 404."""
    with patch("app.services.belief_service.graph_service.get_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/contributors/ghost/beliefs/resonance?idea_id=idea_001"
            )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Contributor not found"


# ---------------------------------------------------------------------------
# AC#6 — concept_resonance weight boundary validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_concept_resonance_weight_zero_is_valid():
    """Concept resonance weight=0.0 is a valid boundary value."""
    node = _contributor()
    updated_node = _contributor(props={
        "concept_resonances": [{"concept_id": "entropy", "weight": 0.0}],
    })

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={"concept_resonances": [{"concept_id": "entropy", "weight": 0.0}]},
            )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_patch_concept_resonance_weight_one_is_valid():
    """Concept resonance weight=1.0 is a valid boundary value."""
    node = _contributor()
    updated_node = _contributor(props={
        "concept_resonances": [{"concept_id": "entropy", "weight": 1.0}],
    })

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={"concept_resonances": [{"concept_id": "entropy", "weight": 1.0}]},
            )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_patch_concept_resonance_weight_negative_returns_422():
    """Concept resonance weight < 0.0 is rejected with 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.patch(
            "/api/contributors/belief_user/beliefs",
            json={"concept_resonances": [{"concept_id": "entropy", "weight": -0.1}]},
        )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# AC#7 — concept_resonances additive / replace merge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_concept_resonances_additive():
    """PATCH concept_resonances without replace=true merges by concept_id."""
    node = _contributor(props={
        "concept_resonances": [{"concept_id": "entropy", "weight": 0.8}],
    })
    updated_node = _contributor(props={
        "concept_resonances": [
            {"concept_id": "entropy", "weight": 0.8},
            {"concept_id": "emergence", "weight": 0.6},
        ],
    })

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={"concept_resonances": [{"concept_id": "emergence", "weight": 0.6}]},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    concept_ids = [c["concept_id"] for c in body["concept_resonances"]]
    assert "entropy" in concept_ids
    assert "emergence" in concept_ids


@pytest.mark.asyncio
async def test_patch_concept_resonances_replace_true():
    """PATCH concept_resonances with replace=true replaces the entire list."""
    node = _contributor(props={
        "concept_resonances": [
            {"concept_id": "entropy", "weight": 0.8},
            {"concept_id": "emergence", "weight": 0.6},
        ],
    })
    updated_node = _contributor(props={
        "concept_resonances": [{"concept_id": "coherence", "weight": 0.9}],
    })

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={
                    "concept_resonances": [{"concept_id": "coherence", "weight": 0.9}],
                    "replace": True,
                },
            )
    assert r.status_code == 200, r.text
    body = r.json()
    concept_ids = [c["concept_id"] for c in body["concept_resonances"]]
    assert concept_ids == ["coherence"]


# ---------------------------------------------------------------------------
# AC#8 — ROI with zero contributors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_roi_zero_contributors():
    """GET /api/beliefs/roi with no contributors returns 200 and adoption_rate=0.0."""
    with patch("app.services.belief_service.graph_service.list_nodes", return_value={"nodes": [], "total": 0}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/beliefs/roi")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contributors_total"] == 0
    assert body["contributors_with_profiles"] == 0
    assert body["profile_adoption_rate"] == 0.0
    assert body["spec_ref"] == "spec-169"


# ---------------------------------------------------------------------------
# Resonance score — neutral inputs yield ~0.5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resonance_score_neutral_when_no_matching_data():
    """Resonance score defaults near 0.5 when idea has no concept/axis/tag data."""
    node = _contributor(props={
        "worldview_axes": {"scientific": 0.8},
        "interest_tags": ["entropy"],
        "concept_resonances": [{"concept_id": "entropy", "weight": 0.9}],
    })
    # Idea with no tags, no axes, no concepts → all sub-scores neutral (0.5)
    idea_node = _idea(tags=[], axes={})

    def _get(nid: str):
        if "contributor" in nid or nid == "belief_user":
            return node
        return idea_node

    with patch("app.services.belief_service.graph_service.get_node", side_effect=_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/api/contributors/belief_user/beliefs/resonance?idea_id=idea_empty"
            )
    assert r.status_code == 200, r.text
    body = r.json()
    # All sub-scores neutral → final = 0.4*0.5 + 0.4*0.5 + 0.2*0.5 = 0.5
    assert abs(body["resonance_score"] - 0.5) < 0.01, f"Expected ~0.5, got {body['resonance_score']}"


# ---------------------------------------------------------------------------
# PATCH partial update leaves other fields unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_only_tags_leaves_worldview_unchanged():
    """PATCH with only interest_tags does not overwrite worldview_axes."""
    initial_props = {
        "worldview_axes": {"scientific": 0.9, "systemic": 0.7},
        "interest_tags": [],
        "concept_resonances": [],
    }
    node = _contributor(props=initial_props)
    # After patch, worldview_axes remain; interest_tags updated
    updated_props = dict(initial_props)
    updated_props["interest_tags"] = ["new_tag"]
    updated_node = _contributor(props=updated_props)

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={"interest_tags": ["new_tag"]},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["worldview_axes"]["scientific"] == 0.9
    assert body["worldview_axes"]["systemic"] == 0.7
    assert "new_tag" in body["interest_tags"]


@pytest.mark.asyncio
async def test_patch_empty_interest_tags_list_is_valid():
    """PATCH with empty interest_tags list is accepted (no-op additive)."""
    node = _contributor(props={"interest_tags": ["entropy"]})
    updated_node = _contributor(props={"interest_tags": ["entropy"]})  # unchanged

    with patch("app.services.belief_service.graph_service.get_node", side_effect=[node, updated_node]), \
         patch("app.services.belief_service.graph_service.update_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                "/api/contributors/belief_user/beliefs",
                json={"interest_tags": []},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "entropy" in body["interest_tags"]
