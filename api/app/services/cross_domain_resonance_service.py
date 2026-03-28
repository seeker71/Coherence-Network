"""Cross-domain concept resonance — structural graph similarity (not keyword matching).

Pairs ideas from different domains when their local graph signatures align:
1-hop edge (type, neighbor-type) multiset Jaccard, plus 2-hop node-type footprint overlap.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.models.cross_domain_resonance import (
    CrossDomainResonanceItem,
    CrossDomainResonanceList,
    NodeSummary,
    ProofResponse,
)
from app.services import graph_service

log = logging.getLogger(__name__)

_MAX_IDEAS_SCAN = 200
_DEFAULT_MIN_SCORE = 0.12


def _domain_of(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    d = props.get("domain")
    if isinstance(d, str) and d.strip():
        return d.strip().lower()
    tags = props.get("tags")
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, str) and t.startswith("domain:"):
                return t.split(":", 1)[1].strip().lower()
    return "general"


def _one_hop_signature(node_id: str) -> frozenset[tuple[str, str]]:
    """Structural signature: (edge_type, neighbor_node_type) for each incident edge."""
    sig: set[tuple[str, str]] = set()
    for e in graph_service.get_edges(node_id, direction="both"):
        other_id = e["to_id"] if e["from_id"] == node_id else e["from_id"]
        other = graph_service.get_node(other_id)
        if not other:
            continue
        sig.add((e.get("type") or "related", other.get("type") or "node"))
    return frozenset(sig)


def _two_hop_type_footprint(node_id: str) -> frozenset[str]:
    """Node types visible within 2 hops (excluding the center), for coarse structural overlap."""
    sg = graph_service.get_subgraph(node_id, depth=2)
    types: set[str] = set()
    for n in sg.get("nodes") or []:
        if n.get("id") == node_id:
            continue
        t = n.get("type")
        if t:
            types.add(t)
    return frozenset(types)


def _jaccard(a: frozenset[Any], b: frozenset[Any]) -> float:
    # Empty/empty → no structural evidence to match (avoid scoring isolated nodes as identical).
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def _find_linking_edge(node_a: str, node_b: str) -> dict[str, Any] | None:
    for e in graph_service.get_edges(node_a, direction="both"):
        other = e["to_id"] if e["from_id"] == node_a else e["from_id"]
        if other == node_b:
            return e
    return None


def _pair_scores(
    na: dict[str, Any],
    nb: dict[str, Any],
) -> tuple[float, float, float, float]:
    """Return structural_sim, depth2_sim, crk_score, resonance_score."""
    ia, ib = na["id"], nb["id"]
    s1 = _one_hop_signature(ia)
    s2 = _one_hop_signature(ib)
    structural = _jaccard(s1, s2)

    t1 = _two_hop_type_footprint(ia)
    t2 = _two_hop_type_footprint(ib)
    depth2 = _jaccard(t1, t2)

    crk = 0.55 * structural + 0.45 * depth2
    resonance = min(1.0, 0.5 * structural + 0.5 * depth2)
    return structural, depth2, crk, resonance


def list_cross_domain_resonances(
    *,
    limit: int = 50,
    offset: int = 0,
    min_score: float = _DEFAULT_MIN_SCORE,
    max_ideas: int = _MAX_IDEAS_SCAN,
) -> CrossDomainResonanceList:
    """Discover idea pairs from different domains with analogous graph structure."""
    raw = graph_service.list_nodes(type="idea", limit=max_ideas, offset=0)
    ideas: list[dict[str, Any]] = raw.get("items") or []
    now = datetime.now(timezone.utc)

    candidates: list[CrossDomainResonanceItem] = []
    for i in range(len(ideas)):
        for j in range(i + 1, len(ideas)):
            a, b = ideas[i], ideas[j]
            da, db = _domain_of(a), _domain_of(b)
            if da == db:
                continue
            struct, d2, crk, res = _pair_scores(a, b)
            if res < min_score:
                continue
            # Stable ordering for id and node_a/b
            if a["id"] > b["id"]:
                a, b = b, a
                da, db = db, da
            eid = None
            edge = _find_linking_edge(a["id"], b["id"])
            if edge:
                eid = edge.get("id")
            edge_time = now
            if edge and edge.get("created_at"):
                try:
                    if isinstance(edge["created_at"], datetime):
                        edge_time = edge["created_at"]
                except Exception:
                    pass

            item = CrossDomainResonanceItem(
                id=f"cdcr-{a['id']}-{b['id']}",
                node_a=NodeSummary(
                    id=a["id"],
                    name=a.get("name") or a["id"],
                    domain=_domain_of(a),
                ),
                node_b=NodeSummary(
                    id=b["id"],
                    name=b.get("name") or b["id"],
                    domain=_domain_of(b),
                ),
                domain_a=da,
                domain_b=db,
                resonance_score=round(res, 4),
                structural_sim=round(struct, 4),
                depth2_sim=round(d2, 4),
                crk_score=round(crk, 4),
                edge_id=eid,
                discovered_at=edge_time,
                last_confirmed=now,
                scan_mode="structural-live",
                source="cdcr",
            )
            candidates.append(item)

    candidates.sort(key=lambda x: x.resonance_score, reverse=True)
    total = len(candidates)
    page = candidates[offset : offset + limit]
    return CrossDomainResonanceList(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
    )


def resonances_for_idea(
    idea_id: str,
    *,
    limit: int = 20,
    min_score: float = _DEFAULT_MIN_SCORE,
) -> CrossDomainResonanceList:
    """Cross-domain partners for a single idea (best matches first)."""
    center = graph_service.get_node(idea_id)
    if not center or center.get("type") != "idea":
        return CrossDomainResonanceList(items=[], total=0, limit=limit, offset=0)

    raw = graph_service.list_nodes(type="idea", limit=_MAX_IDEAS_SCAN, offset=0)
    ideas: list[dict[str, Any]] = raw.get("items") or []
    now = datetime.now(timezone.utc)
    matches: list[CrossDomainResonanceItem] = []
    for other in ideas:
        if other["id"] == idea_id:
            continue
        da, db = _domain_of(center), _domain_of(other)
        if da == db:
            continue
        a, b = center, other
        if a["id"] > b["id"]:
            a, b = b, a
            da, db = db, da
        struct, d2, crk, res = _pair_scores(center, other)
        if res < min_score:
            continue
        eid = None
        edge = _find_linking_edge(a["id"], b["id"])
        if edge:
            eid = edge.get("id")
        edge_time = now
        if edge and edge.get("created_at"):
            try:
                if isinstance(edge["created_at"], datetime):
                    edge_time = edge["created_at"]
            except Exception:
                pass
        matches.append(
            CrossDomainResonanceItem(
                id=f"cdcr-{a['id']}-{b['id']}",
                node_a=NodeSummary(
                    id=a["id"],
                    name=a.get("name") or a["id"],
                    domain=_domain_of(a),
                ),
                node_b=NodeSummary(
                    id=b["id"],
                    name=b.get("name") or b["id"],
                    domain=_domain_of(b),
                ),
                domain_a=da,
                domain_b=db,
                resonance_score=round(res, 4),
                structural_sim=round(struct, 4),
                depth2_sim=round(d2, 4),
                crk_score=round(crk, 4),
                edge_id=eid,
                discovered_at=edge_time,
                last_confirmed=now,
                scan_mode="structural-live",
                source="cdcr",
            )
        )
    matches.sort(key=lambda x: x.resonance_score, reverse=True)
    return CrossDomainResonanceList(
        items=matches[:limit],
        total=len(matches),
        limit=limit,
        offset=0,
    )


def get_proof_summary() -> ProofResponse:
    """Lightweight aggregate for health / proof endpoint."""
    lst = list_cross_domain_resonances(
        limit=5, offset=0, min_score=_DEFAULT_MIN_SCORE, max_ideas=_MAX_IDEAS_SCAN
    )
    # Recompute with default min for avg
    scored = list_cross_domain_resonances(
        limit=500, offset=0, min_score=_DEFAULT_MIN_SCORE, max_ideas=_MAX_IDEAS_SCAN
    )
    scores = [x.resonance_score for x in scored.items]
    avg = sum(scores) / len(scores) if scores else 0.0

    analogous_edges = graph_service.list_edges(edge_type="analogous-to", limit=500, offset=0)
    at_total = analogous_edges.get("total") or 0

    return ProofResponse(
        total_resonances=lst.total,
        total_analogous_to_edges=at_total,
        analogous_to_edges_from_cdcr=0,
        domain_pairs_covered=[
            {"domain_a": x.domain_a, "domain_b": x.domain_b, "count": 1}
            for x in lst.items[:10]
        ],
        discovery_timeline=[],
        top_resonances=[
            {
                "node_a": x.node_a.id,
                "node_b": x.node_b.id,
                "score": x.resonance_score,
                "domain_pair": f"{x.domain_a}|{x.domain_b}",
            }
            for x in lst.items[:10]
        ],
        avg_score=round(avg, 4),
        nodes_with_cross_domain_bridge=lst.total,
        organic_growth_rate=0.0,
        proof_status="active" if lst.total else "stale",
    )
