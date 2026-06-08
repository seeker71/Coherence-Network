"""Tests for /api/utils/concept_match_score — the string-MEMBERSHIP scoring half
of concept_auto_tagger._score_concept.

The body runs as a Form recipe (endpoint_concept_match_score_demo.fk). The
request currently tokenizes the idea + concept text before dispatch (the regex
_extract_keywords + the lowercased concept_text / idea_text assembly), and the
KERNEL scores the already-tokenized keyword lists — forward = fraction of idea
keywords found in concept_text via str_find membership, reverse = fraction of
concept keywords found in idea_text, plus a 0.3 name bonus, combined
round(min(0.5*forward + 0.3*reverse + name_bonus, 1.0), 4). The str_find native
is three-way value-identical for ASCII (string-membership-band.fk); the recipe
fold is Rust+TS value-exact == CPython (parity_suite gate).

These tests verify the route is wired, host-tokenizes, returns the score + echoed
keyword bags, honors the empty-keywords host guard, and — the core gate — matches
the concept service scoring shape on representative + edge inputs.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.concept_auto_tagger import _extract_keywords, _score_concept

BASE = "http://test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


def _expected(idea_name, idea_description, concept_name, concept_description, ckw):
    """The real _score_concept over the same host-tokenized inputs the route builds."""
    keywords = _extract_keywords(f"{idea_name} {idea_description}")
    concept = {"name": concept_name, "description": concept_description, "keywords": ckw}
    return _score_concept(concept, keywords)


class TestConceptMatchScoreEndpoint:
    """The bidirectional string-membership score over host-tokenized keyword lists."""

    @pytest.mark.anyio
    async def test_canonical_sample(self, client: AsyncClient):
        """The default sample scores 0.825 — forward 3/4, reverse 1/2, name bonus 0.3."""
        res = await client.get("/api/utils/concept_match_score")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["score"] == 0.825
        assert data["keywords"] == ["energy", "flow", "coherence", "xyz"]
        assert data["concept_keywords"] == ["energy", "tissue"]
        assert data["runtime"] in ("inline", "subprocess")

    @pytest.mark.anyio
    async def test_matches_real_score_concept(self, client: AsyncClient):
        """The kernel score equals the real _score_concept on the canonical sample."""
        res = await client.get("/api/utils/concept_match_score")
        expected = _expected(
            "energy flow", "coherence xyz",
            "Energy Flow", "energy flows as coherence through the body field",
            ["Energy", "Tissue"],
        )
        assert res.json()["score"] == expected

    @pytest.mark.anyio
    async def test_all_forward_no_concept_keywords(self, client: AsyncClient):
        """Every idea keyword in concept_text, no concept keywords, name not matched → 0.5."""
        params = {
            "idea_name": "alpha beta",
            "idea_description": "gamma",
            "concept_name": "Zeta",
            "concept_description": "alpha beta gamma delta",
            "concept_keywords": "",
        }
        res = await client.get("/api/utils/concept_match_score", params=params)
        assert res.status_code == 200, res.text
        # forward 3/3 = 1.0, reverse 0.0 (no concept kws), name bonus 0.0
        assert res.json()["score"] == 0.5
        assert res.json()["score"] == _expected(
            "alpha beta", "gamma", "Zeta", "alpha beta gamma delta", []
        )

    @pytest.mark.anyio
    async def test_partial_match_matches_parity_reference(self, client: AsyncClient):
        """A richer pair returns the recipe's score, matching the real _score_concept."""
        params = {
            "idea_name": "agent pipeline",
            "idea_description": "orchestration of cells",
            "concept_name": "Agent Orchestration",
            "concept_description": "agents orchestrate the pipeline of living cells",
            "concept_keywords": "Agent,Cell,Flow",
        }
        res = await client.get("/api/utils/concept_match_score", params=params)
        assert res.status_code == 200, res.text
        expected = _expected(
            "agent pipeline", "orchestration of cells",
            "Agent Orchestration", "agents orchestrate the pipeline of living cells",
            ["Agent", "Cell", "Flow"],
        )
        assert res.json()["score"] == expected

    @pytest.mark.anyio
    async def test_empty_keywords_host_guard(self, client: AsyncClient):
        """Only stopwords / <3-char tokens → no keywords → host-guarded 0.0."""
        params = {
            "idea_name": "a an",
            "idea_description": "to of",
            "concept_name": "X",
            "concept_description": "y",
            "concept_keywords": "",
        }
        res = await client.get("/api/utils/concept_match_score", params=params)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["score"] == 0.0
        assert data["keywords"] == []
        assert data["runtime"] == "host-guard"

    @pytest.mark.anyio
    async def test_name_bonus_present_and_absent(self, client: AsyncClient):
        """The 0.3 name bonus fires only when the lowercased concept name is in idea_text."""
        # name "energy flow" is contiguous in idea_text "energy flow" → bonus fires
        with_bonus = await client.get(
            "/api/utils/concept_match_score",
            params={
                "idea_name": "energy flow",
                "idea_description": "",
                "concept_name": "Energy Flow",
                "concept_description": "unrelated words only",
                "concept_keywords": "",
            },
        )
        # name "tissue body" never appears contiguous in idea_text → no bonus
        without_bonus = await client.get(
            "/api/utils/concept_match_score",
            params={
                "idea_name": "energy flow",
                "idea_description": "",
                "concept_name": "Tissue Body",
                "concept_description": "unrelated words only",
                "concept_keywords": "",
            },
        )
        assert with_bonus.json()["score"] > without_bonus.json()["score"]
        # And each matches the real _score_concept.
        assert with_bonus.json()["score"] == _expected(
            "energy flow", "", "Energy Flow", "unrelated words only", []
        )
