"""Resonance-based discovery: rank ideas by alignment with a tunable axis vector (spec 166)."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.models.idea import IDEA_STAGE_ORDER, IdeaWithScore, ManifestationStatus
from app.models.resonance_navigation import (
    AXIS_KEYS,
    ResonanceDiscoveryRequest,
    ResonanceDiscoveryResponse,
    ResonanceIdeaHit,
)
from app.services import contribution_ledger_service, graph_service, idea_service
from app.services.news_resonance_service import extract_keywords

logger = logging.getLogger(__name__)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _stage_index(stage: Any) -> int:
    try:
        return IDEA_STAGE_ORDER.index(stage)
    except (ValueError, TypeError):
        return 0


def _manifestation_factor(status: Any) -> float:
    if status == ManifestationStatus.VALIDATED:
        return 1.0
    if status == ManifestationStatus.PARTIAL:
        return 0.68
    return 0.36


def _keyword_set(text: str) -> frozenset[str]:
    return frozenset(extract_keywords(text or ""))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def _build_centroid_keywords(ideas: list[IdeaWithScore]) -> frozenset[str]:
    merged: set[str] = set()
    for idea in ideas[:400]:
        merged |= set(extract_keywords(f"{idea.name} {idea.description}"))
    # keep top mass: cap size for stability
    return frozenset(sorted(merged)[:200])


def _contributor_keyword_pool(contributor_id: str, idea_map: dict[str, IdeaWithScore]) -> frozenset[str]:
    pool: set[str] = set()
    try:
        hist = contribution_ledger_service.get_contributor_history(contributor_id, limit=80)
    except Exception:
        logger.debug("contributor history unavailable", exc_info=True)
        return frozenset()
    seen: set[str] = set()
    for rec in hist:
        iid = rec.get("idea_id")
        if not isinstance(iid, str) or not iid.strip():
            continue
        if iid in seen:
            continue
        seen.add(iid)
        idea = idea_map.get(iid)
        if idea is None:
            continue
        pool |= set(extract_keywords(f"{idea.name} {idea.description}"))
    return frozenset(sorted(pool)[:120])


def _edge_counts(idea_ids: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for iid in idea_ids:
        try:
            edges = graph_service.get_edges(iid, direction="both")
            out[iid] = len(edges)
        except Exception:
            out[iid] = 0
    return out


def _recency_map(idea_ids: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    try:
        feed = idea_service.get_resonance_feed(window_hours=720, limit=500)
    except Exception:
        logger.debug("resonance feed unavailable for recency", exc_info=True)
        feed = []
    for rank, item in enumerate(feed):
        iid = item.get("idea_id")
        if not isinstance(iid, str):
            continue
        # Top of feed ≈ 1.0, tail ≈ 0.35
        rlen = max(len(feed), 1)
        scores[iid] = _clamp01(1.0 - (rank / rlen) * 0.65)

    now = datetime.now(timezone.utc)
    for iid in idea_ids:
        if iid in scores:
            continue
        try:
            node = graph_service.get_node(iid)
        except Exception:
            node = None
        if not node:
            scores[iid] = 0.42
            continue
        raw = node.get("updated_at")
        if hasattr(raw, "timestamp"):
            dt = raw
        elif isinstance(raw, str):
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                dt = None
        else:
            dt = None
        if dt is None:
            scores[iid] = 0.42
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = max(0.0, (now - dt).total_seconds() / 3600.0)
        # Half-life ~ 2 weeks
        scores[iid] = _clamp01(math.exp(-hours / (24.0 * 14.0)))

    return scores


def _compute_profiles(
    scored: list[IdeaWithScore],
    *,
    contributor_id: str | None,
    recency_by_id: dict[str, float],
    edge_by_id: dict[str, int],
    centroid: frozenset[str],
    contrib_pool: frozenset[str],
) -> dict[str, dict[str, float]]:
    """Per-idea axis profiles in [0,1]."""
    keyword_by_id: dict[str, frozenset[str]] = {
        s.id: _keyword_set(f"{s.name} {s.description}") for s in scored
    }

    profiles: dict[str, dict[str, float]] = {}
    n = len(scored)
    for s in scored:
        iid = s.id
        # Curiosity: novel / less settled → higher
        si = _stage_index(s.stage)
        denom = max(len(IDEA_STAGE_ORDER) - 1, 1)
        stage_part = 1.0 - (si / denom)
        curiosity = _clamp01((1.0 - s.confidence) * 0.55 + stage_part * 0.45)

        # Depth
        ec = edge_by_id.get(iid, 0)
        edge_part = min(1.0, math.log(ec + 1) / math.log(48.0))
        tag_part = min(1.0, len(s.interfaces) / 14.0)
        desc_part = min(1.0, len(s.description) / 3500.0)
        depth = _clamp01(edge_part * 0.38 + desc_part * 0.37 + tag_part * 0.25)

        # Coherence affinity
        mf = _manifestation_factor(s.manifestation_status)
        fe = min(1.0, float(s.free_energy_score) / 120.0)
        coherence_affinity = _clamp01(s.confidence * 0.48 + mf * 0.42 + fe * 0.10)

        # Recency
        recency = recency_by_id.get(iid, 0.45)

        # Serendipity
        kw = keyword_by_id[iid]
        if contributor_id and contrib_pool:
            j = _jaccard(kw, contrib_pool)
            serendipity = _clamp01(1.0 - j)
        else:
            j_cent = _jaccard(kw, centroid)
            serendipity = _clamp01(1.0 - j_cent)

        # Optional diversity nudge when many ideas share the same keywords
        if n > 3:
            sample = 0.0
            cnt = 0
            for other in scored:
                if other.id == iid:
                    continue
                sample += _jaccard(kw, keyword_by_id[other.id])
                cnt += 1
                if cnt >= 12:
                    break
            if cnt:
                serendipity = _clamp01(0.5 * serendipity + 0.5 * (1.0 - sample / cnt))

        profiles[iid] = {
            "curiosity": curiosity,
            "serendipity": serendipity,
            "depth": depth,
            "coherence_affinity": coherence_affinity,
            "recency": recency,
        }

    return profiles


def _weights(req: ResonanceDiscoveryRequest) -> dict[str, float]:
    raw = req.axis_weights or {}
    out: dict[str, float] = {k: 1.0 for k in AXIS_KEYS}
    for k, v in raw.items():
        if k in out and isinstance(v, (int, float)):
            out[k] = max(0.0, min(10.0, float(v)))
    return out


def _alignment(
    desired: dict[str, float],
    profile: dict[str, float],
    weights: dict[str, float],
) -> float:
    num = 0.0
    den = 0.0
    for k in AXIS_KEYS:
        w = weights.get(k, 1.0)
        if w <= 0:
            continue
        d = desired.get(k, 0.5)
        c = profile.get(k, 0.5)
        num += w * (1.0 - abs(d - c))
        den += w
    if den <= 0:
        return 0.0
    return _clamp01(num / den)


def discover(req: ResonanceDiscoveryRequest) -> ResonanceDiscoveryResponse:
    portfolio = idea_service.list_ideas(
        only_unvalidated=False,
        include_internal=req.include_internal,
        limit=250,
        offset=0,
    )
    scored = portfolio.ideas
    if not scored:
        return ResonanceDiscoveryResponse(
            requested_axes=req.axes.model_dump(),
            ideas=[],
            nodes=[],
            connections=[],
        )

    ids = [s.id for s in scored]
    recency_by_id = _recency_map(ids)
    edge_by_id = _edge_counts(ids)
    centroid = _build_centroid_keywords(scored)
    contrib_pool = (
        _contributor_keyword_pool(req.contributor_id, {s.id: s for s in scored})
        if req.contributor_id
        else frozenset()
    )

    profiles = _compute_profiles(
        scored,
        contributor_id=req.contributor_id,
        recency_by_id=recency_by_id,
        edge_by_id=edge_by_id,
        centroid=centroid,
        contrib_pool=contrib_pool,
    )

    desired = req.axes.model_dump()
    wmap = _weights(req)

    hits: list[tuple[float, IdeaWithScore, dict[str, float]]] = []
    for s in scored:
        prof = profiles[s.id]
        score = _alignment(desired, prof, wmap)
        hits.append((score, s, prof))

    hits.sort(key=lambda x: x[0], reverse=True)
    top = hits[: max(1, req.limit)]

    idea_payloads: list[ResonanceIdeaHit] = []
    for score, idea, prof in top:
        idea_payloads.append(
            ResonanceIdeaHit(
                idea=idea.model_dump(mode="json"),
                resonance_score=score,
                axis_profile=prof,
            )
        )

    nodes: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    if req.include_graph and top:
        seen_nodes: set[str] = set()
        for _, idea, _ in top[:8]:
            iid = idea.id
            try:
                n = graph_service.get_node(iid)
                if n and iid not in seen_nodes:
                    nodes.append(n)
                    seen_nodes.add(iid)
                for e in graph_service.get_edges(iid, direction="both")[:12]:
                    connections.append(e)
                    other = e.get("to_id") if e.get("from_id") == iid else e.get("from_id")
                    if isinstance(other, str) and other not in seen_nodes and len(seen_nodes) < 40:
                        on = graph_service.get_node(other)
                        if on:
                            nodes.append(on)
                            seen_nodes.add(other)
            except Exception:
                logger.debug("graph enrichment skipped for %s", iid, exc_info=True)

    return ResonanceDiscoveryResponse(
        requested_axes=desired,
        ideas=idea_payloads,
        nodes=nodes,
        connections=connections,
    )
