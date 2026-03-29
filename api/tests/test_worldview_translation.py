"""Tests for worldview/belief-system translation of ideas.

Feature: Translate any idea through different belief systems and worldviews.

The same idea means different things to different people. A decentralized network
means freedom to a libertarian (economic/philosophical), efficiency to an engineer
(scientific), threat to an institution (philosophical), opportunity to an entrepreneur
(economic). The system translates ideas through multiple lenses — not to change them
but to help people see how their perspective connects to others.

Endpoints under test:
  GET /api/ideas/{id}/translate?view=<lens>
  GET /api/concepts/{id}/translate?from=<lens>&to=<lens>
  GET /api/contributors/{id}/beliefs
  PATCH /api/contributors/{id}/beliefs
  GET /api/contributors/{id}/beliefs/resonance?idea_id=<id>
  GET /api/beliefs/roi

Verification Scenarios
======================
1. Decentralized network idea — all five worldview lenses return distinct framings
   Setup: Create idea with id 'decentralized-network', description about p2p/freedom/nodes
   Action: GET /api/ideas/decentralized-network/translate?view=<each lens>
   Expected: Each lens returns 200, view matches, non-empty summary distinct per lens,
             lens_description characterizes that worldview perspective
   Edge: Invalid lens 'libertarian' → 422 (not a valid TranslateLens value)

2. Same idea, different lens produces different summaries
   Setup: Create idea 'multi-view-idea'
   Action: Translate through scientific, then economic, then spiritual
   Expected: Three summaries all non-empty, at least two differ, each lens_description
             references its worldview (measurement/empirical for scientific, value/incentive
             for economic, meaning/consciousness for spiritual)
   Edge: Lens names are case-sensitive — uppercase 'SCIENTIFIC' → 422

3. Belief profile PATCH + resonance scoring integration
   Setup: Create contributor belief profile with high scientific axis (0.9)
   Create idea with tags ['system', 'energy', 'network', 'causal']
   Action: GET /api/contributors/{id}/beliefs/resonance?idea_id=<id>
   Expected: 200, resonance_score in [0.0, 1.0], breakdown has concept_overlap,
             worldview_alignment, tag_match all in [0.0, 1.0]
   Edge: Missing idea_id query param → 422

4. Concept translate between worldview lenses
   Setup: Core ontology concept 'activity' must exist
   Action: GET /api/concepts/activity/translate?from=scientific&to=spiritual
   Expected: 200, from_lens=scientific, to_lens=spiritual, summary non-empty,
             target_bridging_concepts list (may be empty but must be a list)
   Edge: from==to → 400; unknown concept → 404

5. Belief ROI stats prove adoption is measurable
   Action: GET /api/beliefs/roi
   Expected: 200, contributors_with_profiles >= 0, profile_adoption_rate in [0.0, 1.0],
             spec_ref == 'spec-169', top_worldview_axes is a list
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DECENTRALIZED_IDEA = {
    "id": "worldview-test-decentralized",
    "name": "Decentralized peer-to-peer network",
    "description": (
        "A distributed network where nodes communicate without a central authority. "
        "Participants exchange value directly, capital flows without intermediaries, "
        "and power is allocated through incentive structures not hierarchy. "
        "The system models entropy and emergent order through causal feedback. "
        "Sacred geometry of trust: nodes are souls, connections are resonance."
    ),
    "potential_value": 90.0,
    "estimated_cost": 20.0,
    "confidence": 0.85,
    "tags": [
        "decentralized", "network", "peer-to-peer", "value", "exchange",
        "freedom", "incentive", "entropy", "system", "trust",
    ],
}

_SCIENCE_HEAVY_IDEA = {
    "id": "worldview-test-science",
    "name": "Thermodynamic flow network",
    "description": (
        "Energy flows through connected subsystems. Entropy measurement, causal "
        "feedback loops, and structural patterns determine emergent behavior."
    ),
    "potential_value": 60.0,
    "estimated_cost": 15.0,
    "confidence": 0.75,
    "tags": ["energy", "entropy", "system", "causal", "flow", "network"],
}

_SPIRITUAL_IDEA = {
    "id": "worldview-test-spiritual",
    "name": "Sacred geometry of consciousness",
    "description": (
        "The divine pattern of unity and harmony resonates through every being. "
        "Presence, awareness, and transcendence are the essence of wisdom."
    ),
    "potential_value": 50.0,
    "estimated_cost": 5.0,
    "confidence": 0.6,
    "tags": ["sacred", "consciousness", "unity", "harmony", "spirit"],
}


def _make_contributor_node(name: str, axes: dict | None = None) -> dict:
    """Build a minimal contributor node for mocking."""
    axes = axes or {}
    return {
        "id": f"contributor:{name}",
        "type": "contributor",
        "name": name,
        "properties": {"worldview_axes": axes, "interest_tags": [], "concept_resonances": []},
    }


# ---------------------------------------------------------------------------
# Scenario 1 — Decentralized network idea through all five worldview lenses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decentralized_idea_scientific_lens() -> None:
    """Decentralized network via scientific lens: measurement, systems, causal."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "scientific"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["idea_id"] == "worldview-test-decentralized"
    assert data["view"] == "scientific"
    assert data["translation_kind"] == "concept_framing"
    assert len(data["summary"]) > 20
    lens_desc = data["lens_description"].lower()
    assert any(kw in lens_desc for kw in ("measur", "empiric", "system", "causal", "quantif")), (
        f"Scientific lens_description should reference measurement/causal: {lens_desc}"
    )
    assert isinstance(data["bridging_concepts"], list)
    assert isinstance(data["analogous_ideas"], list)


