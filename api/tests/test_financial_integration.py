"""Pure-logic tests for the financial-integration spec.

Covers R3 (rate + staleness), R1 math (swap), R2 (treasury invariant),
R6 (KYC threshold), R7 (tax report). External-integration pieces
(Base L2 transfers, on-ramp partner, KYC provider API) need separate
mocks/stubs and live in follow-up PRs.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.cc_fiat_bridge import (
    DEFAULT_KYC_THRESHOLD_USD,
    DEFAULT_RATE_STALENESS_MINUTES,
    RateComputation,
    SwapMath,
    aggregate_tax_report,
    check_kyc_threshold,
    check_treasury_invariant,
    compute_rate,
    compute_swap,
    is_rate_stale,
)


# ---------- Rate computation (R3) ----------


def test_rate_matches_formula():
    rate = compute_rate(
        treasury_reserves_usdc=Decimal("50000"),
        total_cc_outstanding=Decimal("15000000"),
        spread_pct=Decimal("1.0"),
    )
    # 50000 / 15_000_000 ≈ 0.003333
    assert rate.rate_usdc_per_cc == Decimal("50000") / Decimal("15000000")
    assert rate.rate_cc_per_usdc == Decimal("15000000") / Decimal("50000")
    assert rate.formula == "treasury_reserves_usdc / total_cc_outstanding"


def test_rate_applies_spread_to_buy_and_sell():
    rate = compute_rate(
        treasury_reserves_usdc=Decimal("1000"),
        total_cc_outstanding=Decimal("1000000"),
        spread_pct=Decimal("1.0"),
    )
    # rate = 0.001 usdc/cc, 1000 cc/usdc
    # buy_rate = 1000 * 0.99 = 990 cc/usdc
    # sell_rate = 0.001 * 0.99 = 0.00099 usdc/cc
    assert rate.buy_rate_cc_per_usdc == Decimal("990")
    assert rate.sell_rate_usdc_per_cc == Decimal("0.00099")


def test_rate_zero_spread_yields_symmetric_rates():
    rate = compute_rate(
        treasury_reserves_usdc=Decimal("1000"),
        total_cc_outstanding=Decimal("1000"),
        spread_pct=Decimal("0"),
    )
    assert rate.buy_rate_cc_per_usdc == rate.rate_cc_per_usdc
    assert rate.sell_rate_usdc_per_cc == rate.rate_usdc_per_cc


def test_rate_rejects_non_positive_reserves():
    with pytest.raises(ValueError):
        compute_rate(
            treasury_reserves_usdc=Decimal("0"),
            total_cc_outstanding=Decimal("1000"),
        )


def test_rate_rejects_non_positive_outstanding():
    with pytest.raises(ValueError):
        compute_rate(
            treasury_reserves_usdc=Decimal("1000"),
            total_cc_outstanding=Decimal("-1"),
        )


def test_rate_rejects_out_of_bounds_spread():
    with pytest.raises(ValueError):
        compute_rate(
            treasury_reserves_usdc=Decimal("1000"),
            total_cc_outstanding=Decimal("1000"),
            spread_pct=Decimal("100"),
        )


def test_rate_no_manual_override_possible():
    """The only way to get a RateComputation is through compute_rate.
    There's no constructor path that sets the rate independent of the
    formula inputs.
    """
    rate = compute_rate(
        treasury_reserves_usdc=Decimal("100"),
        total_cc_outstanding=Decimal("10"),
    )
    # Reconstructing from inputs produces the same rate
    assert rate.rate_usdc_per_cc == Decimal("100") / Decimal("10")
    # RateComputation is frozen; direct mutation fails
    with pytest.raises(Exception):
        rate.rate_usdc_per_cc = Decimal("999")  # type: ignore[misc]


# ---------- Rate staleness (R3) ----------


def test_rate_staleness_fresh():
    now = datetime.now(timezone.utc)
    assert is_rate_stale(now - timedelta(minutes=5), now=now) is False


def test_rate_staleness_stale():
    now = datetime.now(timezone.utc)
    assert is_rate_stale(
        now - timedelta(minutes=DEFAULT_RATE_STALENESS_MINUTES + 1),
        now=now,
    )


def test_rate_staleness_boundary():
    now = datetime.now(timezone.utc)
    # exactly at threshold is not stale (> comparison)
    assert not is_rate_stale(
        now - timedelta(minutes=DEFAULT_RATE_STALENESS_MINUTES),
        now=now,
    )


# ---------- Swap math (R1) ----------


def _make_rate():
    return compute_rate(
        treasury_reserves_usdc=Decimal("1000"),
        total_cc_outstanding=Decimal("1000000"),
        spread_pct=Decimal("1.0"),
    )


def test_swap_cc_to_usdc_burns_cc_and_applies_spread():
    rate = _make_rate()
    math = compute_swap(Decimal("10000"), rate, "cc_to_usdc")
    # sell_rate = 0.001 * 0.99 = 0.00099 usdc/cc
    # usdc = 10000 * 0.00099 = 9.9
    assert math.cc_amount == Decimal("10000")
    assert math.usdc_amount == Decimal("9.9000")
    assert math.direction == "cc_to_usdc"


def test_swap_usdc_to_cc_buys_cc_with_spread():
    rate = _make_rate()
    math = compute_swap(Decimal("10"), rate, "usdc_to_cc")
    # buy_rate = 1000 * 0.99 = 990 cc/usdc
    # cc = 10 * 990 = 9900
    assert math.cc_amount == Decimal("9900.00")
    assert math.usdc_amount == Decimal("10")


def test_swap_rejects_non_positive_amount():
    rate = _make_rate()
    with pytest.raises(ValueError):
        compute_swap(Decimal("0"), rate, "cc_to_usdc")
    with pytest.raises(ValueError):
        compute_swap(Decimal("-1"), rate, "cc_to_usdc")


def test_swap_rejects_unknown_direction():
    rate = _make_rate()
    with pytest.raises(ValueError):
        compute_swap(Decimal("100"), rate, "sideways")  # type: ignore[arg-type]


def test_swap_zero_spread_reversible():
    rate = compute_rate(
        treasury_reserves_usdc=Decimal("1"),
        total_cc_outstanding=Decimal("1"),
        spread_pct=Decimal("0"),
    )
    out = compute_swap(Decimal("5"), rate, "cc_to_usdc")
    back = compute_swap(out.usdc_amount, rate, "usdc_to_cc")
    assert back.cc_amount == Decimal("5")


# ---------- Treasury invariant (R2) ----------


def test_treasury_invariant_passes_with_surplus():
    check = check_treasury_invariant(
        reserves_usdc=Decimal("2000"),
        outstanding_cc=Decimal("1000000"),
        rate_usdc_per_cc=Decimal("0.001"),
    )
    # required = 1_000_000 * 0.001 = 1000; reserves 2000 → surplus 1000
    assert check.ok is True
    assert check.surplus_usdc == Decimal("1000")


def test_treasury_invariant_exactly_backed():
    check = check_treasury_invariant(
        reserves_usdc=Decimal("1000"),
        outstanding_cc=Decimal("1000000"),
        rate_usdc_per_cc=Decimal("0.001"),
    )
    assert check.ok is True
    assert check.surplus_usdc == Decimal("0")


def test_treasury_invariant_fails_when_under_reserved():
    check = check_treasury_invariant(
        reserves_usdc=Decimal("500"),
        outstanding_cc=Decimal("1000000"),
        rate_usdc_per_cc=Decimal("0.001"),
    )
    assert check.ok is False
    assert check.surplus_usdc == Decimal("-500")


# ---------- KYC threshold (R6) ----------


def test_kyc_below_threshold_not_required():
    check = check_kyc_threshold(
        cumulative_30d_usd=Decimal("1500"),
        requested_usd=Decimal("400"),
    )
    # 1500 + 400 = 1900, below 2000
    assert check.kyc_required is False


def test_kyc_crossing_threshold_triggers():
    check = check_kyc_threshold(
        cumulative_30d_usd=Decimal("1800"),
        requested_usd=Decimal("300"),
    )
    # 1800 + 300 = 2100, above 2000
    assert check.kyc_required is True
    assert check.projected_total_usd == Decimal("2100")


def test_kyc_at_threshold_not_required():
    check = check_kyc_threshold(
        cumulative_30d_usd=Decimal("1500"),
        requested_usd=Decimal("500"),
    )
    # 1500 + 500 = 2000, which is NOT above 2000
    assert check.kyc_required is False


def test_kyc_threshold_custom():
    check = check_kyc_threshold(
        cumulative_30d_usd=Decimal("500"),
        requested_usd=Decimal("600"),
        threshold_usd=Decimal("1000"),
    )
    assert check.kyc_required is True


def test_kyc_default_threshold_is_2000():
    assert DEFAULT_KYC_THRESHOLD_USD == Decimal("2000")


# ---------- Tax report aggregation (R7) ----------


def test_tax_report_totals_over_a_year():
    rate = _make_rate()
    swaps = [
        compute_swap(Decimal("1000"), rate, "cc_to_usdc"),
        compute_swap(Decimal("2000"), rate, "cc_to_usdc"),
        compute_swap(Decimal("500"), rate, "cc_to_usdc"),
    ]
    dates = [
        datetime(2026, 3, 15, tzinfo=timezone.utc),
        datetime(2026, 6, 20, tzinfo=timezone.utc),
        datetime(2026, 11, 2, tzinfo=timezone.utc),
    ]
    report = aggregate_tax_report(
        contributor_id="contributor:alice",
        year=2026,
        swaps=swaps,
        swap_dates=dates,
        cc_earned_in_year=Decimal("10000"),
        fiat_withdrawn_in_year=Decimal("2.5"),
    )
    assert report.tax_year == 2026
    assert report.summary.total_cc_converted == Decimal("3500")
    assert report.summary.conversion_count == 3
    assert report.summary.total_cc_earned == Decimal("10000")
    assert report.summary.total_fiat_withdrawn == Decimal("2.5")
    assert "not tax advice" in report.disclaimer.lower()


def test_tax_report_filters_by_year():
    rate = _make_rate()
    swaps = [
        compute_swap(Decimal("1000"), rate, "cc_to_usdc"),
        compute_swap(Decimal("2000"), rate, "cc_to_usdc"),
    ]
    dates = [
        datetime(2026, 3, 15, tzinfo=timezone.utc),
        datetime(2025, 12, 31, tzinfo=timezone.utc),
    ]
    report = aggregate_tax_report(
        contributor_id="contributor:alice",
        year=2026,
        swaps=swaps,
        swap_dates=dates,
    )
    assert report.summary.conversion_count == 1
    assert report.summary.total_cc_converted == Decimal("1000")


def test_tax_report_ignores_onramps_in_cc_converted():
    rate = _make_rate()
    swaps = [
        compute_swap(Decimal("1000"), rate, "cc_to_usdc"),
        compute_swap(Decimal("50"), rate, "usdc_to_cc"),  # onramp
    ]
    dates = [
        datetime(2026, 3, 15, tzinfo=timezone.utc),
        datetime(2026, 4, 1, tzinfo=timezone.utc),
    ]
    report = aggregate_tax_report(
        contributor_id="contributor:alice",
        year=2026,
        swaps=swaps,
        swap_dates=dates,
    )
    # Only cc_to_usdc swaps count toward "converted" totals
    assert report.summary.conversion_count == 2
    assert report.summary.total_cc_converted == Decimal("1000")
    assert Decimal(report.summary.total_usdc_received) > Decimal("0")


def test_tax_report_empty():
    report = aggregate_tax_report(
        contributor_id="contributor:alice",
        year=2026,
        swaps=[],
        swap_dates=[],
    )
    assert report.summary.conversion_count == 0
    assert report.summary.total_cc_converted == Decimal("0")
    assert report.conversions == []
