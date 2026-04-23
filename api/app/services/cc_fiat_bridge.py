"""CC Fiat Bridge — pure-logic pieces of the financial-integration spec.

Covers the parts of specs/financial-integration.md that don't require
external systems (Base L2, on-ramp partners, KYC providers). These
can be tested without network mocks and land the economic invariants
cleanly:

  - Rate computation with spread (R3)
  - Swap math in both directions (R1 math half)
  - Treasury backing invariant check (R2)
  - Rate staleness detection (R3 staleness)
  - KYC threshold check (R6)
  - Tax report aggregation (R7)

The actual Base L2 transfer, USDC custody, on-ramp partner checkout
session, and KYC provider webhook are all out of scope here — they
need external system integration and belong in follow-up PRs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Constants from the spec ----------

DEFAULT_SPREAD_PCT = Decimal("1.0")
DEFAULT_KYC_THRESHOLD_USD = Decimal("2000")
DEFAULT_KYC_WINDOW_DAYS = 30
DEFAULT_RATE_STALENESS_MINUTES = 30
DEFAULT_MIN_WITHDRAWAL_USD = Decimal("10")


# ---------- Rate computation (R3) ----------


@dataclass(frozen=True)
class RateComputation:
    """Result of rate computation with full formula transparency."""

    rate_usdc_per_cc: Decimal
    rate_cc_per_usdc: Decimal
    spread_pct: Decimal
    buy_rate_cc_per_usdc: Decimal        # what a buyer pays (higher CC per USDC)
    sell_rate_usdc_per_cc: Decimal       # what a seller receives (lower USDC per CC)
    treasury_reserves_usdc: Decimal
    total_cc_outstanding: Decimal
    formula: str
    computed_at: datetime


def compute_rate(
    treasury_reserves_usdc: Decimal,
    total_cc_outstanding: Decimal,
    spread_pct: Decimal = DEFAULT_SPREAD_PCT,
    *,
    now: Optional[datetime] = None,
) -> RateComputation:
    """Compute the exchange rate from treasury reserves and CC outstanding.

    Formula: rate_usdc_per_cc = treasury_reserves_usdc / total_cc_outstanding
    Inverse: rate_cc_per_usdc = 1 / rate_usdc_per_cc

    Raises ValueError if outstanding or reserves is non-positive.
    """
    if total_cc_outstanding <= 0:
        raise ValueError("total_cc_outstanding must be positive")
    if treasury_reserves_usdc <= 0:
        raise ValueError("treasury_reserves_usdc must be positive")
    if spread_pct < 0 or spread_pct >= 100:
        raise ValueError("spread_pct must be in [0, 100)")

    rate_usdc_per_cc = treasury_reserves_usdc / total_cc_outstanding
    rate_cc_per_usdc = total_cc_outstanding / treasury_reserves_usdc

    spread_factor = spread_pct / Decimal("100")
    buy_rate_cc_per_usdc = rate_cc_per_usdc * (Decimal("1") - spread_factor)
    sell_rate_usdc_per_cc = rate_usdc_per_cc * (Decimal("1") - spread_factor)

    return RateComputation(
        rate_usdc_per_cc=rate_usdc_per_cc,
        rate_cc_per_usdc=rate_cc_per_usdc,
        spread_pct=spread_pct,
        buy_rate_cc_per_usdc=buy_rate_cc_per_usdc,
        sell_rate_usdc_per_cc=sell_rate_usdc_per_cc,
        treasury_reserves_usdc=treasury_reserves_usdc,
        total_cc_outstanding=total_cc_outstanding,
        formula="treasury_reserves_usdc / total_cc_outstanding",
        computed_at=now or datetime.now(timezone.utc),
    )


def is_rate_stale(
    computed_at: datetime,
    *,
    now: Optional[datetime] = None,
    max_age_minutes: int = DEFAULT_RATE_STALENESS_MINUTES,
) -> bool:
    """True if the rate was last computed more than max_age_minutes ago."""
    n = now or datetime.now(timezone.utc)
    return (n - computed_at) > timedelta(minutes=max_age_minutes)


# ---------- Swap math (R1) ----------


SwapDirection = Literal["cc_to_usdc", "usdc_to_cc"]


@dataclass(frozen=True)
class SwapMath:
    """The math of a single swap, before any on-chain settlement."""

    direction: SwapDirection
    cc_amount: Decimal
    usdc_amount: Decimal
    rate_used: Decimal     # usdc_per_cc (canonical direction)
    spread_pct: Decimal


def compute_swap(
    amount: Decimal,
    rate: RateComputation,
    direction: SwapDirection,
) -> SwapMath:
    """Compute how much CC is burned and how much USDC is transferred
    (or vice versa for onramp) for a single swap, including spread.

    - cc_to_usdc: contributor burns `amount` CC, receives `amount * sell_rate` USDC
    - usdc_to_cc: contributor sends `amount` USDC, receives `amount * buy_rate` CC
    """
    if amount <= 0:
        raise ValueError("swap amount must be positive")
    if direction == "cc_to_usdc":
        usdc_amount = amount * rate.sell_rate_usdc_per_cc
        return SwapMath(
            direction=direction,
            cc_amount=amount,
            usdc_amount=usdc_amount,
            rate_used=rate.sell_rate_usdc_per_cc,
            spread_pct=rate.spread_pct,
        )
    if direction == "usdc_to_cc":
        cc_amount = amount * rate.buy_rate_cc_per_usdc
        return SwapMath(
            direction=direction,
            cc_amount=cc_amount,
            usdc_amount=amount,
            rate_used=rate.buy_rate_cc_per_usdc,
            spread_pct=rate.spread_pct,
        )
    raise ValueError(f"unknown direction: {direction}")


# ---------- Treasury backing invariant (R2) ----------


@dataclass(frozen=True)
class TreasuryInvariantCheck:
    ok: bool
    reserves_usdc: Decimal
    outstanding_cc: Decimal
    required_usdc: Decimal
    surplus_usdc: Decimal


def check_treasury_invariant(
    reserves_usdc: Decimal,
    outstanding_cc: Decimal,
    rate_usdc_per_cc: Decimal,
) -> TreasuryInvariantCheck:
    """Check reserves >= outstanding * rate.

    The backing invariant the spec names: every CC in circulation
    must be backed by at least rate worth of USDC. If the invariant
    fails, mint/burn operations must be suspended until the treasury
    is replenished.
    """
    required = outstanding_cc * rate_usdc_per_cc
    return TreasuryInvariantCheck(
        ok=reserves_usdc >= required,
        reserves_usdc=reserves_usdc,
        outstanding_cc=outstanding_cc,
        required_usdc=required,
        surplus_usdc=reserves_usdc - required,
    )


# ---------- KYC threshold (R6) ----------


@dataclass(frozen=True)
class KYCThresholdCheck:
    kyc_required: bool
    cumulative_30d_usd: Decimal
    requested_usd: Decimal
    threshold_usd: Decimal
    projected_total_usd: Decimal


def check_kyc_threshold(
    cumulative_30d_usd: Decimal,
    requested_usd: Decimal,
    *,
    threshold_usd: Decimal = DEFAULT_KYC_THRESHOLD_USD,
) -> KYCThresholdCheck:
    """Decide whether a fiat conversion requires KYC.

    KYC is required when the cumulative 30-day fiat conversion plus
    the current request crosses the threshold.
    """
    projected = cumulative_30d_usd + requested_usd
    return KYCThresholdCheck(
        kyc_required=projected > threshold_usd,
        cumulative_30d_usd=cumulative_30d_usd,
        requested_usd=requested_usd,
        threshold_usd=threshold_usd,
        projected_total_usd=projected,
    )


# ---------- Tax report aggregation (R7) ----------


class TaxConversionEntry(BaseModel):
    date: datetime
    cc_amount: Decimal
    usdc_amount: Decimal
    rate_used: Decimal
    type: SwapDirection


class TaxReportSummary(BaseModel):
    total_cc_earned: Decimal = Field(default=Decimal("0"))
    total_cc_converted: Decimal = Field(default=Decimal("0"))
    total_usdc_received: Decimal = Field(default=Decimal("0"))
    total_fiat_withdrawn: Decimal = Field(default=Decimal("0"))
    conversion_count: int = 0


class TaxReport(BaseModel):
    contributor_id: str
    tax_year: int
    summary: TaxReportSummary
    conversions: List[TaxConversionEntry]
    disclaimer: str = (
        "This is a data export, not tax advice. Consult a tax professional."
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def aggregate_tax_report(
    contributor_id: str,
    year: int,
    swaps: Iterable[SwapMath],
    swap_dates: Iterable[datetime],
    *,
    cc_earned_in_year: Decimal = Decimal("0"),
    fiat_withdrawn_in_year: Decimal = Decimal("0"),
) -> TaxReport:
    """Aggregate swaps into an annual tax report.

    cc_earned_in_year is the total CC the contributor received from
    render attribution + contributions in the year (not computed here;
    callers should pass it from the contributions/attribution services).
    fiat_withdrawn_in_year is the total fiat withdrawn to bank.
    """
    entries: List[TaxConversionEntry] = []
    total_cc_converted = Decimal("0")
    total_usdc_received = Decimal("0")

    for swap, date in zip(swaps, swap_dates):
        if date.year != year:
            continue
        entries.append(
            TaxConversionEntry(
                date=date,
                cc_amount=swap.cc_amount,
                usdc_amount=swap.usdc_amount,
                rate_used=swap.rate_used,
                type=swap.direction,
            )
        )
        if swap.direction == "cc_to_usdc":
            total_cc_converted += swap.cc_amount
            total_usdc_received += swap.usdc_amount

    return TaxReport(
        contributor_id=contributor_id,
        tax_year=year,
        summary=TaxReportSummary(
            total_cc_earned=cc_earned_in_year,
            total_cc_converted=total_cc_converted,
            total_usdc_received=total_usdc_received,
            total_fiat_withdrawn=fiat_withdrawn_in_year,
            conversion_count=len(entries),
        ),
        conversions=entries,
    )
