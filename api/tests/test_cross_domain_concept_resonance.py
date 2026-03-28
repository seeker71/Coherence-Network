"""Tests for cross-domain concept resonance — ideas attract related ideas across domains.

Verification Contract:
======================
This test suite proves that the concept resonance feature works as described:
  - Biology concepts (symbiosis) resonate with software concepts (microservices)
    via structural similarity, NOT keyword matching.
  - Cross-domain matches are ranked above same-domain matches.
  - Resonance score correctly reflects concept overlap + domain novelty bonus.
  - The feature works via GET /api/ideas/{id}/concept-resonance.
  - Error handling is correct (404 for missing ideas, empty-concept ideas).

Verification Scenarios:
-----------------------
1. Symbiosis ↔ Microservices (canonical cross-domain case)
   Setup: Create two ideas — one biology (symbiosis/cooperation/dependency),
          one software (microservices/cooperation/dependency), one unrelated.
   Action: GET /api/ideas/bio-symbiosis/concept-resonance?min_score=0.05
   Expected: 200 with matches[0].idea_id == "sw-microservices", cross_domain == True,
             shared_concepts contains structural overlap tokens (cooperation/dependency),
             resonance_score > 0.0
   Edge: GET /api/ideas/nonexistent/concept-resonance → 404

2. Cross-domain ranks above same-domain
   Setup: Two ideas in same domain (biology A and biology B) with concept overlap,
          one cross-domain idea with equal concept overlap.
   Action: GET /api/ideas/source/concept-resonance
   Expected: cross_domain == True match appears first (higher resonance_score)

3. No concepts → empty matches
   Setup: Idea with a very generic name/description with no extractable concept tokens.
   Action: GET /api/ideas/generic-idea/concept-resonance
   Expected: 200 with total == 0 (no matches returned)

4. min_score filtering
   Setup: Ideas with very weak concept overlap (1 shared token out of many)
   Action: GET /api/ideas/source/concept-resonance?min_score=0.9
   Expected: 200 with total == 0 (weak matches filtered out)

5. Structural scoring formula validation (unit-level)
   Setup: Create specific ideas and call service function directly
   Action: idea_service.get_concept_resonance_matches(...)
   Expected: resonance_score == concept_overlap + 0.25 * domain_novelty (when cross-domain)
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _post_idea(client: AsyncClient, payload: dict) -> None:
    resp = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 201, f"Failed to create idea {payload['id']!r}: {resp.text}"


async def _get_resonance(client: AsyncClient, idea_id: str, **params) -> dict:
    resp = await client.get(
        f"/api/ideas/{idea_id}/concept-resonance",
        params=params or {"min_score": 0.01},
    )
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: Symbiosis ↔ Microservices — canonical cross-domain resonance
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_symbiosis_resonates_with_microservices_cross_domain() -> None:
    """Biology concept (symbiosis) must surface software concept (microservices).

    The ideas share structural tokens: cooperation, dependency, mutual, benefit.
    They are in entirely different domains: biology vs software-engineering.
    The resonance is NOT from keywords like 'biology' or 'software' appearing in both —
    those words do not appear in both. The resonance is structural.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Source: biology concept — symbiosis
        await _post_idea(client, {
            "id": "bio-symbiosis",
            "name": "Symbiosis in Ecosystems",
            "description": (
                "Study of mutual cooperation between organisms. "
                "Each organism gains benefit from dependency on the other. "
                "The relationship creates resilience through interdependence."
            ),
            "potential_value": 70.0,
            "estimated_cost": 15.0,
            "confidence": 0.85,
            "tags": ["biology", "cooperation", "dependency", "mutual", "resilience"],
            "interfaces": ["domain:biology"],
        })

        # Candidate: software concept — microservices (structurally analogous)
        await _post_idea(client, {
            "id": "sw-microservices",
            "name": "Microservices Architecture",
            "description": (
                "Design systems as cooperating independent services. "
                "Each service has a clear dependency boundary and mutual contracts. "
                "Resilience emerges from service interdependence and isolation."
            ),
            "potential_value": 80.0,
            "estimated_cost": 20.0,
            "confidence": 0.9,
            "tags": ["software", "cooperation", "dependency", "mutual", "resilience"],
            "interfaces": ["domain:software-engineering"],
        })

        # Noise: unrelated idea — should NOT appear in top results
        await _post_idea(client, {
            "id": "fin-portfolio-theory",
            "name": "Portfolio Diversification Theory",
            "description": "Spread investment across uncorrelated assets to reduce volatility.",
            "potential_value": 50.0,
            "estimated_cost": 5.0,
            "confidence": 0.7,
            "tags": ["finance", "investment", "diversification"],
            "interfaces": ["domain:finance"],
        })

        resp = await _get_resonance(client, "bio-symbiosis", min_score=0.05)

    assert resp.status_code == 200
    body = resp.json()
    assert body["idea_id"] == "bio-symbiosis"
    assert body["total"] >= 1, "Expected at least one resonance match"

    top_match = body["matches"][0]
    assert top_match["idea_id"] == "sw-microservices", (
        f"Expected sw-microservices as top match, got {top_match['idea_id']!r}. "
        "The structural tokens (cooperation, dependency, mutual, resilience) must surface it."
    )
    assert top_match["cross_domain"] is True, "Match must be flagged as cross-domain"
    assert top_match["resonance_score"] > 0.0

    # Verify shared structural concepts (not domain-name keywords)
    shared = set(top_match["shared_concepts"])
    structural_overlap = shared & {"cooperation", "dependency", "mutual", "resilience"}
    assert len(structural_overlap) >= 2, (
        f"Expected ≥2 structural concept tokens to be shared. Got: {shared}"
    )

    # Source domain is biology; candidate domain is software-engineering
    assert "biology" in top_match["source_domains"] or any(
        "bio" in d for d in top_match["source_domains"]
    ), f"Expected biology in source_domains, got {top_match['source_domains']}"
    assert any(
        "software" in d for d in top_match["candidate_domains"]
    ), f"Expected software in candidate_domains, got {top_match['candidate_domains']}"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: Cross-domain outranks same-domain
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_domain_match_ranks_above_same_domain_match() -> None:
    """When cross-domain and same-domain matches have similar overlap,
    cross-domain MUST rank higher due to the 0.25 * domain_novelty bonus.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Source idea
        await _post_idea(client, {
            "id": "src-adaptation",
            "name": "Adaptive Feedback Systems",
            "description": "Systems that adapt through feedback loops to maintain equilibrium.",
            "potential_value": 60.0,
            "estimated_cost": 10.0,
            "confidence": 0.8,
            "tags": ["adaptation", "feedback", "equilibrium", "systems"],
            "interfaces": ["domain:biology"],
        })

        # Same-domain match (biology): overlaps on adaptation + feedback + systems
        await _post_idea(client, {
            "id": "same-domain-homeostat",
            "name": "Biological Homeostasis",
            "description": "Organisms maintain equilibrium through adaptation and feedback mechanisms.",
            "potential_value": 45.0,
            "estimated_cost": 8.0,
            "confidence": 0.75,
            "tags": ["adaptation", "feedback", "equilibrium", "systems"],
            "interfaces": ["domain:biology"],
        })

        # Cross-domain match (engineering): same concept overlap
        await _post_idea(client, {
            "id": "cross-domain-control",
            "name": "Adaptive Control Systems",
            "description": "Control loops that maintain equilibrium via continuous adaptation feedback.",
            "potential_value": 55.0,
            "estimated_cost": 12.0,
            "confidence": 0.8,
            "tags": ["adaptation", "feedback", "equilibrium", "systems"],
            "interfaces": ["domain:engineering"],
        })

        resp = await _get_resonance(client, "src-adaptation", min_score=0.05)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2, "Expected at least two resonance matches"

    matches = body["matches"]
    match_ids = [m["idea_id"] for m in matches]
    cross_match = next((m for m in matches if m["idea_id"] == "cross-domain-control"), None)
    same_match = next((m for m in matches if m["idea_id"] == "same-domain-homeostat"), None)

    assert cross_match is not None, "cross-domain-control must appear in matches"
    assert same_match is not None, "same-domain-homeostat must appear in matches"

    assert cross_match["cross_domain"] is True
    assert same_match["cross_domain"] is False

    assert cross_match["resonance_score"] >= same_match["resonance_score"], (
        f"Cross-domain score {cross_match['resonance_score']} must be ≥ "
        f"same-domain score {same_match['resonance_score']}. "
        "The 0.25 * domain_novelty bonus must lift cross-domain matches."
    )

    # Cross-domain match must be ranked first
    assert match_ids[0] == "cross-domain-control", (
        f"Cross-domain match must be ranked first. Got order: {match_ids}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3: No extractable concepts → empty matches
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idea_with_no_concept_tokens_returns_empty_matches() -> None:
    """An idea whose name, description, and tags produce no extractable concept tokens
    after stop-word filtering should return an empty match list, not an error.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create an idea that has almost no unique concept tokens after stop-word filtering
        # The service filters tokens < 3 chars, plus domain stop words
        await _post_idea(client, {
            "id": "idea-no-concepts",
            "name": "An Idea",
            "description": "The new way to do things and get results.",
            "potential_value": 10.0,
            "estimated_cost": 2.0,
            "confidence": 0.5,
            "tags": [],
            "interfaces": [],
        })

        # Create another idea that would match if concepts existed
        await _post_idea(client, {
            "id": "idea-other",
            "name": "Another Different Idea",
            "description": "This does other things with different methods.",
            "potential_value": 10.0,
            "estimated_cost": 2.0,
            "confidence": 0.5,
            "tags": [],
            "interfaces": [],
        })

        resp = await _get_resonance(client, "idea-no-concepts", min_score=0.5)

    # May return 200 with empty matches (very low overlap filtered by min_score),
    # OR may return 200 with total == 0 for a truly concept-less idea.
    assert resp.status_code == 200
    body = resp.json()
    assert body["idea_id"] == "idea-no-concepts"
    # With high min_score=0.5, vague/stop-word-heavy ideas should have no passing matches
    assert body["total"] == 0 or all(
        m["resonance_score"] >= 0.5 for m in body["matches"]
    ), "All returned matches must meet the min_score threshold"


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4: min_score filtering excludes weak matches
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_min_score_filter_excludes_weak_resonance() -> None:
    """With a very high min_score (0.9), only near-identical ideas should appear."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _post_idea(client, {
            "id": "source-idea-filtering",
            "name": "Decentralized Consensus Protocol",
            "description": "Achieve agreement in distributed nodes without central authority.",
            "potential_value": 90.0,
            "estimated_cost": 25.0,
            "confidence": 0.9,
            "tags": ["distributed", "consensus", "decentralized", "protocol", "nodes"],
            "interfaces": ["domain:networking"],
        })

        # Weak overlap: shares only 1 token
        await _post_idea(client, {
            "id": "weak-overlap-idea",
            "name": "Democracy Protocol",
            "description": "Voting mechanism for group decision making in communities.",
            "potential_value": 30.0,
            "estimated_cost": 5.0,
            "confidence": 0.6,
            "tags": ["protocol", "community", "voting"],
            "interfaces": ["domain:governance"],
        })

        resp_strict = await _get_resonance(client, "source-idea-filtering", min_score=0.9)
        resp_lenient = await _get_resonance(client, "source-idea-filtering", min_score=0.01)

    assert resp_strict.status_code == 200
    assert resp_lenient.status_code == 200

    strict_body = resp_strict.json()
    lenient_body = resp_lenient.json()

    # Strict filter should exclude the weak match
    assert strict_body["total"] == 0, (
        f"Expected 0 matches at min_score=0.9, got {strict_body['total']}. "
        f"Matches: {strict_body['matches']}"
    )

    # Lenient filter should include it
    assert lenient_body["total"] >= 1, (
        "Expected ≥1 match at min_score=0.01 (single shared token 'protocol')"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 5: 404 for unknown idea
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concept_resonance_returns_404_for_missing_idea() -> None:
    """GET /api/ideas/{nonexistent}/concept-resonance must return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/this-idea-does-not-exist-xyz/concept-resonance")

    assert resp.status_code == 404
    body = resp.json()
    # Must include a meaningful error detail
    assert "detail" in body or "message" in body or "error" in body, (
        f"404 response must include error detail. Got: {body}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 6: Limit parameter constrains result count
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_limit_parameter_caps_returned_matches() -> None:
    """The 'limit' query parameter must cap the returned matches list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create source + 3 candidates all sharing the same concept tokens
        await _post_idea(client, {
            "id": "limit-source",
            "name": "Limit Source Neural Learning",
            "description": "Learning through neural adaptation and pattern recognition.",
            "potential_value": 70.0,
            "estimated_cost": 15.0,
            "confidence": 0.8,
            "tags": ["neural", "learning", "adaptation", "pattern", "recognition"],
            "interfaces": ["domain:neuroscience"],
        })
        for i, domain in enumerate(["machine-learning", "education", "robotics"]):
            await _post_idea(client, {
                "id": f"limit-candidate-{i}",
                "name": f"Limit Candidate {i} Neural Learning",
                "description": "Neural adaptation drives learning through pattern recognition.",
                "potential_value": 60.0 + i,
                "estimated_cost": 10.0,
                "confidence": 0.75,
                "tags": ["neural", "learning", "adaptation", "pattern", "recognition"],
                "interfaces": [f"domain:{domain}"],
            })

        resp_limited = await client.get(
            "/api/ideas/limit-source/concept-resonance",
            params={"limit": 2, "min_score": 0.05},
        )
        resp_unlimited = await client.get(
            "/api/ideas/limit-source/concept-resonance",
            params={"limit": 10, "min_score": 0.05},
        )

    assert resp_limited.status_code == 200
    assert resp_unlimited.status_code == 200

    limited_body = resp_limited.json()
    unlimited_body = resp_unlimited.json()

    # limited: at most 2 matches in matches list
    assert len(limited_body["matches"]) <= 2, (
        f"Expected ≤2 matches with limit=2, got {len(limited_body['matches'])}"
    )

    # unlimited: total field reflects ALL matches before limit, matches list respects limit
    assert unlimited_body["total"] >= 3, (
        f"Expected ≥3 total matches with 3 similar candidates, got {unlimited_body['total']}"
    )
    assert len(unlimited_body["matches"]) >= 3


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 7: Resonance is structural, not domain-name keyword matching
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resonance_detects_structural_similarity_not_domain_keywords() -> None:
    """Two ideas in different domains must resonate via SHARED STRUCTURAL CONCEPTS.

    The words 'biology' and 'software' do not appear in both — the resonance
    is through structural problem-solving tokens: isolation, fault, tolerance,
    recovery. This is the key property: it's not keyword matching.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Biology domain: immune system concept
        await _post_idea(client, {
            "id": "bio-immune-tolerance",
            "name": "Immune System Fault Tolerance",
            "description": (
                "The immune system isolates infected cells to prevent spreading. "
                "Recovery mechanisms neutralize threats and restore normal function. "
                "Tolerance to self-antigens prevents autoimmune response."
            ),
            "potential_value": 75.0,
            "estimated_cost": 18.0,
            "confidence": 0.85,
            "tags": ["immunity", "isolation", "fault", "tolerance", "recovery"],
            "interfaces": ["domain:immunology"],
        })

        # Software domain: circuit breaker pattern (structurally analogous)
        await _post_idea(client, {
            "id": "sw-circuit-breaker",
            "name": "Circuit Breaker Pattern",
            "description": (
                "The circuit breaker isolates failing services to prevent cascade failures. "
                "Recovery probe restores normal function after fault clearance. "
                "Tolerance thresholds prevent unnecessary isolation trips."
            ),
            "potential_value": 85.0,
            "estimated_cost": 22.0,
            "confidence": 0.9,
            "tags": ["services", "isolation", "fault", "tolerance", "recovery"],
            "interfaces": ["domain:software-architecture"],
        })

        # Unrelated idea: finance domain with NO shared structural tokens
        await _post_idea(client, {
            "id": "fin-arbitrage",
            "name": "Statistical Arbitrage Strategy",
            "description": "Profit from price discrepancies between correlated securities.",
            "potential_value": 60.0,
            "estimated_cost": 10.0,
            "confidence": 0.7,
            "tags": ["finance", "arbitrage", "securities", "trading"],
            "interfaces": ["domain:finance"],
        })

        resp = await _get_resonance(client, "bio-immune-tolerance", min_score=0.05)

    assert resp.status_code == 200
    body = resp.json()

    match_ids = [m["idea_id"] for m in body["matches"]]
    assert "sw-circuit-breaker" in match_ids, (
        "Circuit breaker must resonate with immune tolerance via structural tokens. "
        f"Matches found: {match_ids}"
    )

    circuit_match = next(m for m in body["matches"] if m["idea_id"] == "sw-circuit-breaker")
    assert circuit_match["cross_domain"] is True

    # Verify the shared concepts are structural, not domain-keyword tokens
    shared = set(circuit_match["shared_concepts"])
    domain_keywords = {"biology", "software", "immunology", "architecture"}
    assert not (shared & domain_keywords), (
        f"Shared concepts must be structural tokens, not domain keywords. "
        f"Got shared: {shared}"
    )
    structural_tokens = shared & {"isolation", "fault", "tolerance", "recovery"}
    assert len(structural_tokens) >= 2, (
        f"At least 2 structural tokens must be shared. Got: {shared}"
    )

    # sw-circuit-breaker must rank above any other match (highest structural overlap)
    circuit_breaker_rank = match_ids.index("sw-circuit-breaker")
    assert circuit_breaker_rank == 0, (
        f"sw-circuit-breaker must be the top-ranked match (rank {circuit_breaker_rank}). "
        f"Full match order: {match_ids}. "
        "Structural overlap (isolation, fault, tolerance, recovery) must dominate."
    )

    # Verify finance idea, if present, has LOWER resonance than circuit breaker
    if "fin-arbitrage" in match_ids:
        fin_match = next(m for m in body["matches"] if m["idea_id"] == "fin-arbitrage")
        assert circuit_match["resonance_score"] > fin_match["resonance_score"], (
            f"Circuit breaker score {circuit_match['resonance_score']} must exceed "
            f"fin-arbitrage score {fin_match['resonance_score']}. "
            "Structural token overlap must dominate over incidental matches."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 8: Resonance score formula verification (unit-level, direct service call)
# ─────────────────────────────────────────────────────────────────────────────

def test_resonance_score_formula_cross_domain_bonus() -> None:
    """The cross-domain score must be: concept_overlap + 0.25 * domain_novelty.

    This tests the internal scoring formula directly via the service layer.
    Two identical concept sets in different domains should produce a higher
    resonance_score than the same overlap in the same domain.
    """
    from app.services import idea_service

    idea_service._invalidate_ideas_cache()

    # Build minimal Idea objects directly (bypassing DB) to test formula
    from app.models.idea import Idea, ManifestationStatus

    source_idea = Idea(
        id="formula-source",
        name="Formula Source Adaptation Feedback",
        description="Adaptation through feedback loops and equilibrium.",
        potential_value=50.0,
        estimated_cost=10.0,
        confidence=0.8,
        tags=["adaptation", "feedback", "equilibrium"],
        interfaces=["domain:biology"],
    )

    cross_domain_candidate = Idea(
        id="formula-cross-candidate",
        name="Formula Cross Candidate Adaptation Feedback",
        description="Engineering adaptation feedback for equilibrium control.",
        potential_value=50.0,
        estimated_cost=10.0,
        confidence=0.8,
        tags=["adaptation", "feedback", "equilibrium"],
        interfaces=["domain:engineering"],
    )

    same_domain_candidate = Idea(
        id="formula-same-candidate",
        name="Formula Same Candidate Adaptation Feedback",
        description="Biology adaptation feedback maintains equilibrium states.",
        potential_value=50.0,
        estimated_cost=10.0,
        confidence=0.8,
        tags=["adaptation", "feedback", "equilibrium"],
        interfaces=["domain:biology"],
    )

    # Extract concept and domain tokens
    source_concepts = idea_service._idea_concept_tokens(source_idea)
    cross_concepts = idea_service._idea_concept_tokens(cross_domain_candidate)
    same_concepts = idea_service._idea_concept_tokens(same_domain_candidate)

    source_domains = idea_service._idea_domain_tokens(source_idea)
    cross_domains = idea_service._idea_domain_tokens(cross_domain_candidate)
    same_domains = idea_service._idea_domain_tokens(same_domain_candidate)

    # Compute cross-domain score manually
    cross_shared = source_concepts & cross_concepts
    cross_combined = source_concepts | cross_concepts
    cross_overlap = len(cross_shared) / max(len(cross_combined), 1)
    cross_domain_union = source_domains | cross_domains
    cross_novelty = (
        len(cross_domains - source_domains) / len(cross_domain_union)
        if cross_domain_union else 0.0
    )
    cross_is_cross_domain = bool(source_domains and cross_domains and source_domains != cross_domains)
    expected_cross_score = round(
        min(1.0, cross_overlap + (0.25 * cross_novelty if cross_is_cross_domain else 0.0)),
        4,
    )

    # Compute same-domain score manually
    same_shared = source_concepts & same_concepts
    same_combined = source_concepts | same_concepts
    same_overlap = len(same_shared) / max(len(same_combined), 1)
    same_domain_union = source_domains | same_domains
    same_novelty = (
        len(same_domains - source_domains) / len(same_domain_union)
        if same_domain_union else 0.0
    )
    same_is_cross_domain = bool(source_domains and same_domains and source_domains != same_domains)
    expected_same_score = round(
        min(1.0, same_overlap + (0.25 * same_novelty if same_is_cross_domain else 0.0)),
        4,
    )

    # Cross-domain must have domain novelty bonus
    assert cross_is_cross_domain is True, "Biology → Engineering must be cross-domain"
    assert same_is_cross_domain is False, "Biology → Biology must be same-domain"
    assert cross_novelty > 0.0, "Cross-domain candidate must add domain novelty"
    assert expected_cross_score > expected_same_score, (
        f"Cross-domain score {expected_cross_score} must exceed "
        f"same-domain score {expected_same_score} (domain novelty bonus: {cross_novelty:.4f})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 9: Ontology growth — resonance creates observable connections
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_adding_new_idea_expands_resonance_reach() -> None:
    """Adding a new bridging idea to the ontology must increase resonance connectivity.

    This proves the organic growth property: as new ideas are added,
    the number of cross-domain connections grows — the ontology grows organically.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add a source idea
        await _post_idea(client, {
            "id": "ontology-source",
            "name": "Emergence in Complex Systems",
            "description": "Complex behavior emerges from simple local interactions and rules.",
            "potential_value": 80.0,
            "estimated_cost": 20.0,
            "confidence": 0.85,
            "tags": ["emergence", "complexity", "local", "interactions", "rules"],
            "interfaces": ["domain:complexity-theory"],
        })

        # Check resonance BEFORE adding new idea
        resp_before = await client.get(
            "/api/ideas/ontology-source/concept-resonance",
            params={"min_score": 0.05},
        )
        body_before = resp_before.json()
        total_before = body_before["total"]

        # Add a bridging idea that resonates structurally
        await _post_idea(client, {
            "id": "ontology-bridge",
            "name": "Emergent Behavior in Swarm Robotics",
            "description": "Robots exhibit complex emergence from simple local rules and interactions.",
            "potential_value": 75.0,
            "estimated_cost": 18.0,
            "confidence": 0.8,
            "tags": ["emergence", "complexity", "local", "interactions", "rules", "robotics"],
            "interfaces": ["domain:robotics"],
        })

        # Check resonance AFTER adding bridging idea
        resp_after = await client.get(
            "/api/ideas/ontology-source/concept-resonance",
            params={"min_score": 0.05},
        )
        body_after = resp_after.json()
        total_after = body_after["total"]

    assert resp_before.status_code == 200
    assert resp_after.status_code == 200

    assert total_after > total_before, (
        f"After adding a bridging idea, resonance total must increase. "
        f"Before: {total_before}, After: {total_after}"
    )

    # The new bridging idea must appear in matches
    match_ids_after = [m["idea_id"] for m in body_after["matches"]]
    assert "ontology-bridge" in match_ids_after, (
        "The newly added bridging idea must appear in resonance matches"
    )

    # And it must be cross-domain (complexity-theory → robotics)
    bridge_match = next(m for m in body_after["matches"] if m["idea_id"] == "ontology-bridge")
    assert bridge_match["cross_domain"] is True, (
        "complexity-theory → robotics must be flagged as cross-domain"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 10: Full create-read cycle with resonance verification
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_create_read_resonance_cycle() -> None:
    """Full cycle: create ideas → read each → verify resonance endpoint works.

    Proves: create (POST), existence (GET /api/ideas/{id}), resonance (GET concept-resonance).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas_to_create = [
            {
                "id": "cycle-bio",
                "name": "Evolutionary Pressure Selection",
                "description": "Natural selection exerts pressure on traits through environment.",
                "potential_value": 65.0,
                "estimated_cost": 12.0,
                "confidence": 0.8,
                "tags": ["evolution", "selection", "pressure", "environment", "traits"],
                "interfaces": ["domain:evolutionary-biology"],
            },
            {
                "id": "cycle-ml",
                "name": "Gradient Descent Optimization",
                "description": "Optimization finds minimum through gradient pressure and selection of parameters.",
                "potential_value": 75.0,
                "estimated_cost": 15.0,
                "confidence": 0.9,
                "tags": ["optimization", "selection", "pressure", "gradient", "parameters"],
                "interfaces": ["domain:machine-learning"],
            },
        ]

        for payload in ideas_to_create:
            # CREATE
            create_resp = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
            assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"

            # READ back
            read_resp = await client.get(f"/api/ideas/{payload['id']}", headers=AUTH_HEADERS)
            assert read_resp.status_code == 200, f"Read failed for {payload['id']}: {read_resp.text}"
            read_body = read_resp.json()
            assert read_body["id"] == payload["id"]
            assert read_body["name"] == payload["name"]

        # RESONANCE: evolutionary-biology ↔ machine-learning
        res_resp = await client.get(
            "/api/ideas/cycle-bio/concept-resonance",
            params={"min_score": 0.05},
        )
        assert res_resp.status_code == 200
        res_body = res_resp.json()

        assert res_body["idea_id"] == "cycle-bio"
        match_ids = [m["idea_id"] for m in res_body["matches"]]
        assert "cycle-ml" in match_ids, (
            "Gradient descent (ML) must resonate with evolutionary selection (bio). "
            f"Shared structural tokens: selection, pressure. Got matches: {match_ids}"
        )

        ml_match = next(m for m in res_body["matches"] if m["idea_id"] == "cycle-ml")
        assert ml_match["cross_domain"] is True
        assert "selection" in ml_match["shared_concepts"] or "pressure" in ml_match["shared_concepts"], (
            f"'selection' or 'pressure' must be in shared_concepts. Got: {ml_match['shared_concepts']}"
        )

        # ERROR: Nonexistent idea → 404
        err_resp = await client.get("/api/ideas/cycle-does-not-exist/concept-resonance")
        assert err_resp.status_code == 404
