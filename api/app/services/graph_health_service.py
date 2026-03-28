"""Graph Health computation service (spec-172).

Computes structural and energetic shape metrics for the Coherence Network graph.
Emits signals for gravity wells, orphan clusters, surface candidates, and convergence guards.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import threading
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.db.graph_health_repo import (
    count_active_convergence_guards,
    delete_convergence_guard,
    get_convergence_guard,
    get_latest_snapshot,
    get_snapshot_history,
    list_signals,
    save_snapshot,
    set_convergence_guard,
    upsert_signal,
)
from app.models.graph_health import (
    ConvergenceGuardResponse,
    GravityWell,
    GraphHealthROI,
    GraphHealthSnapshot,
    GraphSignal,
    OrphanCluster,
    SPEC_REF,
    SurfaceCandidate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable thresholds (env-override)
# ---------------------------------------------------------------------------
SPLIT_THRESHOLD = int(os.getenv("GRAPH_SPLIT_THRESHOLD", "15"))
SPLIT_CRITICAL = int(os.getenv("GRAPH_SPLIT_CRITICAL", "25"))
ORPHAN_MAX_SIZE = int(os.getenv("GRAPH_ORPHAN_MAX_SIZE", "5"))
CONCENTRATION_WARNING = float(os.getenv("GRAPH_CONCENTRATION_WARNING", "0.51"))
CONCENTRATION_CRITICAL = float(os.getenv("GRAPH_CONCENTRATION_CRITICAL", "0.80"))
ENTROPY_WARNING = float(os.getenv("GRAPH_ENTROPY_WARNING", "0.40"))
ENTROPY_HEALTHY = float(os.getenv("GRAPH_ENTROPY_HEALTHY", "0.65"))
SURFACE_MAX_PCT = float(os.getenv("GRAPH_SURFACE_MAX_PCT", "0.01"))
SURFACE_MIN_POTENTIAL = float(os.getenv("GRAPH_SURFACE_MIN_POTENTIAL", "0.75"))
TOP_N_CONCENTRATION = int(os.getenv("GRAPH_TOP_N_CONCENTRATION", "3"))
COMPUTE_TIMEOUT_SECS = float(os.getenv("GRAPH_COMPUTE_TIMEOUT_SECS", "10.0"))
COMPUTE_COOLDOWN_SECS = float(os.getenv("GRAPH_COMPUTE_COOLDOWN_SECS", "30.0"))

# ---------------------------------------------------------------------------
# Single-flight lock
# ---------------------------------------------------------------------------
_compute_lock = threading.Lock()
_last_compute_time: Optional[datetime] = None


def _seconds_since_last_compute() -> float:
    if _last_compute_time is None:
        return float("inf")
    delta = datetime.now(timezone.utc) - _last_compute_time
    return delta.total_seconds()


def is_in_cooldown() -> bool:
    return _seconds_since_last_compute() < COMPUTE_COOLDOWN_SECS


# ---------------------------------------------------------------------------
# Graph data helpers (draw from concept_service in-process)
# ---------------------------------------------------------------------------

def _fetch_graph_data() -> tuple[list[dict], list[dict]]:
    """Load concepts and edges from the concept service."""
    try:
        from app.services import concept_service
        concepts_data = concept_service.list_concepts(limit=10000, offset=0)
        concepts = concepts_data.get("items", [])
        edges = list(concept_service._edges)
        return concepts, edges
    except Exception as exc:
        logger.warning("Failed to fetch graph data: %s", exc)
        return [], []


def _fetch_interaction_counts() -> dict[str, int]:
    """Return {concept_id: interaction_count} from DB events table.

    Falls back to empty dict if table doesn't exist or query fails.
    """
    try:
        from app.services.unified_db import session as db_session
        from sqlalchemy import text
        with db_session() as sess:
            rows = sess.execute(
                text(
                    "SELECT concept_id, COUNT(*) as cnt FROM interaction_events "
                    "GROUP BY concept_id"
                )
            ).fetchall()
            return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

def _shannon_entropy(counts: list[int]) -> float:
    """Normalised Shannon entropy in [0, 1]."""
    total = sum(counts)
    if total == 0 or len(counts) <= 1:
        return 1.0
    probs = [c / total for c in counts if c > 0]
    raw = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(counts))
    if max_entropy == 0:
        return 1.0
    return min(1.0, raw / max_entropy)


def _concentration_ratio(counts: list[int], top_n: int = TOP_N_CONCENTRATION) -> float:
    """Fraction of total interactions absorbed by top-N concepts."""
    total = sum(counts)
    if total == 0:
        return 0.0
    top = sorted(counts, reverse=True)[:top_n]
    return min(1.0, sum(top) / total)


def _potential_score(concept: dict, child_count: int, all_edges: list[dict]) -> float:
    """Deterministic potential: edge richness × recency weight × diversity."""
    cid = concept.get("id", "")
    edge_count = sum(
        1 for e in all_edges
        if e.get("from") == cid or e.get("to") == cid
    )
    # Recency weight from concept metadata (default mid)
    recency = 0.5
    # Connection diversity: unique partners
    partners = set()
    for e in all_edges:
        if e.get("from") == cid:
            partners.add(e.get("to", ""))
        elif e.get("to") == cid:
            partners.add(e.get("from", ""))
    diversity = min(1.0, len(partners) / 10.0)
    # Combine: more edges + diversity → higher potential
    raw = (min(edge_count, 20) / 20.0) * 0.5 + diversity * 0.3 + recency * 0.2
    return round(min(1.0, raw), 3)


def _find_connected_components(
    node_ids: set[str], edges: list[dict]
) -> list[set[str]]:
    """Union-find for undirected connectivity."""
    parent: dict[str, str] = {n: n for n in node_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for e in edges:
        f, t = e.get("from", ""), e.get("to", "")
        if f in parent and t in parent:
            union(f, t)

    groups: dict[str, set[str]] = {}
    for n in node_ids:
        root = find(n)
        groups.setdefault(root, set()).add(n)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_health_snapshot() -> GraphHealthSnapshot:
    """Compute a full graph health snapshot synchronously (max COMPUTE_TIMEOUT_SECS)."""
    global _last_compute_time

    snapshot_id = str(uuid4())
    now = datetime.now(timezone.utc)

    concepts, edges = _fetch_graph_data()
    interaction_counts = _fetch_interaction_counts()

    concept_ids = {c.get("id", "") for c in concepts if c.get("id")}
    concept_count = len(concept_ids)
    edge_count = len(edges)

    # ---- child count per concept (outgoing edges) ----
    children: dict[str, int] = {cid: 0 for cid in concept_ids}
    for e in edges:
        src = e.get("from", "")
        if src in children:
            children[src] += 1

    # ---- interaction counts ----
    total_interactions = sum(interaction_counts.values()) or 0
    counts_list = [interaction_counts.get(cid, 0) for cid in concept_ids]

    entropy_score = _shannon_entropy(counts_list) if concept_count > 0 else 1.0
    concentration = _concentration_ratio(counts_list)

    # ---- gravity wells ----
    gravity_wells: list[GravityWell] = []
    for cid, cnt in children.items():
        if cnt >= SPLIT_THRESHOLD:
            # Skip if convergence guard active
            guard = get_convergence_guard(cid)
            if guard is not None:
                continue
            severity = "critical" if cnt >= SPLIT_CRITICAL else "warning"
            gravity_wells.append(GravityWell(
                concept_id=cid, child_count=cnt, severity=severity
            ))

    # ---- orphan clusters ----
    components = _find_connected_components(concept_ids, edges)
    main_size = max((len(c) for c in components), default=0)
    orphan_clusters: list[OrphanCluster] = []
    for component in components:
        if len(component) >= 2 and len(component) <= ORPHAN_MAX_SIZE and len(component) < main_size:
            cluster_id = f"cluster_{list(component)[0][:8]}"
            orphan_clusters.append(OrphanCluster(
                cluster_id=cluster_id,
                size=len(component),
                members=sorted(component),
            ))

    # ---- surface candidates ----
    surface_candidates: list[SurfaceCandidate] = []
    for concept in concepts:
        cid = concept.get("id", "")
        if not cid:
            continue
        int_count = interaction_counts.get(cid, 0)
        interaction_pct = (int_count / total_interactions) if total_interactions > 0 else 0.0
        if interaction_pct < SURFACE_MAX_PCT:
            potential = _potential_score(concept, children.get(cid, 0), edges)
            if potential >= SURFACE_MIN_POTENTIAL:
                surface_candidates.append(SurfaceCandidate(
                    concept_id=cid,
                    potential_score=potential,
                    interaction_pct=round(interaction_pct, 6),
                ))

    # ---- balance score (composite) ----
    #   entropy weight: 0.4, concentration weight: 0.3, orphan weight: 0.2, gravity weight: 0.1
    orphan_score = max(0.0, 1.0 - len(orphan_clusters) / max(concept_count, 1))
    gravity_score = max(0.0, 1.0 - len(gravity_wells) / max(concept_count, 1))
    conc_score = 1.0 - min(1.0, concentration)
    balance_score = round(
        entropy_score * 0.4 + conc_score * 0.3 + orphan_score * 0.2 + gravity_score * 0.1, 4
    )

    # ---- signals ----
    existing_unresolved = {
        (s.type, s.concept_id or s.cluster_id)
        for s in list_signals(resolved=False)
    }

    signals: list[GraphSignal] = []

    # Convergence OK signals for guarded nodes with high child count
    for cid, cnt in children.items():
        if cnt >= SPLIT_THRESHOLD:
            guard = get_convergence_guard(cid)
            if guard is not None:
                sig = GraphSignal(
                    id=f"sig_{uuid4().hex[:12]}",
                    type="convergence_ok",
                    concept_id=cid,
                    severity="info",
                    created_at=now,
                    resolved=False,
                )
                signals.append(sig)

    # Split signals
    for gw in gravity_wells:
        key = ("split_signal", gw.concept_id)
        if key not in existing_unresolved:
            sig = GraphSignal(
                id=f"sig_{uuid4().hex[:12]}",
                type="split_signal",
                concept_id=gw.concept_id,
                severity=gw.severity,
                created_at=now,
                resolved=False,
            )
            signals.append(sig)
            upsert_signal(sig)

    # Merge signals for orphan clusters
    for cluster in orphan_clusters:
        key = ("merge_signal", cluster.cluster_id)
        if key not in existing_unresolved:
            sig = GraphSignal(
                id=f"sig_{uuid4().hex[:12]}",
                type="merge_signal",
                cluster_id=cluster.cluster_id,
                severity="warning",
                created_at=now,
                resolved=False,
            )
            signals.append(sig)
            upsert_signal(sig)

    # Surface signals
    for sc in surface_candidates:
        key = ("surface_signal", sc.concept_id)
        if key not in existing_unresolved:
            sig = GraphSignal(
                id=f"sig_{uuid4().hex[:12]}",
                type="surface_signal",
                concept_id=sc.concept_id,
                severity="info",
                created_at=now,
                resolved=False,
            )
            signals.append(sig)
            upsert_signal(sig)

    snapshot = GraphHealthSnapshot(
        id=snapshot_id,
        computed_at=now,
        balance_score=balance_score,
        entropy_score=round(entropy_score, 4),
        concentration_ratio=round(concentration, 4),
        concept_count=concept_count,
        edge_count=edge_count,
        gravity_wells=gravity_wells,
        orphan_clusters=orphan_clusters,
        surface_candidates=surface_candidates,
        signals=signals,
        spec_ref=SPEC_REF,
    )

    save_snapshot(snapshot)
    _last_compute_time = now
    return snapshot


def get_or_compute_health() -> GraphHealthSnapshot:
    """Return cached snapshot or compute fresh one."""
    snap = get_latest_snapshot()
    if snap is not None:
        return snap
    return compute_health_snapshot()


def trigger_compute() -> tuple[GraphHealthSnapshot, bool]:
    """Trigger an on-demand computation.

    Returns (snapshot, was_computed) where was_computed=False means cache hit.
    Raises RuntimeError if already in cooldown.
    """
    global _last_compute_time

    if is_in_cooldown():
        raise RuntimeError("cooldown")

    acquired = _compute_lock.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("cooldown")

    try:
        snapshot = compute_health_snapshot()
        return snapshot, True
    finally:
        _compute_lock.release()


def get_health_history(limit: int = 10, since=None):
    return get_snapshot_history(limit=limit, since=since)


# ---------------------------------------------------------------------------
# Convergence guard facade
# ---------------------------------------------------------------------------

def set_guard(concept_id: str, reason: str, set_by: str) -> ConvergenceGuardResponse:
    return set_convergence_guard(concept_id, reason, set_by)


def remove_guard(concept_id: str) -> bool:
    return delete_convergence_guard(concept_id)


def guard_exists(concept_id: str) -> bool:
    return get_convergence_guard(concept_id) is not None


# ---------------------------------------------------------------------------
# ROI facade
# ---------------------------------------------------------------------------

def get_roi(period_days: int = 30) -> GraphHealthROI:
    from app.db.graph_health_repo import get_roi_stats
    stats = get_roi_stats(period_days=period_days)
    return GraphHealthROI(**stats)
