"""Tests for Coherence Credit (CC) models and service — Spec 119."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.models.coherence_credit import (
    CostVector,
    ExchangeRate,
    ExchangeRateConfig,
    ProviderRate,
    ValueVector,
)
from app.models.idea import Idea
from app.services import coherence_credit_service as ccs


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCostVector:
    def test_total_equals_sum(self):
        cv = ccs.compute_cost_vector(
            compute_cc=10.0,
            infrastructure_cc=5.0,
            human_attention_cc=3.0,
            opportunity_cc=2.0,
            external_cc=1.0,
        )
        assert cv.total_cc == pytest.approx(21.0)

    def test_defaults_zero(self):
        cv = CostVector(total_cc=0.0)
        assert cv.compute_cc == 0.0
        assert cv.infrastructure_cc == 0.0
        assert cv.human_attention_cc == 0.0
        assert cv.opportunity_cc == 0.0
        assert cv.external_cc == 0.0

    def test_negative_total_rejected(self):
        with pytest.raises(Exception):
            CostVector(total_cc=-1.0)


class TestValueVector:
    def test_total_equals_sum(self):
        vv = ccs.compute_value_vector(
            adoption_cc=20.0,
            lineage_cc=15.0,
            friction_avoided_cc=10.0,
            revenue_cc=5.0,
        )
        assert vv.total_cc == pytest.approx(50.0)

    def test_defaults_zero(self):
        vv = ValueVector(total_cc=0.0)
        assert vv.adoption_cc == 0.0
        assert vv.lineage_cc == 0.0
        assert vv.friction_avoided_cc == 0.0
        assert vv.revenue_cc == 0.0


class TestExchangeRate:
    def test_valid_rate(self):
        rate = ExchangeRate(
            epoch="2026-Q1",
            cc_per_usd=333.33,
            reference_rate_usd=0.003,
        )
        assert rate.epoch == "2026-Q1"
        assert rate.cc_per_usd == 333.33
        assert rate.reference_model == "claude-sonnet-4-20250514"
        assert rate.human_hour_cc == 500.0

    def test_zero_cc_per_usd_rejected(self):
        with pytest.raises(Exception):
            ExchangeRate(epoch="2026-Q1", cc_per_usd=0.0, reference_rate_usd=0.003)

    def test_empty_epoch_rejected(self):
        with pytest.raises(Exception):
            ExchangeRate(epoch="", cc_per_usd=333.33, reference_rate_usd=0.003)


class TestProviderRate:
    def test_valid_provider(self):
        pr = ProviderRate(
            provider_id="test-provider",
            cc_per_1k_input=1.0,
            cc_per_1k_output=4.0,
            quality_score=0.85,
        )
        assert pr.provider_id == "test-provider"
        assert pr.quality_score == 0.85

    def test_quality_score_bounds(self):
        with pytest.raises(Exception):
            ProviderRate(provider_id="x", cc_per_1k_input=1.0, cc_per_1k_output=1.0, quality_score=1.5)

    def test_cheapest_per_quality_unit(self):
        """Compare providers: cost per quality unit for 1K input + 1K output."""
        sonnet = ProviderRate(
            provider_id="sonnet", cc_per_1k_input=1.0, cc_per_1k_output=4.0, quality_score=0.85
        )
        gpt4 = ProviderRate(
            provider_id="gpt4", cc_per_1k_input=10.0, cc_per_1k_output=30.0, quality_score=0.82
        )
        llama = ProviderRate(
            provider_id="llama", cc_per_1k_input=0.2, cc_per_1k_output=0.2, quality_score=0.55
        )

        def cost_per_quality(p: ProviderRate) -> float:
            return (p.cc_per_1k_input + p.cc_per_1k_output) / p.quality_score

        # Sonnet should be cheapest per quality unit among sonnet and gpt4
        assert cost_per_quality(sonnet) < cost_per_quality(gpt4)
        # Llama is cheapest overall but lowest quality
        assert cost_per_quality(llama) < cost_per_quality(sonnet)


# ---------------------------------------------------------------------------
# Conversion tests
# ---------------------------------------------------------------------------


class TestConversions:
    def setup_method(self):
        ccs.reset_config()

    def test_cc_from_usd(self):
        cc = ccs.cc_from_usd(1.0)
        assert cc == pytest.approx(333.33, rel=1e-4)

    def test_usd_from_cc(self):
        usd = ccs.usd_from_cc(333.33)
        assert usd == pytest.approx(1.0, rel=1e-4)

    def test_inverse_cc_usd(self):
        """cc_from_usd and usd_from_cc must be inverse operations."""
        for amount in [0.0, 0.001, 1.0, 100.0, 99999.99]:
            cc = ccs.cc_from_usd(amount)
            back = ccs.usd_from_cc(cc)
            assert back == pytest.approx(amount, rel=1e-6), f"Failed round-trip for {amount}"

    def test_inverse_usd_cc(self):
        for amount in [0.0, 1.0, 333.33, 10000.0]:
            usd = ccs.usd_from_cc(amount)
            back = ccs.cc_from_usd(usd)
            assert back == pytest.approx(amount, rel=1e-6), f"Failed round-trip for {amount}"

    def test_current_rate(self):
        rate = ccs.current_rate()
        assert rate.epoch == "2026-Q1"
        assert rate.cc_per_usd == pytest.approx(333.33, rel=1e-4)
        assert rate.reference_model == "claude-sonnet-4-20250514"


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def setup_method(self):
        ccs.reset_config()

    def teardown_method(self):
        ccs.reset_config()

    def test_default_config_loads_when_no_file(self):
        """When config file is missing, defaults are used."""
        original = ccs._CONFIG_FILE
        try:
            ccs._CONFIG_FILE = "/nonexistent/path/exchange_rates.json"
            ccs.reset_config()
            rate = ccs.current_rate()
            assert rate.epoch == "2026-Q1"
            assert rate.cc_per_usd == pytest.approx(333.33, rel=1e-4)
        finally:
            ccs._CONFIG_FILE = original
            ccs.reset_config()

    def test_config_file_loads_when_present(self):
        """When config file exists, it is loaded."""
        config = {
            "current_epoch": "2026-Q2",
            "rates": [
                {
                    "epoch": "2026-Q2",
                    "cc_per_usd": 400.0,
                    "reference_model": "test-model",
                    "reference_rate_usd": 0.0025,
                    "human_hour_cc": 600.0,
                }
            ],
            "providers": [],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            tmp_path = f.name

        original = ccs._CONFIG_FILE
        try:
            ccs._CONFIG_FILE = tmp_path
            ccs.reset_config()
            rate = ccs.current_rate()
            assert rate.epoch == "2026-Q2"
            assert rate.cc_per_usd == pytest.approx(400.0)
        finally:
            ccs._CONFIG_FILE = original
            ccs.reset_config()
            os.unlink(tmp_path)

    def test_provider_rate_lookup(self):
        """Provider rates can be looked up by ID."""
        ccs.reset_config()
        sonnet = ccs.provider_rate("openrouter-sonnet")
        assert sonnet is not None
        assert sonnet.cc_per_1k_input == 1.0
        assert sonnet.cc_per_1k_output == 4.0

        missing = ccs.provider_rate("nonexistent-provider")
        assert missing is None


# ---------------------------------------------------------------------------
# Idea model integration tests
# ---------------------------------------------------------------------------


class TestIdeaValueBasis:
    def test_value_basis_field(self):
        """value_basis can be set on Idea model."""
        idea = Idea(
            id="test-idea",
            name="Test",
            description="A test idea",
            potential_value=10.0,
            estimated_cost=5.0,
            value_basis={
                "potential_value": "10 = test rationale",
                "estimated_cost": "5 = test cost rationale",
            },
        )
        assert idea.value_basis is not None
        assert "potential_value" in idea.value_basis
        assert idea.value_basis["potential_value"] == "10 = test rationale"

    def test_value_basis_default_none(self):
        idea = Idea(
            id="test-idea",
            name="Test",
            description="A test idea",
            potential_value=10.0,
            estimated_cost=5.0,
        )
        assert idea.value_basis is None

    def test_value_basis_serialization(self):
        vb = {"potential_value": "10 = grounded", "actual_value": "5 = measured"}
        idea = Idea(
            id="test-idea",
            name="Test",
            description="A test idea",
            potential_value=10.0,
            estimated_cost=5.0,
            value_basis=vb,
        )
        data = idea.model_dump()
        assert data["value_basis"] == vb

        # Deserialize back
        idea2 = Idea(**data)
        assert idea2.value_basis == vb

    def test_cost_vector_on_idea(self):
        cv = ccs.compute_cost_vector(compute_cc=5.0, infrastructure_cc=2.0)
        idea = Idea(
            id="test-idea",
            name="Test",
            description="A test idea",
            potential_value=10.0,
            estimated_cost=5.0,
            cost_vector=cv.model_dump(),
        )
        assert idea.cost_vector is not None
        assert idea.cost_vector.total_cc == pytest.approx(7.0)

    def test_value_vector_on_idea(self):
        vv = ccs.compute_value_vector(adoption_cc=10.0, lineage_cc=5.0)
        idea = Idea(
            id="test-idea",
            name="Test",
            description="A test idea",
            potential_value=10.0,
            estimated_cost=5.0,
            value_vector=vv.model_dump(),
        )
        assert idea.value_vector is not None
        assert idea.value_vector.total_cc == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Seed data verification
# ---------------------------------------------------------------------------


class TestSeedData:
    def test_every_idea_has_value_basis(self):
        """Every idea in SEED_IDEAS must have a value_basis entry."""
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "scripts"))
        from seed_db import SEED_IDEAS

        missing = []
        for idea in SEED_IDEAS:
            if "value_basis" not in idea or not idea["value_basis"]:
                missing.append(idea["id"])

        assert missing == [], f"Ideas missing value_basis: {missing}"

    def test_value_basis_has_required_keys(self):
        """Each value_basis should have entries for the standard numeric fields."""
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "scripts"))
        from seed_db import SEED_IDEAS

        required_keys = {"potential_value", "actual_value", "estimated_cost", "actual_cost", "confidence", "resistance_risk"}

        problems = []
        for idea in SEED_IDEAS:
            vb = idea.get("value_basis", {})
            missing_keys = required_keys - set(vb.keys())
            if missing_keys:
                problems.append(f"{idea['id']} missing: {missing_keys}")

        assert problems == [], f"Value basis key problems: {problems}"
