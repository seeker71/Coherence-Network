"""CC Exchange Adapter Service — pluggable bridge to external exchanges.

Supports manual settlement (human confirms both sides) and API-based
settlement (when external systems publish protocols). Each adapter
implements a common interface.

Architecture:
    CC Internal Economy → Exchange Adapter → External System
    (treasury mint/burn)   (quote/swap)     (NE Exchange, CES, etc.)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from app.models.cc_exchange import (
    AdapterInfo,
    ExchangeQuote,
    SwapConfirmation,
    SwapRequest,
    SwapResult,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory swap store (production: move to DB table)
# ---------------------------------------------------------------------------

_swaps: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Adapter Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ExchangeAdapter(Protocol):
    """Interface for external exchange connections."""

    @property
    def name(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def currencies(self) -> list[str]: ...

    @property
    def settlement_method(self) -> str: ...

    def get_rate(self, from_currency: str, to_currency: str) -> float: ...

    def health_check(self) -> bool: ...


# ---------------------------------------------------------------------------
# New Earth Exchange Adapter
# ---------------------------------------------------------------------------


class NewEarthAdapter:
    """New Earth Exchange adapter.

    Starts with manual settlement — user initiates swap, confirms when
    both sides settle offline. Upgrades to API-based when New Earth
    publishes their protocol.

    Rate: 1 NE credit = 1 CC (parity, since both are contribution-based).
    Adjustable when real market data is available.
    """

    name = "new_earth"
    display_name = "New Earth Exchange"
    description = (
        "Sacha Stone's alternative exchange — zero-point economics, "
        "mutual credit, value exchange outside debt-based fiat. "
        "Settlement: manual confirmation until API is published."
    )
    currencies = ["NEW_EARTH"]
    settlement_method = "manual"

    # Base rate: 1 NE = 1 CC (parity)
    _rate_cc_per_ne: float = 1.0

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        if from_currency == "CC" and to_currency == "NEW_EARTH":
            return self._rate_cc_per_ne
        if from_currency == "NEW_EARTH" and to_currency == "CC":
            return 1.0 / self._rate_cc_per_ne
        raise ValueError(f"Unsupported pair: {from_currency}/{to_currency}")

    def health_check(self) -> bool:
        return True  # Manual settlement is always "healthy"


# ---------------------------------------------------------------------------
# Community Exchange System (CES) Adapter
# ---------------------------------------------------------------------------


class CESAdapter:
    """Community Exchange System adapter.

    CES (community-exchange.org) connects 10,000+ mutual credit systems
    worldwide. Uses the Komunitin/CES2 open-source protocol for
    inter-community settlement.

    Rate: 1 CES unit = 1 hour of labor ≈ configurable CC amount.
    Default: 1 CES hour = 50 CC (based on ~$15/hr ÷ 333 CC/USD).
    """

    name = "ces"
    display_name = "Community Exchange System"
    description = (
        "Open mutual credit network — 10,000+ systems worldwide. "
        "Time-based: 1 unit = 1 hour of contribution. "
        "Settlement: manual until CES2/Komunitin API integration."
    )
    currencies = ["CES"]
    settlement_method = "manual"

    _rate_cc_per_ces: float = 50.0  # 1 CES hour ≈ 50 CC

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        if from_currency == "CC" and to_currency == "CES":
            return 1.0 / self._rate_cc_per_ces  # CC → CES: divide
        if from_currency == "CES" and to_currency == "CC":
            return self._rate_cc_per_ces  # CES → CC: multiply
        raise ValueError(f"Unsupported pair: {from_currency}/{to_currency}")

    def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

_adapters: dict[str, ExchangeAdapter] = {}


def _ensure_adapters() -> None:
    if not _adapters:
        ne = NewEarthAdapter()
        ces = CESAdapter()
        _adapters[ne.name] = ne
        _adapters[ces.name] = ces


def list_adapters() -> list[AdapterInfo]:
    """List all registered exchange adapters."""
    _ensure_adapters()
    result = []
    for adapter in _adapters.values():
        base_rate = None
        try:
            base_rate = adapter.get_rate("CC", adapter.currencies[0])
        except Exception:
            pass
        result.append(
            AdapterInfo(
                name=adapter.name,
                display_name=adapter.display_name,
                description=adapter.description,
                currencies=adapter.currencies,
                settlement_method=adapter.settlement_method,
                healthy=adapter.health_check(),
                base_rate=base_rate,
            )
        )
    return result


def get_adapter(name: str) -> ExchangeAdapter | None:
    _ensure_adapters()
    return _adapters.get(name)


def find_adapter_for_currency(currency: str) -> ExchangeAdapter | None:
    """Find the adapter that handles a given currency."""
    _ensure_adapters()
    for adapter in _adapters.values():
        if currency in adapter.currencies:
            return adapter
    return None


# ---------------------------------------------------------------------------
# Quote / Swap / Confirm
# ---------------------------------------------------------------------------


def get_quote(from_currency: str, to_currency: str, amount: float) -> ExchangeQuote:
    """Get a conversion quote."""
    # Find the right adapter
    target = to_currency if from_currency == "CC" else from_currency
    adapter = find_adapter_for_currency(target)
    if not adapter:
        raise ValueError(f"No adapter found for currency: {target}")

    rate = adapter.get_rate(from_currency, to_currency)
    amount_to = round(amount * rate, 6)

    return ExchangeQuote(
        quote_id=uuid.uuid4().hex[:12],
        from_currency=from_currency,
        to_currency=to_currency,
        rate=rate,
        amount_from=amount,
        amount_to=amount_to,
        adapter=adapter.name,
        valid_until=datetime.now(timezone.utc) + timedelta(minutes=15),
    )


def initiate_swap(request: SwapRequest) -> SwapResult:
    """Initiate a swap transaction.

    For manual settlement: creates a pending swap that requires human confirmation.
    For API settlement: would call the external exchange API.

    CC side: burns CC from user balance (via treasury) on swap-out,
    or mints CC on swap-in. The treasury coherence invariant holds.
    """
    target = request.to_currency if request.from_currency == "CC" else request.from_currency
    adapter = find_adapter_for_currency(target)
    if not adapter:
        raise ValueError(f"No adapter for currency: {target}")

    rate = adapter.get_rate(request.from_currency, request.to_currency)
    amount_to = round(request.amount * rate, 6)
    tx_id = uuid.uuid4().hex[:16]

    # Record the swap
    swap = {
        "tx_id": tx_id,
        "user_id": request.user_id,
        "from_currency": request.from_currency,
        "to_currency": request.to_currency,
        "amount_from": request.amount,
        "amount_to": amount_to,
        "rate_used": rate,
        "adapter": adapter.name,
        "settlement_method": adapter.settlement_method,
        "status": "pending_confirmation",
        "initiated_at": datetime.now(timezone.utc),
        "recipient_address": request.recipient_address,
        "note": request.note,
    }
    _swaps[tx_id] = swap

    # Record in treasury ledger
    from app.services import cc_treasury_service
    from app.services.cc_oracle_service import get_exchange_rate

    exchange_rate = get_exchange_rate()
    cc_rate = exchange_rate.cc_per_usd

    if request.from_currency == "CC":
        # Swapping CC out → burn from user
        cc_treasury_service.record_swap_out(
            request.user_id, request.amount, adapter.name, tx_id, cc_rate
        )
    else:
        # Swapping in → will mint on confirmation
        pass

    log.info(
        "Swap initiated: %s %s %s → %s %s via %s [%s]",
        tx_id, request.amount, request.from_currency,
        amount_to, request.to_currency, adapter.name, adapter.settlement_method,
    )

    return SwapResult(
        tx_id=tx_id,
        status="pending_confirmation",
        from_currency=request.from_currency,
        to_currency=request.to_currency,
        amount_from=request.amount,
        amount_to=amount_to,
        rate_used=rate,
        adapter=adapter.name,
        initiated_at=swap["initiated_at"],
        settlement_method=adapter.settlement_method,
    )


def confirm_swap(tx_id: str, external_tx_ref: str = "", confirmed_by: str = "") -> SwapConfirmation:
    """Confirm a pending swap (manual settlement)."""
    swap = _swaps.get(tx_id)
    if not swap:
        raise ValueError(f"Swap not found: {tx_id}")
    if swap["status"] != "pending_confirmation":
        raise ValueError(f"Swap {tx_id} is not pending (status: {swap['status']})")

    now = datetime.now(timezone.utc)

    # If swap-in (external → CC), mint CC now
    if swap["to_currency"] == "CC":
        from app.services import cc_treasury_service
        from app.services.cc_oracle_service import get_exchange_rate

        exchange_rate = get_exchange_rate()
        usd_value = swap["amount_to"] / exchange_rate.cc_per_usd
        cc_treasury_service.mint(swap["user_id"], swap["amount_to"], usd_value, exchange_rate.cc_per_usd)

    swap["status"] = "confirmed"
    swap["confirmed_at"] = now
    swap["external_tx_ref"] = external_tx_ref
    swap["confirmed_by"] = confirmed_by

    log.info("Swap confirmed: %s by %s (ref: %s)", tx_id, confirmed_by, external_tx_ref)

    return SwapConfirmation(
        tx_id=tx_id,
        status="confirmed",
        confirmed_at=now,
        external_tx_ref=external_tx_ref,
        confirmed_by=confirmed_by,
    )


def get_swap(tx_id: str) -> dict[str, Any] | None:
    return _swaps.get(tx_id)


def get_user_swaps(user_id: str) -> list[dict[str, Any]]:
    return [s for s in _swaps.values() if s["user_id"] == user_id]
