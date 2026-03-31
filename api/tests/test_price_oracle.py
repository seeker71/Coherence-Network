"""Tests for price oracle service — spec 122 R3 exchange rate computation."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.services.price_oracle_service import (
    PriceQuote,
    clear_cache,
    get_cached_quote,
    get_price_quote,
    PriceOracleError,
)


class FakeQuote:
    btc_usd = 50000.0
    eth_usd = 3333.33
    cc_per_usd = 333.33
    cc_per_btc = 50000.0 * 333.33 * 1.01
    cc_per_eth = 3333.33 * 333.33 * 1.01
    spread_pct = 1.0
    fetched_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


class TestPriceOracle:
    def test_price_cache_ttl(self):
        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            return_value={"btc_usd": 50000.0, "eth_usd": 3333.33},
        ):
            quote1 = get_price_quote(force_refresh=True)
            quote2 = get_price_quote(use_cache=True)
            assert quote1.btc_usd == quote2.btc_usd
            assert quote1.fetched_at == quote2.fetched_at

    def test_price_oracle_failure_fallback(self):
        clear_cache()
        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            side_effect=PriceOracleError("Network unreachable"),
        ):
            with pytest.raises(PriceOracleError, match="unavailable"):
                get_price_quote(use_cache=False, force_refresh=True)

    def test_spread_applied(self):
        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            return_value={"btc_usd": 50000.0, "eth_usd": 3333.33},
        ):
            quote = get_price_quote(force_refresh=True)
            assert quote.spread_pct == 1.0
            assert quote.cc_per_btc > 50000.0 * 333.33
            assert quote.cc_per_eth > 3333.33 * 333.33

    def test_cc_per_btc_calculation(self):
        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            return_value={"btc_usd": 50000.0, "eth_usd": 3333.33},
        ):
            quote = get_price_quote(force_refresh=True)
            expected_cc_per_btc = 50000.0 * 333.33 * 1.01
            assert abs(quote.cc_per_btc - expected_cc_per_btc) < 0.01

    def test_cc_per_eth_calculation(self):
        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            return_value={"btc_usd": 50000.0, "eth_usd": 3333.33},
        ):
            quote = get_price_quote(force_refresh=True)
            expected_cc_per_eth = 3333.33 * 333.33 * 1.01
            assert abs(quote.cc_per_eth - expected_cc_per_eth) < 0.01

    def test_cached_quote_returns_stale(self):
        stale_quote = PriceQuote(
            btc_usd=40000.0,
            eth_usd=3000.0,
            cc_per_usd=333.33,
            cc_per_btc=40000.0 * 333.33 * 1.01,
            cc_per_eth=3000.0 * 333.33 * 1.01,
            spread_pct=1.0,
            fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        import app.services.price_oracle_service as pos
        pos._price_cache = stale_quote
        quote = get_cached_quote()
        assert quote is not None
        assert quote.is_stale()

    def test_force_refresh_bypasses_cache(self):
        fresh_quote = PriceQuote(
            btc_usd=60000.0,
            eth_usd=4000.0,
            cc_per_usd=333.33,
            cc_per_btc=60000.0 * 333.33 * 1.01,
            cc_per_eth=4000.0 * 333.33 * 1.01,
            spread_pct=1.0,
            fetched_at=datetime.now(timezone.utc),
        )
        import app.services.price_oracle_service as pos
        pos._price_cache = fresh_quote

        with patch(
            "app.services.price_oracle_service._fetch_prices_from_coingecko",
            return_value={"btc_usd": 50000.0, "eth_usd": 3333.33},
        ):
            quote = get_price_quote(force_refresh=True)
            assert quote.btc_usd == 50000.0
