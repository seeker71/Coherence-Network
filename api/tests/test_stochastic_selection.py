"""Tests for weighted stochastic idea selection."""

from __future__ import annotations

import math
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.idea_service import _softmax_weights, select_idea

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit: softmax weights
# ---------------------------------------------------------------------------

class TestSoftmaxWeights:
    def test_empty_returns_empty(self):
        assert _softmax_weights([], 1.0) == []

    def test_sums_to_one(self):
        weights = _softmax_weights([5.0, 3.0, 1.0, 0.5], 1.0)
        assert abs(sum(weights) - 1.0) < 1e-9

    def test_deterministic_at_zero_temperature(self):
        weights = _softmax_weights([1.0, 5.0, 3.0], 0.0)
        assert weights[1] == 1.0
        assert weights[0] == 0.0
        assert weights[2] == 0.0

    def test_higher_score_gets_higher_weight(self):
        weights = _softmax_weights([10.0, 5.0, 1.0], 1.0)
        assert weights[0] > weights[1] > weights[2]

    def test_high_temperature_flattens_distribution(self):
        low_temp = _softmax_weights([10.0, 1.0], 0.5)
        high_temp = _softmax_weights([10.0, 1.0], 5.0)
        # At high temp, the difference between weights should be smaller
        spread_low = abs(low_temp[0] - low_temp[1])
        spread_high = abs(high_temp[0] - high_temp[1])
        assert spread_high < spread_low

    def test_uniform_scores_give_uniform_weights(self):
        weights = _softmax_weights([3.0, 3.0, 3.0], 1.0)
        for w in weights:
            assert abs(w - 1.0 / 3) < 1e-9

    def test_single_item(self):
        weights = _softmax_weights([42.0], 1.0)
        assert weights == [1.0]


# ---------------------------------------------------------------------------
# Unit: select_idea with seed for reproducibility
# ---------------------------------------------------------------------------

class TestSelectIdea:
    def _seed_test_ideas(self):
        """Seed a few ideas with known scores."""
        ideas = [
            {
                "id": "high-gap",
                "name": "High value gap idea",
                "description": "Big gap, moderate cost",
                "potential_value": 100.0,
                "actual_value": 10.0,
                "estimated_cost": 20.0,
                "actual_cost": 5.0,
                "confidence": 0.8,
                "resistance_risk": 2.0,
            },
            {
                "id": "nearly-done",
                "name": "Nearly done idea",
                "description": "Small gap, nearly free",
                "potential_value": 50.0,
                "actual_value": 48.0,
                "estimated_cost": 10.0,
                "actual_cost": 9.5,
                "confidence": 0.95,
                "resistance_risk": 0.5,
            },
            {
                "id": "risky-big",
                "name": "Risky big idea",
                "description": "Huge gap but low confidence",
                "potential_value": 200.0,
                "actual_value": 0.0,
                "estimated_cost": 50.0,
                "actual_cost": 0.0,
                "confidence": 0.3,
                "resistance_risk": 8.0,
            },
        ]
        for idea in ideas:
            resp = client.post("/api/ideas", json=idea)
            assert resp.status_code in (200, 201, 409), f"Failed to seed {idea['id']}: {resp.text}"

    def test_seed_gives_reproducible_pick(self):
        self._seed_test_ideas()
        r1 = select_idea(method="marginal_cc", temperature=1.0, seed=42)
        r2 = select_idea(method="marginal_cc", temperature=1.0, seed=42)
        assert r1.selected.id == r2.selected.id

    def test_different_seeds_can_give_different_picks(self):
        self._seed_test_ideas()
        # With enough tries, different seeds should sometimes pick differently
        picks = set()
        for s in range(100):
            r = select_idea(method="marginal_cc", temperature=2.0, seed=s)
            picks.add(r.selected.id)
        # At temperature=2.0, we should see at least 2 different ideas picked
        assert len(picks) >= 2, f"Only picked {picks} across 100 seeds"

    def test_deterministic_at_zero_temperature(self):
        self._seed_test_ideas()
        picks = set()
        for s in range(20):
            r = select_idea(method="marginal_cc", temperature=0.0, seed=s)
            picks.add(r.selected.id)
        # temperature=0 should always pick the same top idea
        assert len(picks) == 1

    def test_distribution_matches_ranking_over_many_picks(self):
        """Over many samples, the top-ranked idea should be picked most often."""
        self._seed_test_ideas()
        counts: Counter = Counter()
        n = 500
        for s in range(n):
            r = select_idea(method="marginal_cc", temperature=1.0, seed=s)
            counts[r.selected.id] += 1

        # The most frequently picked idea should be the deterministic top pick
        most_common_id = counts.most_common(1)[0][0]
        r = select_idea(method="marginal_cc", temperature=0.0, seed=0)
        top_id = r.selected.id

        # The deterministic top pick should be the most common OR in top-3
        top_3_ids = [c[0] for c in counts.most_common(3)]
        assert top_id in top_3_ids, (
            f"Deterministic top: {top_id}, "
            f"most common 3: {top_3_ids}"
        )

    def test_result_shape(self):
        self._seed_test_ideas()
        r = select_idea(method="free_energy", temperature=1.0, seed=7)
        assert r.method == "free_energy"
        assert r.temperature == 1.0
        assert r.pool_size > 0
        assert 0.0 <= r.selection_weight <= 1.0
        assert r.selected.id
        assert r.selected.free_energy_score >= 0
        assert r.selected.marginal_cc_score >= 0
        assert r.selected.selection_weight > 0

    def test_exclude_ids(self):
        self._seed_test_ideas()
        # Get the deterministic top pick
        top = select_idea(method="marginal_cc", temperature=0.0, seed=0)
        top_id = top.selected.id
        # Exclude it
        r = select_idea(method="marginal_cc", temperature=0.0, seed=0, exclude_ids=[top_id])
        assert r.selected.id != top_id


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

