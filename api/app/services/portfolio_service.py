"""Portfolio service — aggregates contributor personal view data (spec 174)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.models.portfolio import (
    CCBalance,
    CCHistory,
    CCHistoryBucket,
    ContributionDetail,
    ContributorSummary,
    HealthSignal,
    IdeaContributionDrilldown,
    IdeaContributionsList,
    IdeaContributionSummary,
    LinkedIdentity,
    NetworkStats,
    PortfolioSummary,
    StakeDetail,
    StakeIdeaActivity,
    StakesList,
    StakeSummary,
    TasksList,
    TaskSummary,
    ValueLineageSummary,
)
from app.services import graph_service

log = logging.getLogger(__name__)

_GRAPH_NODE_TOP_KEYS = frozenset({
    "id",
    "type",
    "name",
    "description",
    "phase",
    "created_at",
    "updated_at",
    "properties",
})


def _graph_node_props(node: dict[str, Any]) -> dict[str, Any]:
    """Resolve per-type fields from a graph node.

    ``Node.to_dict()`` merges ``properties`` into the top level; unit tests may
    use a nested ``properties`` dict instead.
    """
    nested = node.get("properties")
    if isinstance(nested, dict) and nested:
        return nested
    return {k: v for k, v in node.items() if k not in _GRAPH_NODE_TOP_KEYS}


def _linked_identities_from_store(contributor_key: str) -> list[LinkedIdentity]:
    """Merge SQLite-linked identities (OAuth / manual) with graph-derived ones."""
    try:
        from app.services import contributor_identity_service

        records = contributor_identity_service.get_identities(contributor_key)
    except Exception:
        log.debug("portfolio: identity store unreadable for %s", contributor_key, exc_info=True)
        return []
    out: list[LinkedIdentity] = []
    for rec in records:
        prov = (rec.get("provider") or "unknown").lower()
        if prov in ("ethereum", "bitcoin", "solana", "cosmos"):
            identity_type = "wallet"
        else:
            identity_type = prov
        pid = str(rec.get("provider_id") or "")
        if not pid:
            continue
        out.append(
            LinkedIdentity(
                type=identity_type,
                handle=pid,
                verified=bool(rec.get("verified")),
            )
        )
    return out


# ── Contributor resolution ───────────────────────────────────────────


def _find_contributor(contributor_id: str) -> dict[str, Any] | None:
    """Resolve a contributor node by name or legacy UUID."""
    node = graph_service.get_node(f"contributor:{contributor_id}")
    if node:
        return node
    result = graph_service.list_nodes(type="contributor", limit=500)
    for n in result.get("items", []):
        if (
            n.get("legacy_id") == contributor_id
            or n.get("name") == contributor_id
        ):
            return n
    return None


def _contributor_summary(node: dict[str, Any], contributor_key: str) -> ContributorSummary:
    identities: list[LinkedIdentity] = []
    # Node properties might be merged into top level or in "properties" key
    props = _graph_node_props(node)

    gh = props.get("github_handle") or node.get("github_handle")
    if gh:
        identities.append(LinkedIdentity(type="github", handle=gh, verified=True))

    tg = props.get("telegram_handle") or node.get("telegram_handle")
    if tg:
        identities.append(LinkedIdentity(type="telegram", handle=tg, verified=True))

    wa = node.get("wallet_address") or props.get("wallet_address")
    if wa:
        identities.append(LinkedIdentity(type="wallet", handle=wa, verified=False))

    identities.extend(_linked_identities_from_store(contributor_key))

    seen: set[tuple[str, str]] = set()
    merged: list[LinkedIdentity] = []
    for ident in identities:
        key = (ident.type, ident.handle)
        if key in seen:
            continue
        seen.add(key)
        merged.append(ident)

    return ContributorSummary(
        id=node.get("legacy_id") or node.get("id", ""),
        display_name=node.get("name", "unknown"),
        identities=merged,
    )


# ── Network stats ────────────────────────────────────────────────────


def get_network_stats() -> NetworkStats:
    """Return total CC supply derived from all contributions."""
    contributions = graph_service.list_nodes(type="contribution", limit=10000)
    total_cc = sum(
        float(_graph_node_props(n).get("cost_amount", 0) or 0)
        for n in contributions.get("items", [])
    )
    contributor_count = graph_service.list_nodes(type="contributor", limit=1)
    return NetworkStats(
        total_supply=max(total_cc, 1.0),
        total_contributors=contributor_count.get("total", 0),
        last_computed_at=datetime.now(timezone.utc),
    )


# ── CC balance ──────────────────────────────────────────────────────


def get_cc_balance(contributor_id: str) -> CCBalance:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    c_name = node.get("name", "")
    contributions = graph_service.list_nodes(type="contribution", limit=10000)
    balance = 0.0
    for c in contributions.get("items", []):
        props = _graph_node_props(c)
        if props.get("contributor_id") == contributor_id or props.get("contributor_name") == c_name:
            balance += float(props.get("cost_amount", 0) or 0)

    stats = get_network_stats()
    pct = (balance / stats.total_supply * 100) if stats.total_supply > 0 else 0.0
    return CCBalance(
        contributor_id=contributor_id,
        balance=balance,
        network_total=stats.total_supply,
        network_pct=round(pct, 4),
        last_updated=datetime.now(timezone.utc),
    )


# ── CC history ──────────────────────────────────────────────────────


def _parse_window_days(window: str) -> int:
    if window.endswith("d"):
        return int(window[:-1])
    raise ValueError(f"Invalid window format: {window}")


def _parse_bucket_days(bucket: str) -> int:
    mapping = {"1d": 1, "7d": 7, "30d": 30}
    if bucket not in mapping:
        raise ValueError(f"Invalid bucket: {bucket}. Must be one of 1d, 7d, 30d")
    return mapping[bucket]


def get_cc_history(contributor_id: str, window: str = "90d", bucket: str = "7d") -> CCHistory:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    window_days = _parse_window_days(window)
    if window_days > 365:
        raise ValueError("window exceeds maximum of 365d")
    bucket_days = _parse_bucket_days(bucket)

    c_name = node.get("name", "")
    contributions = graph_service.list_nodes(type="contribution", limit=10000)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=window_days)

    events: list[tuple[datetime, float]] = []
    for c in contributions.get("items", []):
        props = _graph_node_props(c)
        if props.get("contributor_id") != contributor_id and props.get("contributor_name") != c_name:
            continue
        ts_raw = c.get("created_at") or c.get("updated_at")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if ts < start:
            continue
        amount = float(props.get("cost_amount", 0) or 0)
        events.append((ts, amount))

    series: list[CCHistoryBucket] = []
    running_total = 0.0
    num_buckets = max(1, window_days // bucket_days)
    stats = get_network_stats()

    for i in range(num_buckets):
        bucket_start = start + timedelta(days=i * bucket_days)
        bucket_end = bucket_start + timedelta(days=bucket_days, seconds=-1)
        earned = sum(amt for ts, amt in events if bucket_start <= ts <= bucket_end)
        running_total += earned
        pct = (running_total / stats.total_supply * 100) if stats.total_supply > 0 else 0.0
        series.append(CCHistoryBucket(
            period_start=bucket_start,
            period_end=bucket_end,
            cc_earned=earned,
            running_total=running_total,
            network_pct_at_period_end=round(pct, 6),
        ))

    return CCHistory(contributor_id=contributor_id, window=window, bucket=bucket, series=series)


# ── Portfolio summary ────────────────────────────────────────────────


def get_portfolio_summary(contributor_id: str, include_cc: bool = True) -> PortfolioSummary:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    c_name = node.get("name", "")
    contributions = graph_service.list_nodes(type="contribution", limit=10000)
    idea_ids: set[str] = set()
    task_count = 0
    recent: Optional[datetime] = None

    for c in contributions.get("items", []):
        props = _graph_node_props(c)
        if props.get("contributor_id") != contributor_id and props.get("contributor_name") != c_name:
            continue
        if props.get("idea_id"):
            idea_ids.add(props["idea_id"])
        if props.get("contribution_type") in ("task", "impl", "code"):
            task_count += 1
        ts_raw = c.get("updated_at") or c.get("created_at")
        if ts_raw:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if recent is None or ts > recent:
                    recent = ts
            except (ValueError, AttributeError):
                pass

    stake_count = 0
    stakes_scan = graph_service.list_nodes(type="stake", limit=10000)
    for s in stakes_scan.get("items", []):
        sprops = _graph_node_props(s)
        if sprops.get("contributor_id") == contributor_id:
            stake_count += 1

    balance_val: Optional[float] = None
    pct_val: Optional[float] = None
    if include_cc:
        try:
            bal = get_cc_balance(contributor_id)
            balance_val = bal.balance
            pct_val = bal.network_pct
        except Exception:
            pass

    return PortfolioSummary(
        contributor=_contributor_summary(node, contributor_id),
        cc_balance=balance_val,
        cc_network_pct=pct_val,
        idea_contribution_count=len(idea_ids),
        stake_count=stake_count,
        task_completion_count=task_count,
        recent_activity=recent,
    )


# ── Idea contributions list ─────────────────────────────────────────


def _health_for_idea(idea_node: dict[str, Any], contributions_in_idea: list[dict]) -> HealthSignal:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    recent_count = 0
    for c in contributions_in_idea:
        ts_raw = c.get("updated_at") or c.get("created_at")
        if ts_raw:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if ts >= cutoff:
                    recent_count += 1
            except (ValueError, AttributeError):
                pass

    if recent_count >= 3:
        activity = "active"
    elif recent_count >= 1:
        activity = "slow"
    else:
        activity = "dormant"

    props = _graph_node_props(idea_node)
    coherence = props.get("coherence_score")
    delta: Optional[float] = None
    if coherence is not None:
        try:
            delta = (float(coherence) - 0.5) * 100
        except (ValueError, TypeError):
            pass

    return HealthSignal(activity_signal=activity, value_delta_pct=delta, evidence_count=recent_count)


def get_idea_contributions(
    contributor_id: str,
    sort: str = "cc_attributed_desc",
    limit: int = 20,
    offset: int = 0,
) -> IdeaContributionsList:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    c_name = node.get("name", "")
    contributions = graph_service.list_nodes(type="contribution", limit=10000)

    idea_map: dict[str, list[dict]] = {}
    for c in contributions.get("items", []):
        props = _graph_node_props(c)
        if props.get("contributor_id") != contributor_id and props.get("contributor_name") != c_name:
            continue
        idea_id = props.get("idea_id") or "unknown"
        idea_map.setdefault(idea_id, []).append(c)

    items: list[IdeaContributionSummary] = []
    for idea_id, conts in idea_map.items():
        idea_node = graph_service.get_node(f"idea:{idea_id}") or {}
        idea_title = idea_node.get("name") or idea_id
        idea_status = _graph_node_props(idea_node).get("status", "unknown")
        cc_total = sum(float(_graph_node_props(c).get("cost_amount", 0) or 0) for c in conts)
        types = list({_graph_node_props(c).get("contribution_type", "unknown") for c in conts})
        last_ts: Optional[datetime] = None
        for c in conts:
            ts_raw = c.get("updated_at") or c.get("created_at")
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                except (ValueError, AttributeError):
                    pass
        health = _health_for_idea(idea_node, conts)
        items.append(IdeaContributionSummary(
            idea_id=idea_id,
            idea_title=idea_title,
            idea_status=idea_status,
            contribution_types=types,
            cc_attributed=cc_total,
            contribution_count=len(conts),
            last_contributed_at=last_ts,
            health=health,
        ))

    if sort == "cc_attributed_desc":
        items.sort(key=lambda x: x.cc_attributed, reverse=True)
    elif sort == "recent":
        items.sort(key=lambda x: x.last_contributed_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    total = len(items)
    return IdeaContributionsList(contributor_id=contributor_id, total=total, items=items[offset: offset + limit])


def get_idea_contribution_detail(contributor_id: str, idea_id: str) -> IdeaContributionDrilldown:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    c_name = node.get("name", "")
    contributions = graph_service.list_nodes(type="contribution", limit=10000)

    idea_node = graph_service.get_node(f"idea:{idea_id}") or {}
    idea_title = idea_node.get("name") or idea_id

    details: list[ContributionDetail] = []
    for c in contributions.get("items", []):
        props = _graph_node_props(c)
        if props.get("contributor_id") != contributor_id and props.get("contributor_name") != c_name:
            continue
        if props.get("idea_id") != idea_id:
            continue
        ts_raw = c.get("created_at") or c.get("updated_at")
        ts: Optional[datetime] = None
        if ts_raw:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        details.append(ContributionDetail(
            id=c.get("id") or c.get("legacy_id") or "",
            type=props.get("contribution_type", "unknown"),
            date=ts,
            asset_id=props.get("asset_id"),
            cc_attributed=float(props.get("cost_amount", 0) or 0),
            coherence_score=float(props.get("coherence_score", 0) or 0),
        ))

    if not details:
        raise PermissionError("No contributions found for this contributor on this idea")

    total_val = sum(d.cc_attributed for d in details)
    return IdeaContributionDrilldown(
        contributor_id=contributor_id,
        idea_id=idea_id,
        idea_title=idea_title,
        contributions=details,
        value_lineage_summary=ValueLineageSummary(
            total_value=total_val,
            roi_ratio=1.0,
            stage_events=len(details),
        ),
    )


# ── Stakes ──────────────────────────────────────────────────────────


def get_stakes(contributor_id: str, sort: str = "roi_desc", limit: int = 20, offset: int = 0) -> StakesList:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    stakes_result = graph_service.list_nodes(type="stake", limit=10000)
    items: list[StakeSummary] = []
    for s in stakes_result.get("items", []):
        props = _graph_node_props(s)
        if props.get("contributor_id") != contributor_id:
            continue
        idea_id = props.get("idea_id", "")
        idea_node = graph_service.get_node(f"idea:{idea_id}") or {}
        idea_title = idea_node.get("name") or ("[Deleted Idea]" if not idea_node else idea_id)
        cc_staked = float(props.get("cc_staked", 0) or 0)
        cc_val_raw = props.get("cc_valuation")
        cc_val: Optional[float] = float(cc_val_raw) if cc_val_raw is not None else None
        roi: Optional[float] = None
        if cc_val is not None and cc_staked > 0:
            roi = round((cc_val - cc_staked) / cc_staked * 100, 2)

        staked_at: Optional[datetime] = None
        ts_raw = props.get("staked_at") or s.get("created_at")
        if ts_raw:
            try:
                staked_at = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        items.append(StakeSummary(
            stake_id=s.get("id") or s.get("legacy_id") or "",
            idea_id=idea_id,
            idea_title=idea_title,
            cc_staked=cc_staked,
            cc_valuation=cc_val,
            roi_pct=roi,
            staked_at=staked_at,
            health=HealthSignal(activity_signal="unknown"),
        ))

    if sort == "roi_desc":
        items.sort(key=lambda x: x.roi_pct if x.roi_pct is not None else float("-inf"), reverse=True)

    return StakesList(contributor_id=contributor_id, total=len(items), items=items[offset: offset + limit])


# ── Tasks ────────────────────────────────────────────────────────────


def get_tasks(contributor_id: str, status: str = "completed", limit: int = 20, offset: int = 0) -> TasksList:
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    c_name = node.get("name", "")
    tasks_result = graph_service.list_nodes(type="task", limit=10000)
    items: list[TaskSummary] = []
    for t in tasks_result.get("items", []):
        props = _graph_node_props(t)
        executor = props.get("executor_contributor_id") or props.get("contributor_id") or props.get("contributor_name", "")
        if executor not in (contributor_id, c_name):
            continue
        t_status = props.get("status", "")
        if status and t_status != status:
            continue

        completed_at: Optional[datetime] = None
        ts_raw = props.get("completed_at") or t.get("updated_at")
        if ts_raw:
            try:
                completed_at = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        idea_id = props.get("idea_id")
        idea_title: Optional[str] = None
        if idea_id:
            idea_node = graph_service.get_node(f"idea:{idea_id}") or {}
            idea_title = idea_node.get("name")

        items.append(TaskSummary(
            task_id=t.get("id") or t.get("legacy_id") or "",
            description=(t.get("description") or t.get("name") or "")[:200],
            idea_id=idea_id,
            idea_title=idea_title,
            provider=props.get("provider"),
            outcome=props.get("outcome") or props.get("result"),
            cc_earned=float(props.get("cc_earned", 0) or 0),
            completed_at=completed_at,
        ))

    items.sort(key=lambda x: x.completed_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return TasksList(contributor_id=contributor_id, total=len(items), items=items[offset: offset + limit])


# ── Stake detail ─────────────────────────────────────────────────────


def get_stake_detail(contributor_id: str, stake_id: str) -> StakeDetail:
    """Return full detail for a single stake position including idea activity since staking."""
    node = _find_contributor(contributor_id)
    if not node:
        raise ValueError(f"Contributor not found: {contributor_id}")

    stake_node: dict[str, Any] | None = graph_service.get_node(f"stake:{stake_id}")
    if not stake_node:
        stakes_result = graph_service.list_nodes(type="stake", limit=10000)
        for s in stakes_result.get("items", []):
            if s.get("id") == stake_id or s.get("legacy_id") == stake_id:
                stake_node = s
                break
    if not stake_node:
        raise ValueError(f"Stake not found: {stake_id}")

    sprops = _graph_node_props(stake_node)
    if sprops.get("contributor_id") != contributor_id:
        raise PermissionError(f"Stake {stake_id} does not belong to contributor {contributor_id}")

    idea_id = sprops.get("idea_id", "")
    idea_node = graph_service.get_node(f"idea:{idea_id}") or {}
    idea_title = idea_node.get("name") or idea_id
    idea_props = _graph_node_props(idea_node)

    cc_staked = float(sprops.get("cc_staked", 0) or 0)
    cc_val_raw = sprops.get("cc_valuation")
    cc_val: Optional[float] = float(cc_val_raw) if cc_val_raw is not None else None
    roi: Optional[float] = None
    if cc_val is not None and cc_staked > 0:
        roi = round((cc_val - cc_staked) / cc_staked * 100, 2)

    staked_at: Optional[datetime] = None
    ts_raw = sprops.get("staked_at") or stake_node.get("created_at")
    if ts_raw:
        try:
            staked_at = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    last_valued_at: Optional[datetime] = None
    lv_raw = sprops.get("last_valued_at") or stake_node.get("updated_at")
    if lv_raw:
        try:
            last_valued_at = datetime.fromisoformat(str(lv_raw).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    coherence_current: Optional[float] = None
    raw_coh = idea_props.get("coherence_score")
    if raw_coh is not None:
        try:
            coherence_current = float(raw_coh)
        except (ValueError, TypeError):
            pass

    coherence_at_staking: Optional[float] = None
    raw_coh_at_stake = sprops.get("coherence_at_staking")
    if raw_coh_at_stake is not None:
        try:
            coherence_at_staking = float(raw_coh_at_stake)
        except (ValueError, TypeError):
            pass

    contributions_since = 0
    if staked_at and idea_id:
        contributions = graph_service.list_nodes(type="contribution", limit=10000)
        for c in contributions.get("items", []):
            cprops = _graph_node_props(c)
            if cprops.get("idea_id") != idea_id:
                continue
            ts_raw2 = c.get("updated_at") or c.get("created_at")
            if ts_raw2:
                try:
                    ts2 = datetime.fromisoformat(str(ts_raw2).replace("Z", "+00:00"))
                    if ts2 >= staked_at:
                        contributions_since += 1
                except (ValueError, AttributeError):
                    pass

    if coherence_current is not None and coherence_at_staking is not None:
        delta = coherence_current - coherence_at_staking
        if delta > 0.05:
            activity = "improved"
        elif delta < -0.05:
            activity = "declined"
        else:
            activity = "stable"
    elif contributions_since > 0:
        activity = "stable"
    else:
        activity = "unknown"

    idea_activity = StakeIdeaActivity(
        activity_since_staking=activity,
        coherence_at_staking=coherence_at_staking,
        coherence_current=coherence_current,
        contributions_since_staking=contributions_since,
    )

    total_val = cc_val if cc_val is not None else cc_staked
    value_lineage = ValueLineageSummary(
        total_value=total_val,
        roi_ratio=round(cc_val / cc_staked, 4) if cc_val is not None and cc_staked > 0 else None,
        stage_events=contributions_since,
    )

    return StakeDetail(
        stake_id=stake_id,
        contributor_id=contributor_id,
        idea_id=idea_id,
        idea_title=idea_title,
        cc_staked=cc_staked,
        cc_valuation=cc_val,
        roi_pct=roi,
        staked_at=staked_at,
        last_valued_at=last_valued_at,
        idea_activity=idea_activity,
        value_lineage=value_lineage,
    )
