"""Graph shape diagnostics: entropy, concentration, gravity wells, orphan clusters (spec-172)."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.db import graph_health_repo
from app.models.graph_health import (
    GraphHealthSnapshot,
    GraphSignal,
    GravityWell,
    OrphanCluster,
    SurfaceCandidate,
)
from app.services.self_balancing_graph_idea import IDEA_ID, IDEA_NAME

# Spec thresholds — gravity well when outgoing has_child count reaches these bounds.
SPLIT_THRESHOLD = 10
SPLIT_CRITICAL = 15

# Entropy bands for healthy vs unhealthy (normalized Shannon).
ENTROPY_HEALTHY = 0.85
ENTROPY_WARNING = 0.35

_last_compute_time: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _shannon_entropy(counts: list[int]) -> float:
    """Normalized Shannon entropy in [0, 1] over nonnegative engagement counts."""
    total = sum(counts)
    if total <= 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    if not probs:
        return 0.0
    h = -sum(p * math.log(p + 1e-30) for p in probs)
    k = len(probs)
    max_h = math.log(k) if k > 1 else 1.0
    if max_h <= 0:
        return 0.0
    return min(1.0, max(0.0, h / max_h))


def _concentration_ratio(counts: list[int], top_n: int = 3) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    top = sorted(counts, reverse=True)[:top_n]
    return sum(top) / total


def guard_exists(concept_id: str) -> bool:
    return graph_health_repo.get_guard(concept_id) is not None


def _child_counts(concepts: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {c["id"]: 0 for c in concepts}
    for e in edges:
        if e.get("type") == "has_child":
            fid = e.get("from")
            if fid in counts:
                counts[fid] += 1
    return counts


def _engagement_counts(concepts: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[int]:
    """Per-concept engagement: degree + 1 so isolated nodes still participate."""
    deg: dict[str, int] = {c["id"]: 0 for c in concepts}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a in deg:
            deg[a] += 1
        if b in deg:
            deg[b] += 1
    return [max(1, deg[c["id"]]) for c in concepts]


def _undirected_components(
    concepts: list[dict[str, Any]], edges: list[dict[str, Any]],
) -> list[list[str]]:
    ids = [c["id"] for c in concepts]
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in ids:
        if start in seen:
            continue
        comp: list[str] = []
        q = deque([start])
        seen.add(start)
        while q:
            u = q.popleft()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(comp)
    return comps


def _orphan_clusters(
    concepts: list[dict[str, Any]], edges: list[dict[str, Any]],
) -> list[OrphanCluster]:
    comps = _undirected_components(concepts, edges)
    if len(comps) <= 1:
        return []
    comps.sort(key=len, reverse=True)
    out: list[OrphanCluster] = []
    for i, comp in enumerate(comps[1:], start=1):
        if len(comp) < 2:
            continue
        oid = f"orphan-{i}-{comp[0]}"
        sev: Any = "warning" if len(comp) <= 4 else "critical"
        out.append(
            OrphanCluster(
                cluster_id=oid,
                concept_ids=sorted(comp),
                size=len(comp),
                severity=sev,
            ),
        )
    return out


def _gravity_wells(
    child_counts: dict[str, int],
) -> list[GravityWell]:
    wells: list[GravityWell] = []
    for cid, n in child_counts.items():
        if n < SPLIT_THRESHOLD:
            continue
        sev: Any = "critical" if n >= SPLIT_CRITICAL else "warning"
        wells.append(GravityWell(concept_id=cid, child_count=n, severity=sev))
    return wells


def _surface_candidates(
    concepts: list[dict[str, Any]],
    engagement: list[int],
    concentration: float,
) -> list[SurfaceCandidate]:
    if concentration < 0.55 or not concepts:
        return []
    # Neglected branches: below-median engagement but connected (degree >= 2 in engagement proxy).
    pairs = sorted(
        zip([c["id"] for c in concepts], engagement, strict=True),
        key=lambda x: x[1],
    )
    mid = len(pairs) // 2
    out: list[SurfaceCandidate] = []
    for i, (cid, eng) in enumerate(pairs):
        if i >= mid and eng <= pairs[mid][1]:
            score = min(1.0, 0.4 + 0.6 * (1.0 - concentration))
            out.append(
                SurfaceCandidate(
                    concept_id=cid,
                    reason="low engagement but connected branch",
                    score=round(score, 2),
                ),
            )
        if len(out) >= 8:
            break
    return out


def _balance_components(
    entropy: float,
    concentration: float,
    orphan_clusters: list[OrphanCluster],
    gravity_wells: list[GravityWell],
) -> float:
    orphan_health = max(0.0, 1.0 - 0.2 * len(orphan_clusters))
    crit = sum(1 for w in gravity_wells if w.severity == "critical")
    grav_pressure = min(
        1.0,
        0.12 * len(gravity_wells) + 0.15 * crit,
    )
    raw = (
        0.4 * entropy
        + 0.3 * (1.0 - concentration)
        + 0.2 * orphan_health
        + 0.1 * (1.0 - grav_pressure)
    )
    return round(min(1.0, max(0.0, raw)), 4)


def _build_signals(
    gravity_wells: list[GravityWell],
    guarded_ok: list[GravityWell],
    orphan_clusters: list[OrphanCluster],
    surface_candidates: list[SurfaceCandidate],
) -> list[GraphSignal]:
    ts = _now()
    signals: list[GraphSignal] = []

    for w in guarded_ok:
        signals.append(
            GraphSignal(
                id=f"sig_{uuid.uuid4().hex[:12]}",
                type="convergence_ok",
                concept_id=w.concept_id,
                severity="info",
                created_at=ts,
                resolved=False,
            ),
        )

    for w in gravity_wells:
        sev: Any = "critical" if w.severity == "critical" else "warning"
        signals.append(
            GraphSignal(
                id=f"sig_{uuid.uuid4().hex[:12]}",
                type="split_signal",
                concept_id=w.concept_id,
                severity=sev,
                created_at=ts,
                resolved=False,
            ),
        )

    for oc in orphan_clusters:
        signals.append(
            GraphSignal(
                id=f"sig_{uuid.uuid4().hex[:12]}",
                type="merge_signal",
                cluster_id=oc.cluster_id,
                severity="warning",
                created_at=ts,
                resolved=False,
            ),
        )

    for sc in surface_candidates:
        signals.append(
            GraphSignal(
                id=f"sig_{uuid.uuid4().hex[:12]}",
                type="surface_signal",
                concept_id=sc.concept_id,
                severity="info",
                created_at=ts,
                resolved=False,
            ),
        )

    return signals


def compute_snapshot() -> GraphHealthSnapshot:
    """Recompute health from concept_service graph state."""
    global _last_compute_time
    from app.services import concept_service as cs

    concepts = list(cs._concepts)
    edges = list(cs._edges)

    if not concepts:
        snap = GraphHealthSnapshot(
            balance_score=0.0,
            entropy_score=0.0,
            concentration_ratio=0.0,
            gravity_wells=[],
            orphan_clusters=[],
            surface_candidates=[],
            signals=[],
            computed_at=_now(),
        )
        graph_health_repo.set_snapshot(snap)
        _last_compute_time = snap.computed_at
        return snap

    eng = _engagement_counts(concepts, edges)
    ent = _shannon_entropy(eng)
    conc = _concentration_ratio(eng, top_n=3)
    child_c = _child_counts(concepts, edges)

    raw_wells = _gravity_wells(child_c)
    guarded_ok = [w for w in raw_wells if guard_exists(w.concept_id)]
    wells = [w for w in raw_wells if not guard_exists(w.concept_id)]
    orphans = _orphan_clusters(concepts, edges)
    surf = _surface_candidates(concepts, eng, conc)

    balance = _balance_components(ent, conc, orphans, raw_wells)
    signals = _build_signals(wells, guarded_ok, orphans, surf)

    snap = GraphHealthSnapshot(
        balance_score=balance,
        entropy_score=round(ent, 4),
        concentration_ratio=round(conc, 4),
        gravity_wells=wells,
        orphan_clusters=orphans,
        surface_candidates=surf,
        signals=signals,
        computed_at=_now(),
    )
    graph_health_repo.set_snapshot(snap)
    _last_compute_time = snap.computed_at
    return snap


def get_latest_or_baseline() -> GraphHealthSnapshot:
    s = graph_health_repo.get_snapshot()
    if s is not None:
        return s
    return GraphHealthSnapshot(
        balance_score=0.0,
        entropy_score=0.0,
        concentration_ratio=0.0,
        gravity_wells=[],
        orphan_clusters=[],
        surface_candidates=[],
        signals=[],
        computed_at=_now(),
    )


def roi_snapshot() -> dict[str, Any]:
    latest = graph_health_repo.get_snapshot()
    prev = graph_health_repo.get_previous_balance()
    cur = latest.balance_score if latest else 0.0
    delta = 0.0 if prev is None else round(cur - prev, 4)
    sp, mg, sf = graph_health_repo.roi_counts()
    return {
        "balance_score_delta": delta,
        "split_signals_actioned": sp,
        "merge_signals_actioned": mg,
        "surface_signals_actioned": sf,
        "spec_ref": "spec-172",
        "idea_id": IDEA_ID,
        "idea_name": IDEA_NAME,
    }
