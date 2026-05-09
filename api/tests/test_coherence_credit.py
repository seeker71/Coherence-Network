"""Tests for the cc-economics-and-value-coherence spec
(specs/cc-economics-and-value-coherence.md).

Exercises the lower-level CC economics service that the spec names
in source: — exchange rate lookup, USD↔CC conversion, cost/value
vector composition. The router-level supply/stake/exchange-rate
endpoints layer on top of this service; their flow tests live in
test_creator_economy.py and friends.
"""
from __future__ import annotations

import pytest

from app.models.coherence_credit import (
    CostVector,
    ExchangeRate,
    ValueVector,
)
from app.services import coherence_credit_service as ccs


@pytest.fixture(autouse=True)
def reset_cc_config():
    """Each test starts with a fresh config (the service caches)."""
    ccs.reset_config()
    yield
    ccs.reset_config()


def test_current_rate_returns_exchange_rate_instance():
    rate = ccs.current_rate()
    assert isinstance(rate, ExchangeRate)
    assert rate.cc_per_usd > 0


def test_cc_from_usd_round_trips_via_usd_from_cc():
    """100 USD → CC → USD should land on 100 (within float tolerance)."""
    cc = ccs.cc_from_usd(100.0)
    back = ccs.usd_from_cc(cc)
    assert abs(back - 100.0) < 1e-6


def test_cc_from_usd_scales_linearly():
    one = ccs.cc_from_usd(1.0)
    ten = ccs.cc_from_usd(10.0)
    assert abs(ten - one * 10) < 1e-6


def test_compute_cost_vector_auto_sums_total():
    cv = ccs.compute_cost_vector(
        compute_cc=1.0,
        infrastructure_cc=2.0,
        human_attention_cc=3.0,
        opportunity_cc=4.0,
        external_cc=5.0,
    )
    assert isinstance(cv, CostVector)
    assert cv.total_cc == 15.0
    assert cv.compute_cc == 1.0
    assert cv.external_cc == 5.0


def test_compute_cost_vector_defaults_to_zero():
    cv = ccs.compute_cost_vector()
    assert cv.total_cc == 0.0
    assert cv.compute_cc == 0.0


def test_compute_value_vector_auto_sums_total():
    vv = ccs.compute_value_vector(
        adoption_cc=10.0,
        lineage_cc=5.0,
        friction_avoided_cc=2.0,
        revenue_cc=3.0,
    )
    assert isinstance(vv, ValueVector)
    assert vv.total_cc == 20.0
    assert vv.adoption_cc == 10.0


def test_compute_value_vector_defaults_to_zero():
    vv = ccs.compute_value_vector()
    assert vv.total_cc == 0.0


def test_provider_rate_returns_none_for_unknown_provider():
    assert ccs.provider_rate("nonexistent-provider-xyz") is None


def test_current_rate_fallback_when_unknown_epoch():
    """Asking for an epoch that doesn't exist falls back to first rate
    (or default), not None — the function's signature returns ExchangeRate."""
    rate = ccs.current_rate(epoch="this-epoch-does-not-exist")
    assert isinstance(rate, ExchangeRate)
    assert rate.cc_per_usd > 0
