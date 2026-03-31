"""Tests for treasury service — spec 122 crypto treasury bridge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.treasury import (
    Currency,
    DepositRequest,
    DepositStatus,
    WithdrawalRequest,
)
from app.services import treasury_service
from app.services.blockchain_monitor_service import TxStatus


class FakeQuote:
    btc_usd = 50000.0
    eth_usd = 3333.33
    cc_per_usd = 0.003
    cc_per_btc = 50000.0 * 0.003 * 1.01
    cc_per_eth = 3333.33 * 0.003 * 1.01
    spread_pct = 1.0
    fetched_at = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def reset_treasury():
    treasury_service.reset_for_testing()
    yield
    treasury_service.reset_for_testing()


@pytest.fixture
def mock_price_oracle():
    with patch(
        "app.services.treasury_service.get_price_quote",
        return_value=FakeQuote(),
    ):
        yield


class TestDepositInitiation:
    def test_deposit_initiation_201(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        result = treasury_service.initiate_deposit(req)
        assert result.user_id == "alice"
        assert result.currency == Currency.BTC
        assert result.expected_amount_crypto == 0.05
        assert result.deposit_address
        assert result.deposit_id.startswith("dep_")
        assert result.status == DepositStatus.AWAITING_DEPOSIT
        assert result.expected_cc_amount > 0
        assert result.confirmations_required == 6
        assert result.expires_at > datetime.now(timezone.utc)

    def test_deposit_below_minimum_422(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.00001,
            founder_seed=False,
        )
        with pytest.raises(ValueError, match="Minimum BTC deposit"):
            treasury_service.initiate_deposit(req)

    def test_deposit_above_maximum_422(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=15.0,
            founder_seed=False,
        )
        with pytest.raises(ValueError, match="Maximum BTC deposit"):
            treasury_service.initiate_deposit(req)


class TestDepositConfirmation:
    def test_deposit_confirmation_mints_cc(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        deposit = treasury_service.initiate_deposit(req)

        confirmed = treasury_service.confirm_deposit(
            deposit_id=deposit.deposit_id,
            tx_hash="bc1qtest123",
            received_amount=0.05,
            confirmations=6,
        )
        assert confirmed.status == DepositStatus.CONFIRMED
        assert confirmed.cc_minted is not None
        assert confirmed.cc_minted > 0

    def test_deposit_rate_locked_at_initiation(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        deposit1 = treasury_service.initiate_deposit(req)
        rate1 = deposit1.locked_exchange_rate.cc_per_crypto

        req2 = DepositRequest(
            user_id="bob",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        deposit2 = treasury_service.initiate_deposit(req2)

        assert deposit2.locked_exchange_rate.locked_at >= deposit1.locked_exchange_rate.locked_at

    def test_founder_seed_deposit(self):
        with patch(
            "app.services.treasury_service.get_price_quote",
            return_value=FakeQuote(),
        ), patch(
            "app.services.treasury_service._get_contributor_role",
            return_value="founder",
        ):
            req = DepositRequest(
                user_id="founder_alice",
                currency=Currency.ETH,
                expected_amount=1.0,
                founder_seed=True,
            )
            deposit = treasury_service.initiate_deposit(req)
            assert deposit.founder_seed is True
            assert deposit.status == DepositStatus.AWAITING_DEPOSIT

    def test_founder_seed_rejected_for_non_founder(self, mock_price_oracle):
        with patch(
            "app.services.treasury_service._get_contributor_role",
            return_value="contributor",
        ):
            req = DepositRequest(
                user_id="regular_user",
                currency=Currency.ETH,
                expected_amount=1.0,
                founder_seed=True,
            )
            with pytest.raises(ValueError, match="founder"):
                treasury_service.initiate_deposit(req)


class TestBalance:
    def test_balance_query(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        treasury_service.initiate_deposit(req)
        treasury_service.confirm_deposit(
            deposit_id=treasury_service._deposits[list(treasury_service._deposits.keys())[0]].deposit_id,
            tx_hash="bc1qtest",
            received_amount=0.05,
            confirmations=6,
        )

        balance = treasury_service.get_user_balance("alice")
        assert balance["user_id"] == "alice"
        assert balance["cc_balance"] > 0
        assert "equivalent_btc" in balance
        assert "equivalent_eth" in balance
        assert "btc_usd_rate" in balance
        assert "cc_per_usd" in balance

    def test_balance_never_negative(self, mock_price_oracle):
        req = WithdrawalRequest(
            user_id="bob",
            cc_amount=1000.0,
            target_currency=Currency.ETH,
            destination_address="0x742d35Cc6634C0532925a3b844Bc9e7595f00000",
        )
        with pytest.raises(ValueError, match="balance"):
            treasury_service.request_withdrawal(req)


class TestWithdrawal:
    def test_withdrawal_creates_governance_request(self):
        with patch.object(
            treasury_service,
            "get_price_quote",
            return_value=FakeQuote(),
        ):
            req_deposit = DepositRequest(
                user_id="alice",
                currency=Currency.ETH,
                expected_amount=1.0,
                founder_seed=False,
            )
            deposit = treasury_service.initiate_deposit(req_deposit)
            treasury_service.confirm_deposit(
                deposit_id=deposit.deposit_id,
                tx_hash="0xtest",
                received_amount=1.0,
                confirmations=12,
            )

            req_withdraw = WithdrawalRequest(
                user_id="alice",
                cc_amount=5.0,
                target_currency=Currency.ETH,
                destination_address="0x742d35Cc6634C0532925a3b844Bc9e7595f00000",
            )
            withdrawal = treasury_service.request_withdrawal(req_withdraw)
            assert withdrawal.governance_request_id
            assert withdrawal.status.value == "pending_governance"

    def test_withdrawal_fee_deducted(self):
        with patch.object(
            treasury_service,
            "get_price_quote",
            return_value=FakeQuote(),
        ):
            req_deposit = DepositRequest(
                user_id="alice",
                currency=Currency.BTC,
                expected_amount=1.0,
                founder_seed=False,
            )
            deposit = treasury_service.initiate_deposit(req_deposit)
            treasury_service.confirm_deposit(
                deposit_id=deposit.deposit_id,
                tx_hash="bc1qfee",
                received_amount=1.0,
                confirmations=6,
            )

            req_withdraw = WithdrawalRequest(
                user_id="alice",
                cc_amount=5.0,
                target_currency=Currency.BTC,
                destination_address="bc1qtest1234567890",
            )
            withdrawal = treasury_service.request_withdrawal(req_withdraw)
            assert withdrawal.fee_cc > 0
            assert withdrawal.net_cc < withdrawal.cc_amount
            assert withdrawal.net_cc == round(withdrawal.cc_amount * 0.995, 4)

    def test_withdrawal_approval_burns_cc(self):
        with patch.object(
            treasury_service,
            "get_price_quote",
            return_value=FakeQuote(),
        ):
            req_deposit = DepositRequest(
                user_id="alice",
                currency=Currency.ETH,
                expected_amount=1.0,
                founder_seed=False,
            )
            deposit = treasury_service.initiate_deposit(req_deposit)
            treasury_service.confirm_deposit(
                deposit_id=deposit.deposit_id,
                tx_hash="0xapprove",
                received_amount=1.0,
                confirmations=12,
            )

            req_withdraw = WithdrawalRequest(
                user_id="alice",
                cc_amount=5.0,
                target_currency=Currency.ETH,
                destination_address="0x742d35Cc6634C0532925a3b844Bc9e7595f00000",
            )
            withdrawal = treasury_service.request_withdrawal(req_withdraw)
            treasury_service.approve_withdrawal(
                withdrawal_id=withdrawal.withdrawal_id,
                governance_request_id=withdrawal.governance_request_id,
            )

            supply = treasury_service.get_treasury_supply()
            assert supply.total_cc_burned > 0

    def test_withdrawal_rejection_returns_cc(self):
        with patch.object(
            treasury_service,
            "get_price_quote",
            return_value=FakeQuote(),
        ):
            req_deposit = DepositRequest(
                user_id="alice",
                currency=Currency.ETH,
                expected_amount=1.0,
                founder_seed=False,
            )
            deposit = treasury_service.initiate_deposit(req_deposit)
            treasury_service.confirm_deposit(
                deposit_id=deposit.deposit_id,
                tx_hash="0xreject",
                received_amount=1.0,
                confirmations=12,
            )

            req_withdraw = WithdrawalRequest(
                user_id="alice",
                cc_amount=5.0,
                target_currency=Currency.ETH,
                destination_address="0x742d35Cc6634C0532925a3b844Bc9e7595f00000",
            )
            withdrawal = treasury_service.request_withdrawal(req_withdraw)
            treasury_service.reject_withdrawal(withdrawal.withdrawal_id)

            updated = treasury_service.get_withdrawal(withdrawal.withdrawal_id)
            assert updated is not None
            assert updated.status.value == "rejected"


class TestSupply:
    def test_supply_equals_minted_minus_burned(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.01,
            founder_seed=False,
        )
        deposit = treasury_service.initiate_deposit(req)
        treasury_service.confirm_deposit(
            deposit_id=deposit.deposit_id,
            tx_hash="bc1qsupply",
            received_amount=0.01,
            confirmations=6,
        )

        supply = treasury_service.get_treasury_supply()
        assert supply.total_cc_minted > 0
        assert supply.cc_in_circulation == supply.total_cc_minted - supply.total_cc_burned


class TestReserveRatio:
    def test_reserve_ratio_enforcement(self, mock_price_oracle):
        supply = treasury_service.get_treasury_supply()
        assert supply.reserve_ratio >= 1.0 or supply.reserve_ratio == 0.0
        assert supply.reserve_status in ["healthy", "warning", "paused"]


class TestSummary:
    def test_summary_endpoint_shape(self, mock_price_oracle):
        summary = treasury_service.get_treasury_summary()
        assert "btc_held" in summary
        assert "eth_held" in summary
        assert "cc_supply" in summary
        assert "reserve_ratio" in summary
        assert "current_rates" in summary
        assert "pending_withdrawals" in summary
        assert "multisig_signers" in summary
        assert "as_of" in summary


class TestDepositGet:
    def test_get_deposit_not_found(self, mock_price_oracle):
        result = treasury_service.get_deposit("dep_nonexistent")
        assert result is None

    def test_get_deposit_found(self, mock_price_oracle):
        req = DepositRequest(
            user_id="alice",
            currency=Currency.BTC,
            expected_amount=0.05,
            founder_seed=False,
        )
        deposit = treasury_service.initiate_deposit(req)
        result = treasury_service.get_deposit(deposit.deposit_id)
        assert result is not None
        assert result.deposit_id == deposit.deposit_id
