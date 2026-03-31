"""Price Oracle Service — CoinGecko-backed price fetching with TTL cache.

Implements spec 122 R3: CC/BTC and CC/ETH exchange rates from CoinGecko,
cached for 5 minutes with 1% spread applied.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ORACLE_URL = "https://api.coingecko.com/api/v3"
CACHE_TTL_SECONDS = 300
SPREAD_PCT = 1.0


@dataclass
class PriceQuote:
    btc_usd: float
    eth_usd: float
    cc_per_usd: float
    cc_per_btc: float
    cc_per_eth: float
    spread_pct: float
    fetched_at: datetime

    def is_stale(self, ttl: int = CACHE_TTL_SECONDS) -> bool:
        age = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()
        return age > ttl


_price_cache: Optional[PriceQuote] = None
_cache_lock = threading.Lock()


class PriceOracleError(Exception):
    pass


def _load_config() -> dict:
    try:
        from app.services.config_service import get_config
        cfg = get_config()
        treasury = cfg.get("treasury", {})
        return {
            "oracle_url": treasury.get("price_oracle_url", DEFAULT_ORACLE_URL),
            "cache_ttl": int(treasury.get("price_cache_ttl_seconds", CACHE_TTL_SECONDS)),
            "spread_pct": float(treasury.get("spread_pct", SPREAD_PCT)),
            "cc_per_usd": float(treasury.get("cc_per_usd", 333.33)),
        }
    except Exception:
        return {
            "oracle_url": DEFAULT_ORACLE_URL,
            "cache_ttl": CACHE_TTL_SECONDS,
            "spread_pct": SPREAD_PCT,
            "cc_per_usd": 333.33,
        }


def _fetch_prices_from_coingecko(oracle_url: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            f"{oracle_url}/simple/price",
            params={
                "ids": "bitcoin,ethereum",
                "vs_currencies": "usd",
            },
        )
        if resp.status_code != 200:
            raise PriceOracleError(f"CoinGecko returned {resp.status_code}")
        data = resp.json()
        return {
            "btc_usd": float(data["bitcoin"]["usd"]),
            "eth_usd": float(data["ethereum"]["usd"]),
        }


def get_price_quote(use_cache: bool = True, force_refresh: bool = False) -> PriceQuote:
    global _price_cache

    cfg = _load_config()
    ttl = cfg["cache_ttl"]
    spread = cfg["spread_pct"]
    cc_per_usd = cfg["cc_per_usd"]

    if use_cache and not force_refresh and _price_cache is not None:
        if not _price_cache.is_stale(ttl):
            return _price_cache

    try:
        prices = _fetch_prices_from_coingecko(cfg["oracle_url"])
    except PriceOracleError as exc:
        if _price_cache is not None:
            logger.warning("Price oracle failed (%s), using stale cache", exc)
            return _price_cache
        raise PriceOracleError("Price data unavailable, try again later.") from exc

    btc_usd = prices["btc_usd"]
    eth_usd = prices["eth_usd"]

    gross_cc_per_btc = cc_per_usd * btc_usd
    gross_cc_per_eth = cc_per_usd * eth_usd
    spread_multiplier = 1.0 + (spread / 100.0)
    cc_per_btc = round(gross_cc_per_btc * spread_multiplier, 4)
    cc_per_eth = round(gross_cc_per_eth * spread_multiplier, 4)

    quote = PriceQuote(
        btc_usd=btc_usd,
        eth_usd=eth_usd,
        cc_per_usd=cc_per_usd,
        cc_per_btc=cc_per_btc,
        cc_per_eth=cc_per_eth,
        spread_pct=spread,
        fetched_at=datetime.now(timezone.utc),
    )

    with _cache_lock:
        _price_cache = quote

    return quote


def get_cached_quote() -> Optional[PriceQuote]:
    return _price_cache


def clear_cache() -> None:
    global _price_cache
    with _cache_lock:
        _price_cache = None
