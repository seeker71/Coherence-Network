"""Distribution engine — reads contributions from graph edges."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.models.distribution import Distribution, Payout
from app.services import graph_service


class DistributionEngine:
    async def distribute(self, asset_id: UUID, asset_node_id: str, value_amount: Decimal) -> Distribution:
        """Distribute value proportionally to contributors weighted by coherence."""
        edges = graph_service.get_edges(asset_node_id, direction="incoming", edge_type="contribution")

        if not edges:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        weighted_costs: dict[UUID, Decimal] = {}
        for edge in edges:
            props = edge.get("properties", {})
            contributor_id = UUID(props["contributor_id"]) if props.get("contributor_id") else None
            if not contributor_id:
                continue
            cost = Decimal(str(props.get("cost_amount", "0")))
            coherence = float(props.get("coherence_score", 0.5))
            weight = Decimal("0.5") + Decimal(str(coherence))
            weighted_cost = cost * weight
            weighted_costs[contributor_id] = weighted_costs.get(contributor_id, Decimal("0.00")) + weighted_cost

        total_weighted = sum(weighted_costs.values(), Decimal("0.00"))
        if total_weighted == 0:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        payouts: list[Payout] = []
        for contributor_id, weighted in weighted_costs.items():
            raw = (weighted / total_weighted) * value_amount
            amount = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            payouts.append(Payout(contributor_id=contributor_id, amount=amount))

        return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=payouts)
