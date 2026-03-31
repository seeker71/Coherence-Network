"""Treasury Service — spec 122 crypto treasury bridge.

Deposit initiation, CC minting, withdrawal flow, balance tracking,
reserve enforcement, and supply computation.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from app.models.governance import ActorType, ChangeRequestCreate, ChangeRequestType
from app.models.treasury import (
    Currency,
    Deposit,
    DepositRequest,
    DepositStatus,
    LockedRate,
    ReserveStatus,
    TreasuryConfig,
    TreasurySupply,
    UserBalance,
    Withdrawal,
    WithdrawalRequest,
    WithdrawalStatus,
)
from app.services import governance_service
from app.services.price_oracle_service import get_price_quote

logger = logging.getLogger(__name__)

_deposits: Dict[str, Deposit] = {}
_withdrawals: Dict[str, Withdrawal] = {}
_user_balances: Dict[str, UserBalance] = {}
_balances_lock = threading.Lock()
_supply_lock = threading.Lock()

_total_cc_minted = 0.0
_total_cc_burned = 0.0
_total_btc_held = 0.0
_total_eth_held = 0.0


def _load_config() -> TreasuryConfig:
    try:
        from app.services.config_service import get_config
        cfg = get_config()
        treasury = cfg.get("treasury", {})
        return TreasuryConfig(
            btc_wallet_address=treasury.get("btc_wallet_address", ""),
            eth_wallet_address=treasury.get("eth_wallet_address", ""),
            multisig_signers=treasury.get("multisig_signers", ["signer-a", "signer-b", "signer-c"]),
            multisig_threshold_low=treasury.get("multisig_threshold_low", 2),
            multisig_threshold_high=treasury.get("multisig_threshold_high", 3),
            high_value_threshold_btc=treasury.get("high_value_threshold_btc", 1.0),
            high_value_threshold_eth=treasury.get("high_value_threshold_eth", 10.0),
            min_deposit_btc=treasury.get("min_deposit_btc", 0.0001),
            min_deposit_eth=treasury.get("min_deposit_eth", 0.001),
            max_deposit_btc=treasury.get("max_deposit_btc", 10.0),
            max_deposit_eth=treasury.get("max_deposit_eth", 100.0),
            btc_confirmations=treasury.get("btc_confirmations", 6),
            eth_confirmations=treasury.get("eth_confirmations", 12),
            spread_pct=treasury.get("spread_pct", 1.0),
            withdrawal_fee_pct=treasury.get("withdrawal_fee_pct", 0.5),
            min_reserve_ratio=treasury.get("min_reserve_ratio", 1.0),
            price_oracle_url=treasury.get("price_oracle_url", "https://api.coingecko.com/api/v3"),
            price_cache_ttl_seconds=treasury.get("price_cache_ttl_seconds", 300),
            deposit_expiry_minutes=treasury.get("deposit_expiry_minutes", 60),
        )
    except Exception:
        return TreasuryConfig()


def _generate_address(currency: Currency, config: TreasuryConfig) -> str:
    if currency == Currency.BTC:
        addr = config.btc_wallet_address
        if not addr:
            addr = "bc1qplaceholder00000000000000000000000"
        return addr
    else:
        addr = config.eth_wallet_address
        if not addr:
            addr = "0x0000000000000000000000000000000000000000"
        return addr


def _get_contributor_role(user_id: str) -> str:
    try:
        from app.services import contributor_service
        contributor = contributor_service.get_contributor(user_id)
        return getattr(contributor, "role", "contributor")
    except Exception:
        return "contributor"


def initiate_deposit(req: DepositRequest) -> Deposit:
    global _total_btc_held, _total_eth_held, _total_cc_minted

    config = _load_config()

    if req.currency == Currency.BTC:
        if req.expected_amount < config.min_deposit_btc:
            raise ValueError(f"Minimum BTC deposit is {config.min_deposit_btc}")
        if req.expected_amount > config.max_deposit_btc:
            raise ValueError(f"Maximum BTC deposit is {config.max_deposit_btc}")
        confirmations_required = config.btc_confirmations
    else:
        if req.expected_amount < config.min_deposit_eth:
            raise ValueError(f"Minimum ETH deposit is {config.min_deposit_eth}")
        if req.expected_amount > config.max_deposit_eth:
            raise ValueError(f"Maximum ETH deposit is {config.max_deposit_eth}")
        confirmations_required = config.eth_confirmations

    if req.founder_seed:
        role = _get_contributor_role(req.user_id)
        if role != "founder":
            raise ValueError("Only founder accounts can use founder_seed mode")

    quote = get_price_quote()
    if req.currency == Currency.BTC:
        cc_per_crypto = quote.cc_per_btc
        crypto_usd = quote.btc_usd
        expected_cc = round(req.expected_amount * cc_per_crypto, 4)
        deposit_address = _generate_address(Currency.BTC, config)
    else:
        cc_per_crypto = quote.cc_per_eth
        crypto_usd = quote.eth_usd
        expected_cc = round(req.expected_amount * cc_per_crypto, 4)
        deposit_address = _generate_address(Currency.ETH, config)

    locked_rate = LockedRate(
        cc_per_crypto=cc_per_crypto,
        crypto_usd=crypto_usd,
        cc_per_usd=quote.cc_per_usd,
        spread_pct=quote.spread_pct,
        locked_at=datetime.now(timezone.utc),
    )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=config.deposit_expiry_minutes)

    deposit = Deposit(
        deposit_id=f"dep_{uuid.uuid4().hex[:12]}",
        user_id=req.user_id,
        currency=req.currency,
        deposit_address=deposit_address,
        expected_amount_crypto=req.expected_amount,
        confirmations_required=confirmations_required,
        locked_exchange_rate=locked_rate,
        expected_cc_amount=expected_cc,
        status=DepositStatus.AWAITING_DEPOSIT,
        founder_seed=req.founder_seed,
        expires_at=expires_at,
        created_at=now,
    )

    with _balances_lock:
        _deposits[deposit.deposit_id] = deposit

    return deposit


def confirm_deposit(deposit_id: str, tx_hash: str, received_amount: float, confirmations: int) -> Deposit:
    global _total_btc_held, _total_eth_held, _total_cc_minted

    with _balances_lock:
        if deposit_id not in _deposits:
            raise ValueError("Deposit not found")
        deposit = _deposits[deposit_id]

        if deposit.status == DepositStatus.CONFIRMED:
            return deposit

        deposit.tx_hash = tx_hash
        deposit.received_amount_crypto = received_amount
        deposit.confirmations = confirmations

        if confirmations >= deposit.confirmations_required:
            deposit.status = DepositStatus.CONFIRMED
            deposit.cc_minted = deposit.expected_cc_amount
            deposit.confirmed_at = datetime.now(timezone.utc)

            _total_cc_minted += deposit.expected_cc_amount

            if deposit.currency == Currency.BTC:
                _total_btc_held += received_amount
            else:
                _total_eth_held += received_amount

            _credit_user_balance(
                deposit.user_id,
                deposit.expected_cc_amount,
                is_deposit=True,
            )

    return deposit


def _credit_user_balance(user_id: str, amount: float, is_deposit: bool = True) -> None:
    global _user_balances
    if user_id not in _user_balances:
        _user_balances[user_id] = UserBalance(user_id=user_id)
    ub = _user_balances[user_id]
    ub.cc_balance += amount
    if is_deposit:
        ub.total_deposited_cc += amount
    ub.last_updated = datetime.now(timezone.utc)


def _debit_user_balance(user_id: str, amount: float) -> None:
    global _user_balances
    if user_id not in _user_balances:
        raise ValueError("Insufficient CC balance")
    ub = _user_balances[user_id]
    if ub.cc_balance < amount:
        raise ValueError("Insufficient CC balance")
    ub.cc_balance -= amount
    ub.total_withdrawn_cc += amount
    ub.last_updated = datetime.now(timezone.utc)


def get_deposit(deposit_id: str) -> Optional[Deposit]:
    with _balances_lock:
        return _deposits.get(deposit_id)


def get_user_balance(user_id: str) -> dict:
    quote = get_price_quote()

    with _balances_lock:
        if user_id in _user_balances:
            ub = _user_balances[user_id]
            cc_balance = ub.cc_balance
        else:
            cc_balance = 0.0

    equivalent_btc = round(cc_balance / quote.cc_per_btc, 8) if quote.cc_per_btc > 0 else 0.0
    equivalent_eth = round(cc_balance / quote.cc_per_eth, 8) if quote.cc_per_eth > 0 else 0.0

    return {
        "user_id": user_id,
        "cc_balance": cc_balance,
        "equivalent_btc": equivalent_btc,
        "equivalent_eth": equivalent_eth,
        "btc_usd_rate": quote.btc_usd,
        "eth_usd_rate": quote.eth_usd,
        "cc_per_usd": quote.cc_per_usd,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def request_withdrawal(req: WithdrawalRequest) -> Withdrawal:
    global _total_cc_minted, _total_cc_burned

    config = _load_config()

    with _balances_lock:
        if req.user_id in _user_balances:
            ub = _user_balances[req.user_id]
            if ub.cc_balance < req.cc_amount:
                raise ValueError("Insufficient CC balance")
        else:
            raise ValueError("Insufficient CC balance")

    quote = get_price_quote()
    if req.target_currency == Currency.BTC:
        estimated_crypto = round(req.cc_amount / quote.cc_per_btc, 8)
    else:
        estimated_crypto = round(req.cc_amount / quote.cc_per_eth, 8)

    fee_pct = config.withdrawal_fee_pct / 100.0
    fee_cc = round(req.cc_amount * fee_pct, 4)
    min_fee_btc = 0.0001
    min_fee_eth = 0.001
    if req.target_currency == Currency.BTC:
        min_fee_in_cc = round(min_fee_btc * quote.cc_per_btc, 4)
        if fee_cc < min_fee_in_cc:
            fee_cc = min_fee_in_cc
    else:
        min_fee_in_cc = round(min_fee_eth * quote.cc_per_eth, 4)
        if fee_cc < min_fee_in_cc:
            fee_cc = min_fee_in_cc
    if fee_cc >= req.cc_amount:
        raise ValueError(
            f"Withdrawal amount {req.cc_amount} CC is too small; "
            f"minimum fee alone is {fee_cc} CC. Increase withdrawal amount."
        )
    net_cc = round(req.cc_amount - fee_cc, 4)

    governance_title = f"Treasury withdrawal: {net_cc} CC -> {req.target_currency.value}"
    cr_payload = {
        "withdrawal_id": "",
        "user_id": req.user_id,
        "cc_amount": req.cc_amount,
        "net_cc": net_cc,
        "fee_cc": fee_cc,
        "target_currency": req.target_currency.value,
        "estimated_crypto_amount": estimated_crypto,
        "destination_address": req.destination_address,
    }

    try:
        cr_create = ChangeRequestCreate(
            request_type=ChangeRequestType.TREASURY_WITHDRAWAL,
            title=governance_title,
            payload=cr_payload,
            proposer_id=req.user_id,
            proposer_type=ActorType.HUMAN,
            required_approvals=2,
            auto_apply_on_approval=False,
        )
        cr_response = governance_service.create_change_request(cr_create)
        governance_request_id = cr_response.id
    except Exception:
        governance_request_id = f"cr_{uuid.uuid4().hex[:12]}"

    withdrawal = Withdrawal(
        withdrawal_id=f"wdr_{uuid.uuid4().hex[:12]}",
        user_id=req.user_id,
        cc_amount=req.cc_amount,
        fee_cc=fee_cc,
        net_cc=net_cc,
        target_currency=req.target_currency,
        estimated_crypto_amount=estimated_crypto,
        destination_address=req.destination_address,
        governance_request_id=governance_request_id,
        status=WithdrawalStatus.PENDING_GOVERNANCE,
    )

    cr_payload["withdrawal_id"] = withdrawal.withdrawal_id

    with _balances_lock:
        _withdrawals[withdrawal.withdrawal_id] = withdrawal

    return withdrawal


def approve_withdrawal(withdrawal_id: str, governance_request_id: str) -> Withdrawal:
    global _total_cc_burned

    with _balances_lock:
        if withdrawal_id not in _withdrawals:
            raise ValueError("Withdrawal not found")
        withdrawal = _withdrawals[withdrawal_id]
        if withdrawal.status != WithdrawalStatus.PENDING_GOVERNANCE:
            raise ValueError(f"Withdrawal is not pending governance (status: {withdrawal.status})")

        _debit_user_balance(withdrawal.user_id, withdrawal.cc_amount)
        _total_cc_burned += withdrawal.cc_amount

        withdrawal.status = WithdrawalStatus.APPROVED
        withdrawal.governance_request_id = governance_request_id

    return withdrawal


def reject_withdrawal(withdrawal_id: str) -> Withdrawal:
    with _balances_lock:
        if withdrawal_id not in _withdrawals:
            raise ValueError("Withdrawal not found")
        withdrawal = _withdrawals[withdrawal_id]
        if withdrawal.status != WithdrawalStatus.PENDING_GOVERNANCE:
            raise ValueError(f"Withdrawal is not pending governance (status: {withdrawal.status})")

        withdrawal.status = WithdrawalStatus.REJECTED

    return withdrawal


def get_withdrawal(withdrawal_id: str) -> Optional[Withdrawal]:
    with _balances_lock:
        return _withdrawals.get(withdrawal_id)


def get_treasury_supply() -> TreasurySupply:
    global _total_cc_minted, _total_cc_burned, _total_btc_held, _total_eth_held

    config = _load_config()
    quote = get_price_quote()

    with _supply_lock:
        cc_in_circulation = max(0.0, _total_cc_minted - _total_cc_burned)
        btc_value_usd = _total_btc_held * quote.btc_usd
        eth_value_usd = _total_eth_held * quote.eth_usd
        total_treasury_value_usd = btc_value_usd + eth_value_usd
        cc_value_usd = cc_in_circulation / quote.cc_per_usd if quote.cc_per_usd > 0 else 0.0

        if cc_value_usd > 0:
            reserve_ratio = round(total_treasury_value_usd / cc_value_usd, 4)
        else:
            reserve_ratio = 1.0

        if reserve_ratio >= 1.0:
            reserve_status = ReserveStatus.HEALTHY
        elif reserve_ratio >= 0.5:
            reserve_status = ReserveStatus.WARNING
        else:
            reserve_status = ReserveStatus.PAUSED

        pending_count = sum(
            1 for w in _withdrawals.values()
            if w.status == WithdrawalStatus.PENDING_GOVERNANCE
        )

    return TreasurySupply(
        total_cc_minted=round(_total_cc_minted, 4),
        total_cc_burned=round(_total_cc_burned, 4),
        cc_in_circulation=round(cc_in_circulation, 4),
        total_btc_held=round(_total_btc_held, 8),
        total_eth_held=round(_total_eth_held, 8),
        reserve_ratio=reserve_ratio,
        reserve_status=reserve_status,
        withdrawals_paused=(reserve_status == ReserveStatus.PAUSED),
    )


def get_treasury_summary() -> dict:
    global _total_btc_held, _total_eth_held

    config = _load_config()
    quote = get_price_quote()
    supply = get_treasury_supply()

    pending_count = sum(
        1 for w in _withdrawals.values()
        if w.status == WithdrawalStatus.PENDING_GOVERNANCE
    )

    return {
        "btc_held": round(_total_btc_held, 8),
        "eth_held": round(_total_eth_held, 8),
        "cc_supply": round(supply.cc_in_circulation, 4),
        "reserve_ratio": supply.reserve_ratio,
        "current_rates": {
            "cc_per_btc": quote.cc_per_btc,
            "cc_per_eth": quote.cc_per_eth,
            "cc_per_usd": quote.cc_per_usd,
            "btc_usd": quote.btc_usd,
            "eth_usd": quote.eth_usd,
        },
        "pending_withdrawals": pending_count,
        "multisig_signers": config.multisig_signers,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def reset_for_testing() -> None:
    global _deposits, _withdrawals, _user_balances
    global _total_cc_minted, _total_cc_burned, _total_btc_held, _total_eth_held
    with _balances_lock, _supply_lock:
        _deposits.clear()
        _withdrawals.clear()
        _user_balances.clear()
        _total_cc_minted = 0.0
        _total_cc_burned = 0.0
        _total_btc_held = 0.0
        _total_eth_held = 0.0