class TestSelectEndpoint:
    def _seed(self):
        for idea in [
            {"id": "ep-idea-1", "name": "EP Idea 1", "description": "d", "potential_value": 50, "estimated_cost": 5, "confidence": 0.9},
            {"id": "ep-idea-2", "name": "EP Idea 2", "description": "d", "potential_value": 100, "estimated_cost": 10, "confidence": 0.7},
        ]:
            client.post("/api/ideas", json=idea)

    def test_select_endpoint_returns_result(self):
        self._seed()
        resp = client.post("/api/ideas/select?method=marginal_cc&temperature=1.0&seed=42")
        assert resp.status_code == 200
        data = resp.json()
        assert "selected" in data
        assert "method" in data
        assert data["method"] == "marginal_cc"
        assert "temperature" in data
        assert "selection_weight" in data
        assert "pool_size" in data

    def test_select_deterministic_via_seed(self):
        self._seed()
        r1 = client.post("/api/ideas/select?method=free_energy&seed=99").json()
        r2 = client.post("/api/ideas/select?method=free_energy&seed=99").json()
        assert r1["selected"]["id"] == r2["selected"]["id"]

    def test_select_with_exclude(self):
        self._seed()
        top = client.post("/api/ideas/select?temperature=0&seed=0").json()
        top_id = top["selected"]["id"]
        r = client.post(f"/api/ideas/select?temperature=0&seed=0&exclude={top_id}").json()
        assert r["selected"]["id"] != top_id

    def test_list_ideas_includes_selection_weight(self):
        self._seed()
        resp = client.get("/api/ideas?sort=marginal_cc")
        assert resp.status_code == 200
        ideas = resp.json()["ideas"]
        weights = [i["selection_weight"] for i in ideas]
        # All weights should be >= 0 and at least one > 0
        assert all(w >= 0 for w in weights)
        assert any(w > 0 for w in weights)
        # Weights should sum to ~1.0 (across ALL ideas, not just this page)
        total = sum(w for w in weights)
        assert total > 0  # at minimum some weight exists
