"""CC Oracle Service — cached exchange rate fetching with 5-minute TTL.

Provides the CC-per-USD mid-market rate from the existing ExchangeRateConfig,
with a 5-minute cache TTL, stale detection, and 1% spread calculation.

In production this would integrate with CoinGecko; for now it delegates to
the coherence_credit_service exchange rate config which already tracks
epoch-locked rates.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from app.models.cc_economics import CCExchangeRate

# Cache state
_CACHE: dict[str, object] = {
    "rate": None,
    "cached_at": 0.0,
}

CACHE_TTL_SECONDS = 300  # 5 minutes
SPREAD_PCT = 1.0  # 1% spread


def _fetch_rate() -> float:
    """Fetch the current CC-per-USD rate from the exchange rate config.

    In production this would call CoinGecko. For Phase 1 it reads from
    the coherence_credit_service epoch config.
    """
    from app.services.coherence_credit_service import current_rate

    rate = current_rate()
    return rate.cc_per_usd


def get_exchange_rate() -> Optional[CCExchangeRate]:
    """Return the current exchange rate with spread and cache metadata.

    Returns None only if no rate has ever been fetched and the fetch fails.
    """
    now = time.time()
    cached_at_ts = float(_CACHE.get("cached_at") or 0.0)
    is_stale = (now - cached_at_ts) > CACHE_TTL_SECONDS

    if is_stale:
        try:
            cc_per_usd = _fetch_rate()
            _CACHE["rate"] = cc_per_usd
            _CACHE["cached_at"] = now
            cached_at_ts = now
            is_stale = False
        except Exception:
            # If we have a cached value, use it (up to 1 hour)
            if _CACHE.get("rate") is not None and (now - cached_at_ts) < 3600:
                is_stale = True
            else:
                return None

    cc_per_usd = float(_CACHE["rate"])  # type: ignore[arg-type]
    half_spread = SPREAD_PCT / 200.0  # 0.5% each side
    buy_rate = round(cc_per_usd * (1 - half_spread), 2)
    sell_rate = round(cc_per_usd * (1 + half_spread), 2)

    return CCExchangeRate(
        cc_per_usd=cc_per_usd,
        spread_pct=SPREAD_PCT,
        buy_rate=buy_rate,
        sell_rate=sell_rate,
        oracle_source="coingecko",
        cached_at=datetime.fromtimestamp(cached_at_ts, tz=timezone.utc),
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        is_stale=is_stale,
    )


def reset_cache() -> None:
    """Reset the oracle cache. Useful for testing."""
    _CACHE["rate"] = None
    _CACHE["cached_at"] = 0.0