@pytest.mark.asyncio
async def test_decentralized_idea_economic_lens() -> None:
    """Decentralized network via economic lens: value, incentive, exchange, capital."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "economic"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["view"] == "economic"
    lens_desc = data["lens_description"].lower()
    assert any(kw in lens_desc for kw in ("value", "exchange", "incentive", "resource", "allocat")), (
        f"Economic lens_description should reference value/exchange: {lens_desc}"
    )
    assert len(data["summary"]) > 20


@pytest.mark.asyncio
async def test_decentralized_idea_spiritual_lens() -> None:
    """Decentralized network via spiritual lens: meaning, resonance, sacred order."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "spiritual"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["view"] == "spiritual"
    lens_desc = data["lens_description"].lower()
    assert any(kw in lens_desc for kw in ("meaning", "sacred", "consciousness", "transcend", "spirit", "purpose")), (
        f"Spiritual lens_description should reference meaning/sacred: {lens_desc}"
    )
    assert len(data["summary"]) > 20


@pytest.mark.asyncio
async def test_decentralized_idea_artistic_lens() -> None:
    """Decentralized network via artistic lens: form, rhythm, expression, composition."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "artistic"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["view"] == "artistic"
    lens_desc = data["lens_description"].lower()
    assert any(kw in lens_desc for kw in ("form", "beauty", "expression", "rhythm", "aesthetic", "composit")), (
        f"Artistic lens_description should reference form/beauty: {lens_desc}"
    )
    assert len(data["summary"]) > 20


@pytest.mark.asyncio
async def test_decentralized_idea_philosophical_lens() -> None:
    """Decentralized network via philosophical lens: being, ethics, freedom, knowledge."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "philosophical"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["view"] == "philosophical"
    lens_desc = data["lens_description"].lower()
    assert any(kw in lens_desc for kw in ("truth", "being", "exist", "ethic", "knowledge", "question")), (
        f"Philosophical lens_description should reference truth/being: {lens_desc}"
    )
    assert len(data["summary"]) > 20


