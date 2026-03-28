"""Graph self-balance: split signals, orphan merge hints, energy concentration (Spec 170).

Analyzes `graph_nodes` / `graph_edges` for dynamic equilibrium — anti-collapse
and neglected-branch surfacing when attention concentrates.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_

from app.models.graph import Edge, Node
from app.models.graph_balance import (
    BalanceParameters,
    EntropyReport,
    GraphBalanceReport,
    IdeaEnergyRow,
    MergeSuggestion,
    NeglectedBranch,
    SplitSignal,
)
from app.services.unified_db import session

_PARENT_OF = "parent-of"
_FOCUS_TYPES = frozenset({"idea", "concept"})


def _safe_float(d: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return default


def _node_energy(node_dict: dict[str, Any]) -> float:
    v = _safe_float(node_dict, "free_energy_score", "energy", default=0.0)
    if v > 0:
        return v
    return 1.0


def _median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (float(s[mid - 1]) + float(s[mid])) / 2.0


def _shannon_normalized(weights: list[float]) -> float:
    """Normalized Shannon entropy in [0,1] for nonnegative weights."""
    total = sum(max(0.0, w) for w in weights)
    if total <= 0 or not weights:
        return 1.0
    h = 0.0
    for w in weights:
        p = max(0.0, w) / total
        if p > 0:
            h -= p * math.log(p + 1e-15)
    k = len(weights)
    if k <= 1:
        return 0.0
    return float(h / math.log(k))


def _collect_orphan_ids(s: Session) -> set[str]:
    """Nodes with no incoming parent-of (unanchored in hierarchy)."""
    sub = (
        s.query(Edge.to_id)
        .filter(Edge.type == _PARENT_OF)
        .distinct()
    )
    anchored = {row[0] for row in sub.all()}
    q = s.query(Node.id).filter(Node.type.in_(list(_FOCUS_TYPES)))
    return {row[0] for row in q.all() if row[0] not in anchored}


def _orphan_subgraph_edges(s: Session, orphan_ids: set[str]) -> list[tuple[str, str]]:
    if len(orphan_ids) < 2:
        return []
    rows = (
        s.query(Edge.from_id, Edge.to_id)
        .filter(
            or_(Edge.from_id.in_(orphan_ids), Edge.to_id.in_(orphan_ids)),
        )
        .all()
    )
    out: list[tuple[str, str]] = []
    for a, b in rows:
        if a in orphan_ids and b in orphan_ids and a != b:
            out.append((a, b))
    return out


def _connected_components(nodes: set[str], edges: list[tuple[str, str]]) -> list[set[str]]:
    parent: dict[str, str] = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in edges:
        if a in nodes and b in nodes:
            union(a, b)

    groups: dict[str, set[str]] = defaultdict(set)
    for n in nodes:
        groups[find(n)].add(n)
    return [g for g in groups.values() if len(g) >= 2]


def _load_nodes_by_ids(s: Session, ids: set[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    rows = s.query(Node).filter(Node.id.in_(ids)).all()
    return {n.id: n.to_dict() for n in rows}


def compute_balance_report(
    *,
    max_children: int = 10,
    concentration_threshold: float = 0.8,
) -> GraphBalanceReport:
    """Build the full balance report from current graph state."""
    max_children = max(5, min(100, max_children))
    concentration_threshold = max(0.5, min(1.0, concentration_threshold))

    split_signals: list[SplitSignal] = []
    merge_suggestions: list[MergeSuggestion] = []

    with session() as s:
        # --- Split: too many parent-of children ---
        rows = (
            s.query(Edge.from_id, func.count(Edge.id))
            .filter(Edge.type == _PARENT_OF)
            .group_by(Edge.from_id)
            .having(func.count(Edge.id) >= max_children)
            .all()
        )
        for from_id, cnt in rows:
            node = s.get(Node, from_id)
            if not node:
                continue
            nd = node.to_dict()
            split_signals.append(
                SplitSignal(
                    node_id=from_id,
                    name=nd.get("name") or from_id,
                    node_type=nd.get("type") or "node",
                    child_count=int(cnt),
                    reason=(
                        f"Outgoing '{_PARENT_OF}' fan-out ({cnt}) meets or exceeds "
                        f"threshold ({max_children})."
                    ),
                    suggested_action=(
                        "Partition children under new intermediate concepts or domains; "
                        "keeps hierarchy readable and avoids single-point collapse."
                    ),
                )
            )

        # --- Merge: orphan clusters ---
        orphan_ids = _collect_orphan_ids(s)
        o_edges = _orphan_subgraph_edges(s, orphan_ids)
        comps = _connected_components(orphan_ids, o_edges)
        id_to_node = _load_nodes_by_ids(s, orphan_ids)
        for comp in comps:
            ids_sorted = sorted(comp)
            names = [id_to_node.get(i, {}).get("name") or i for i in ids_sorted]
            merge_suggestions.append(
                MergeSuggestion(
                    node_ids=ids_sorted,
                    names=names,
                    component_size=len(ids_sorted),
                    reason=(
                        "These idea/concept nodes share no parent and are connected to "
                        "each other — a natural merge or re-parent candidate set."
                    ),
                    suggested_action=(
                        "Review for duplicate scope; merge redundant nodes or attach "
                        "under a shared parent domain."
                    ),
                )
            )

        # --- Entropy: idea energy concentration ---
        idea_rows = s.query(Node).filter(Node.type == "idea").all()
        ideas: list[dict[str, Any]] = [n.to_dict() for n in idea_rows]

    energies = [(i["id"], i.get("name") or i["id"], _node_energy(i)) for i in ideas]
    total_e = sum(e for _, _, e in energies) or 1.0
    sorted_by_e = sorted(energies, key=lambda x: -x[2])
    top3 = sorted_by_e[:3]
    top3_sum = sum(e for _, _, e in top3)
    top3_share = top3_sum / total_e if total_e > 0 else 0.0
    top3_ids = {x[0] for x in top3}

    top_ideas: list[IdeaEnergyRow] = []
    for iid, name, e in sorted_by_e[: min(10, len(sorted_by_e))]:
        top_ideas.append(
            IdeaEnergyRow(
                idea_id=iid,
                name=name,
                energy=e,
                energy_share=(e / total_e) if total_e > 0 else 0.0,
            )
        )

    all_vg = [_safe_float(i, "value_gap") for i in ideas]
    all_roi = [_safe_float(i, "roi_cc") for i in ideas]
    med_vg = _median([x for x in all_vg if x > 0] or all_vg)
    med_roi = _median([x for x in all_roi if x > 0] or all_roi)

    neglected: list[NeglectedBranch] = []
    alert = len(ideas) >= 4 and top3_share >= concentration_threshold
    if alert:
        for i in ideas:
            iid = i["id"]
            if iid in top3_ids:
                continue
            en = _node_energy(i)
            vg = _safe_float(i, "value_gap")
            rc = _safe_float(i, "roi_cc")
            high_potential = (vg >= med_vg and med_vg > 0) or (rc >= med_roi and med_roi > 0)
            if high_potential:
                neglected.append(
                    NeglectedBranch(
                        idea_id=iid,
                        name=i.get("name") or iid,
                        energy=en,
                        value_gap=vg,
                        roi_cc=rc,
                        reason=(
                            "Outside top-3 energy share but value_gap or roi_cc is at/above "
                            "median — attention may be misallocated."
                        ),
                    )
                )
        neglected.sort(key=lambda x: -(x.value_gap + x.roi_cc))

    ent = EntropyReport(
        total_ideas=len(ideas),
        total_energy=float(total_e),
        top3_energy_share=float(top3_share),
        concentration_alert=alert,
        top_ideas=top_ideas,
        neglected_branches=neglected[:25],
        shannon_entropy_normalized=_shannon_normalized([e for _, _, e in energies]),
    )

    return GraphBalanceReport(
        split_signals=split_signals,
        merge_suggestions=merge_suggestions,
        entropy=ent,
        parameters=BalanceParameters(
            max_children=max_children,
            concentration_threshold=concentration_threshold,
            weak_degree_max=2,
        ),
    )
