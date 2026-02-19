from __future__ import annotations

import hashlib
import os
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.adapters.graph_store import GraphStore
from app.models.distribution import (
    Distribution,
    DistributionSettlementStatus,
    Payout,
    PayoutSettlementStatus,
)
from app.services.evm_settlement_provider import EvmNativeSettlementProvider, EvmSettlementConfig


class SettlementProvider(Protocol):
    async def send_payout(
        self,
        *,
        distribution_id: str,
        contributor_id: str,
        wallet_address: str,
        amount: Decimal,
    ) -> str:
        ...

    async def confirm_tx(self, tx_hash: str) -> bool:
        ...


class SimulatedSettlementProvider:
    async def send_payout(
        self,
        *,
        distribution_id: str,
        contributor_id: str,
        wallet_address: str,
        amount: Decimal,
    ) -> str:
        seed = f"{distribution_id}:{contributor_id}:{wallet_address}:{amount}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"0x{digest}"

    async def confirm_tx(self, tx_hash: str) -> bool:
        return tx_hash.startswith("0x") and len(tx_hash) == 66


class MisconfiguredSettlementProvider:
    def __init__(self, error_message: str):
        self._error_message = error_message

    async def send_payout(
        self,
        *,
        distribution_id: str,
        contributor_id: str,
        wallet_address: str,
        amount: Decimal,
    ) -> str:
        raise RuntimeError(self._error_message)

    async def confirm_tx(self, tx_hash: str) -> bool:
        return False


class DistributionSettlementService:
    """Settle computed payouts and attach transaction identity data.

    Default backend is simulated. To enable real EVM settlement set:
    - DISTRIBUTION_SETTLEMENT_BACKEND=evm_native
    - EVM_SETTLEMENT_RPC_URL
    - EVM_SETTLEMENT_CHAIN_ID
    - EVM_SETTLEMENT_PRIVATE_KEY
    """

    def __init__(self, store: GraphStore, provider: SettlementProvider | None = None):
        self.store = store
        self._provider: SettlementProvider = provider or self._provider_from_env()

    async def settle(self, distribution: Distribution) -> Distribution:
        if not distribution.payouts:
            return distribution.model_copy(
                update={
                    "settlement_status": DistributionSettlementStatus.SETTLED,
                    "settled_at": datetime.utcnow(),
                }
            )

        settled_rows: list[Payout] = []
        counters = {"confirmed": 0, "skipped": 0, "failed": 0}

        for payout in distribution.payouts:
            contributor = self.store.get_contributor(payout.contributor_id)
            wallet_address = contributor.wallet_address if contributor else None
            if not wallet_address:
                counters["skipped"] += 1
                settled_rows.append(self._missing_wallet_result(payout))
                continue

            payout_row, outcome = await self._settle_wallet_payout(
                distribution_id=str(distribution.id),
                payout=payout,
                wallet_address=wallet_address,
            )
            counters[outcome] += 1
            settled_rows.append(payout_row)

        settlement_status = self._resolve_distribution_status(counters)
        settled_at = datetime.utcnow() if counters["confirmed"] > 0 else None
        return distribution.model_copy(
            update={
                "payouts": settled_rows,
                "settlement_status": settlement_status,
                "settled_at": settled_at,
            }
        )

    def _missing_wallet_result(self, payout: Payout) -> Payout:
        return payout.model_copy(
            update={
                "wallet_address": None,
                "settlement_status": PayoutSettlementStatus.SKIPPED_MISSING_WALLET,
                "settlement_error": "missing_wallet_address",
            }
        )

    async def _settle_wallet_payout(
        self,
        *,
        distribution_id: str,
        payout: Payout,
        wallet_address: str,
    ) -> tuple[Payout, str]:
        try:
            tx_hash = await self._provider.send_payout(
                distribution_id=distribution_id,
                contributor_id=str(payout.contributor_id),
                wallet_address=wallet_address,
                amount=payout.amount,
            )
            confirmed = await self._provider.confirm_tx(tx_hash)
            if confirmed:
                return (
                    payout.model_copy(
                        update={
                            "wallet_address": wallet_address,
                            "tx_hash": tx_hash,
                            "settlement_status": PayoutSettlementStatus.CONFIRMED,
                            "settled_at": datetime.utcnow(),
                        }
                    ),
                    "confirmed",
                )
            return (
                payout.model_copy(
                    update={
                        "wallet_address": wallet_address,
                        "tx_hash": tx_hash,
                        "settlement_status": PayoutSettlementStatus.FAILED,
                        "settlement_error": "tx_not_confirmed",
                    }
                ),
                "failed",
            )
        except Exception as exc:  # pragma: no cover - defensive path
            return (
                payout.model_copy(
                    update={
                        "wallet_address": wallet_address,
                        "settlement_status": PayoutSettlementStatus.FAILED,
                        "settlement_error": str(exc),
                    }
                ),
                "failed",
            )

    def _provider_from_env(self) -> SettlementProvider:
        backend = (os.getenv("DISTRIBUTION_SETTLEMENT_BACKEND") or "simulated").strip().lower()
        if backend in {"", "simulated", "mock"}:
            return SimulatedSettlementProvider()
        if backend in {"evm_native", "evm"}:
            try:
                return EvmNativeSettlementProvider(EvmSettlementConfig.from_env())
            except Exception as exc:
                return MisconfiguredSettlementProvider(f"evm_settlement_misconfigured:{exc}")
        return MisconfiguredSettlementProvider(f"unsupported_settlement_backend:{backend}")

    def _resolve_distribution_status(self, counters: dict[str, int]) -> DistributionSettlementStatus:
        confirmed_count = counters.get("confirmed", 0)
        skipped_count = counters.get("skipped", 0)
        failed_count = counters.get("failed", 0)
        if confirmed_count and not skipped_count and not failed_count:
            return DistributionSettlementStatus.SETTLED
        if confirmed_count and (skipped_count or failed_count):
            return DistributionSettlementStatus.PARTIALLY_SETTLED
        return DistributionSettlementStatus.FAILED
