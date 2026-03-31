"""Treasury Pydantic models — spec 122 crypto treasury bridge."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Currency(str, Enum):
    BTC = "BTC"
    ETH = "ETH"


class DepositStatus(str, Enum):
    AWAITING_DEPOSIT = "awaiting_deposit"
    DETECTED = "detected"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    FAILED = "failed"


class WithdrawalStatus(str, Enum):
    PENDING_GOVERNANCE = "pending_governance"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class ReserveStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    PAUSED = "paused"


class LockedRate(BaseModel):
    cc_per_crypto: float = Field(gt=0)
    crypto_usd: float = Field(gt=0)
    cc_per_usd: float = Field(gt=0)
    spread_pct: float = Field(ge=0)
    locked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TreasuryConfig(BaseModel):
    btc_wallet_address: str = ""
    eth_wallet_address: str = ""
    multisig_signers: list[str] = Field(default_factory=lambda: ["signer-a", "signer-b", "signer-c"])
    multisig_threshold_low: int = 2
    multisig_threshold_high: int = 3
    high_value_threshold_btc: float = 1.0
    high_value_threshold_eth: float = 10.0
    min_deposit_btc: float = 0.0001
    min_deposit_eth: float = 0.001
    max_deposit_btc: float = 10.0
    max_deposit_eth: float = 100.0
    btc_confirmations: int = 6
    eth_confirmations: int = 12
    spread_pct: float = 1.0
    withdrawal_fee_pct: float = 0.5
    min_reserve_ratio: float = 1.0
    price_oracle_url: str = "https://api.coingecko.com/api/v3"
    price_cache_ttl_seconds: int = 300
    deposit_expiry_minutes: int = 60


class Deposit(BaseModel):
    deposit_id: str = Field(default_factory=lambda: f"dep_{uuid4().hex[:12]}")
    user_id: str = Field(min_length=1)
    currency: Currency
    deposit_address: str
    expected_amount_crypto: float = Field(gt=0)
    received_amount_crypto: Optional[float] = None
    tx_hash: Optional[str] = None
    confirmations: int = 0
    confirmations_required: int
    locked_exchange_rate: LockedRate
    expected_cc_amount: float
    cc_minted: Optional[float] = None
    status: DepositStatus = DepositStatus.AWAITING_DEPOSIT
    founder_seed: bool = False
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None


class Withdrawal(BaseModel):
    withdrawal_id: str = Field(default_factory=lambda: f"wdr_{uuid4().hex[:12]}")
    user_id: str = Field(min_length=1)
    cc_amount: float = Field(gt=0)
    fee_cc: float = Field(ge=0)
    net_cc: float = Field(gt=0)
    target_currency: Currency
    estimated_crypto_amount: float
    destination_address: str = Field(min_length=1)
    governance_request_id: str
    tx_hash: Optional[str] = None
    status: WithdrawalStatus = WithdrawalStatus.PENDING_GOVERNANCE
    multisig_signatures: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class UserBalance(BaseModel):
    user_id: str
    cc_balance: float = Field(ge=0, default=0.0)
    total_deposited_cc: float = Field(ge=0, default=0.0)
    total_withdrawn_cc: float = Field(ge=0, default=0.0)
    total_earned_cc: float = Field(ge=0, default=0.0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TreasurySupply(BaseModel):
    total_cc_minted: float = Field(ge=0, default=0.0)
    total_cc_burned: float = Field(ge=0, default=0.0)
    cc_in_circulation: float = Field(ge=0, default=0.0)
    total_btc_held: float = Field(ge=0, default=0.0)
    total_eth_held: float = Field(ge=0, default=0.0)
    reserve_ratio: float = Field(ge=0, default=1.0)
    reserve_status: ReserveStatus = ReserveStatus.HEALTHY
    withdrawals_paused: bool = False


class DepositRequest(BaseModel):
    user_id: str = Field(min_length=1)
    currency: Currency
    expected_amount: float = Field(gt=0)
    founder_seed: bool = False


class WithdrawalRequest(BaseModel):
    user_id: str = Field(min_length=1)
    cc_amount: float = Field(gt=0)
    target_currency: Currency
    destination_address: str = Field(min_length=1)


class TreasurySummary(BaseModel):
    btc_held: float
    eth_held: float
    cc_supply: float
    reserve_ratio: float
    current_rates: dict
    pending_withdrawals: int
    multisig_signers: list[str]
    as_of: datetime