@pytest.mark.asyncio
async def test_invalid_lens_returns_422() -> None:
    """Edge Scenario 1: 'libertarian' is not a valid TranslateLens → 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "libertarian"},
        )
    assert r.status_code == 422, f"Expected 422 for invalid lens, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Scenario 2 — Same idea, different lenses produce distinct framings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_idea_different_lenses_produce_distinct_summaries() -> None:
    """Scenario 2: Three lenses on one idea produce differentiated summaries."""
    idea = {
        "id": "worldview-test-multi-view",
        "name": "Collective intelligence network",
        "description": (
            "A distributed system where collective patterns emerge from individual contributions. "
            "Energy, value, meaning, and beauty co-arise in each node's resonance."
        ),
        "potential_value": 70.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
        "tags": ["collective", "network", "emergence", "value", "resonance"],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=idea, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r_sci = await client.get(
            "/api/ideas/worldview-test-multi-view/translate", params={"view": "scientific"}
        )
        r_eco = await client.get(
            "/api/ideas/worldview-test-multi-view/translate", params={"view": "economic"}
        )
        r_spi = await client.get(
            "/api/ideas/worldview-test-multi-view/translate", params={"view": "spiritual"}
        )

    assert r_sci.status_code == 200
    assert r_eco.status_code == 200
    assert r_spi.status_code == 200

    sci_data = r_sci.json()
    eco_data = r_eco.json()
    spi_data = r_spi.json()

    # Each view field matches the requested lens
    assert sci_data["view"] == "scientific"
    assert eco_data["view"] == "economic"
    assert spi_data["view"] == "spiritual"

    # Summaries are all non-empty
    assert len(sci_data["summary"]) > 20
    assert len(eco_data["summary"]) > 20
    assert len(spi_data["summary"]) > 20

    # At least two of the three summaries differ (true differentiation)
    summaries = {sci_data["summary"], eco_data["summary"], spi_data["summary"]}
    assert len(summaries) >= 2, "All three lens summaries are identical — no differentiation"

    # Lens descriptions differ per worldview
    assert sci_data["lens_description"] != eco_data["lens_description"]
    assert eco_data["lens_description"] != spi_data["lens_description"]


@pytest.mark.asyncio
async def test_uppercase_lens_name_returns_422() -> None:
    """Edge Scenario 2: uppercase lens names are rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_SCIENCE_HEAVY_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-science/translate",
            params={"view": "SCIENTIFIC"},
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 3 — Belief profile + resonance scoring integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_belief_resonance_returns_score_in_range() -> None:
    """Scenario 3: Contributor with scientific belief profile resonates with scientific idea."""
    contributor_id = "worldview-test-scientist"
    node = _make_contributor_node(
        name=contributor_id,
        axes={"scientific": 0.9, "systemic": 0.8, "spiritual": 0.1},
    )
    idea_id = "worldview-test-science"
    # Build an idea node for the resonance mock
    idea_node = {
        "id": idea_id,
        "type": "idea",
        "name": "Thermodynamic flow network",
        "properties": {
            "tags": ["energy", "entropy", "system", "causal"],
            "potential_value": 60.0,
            "estimated_cost": 15.0,
            "confidence": 0.75,
            "worldview_axes": {"scientific": 0.9, "systemic": 0.7},
        },
    }

    with (
        patch("app.services.belief_service.graph_service.get_node") as mock_get,
        patch("app.services.belief_service.graph_service.update_node", return_value=node),
    ):
        def _get_node_side_effect(node_id: str):
            if node_id == contributor_id or node_id == f"contributor:{contributor_id}":
                return node
            if node_id == idea_id:
                return idea_node
            return None

        mock_get.side_effect = _get_node_side_effect

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First create the idea so the resonance endpoint can find it
            cr = await client.post("/api/ideas", json=_SCIENCE_HEAVY_IDEA, headers=AUTH_HEADERS)
            assert cr.status_code == 201, cr.text

            r = await client.get(
                f"/api/contributors/{contributor_id}/beliefs/resonance",
                params={"idea_id": idea_id},
            )

    assert r.status_code == 200, r.text
    data = r.json()
    assert "resonance_score" in data
    score = data["resonance_score"]
    assert 0.0 <= score <= 1.0, f"resonance_score out of range: {score}"
    assert "breakdown" in data
    breakdown = data["breakdown"]
    for field in ("concept_overlap", "worldview_alignment", "tag_match"):
        assert field in breakdown
        assert 0.0 <= breakdown[field] <= 1.0


