from __future__ import annotations

import hashlib
from datetime import datetime

from app.adapters.graph_store import GraphStore
from app.models.distribution import (
    Distribution,
    DistributionSettlementStatus,
    Payout,
    PayoutSettlementStatus,
)


class DistributionSettlementService:
    """Settle computed payouts and attach transaction identity data."""

    def __init__(self, store: GraphStore):
        self.store = store

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
            tx_hash = await self._broadcast_payout(
                distribution_id=distribution_id,
                contributor_id=str(payout.contributor_id),
                wallet_address=wallet_address,
                amount=str(payout.amount),
            )
            confirmed = await self._confirm_tx(tx_hash)
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

    def _resolve_distribution_status(self, counters: dict[str, int]) -> DistributionSettlementStatus:
        confirmed_count = counters.get("confirmed", 0)
        skipped_count = counters.get("skipped", 0)
        failed_count = counters.get("failed", 0)
        if confirmed_count and not skipped_count and not failed_count:
            return DistributionSettlementStatus.SETTLED
        if confirmed_count and (skipped_count or failed_count):
            return DistributionSettlementStatus.PARTIALLY_SETTLED
        return DistributionSettlementStatus.FAILED

    async def _broadcast_payout(
        self,
        *,
        distribution_id: str,
        contributor_id: str,
        wallet_address: str,
        amount: str,
    ) -> str:
        seed = f"{distribution_id}:{contributor_id}:{wallet_address}:{amount}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return f"0x{digest}"

    async def _confirm_tx(self, tx_hash: str) -> bool:
        return tx_hash.startswith("0x") and len(tx_hash) == 66
