"""Tests for treasury service — crypto deposit recording and CC conversion."""
from __future__ import annotations

import pytest

from app.services import treasury_service
from app.services.contribution_ledger_service import _ensure_schema


class TestRecordDeposit:
    def test_eth_deposit_converts_to_cc(self) -> None:
        _ensure_schema()
        result = treasury_service.record_deposit(
            contributor_id="test-depositor-eth",
            asset="eth",
            amount=0.5,
            tx_hash="0xabc123",
        )
        assert result["asset"] == "eth"
        assert result["amount"] == 0.5
        # Default rate: 1 ETH = 1000 CC -> 0.5 ETH = 500 CC
        assert result["cc_converted"] == 500.0
        assert result["tx_hash"] == "0xabc123"
        assert result["contributor_id"] == "test-depositor-eth"
        assert "deposit_id" in result
        assert "recorded_at" in result

    def test_btc_deposit_converts_to_cc(self) -> None:
        _ensure_schema()
        result = treasury_service.record_deposit(
            contributor_id="test-depositor-btc",
            asset="btc",
            amount=0.01,
            tx_hash="btctx123",
        )
        assert result["asset"] == "btc"
        assert result["amount"] == 0.01
        # Default rate: 1 BTC = 10000 CC -> 0.01 BTC = 100 CC
        assert result["cc_converted"] == 100.0

    def test_invalid_asset_raises_error(self) -> None:
        _ensure_schema()
        with pytest.raises(ValueError, match="Invalid asset type"):
            treasury_service.record_deposit(
                contributor_id="test-depositor",
                asset="doge",
                amount=1.0,
                tx_hash="tx123",
            )

    def test_zero_amount_raises_error(self) -> None:
        _ensure_schema()
        with pytest.raises(ValueError, match="positive"):
            treasury_service.record_deposit(
                contributor_id="test-depositor",
                asset="eth",
                amount=0,
                tx_hash="tx123",
            )

    def test_empty_tx_hash_raises_error(self) -> None:
        _ensure_schema()
        with pytest.raises(ValueError, match="Transaction hash"):
            treasury_service.record_deposit(
                contributor_id="test-depositor",
                asset="eth",
                amount=1.0,
                tx_hash="",
            )


class TestDepositHistory:
    def test_get_deposit_history(self) -> None:
        _ensure_schema()
        treasury_service.record_deposit(
            contributor_id="test-history-user",
            asset="eth",
            amount=1.0,
            tx_hash="0xhistory1",
        )
        treasury_service.record_deposit(
            contributor_id="test-history-user",
            asset="btc",
            amount=0.1,
            tx_hash="btchistory1",
        )
        history = treasury_service.get_deposit_history("test-history-user")
        assert len(history) >= 2
        assets = {d["asset"] for d in history}
        assert "eth" in assets
        assert "btc" in assets


class TestTreasuryBalance:
    def test_balance_reflects_deposits(self) -> None:
        _ensure_schema()
        treasury_service.record_deposit(
            contributor_id="test-balance-user",
            asset="eth",
            amount=2.0,
            tx_hash="0xbalance1",
        )
        balance = treasury_service.get_treasury_balance()
        assert balance["deposit_count"] >= 1
        assert balance["total_cc_converted"] > 0
        assert "deposits_by_asset" in balance


class TestTreasuryInfo:
    def test_treasury_info_returns_addresses_and_rates(self) -> None:
        info = treasury_service.get_treasury_info()
        assert "eth_address" in info
        assert "btc_address" in info
        assert "cc_per_eth" in info
        assert "cc_per_btc" in info
        assert info["cc_per_eth"] > 0
        assert info["cc_per_btc"] > 0