@pytest.mark.asyncio
async def test_belief_resonance_missing_idea_id_returns_422() -> None:
    """Edge Scenario 3: missing idea_id query param → 422."""
    contributor_id = "worldview-test-scientist-edge"
    node = _make_contributor_node(name=contributor_id)
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/contributors/{contributor_id}/beliefs/resonance",
            )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_belief_profile_patch_and_get_worldview_axes() -> None:
    """Contributor belief axes can be set via PATCH and read back via GET."""
    contributor_id = "worldview-test-patcher"
    initial_node = _make_contributor_node(name=contributor_id)
    updated_axes = {"scientific": 0.85, "spiritual": 0.3, "pragmatic": 0.5}
    updated_node = _make_contributor_node(
        name=contributor_id,
        axes=updated_axes,
    )

    # Service calls get_node twice: once to fetch current state, once to re-read after update.
    # First call returns initial node; second call returns updated node.
    get_node_calls = [initial_node, updated_node]

    with (
        patch(
            "app.services.belief_service.graph_service.get_node",
            side_effect=lambda _: get_node_calls.pop(0) if get_node_calls else updated_node,
        ),
        patch("app.services.belief_service.graph_service.update_node", return_value=updated_node),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_patch = await client.patch(
                f"/api/contributors/{contributor_id}/beliefs",
                json={"worldview_axes": updated_axes},
            )
    assert r_patch.status_code == 200, r_patch.text
    patch_body = r_patch.json()
    assert patch_body["contributor_id"] == contributor_id
    for axis, expected in updated_axes.items():
        assert axis in patch_body["worldview_axes"]
        assert patch_body["worldview_axes"][axis] == expected


@pytest.mark.asyncio
async def test_belief_profile_invalid_axis_name_returns_422() -> None:
    """Edge: patching an unknown axis (e.g. 'libertarian') → 422."""
    contributor_id = "worldview-test-bad-axis"
    node = _make_contributor_node(name=contributor_id)
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                f"/api/contributors/{contributor_id}/beliefs",
                json={"worldview_axes": {"libertarian": 0.9}},
            )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_belief_profile_axis_weight_out_of_range_returns_422() -> None:
    """Edge: axis weight > 1.0 → 422."""
    contributor_id = "worldview-test-bad-weight"
    node = _make_contributor_node(name=contributor_id)
    with patch("app.services.belief_service.graph_service.get_node", return_value=node):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                f"/api/contributors/{contributor_id}/beliefs",
                json={"worldview_axes": {"scientific": 1.5}},
            )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 4 — Concept translate between worldview lenses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concept_scientific_to_spiritual_translation() -> None:
    """Scenario 4: 'activity' concept from scientific to spiritual lens."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pre = await client.get("/api/concepts/activity")
        assert pre.status_code == 200, "Ontology must include 'activity' concept"

        r = await client.get(
            "/api/concepts/activity/translate",
            params={"from": "scientific", "to": "spiritual"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["concept_id"] == "activity"
    assert data["from_lens"] == "scientific"
    assert data["to_lens"] == "spiritual"
    assert data["translation_kind"] == "concept_framing"
    assert len(data["summary"]) > 10
    assert isinstance(data["target_bridging_concepts"], list)
    assert isinstance(data["source_axes"], list)


@pytest.mark.asyncio
async def test_concept_economic_to_philosophical_translation() -> None:
    """Concept translate: economic → philosophical worldview lens."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pre = await client.get("/api/concepts/activity")
        assert pre.status_code == 200

        r = await client.get(
            "/api/concepts/activity/translate",
            params={"from": "economic", "to": "philosophical"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["from_lens"] == "economic"
    assert data["to_lens"] == "philosophical"
    assert len(data["summary"]) > 10


@pytest.mark.asyncio
async def test_concept_same_lens_returns_400() -> None:
    """Edge Scenario 4: from == to → 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/concepts/activity/translate",
            params={"from": "artistic", "to": "artistic"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_concept_missing_returns_404() -> None:
    """Edge Scenario 4: unknown concept → 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/concepts/worldview-no-such-concept-9999/translate",
            params={"from": "scientific", "to": "spiritual"},
        )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 5 — Belief ROI: adoption is measurable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_belief_roi_stats_structure() -> None:
    """Scenario 5: GET /api/beliefs/roi returns adoption metrics."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/beliefs/roi")
    assert r.status_code == 200, r.text
    data = r.json()

    required_fields = [
        "contributors_with_profiles",
        "contributors_total",
        "profile_adoption_rate",
        "top_worldview_axes",
        "avg_resonance_match_rate",
        "concept_resonances_total",
        "spec_ref",
    ]
    for field in required_fields:
        assert field in data, f"Missing field in beliefs/roi: {field}"

    assert data["contributors_with_profiles"] >= 0
    assert data["contributors_total"] >= 0
    assert 0.0 <= data["profile_adoption_rate"] <= 1.0
    assert 0.0 <= data["avg_resonance_match_rate"] <= 1.0
    assert data["concept_resonances_total"] >= 0
    assert data["spec_ref"] == "spec-169"
    assert isinstance(data["top_worldview_axes"], list)
    for axis_stat in data["top_worldview_axes"]:
        assert "axis" in axis_stat
        assert "avg_weight" in axis_stat


# ---------------------------------------------------------------------------
# Additional: Bridging concepts have valid structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_translation_bridging_concepts_have_required_fields() -> None:
    """Bridging concepts returned by translate must each have id, name, score, axes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_SPIRITUAL_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-spiritual/translate",
            params={"view": "scientific"},
        )
    assert r.status_code == 200, r.text
    data = r.json()
    for bc in data["bridging_concepts"]:
        assert "id" in bc, f"bridging_concept missing 'id': {bc}"
        assert "name" in bc, f"bridging_concept missing 'name': {bc}"
        assert "score" in bc, f"bridging_concept missing 'score': {bc}"
        assert "axes" in bc, f"bridging_concept missing 'axes': {bc}"
        score = bc["score"]
        assert 0.0 <= score <= 1.0, f"bridging_concept score out of range: {score}"


