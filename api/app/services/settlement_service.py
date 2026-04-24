"""Settlement service — daily batch aggregation for story-protocol-integration R8.

Aggregates render events for a day, applies the evidence-verification
multiplier (R9), and produces a frozen SettlementBatch with per-asset
entries and per-concept pools.

Inputs are explicit rather than read from in-process state so the
service stays pure-logic: the caller fetches render events from the
render-events store, asset concept tags from asset registration,
and evidence multipliers from evidence_service. That way the
settlement math can be tested in isolation and wired to graph-backed
storage in a follow-up without changing the contract.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type
from decimal import Decimal
from typing import Dict, List, Mapping, Optional

from app.models.evidence import EvidenceVerification
from app.models.renderer import RenderEvent
from app.models.settlement import ConceptPool, SettlementBatch, SettlementEntry
from app.services.story_protocol_bridge import AssetConceptTag


def _filter_events_by_date(
    events: List[RenderEvent],
    batch_date: date_type,
) -> List[RenderEvent]:
    return [e for e in events if e.timestamp.date() == batch_date]


def _compute_concept_pools(
    total_cc: Decimal,
    tags: List[AssetConceptTag],
) -> List[ConceptPool]:
    """Split an asset's total CC across its concept tags by weight.

    Weights are scaled so the pool sums to total_cc even if the raw
    weights don't sum to 1.0. If an asset has no tags, a single
    'uncategorized' pool carries the full amount.
    """
    if total_cc == 0:
        return []
    if not tags:
        return [ConceptPool(concept_id="uncategorized", cc_amount=total_cc)]
    weight_sum = sum(Decimal(str(t.weight)) for t in tags)
    if weight_sum <= 0:
        return [ConceptPool(concept_id="uncategorized", cc_amount=total_cc)]
    return [
        ConceptPool(
            concept_id=t.concept_id,
            cc_amount=total_cc * Decimal(str(t.weight)) / weight_sum,
        )
        for t in tags
    ]


def run_daily_settlement(
    batch_date: date_type,
    events: List[RenderEvent],
    asset_concept_tags: Mapping[str, List[AssetConceptTag]],
    evidence_multipliers: Mapping[str, Decimal],
) -> SettlementBatch:
    """Aggregate a day's render events into a settlement batch.

    - Groups events by asset_id
    - Sums base CC pool per asset
    - Applies evidence multiplier (spec R9)
    - Distributes per-role shares (asset / renderer / host) proportional
      to the underlying render event attributions
    - Splits the asset-creator portion across concept pools by tag weight
    """
    day_events = _filter_events_by_date(events, batch_date)

    by_asset: Dict[str, List[RenderEvent]] = defaultdict(list)
    for e in day_events:
        by_asset[e.asset_id].append(e)

    entries: List[SettlementEntry] = []
    total_reads = 0
    total_cc = Decimal("0")

    for asset_id, asset_events in by_asset.items():
        base_pool = sum((e.cc_pool for e in asset_events), Decimal("0"))
        base_asset = sum((e.cc_asset_creator for e in asset_events), Decimal("0"))
        base_renderer = sum(
            (e.cc_renderer_creator for e in asset_events), Decimal("0")
        )
        base_host = sum((e.cc_host_node for e in asset_events), Decimal("0"))

        multiplier = evidence_multipliers.get(asset_id, Decimal("1"))
        effective_pool = base_pool * multiplier
        asset_creator_share = base_asset * multiplier
        renderer_creator_share = base_renderer * multiplier
        host_node_share = base_host * multiplier

        concept_pools = _compute_concept_pools(
            asset_creator_share,
            list(asset_concept_tags.get(asset_id, [])),
        )

        entry = SettlementEntry(
            asset_id=asset_id,
            read_count=len(asset_events),
            base_cc_pool=base_pool,
            evidence_multiplier=multiplier,
            effective_cc_pool=effective_pool,
            cc_to_asset_creator=asset_creator_share,
            cc_to_renderer_creators=renderer_creator_share,
            cc_to_host_nodes=host_node_share,
            concept_pools=concept_pools,
        )
        entries.append(entry)
        total_reads += len(asset_events)
        total_cc += effective_pool

    # Deterministic ordering by asset_id for stable snapshots
    entries.sort(key=lambda e: e.asset_id)

    return SettlementBatch(
        batch_date=batch_date,
        entries=entries,
        total_read_count=total_reads,
        total_cc_distributed=total_cc,
    )


# In-process batch registry for retrieval after computation.
_BATCHES: Dict[date_type, SettlementBatch] = {}


def store_batch(batch: SettlementBatch) -> None:
    _BATCHES[batch.batch_date] = batch


def get_batch(batch_date: date_type) -> Optional[SettlementBatch]:
    return _BATCHES.get(batch_date)


def list_batches() -> List[SettlementBatch]:
    return sorted(_BATCHES.values(), key=lambda b: b.batch_date, reverse=True)


def _reset_for_tests() -> None:
    _BATCHES.clear()
