"""Acceptance tests for the Belief System Interface (belief-system-interface).

Derived acceptance criteria:

1. The concepts API exposes ``cross-view-synthesis``, whose description encodes
   integration of multiple belief systems and worldviews (Living Codex ontology).
2. Searching the ontology for ``belief`` returns at least one concept whose name
   or description relates to belief systems or cross-view synthesis.
3. The concept resonance kernel defines UCore anchors and sacred frequencies used
   as harmonic bases when mapping text into symbols (worldview / belief lens).
4. ``text_to_symbol`` is deterministic for the same text and base concept.
5. ``compare_concepts`` returns bounded CRK and coherence in [0, 1]; comparing a
   symbol to itself yields high coherence.
6. Different ``base_concept`` values change the fundamental frequency anchor
   (distinct belief / core lenses).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.concept_resonance_kernel import (
    CORE_CONCEPTS,
    SACRED_FREQUENCIES,
    compare_concepts,
    concept_to_symbol,
    text_to_symbol,
)
from app.services import concept_service


@pytest.mark.asyncio
async def test_concepts_api_exposes_cross_view_synthesis():
    """R1: GET /api/concepts/cross-view-synthesis includes belief-system semantics."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts/cross-view-synthesis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "cross-view-synthesis"
    desc = (data.get("description") or "").lower()
    assert "belief system" in desc or "belief systems" in desc
    assert "worldview" in desc or "worldviews" in desc


@pytest.mark.asyncio
async def test_concepts_search_surfaces_belief_related_nodes():
    """R2: Search finds ontology nodes relevant to belief / worldviews."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts/search", params={"q": "belief", "limit": 50})
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    ids = {c.get("id") for c in items}
    assert "cross-view-synthesis" in ids


def test_concept_service_search_matches_http_contract():
    """R2 (service): concept_service.search_concepts aligns with router behavior."""
    items = concept_service.search_concepts("belief", limit=50)
    assert any(c.get("id") == "cross-view-synthesis" for c in items)


def test_ucore_and_sacred_frequencies_define_belief_system_bridge():
    """R3: Kernel exposes UCore anchor and sacred frequency tables."""
    assert "ucore" in CORE_CONCEPTS
    assert CORE_CONCEPTS["ucore"]["frequency"] == 432.0
    assert "432hz" in SACRED_FREQUENCIES
    assert SACRED_FREQUENCIES["432hz"]["value"] == 432.0
    assert "love" in CORE_CONCEPTS
    assert CORE_CONCEPTS["love"]["frequency"] != CORE_CONCEPTS["ucore"]["frequency"]


def test_text_to_symbol_is_deterministic():
    """R4: Same text + base → identical harmonic structure (component count, bands)."""
    text = "open source coherence maps belief and evidence together"
    a = text_to_symbol(text, base_concept="ucore")
    b = text_to_symbol(text, base_concept="ucore")
    assert len(a.components) == len(b.components)
    assert [c.band for c in a.components] == [c.band for c in b.components]
    assert [round(c.omega, 6) for c in a.components] == [round(c.omega, 6) for c in b.components]


def test_compare_concepts_self_high_coherence_bounded_scores():
    """R5: Self-comparison is coherent; all scores live in valid ranges."""
    sym = text_to_symbol("shared vocabulary across cultures", base_concept="ucore")
    result = compare_concepts(sym, sym)
    assert 0.0 <= result.crk <= 1.0
    assert 0.0 <= result.coherence <= 1.0
    assert 0.0 <= result.d_codex <= 1.0
    assert result.coherence >= 0.99


def test_base_concept_changes_fundamental_frequency_anchor():
    """R6: Worldview base (ucore vs love) shifts the fundamental harmonic."""
    text = "deterministic bridge text for frequency check"
    u = text_to_symbol(text, base_concept="ucore")
    l = text_to_symbol(text, base_concept="love")
    u_fund = next(c.omega for c in u.components if c.band == "fundamental")
    l_fund = next(c.omega for c in l.components if c.band == "fundamental")
    assert u_fund == CORE_CONCEPTS["ucore"]["frequency"]
    assert l_fund == CORE_CONCEPTS["love"]["frequency"]
    assert u_fund != l_fund


def test_concept_to_symbol_unknown_id_defaults_to_ucore_frequency():
    """concept_to_symbol falls back to 432 Hz base when concept id is unknown."""
    sym = concept_to_symbol("nonexistent-concept-id-for-test", text_keywords=None)
    fund = next(c.omega for c in sym.components if c.band == "fundamental")
    assert fund == 432.0