@pytest.mark.asyncio
async def test_translation_response_schema_complete() -> None:
    """Translate response always contains all documented fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        r = await client.get(
            "/api/ideas/worldview-test-decentralized/translate",
            params={"view": "economic"},
        )
    assert r.status_code == 200, r.text
    data = r.json()

    required_keys = [
        "idea_id",
        "view",
        "translation_kind",
        "lens_description",
        "summary",
        "bridging_concepts",
        "analogous_ideas",
    ]
    for key in required_keys:
        assert key in data, f"Missing required key '{key}' in translation response"

    assert data["translation_kind"] == "concept_framing"
    assert isinstance(data["bridging_concepts"], list)
    assert isinstance(data["analogous_ideas"], list)


@pytest.mark.asyncio
async def test_missing_idea_translate_returns_404() -> None:
    """Non-existent idea id → 404 on translate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/api/ideas/worldview-test-no-such-idea-xyz/translate",
            params={"view": "philosophical"},
        )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Additional: Belief profile for non-existent contributor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_belief_profile_nonexistent_contributor_returns_404() -> None:
    """GET /api/contributors/{id}/beliefs for unknown contributor → 404."""
    with patch("app.services.belief_service.graph_service.get_node", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/contributors/worldview-test-nobody/beliefs")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Additional: Lens descriptions are stable and unique per lens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_five_lenses_have_unique_descriptions() -> None:
    """Each of the 5 lenses returns a unique lens_description for the same idea."""
    lenses = ["scientific", "economic", "spiritual", "artistic", "philosophical"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cr = await client.post("/api/ideas", json=_DECENTRALIZED_IDEA, headers=AUTH_HEADERS)
        assert cr.status_code == 201, cr.text

        descriptions = []
        for lens in lenses:
            r = await client.get(
                "/api/ideas/worldview-test-decentralized/translate",
                params={"view": lens},
            )
            assert r.status_code == 200, f"Lens {lens} failed: {r.text}"
            descriptions.append(r.json()["lens_description"])

    # All 5 lens descriptions must be distinct
    assert len(set(descriptions)) == 5, (
        f"Expected 5 unique lens descriptions, got {len(set(descriptions))}: {descriptions}"
    )
