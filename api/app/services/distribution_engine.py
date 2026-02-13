from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.adapters.graph_store import GraphStore
from app.models.distribution import Distribution, Payout


class DistributionEngine:
    def __init__(self, store: GraphStore):
        self.store = store

    async def distribute(self, asset_id: UUID, value_amount: Decimal) -> Distribution:
        """Distribute value proportionally to contributors weighted by coherence."""
        contributions = self.store.get_asset_contributions(asset_id)

        if not contributions:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        weighted_costs: dict[UUID, Decimal] = {}
        for contrib in contributions:
            weight = Decimal("0.5") + Decimal(str(contrib.coherence_score))
            weighted_cost = contrib.cost_amount * weight
            weighted_costs[contrib.contributor_id] = weighted_costs.get(contrib.contributor_id, Decimal("0.00")) + weighted_cost

        total_weighted = sum(weighted_costs.values(), Decimal("0.00"))
        if total_weighted == 0:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        payouts: list[Payout] = []
        for contributor_id, weighted in weighted_costs.items():
            raw = (weighted / total_weighted) * value_amount
            amount = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            payouts.append(Payout(contributor_id=contributor_id, amount=amount))

        return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=payouts)
