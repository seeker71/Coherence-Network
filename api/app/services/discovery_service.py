"""Discovery service — Serendipity Discovery feed.

Combines multiple resonance signals into a single personalized feed:
- Resonant ideas (belief-profile match)
- Resonant peers (worldview + concept overlap)
- Cross-domain bridges (CRK structural resonance)
- Resonant news (keyword resonance with staked ideas)
- Growth edges (ontology suggestions)

Each source is independently wrapped in try/except so a failure in one
does not break the entire feed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.models.discovery import DiscoveryFeed, DiscoveryItem

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source A: Resonant Ideas
# ---------------------------------------------------------------------------

def _collect_resonant_ideas(
    contributor_id: str,
    profile: dict[str, Any] | None,
    limit: int,
) -> list[DiscoveryItem]:
    """Ideas scored against the contributor's belief profile."""
    from app.services import belief_service, idea_service

    items: list[DiscoveryItem] = []
    try:
        portfolio = idea_service.list_ideas(limit=100, offset=0, read_only_guard=True)
        ideas = portfolio.ideas if hasattr(portfolio, "ideas") else []

        for idea in ideas:
            try:
                result = belief_service.compute_resonance(contributor_id, idea.id)
                score = result.resonance_score
            except Exception:
                # Contributor or idea lacks data; use neutral score
                score = 0.5

            items.append(DiscoveryItem(
                kind="resonant_idea",
                score=score,
                title=idea.name,
                summary=getattr(idea, "description", "") or "",
                entity_id=idea.id,
                entity_type="idea",
                reason=f"Resonance score {score:.2f} with your belief profile",
                tags=getattr(idea, "tags", []) or [],
                links={"idea": f"/ideas/{idea.id}"},
            ))

        items.sort(key=lambda i: i.score, reverse=True)
    except Exception:
        log.debug("discovery: resonant_ideas source failed", exc_info=True)

    return items[:limit]


# ---------------------------------------------------------------------------
# Source B: Resonant Peers
# ---------------------------------------------------------------------------

def _collect_resonant_peers(
    contributor_id: str,
    profile: dict[str, Any] | None,
    limit: int,
) -> list[DiscoveryItem]:
    """Contributors with similar worldview / concept resonance."""
    from app.services import belief_service, graph_service
    from app.routers.peers import _compute_peer_resonance

    items: list[DiscoveryItem] = []
    try:
        source_profile = belief_service.get_belief_profile(contributor_id)

        result = graph_service.list_nodes(type="contributor", limit=200)
        nodes = result.get("items") or []

        for node in nodes:
            cid = node["id"].removeprefix("contributor:")
            if cid == contributor_id:
                continue
            try:
                peer_profile = belief_service._node_to_belief_profile(node)
                score = _compute_peer_resonance(source_profile, peer_profile)
                if score <= 0.1:
                    continue

                shared_tags = list(
                    set(source_profile.interest_tags) & set(peer_profile.interest_tags)
                )
                name = node.get("name", cid)

                items.append(DiscoveryItem(
                    kind="resonant_peer",
                    score=score,
                    title=name,
                    summary=f"Shares worldview alignment and {len(shared_tags)} interest tags",
                    entity_id=cid,
                    entity_type="contributor",
                    reason=f"Resonance {score:.2f} — shared tags: {', '.join(shared_tags[:5]) or 'worldview alignment'}",
                    tags=shared_tags,
                    links={"contributor": f"/contributors/{cid}"},
                ))
            except Exception:
                continue

        items.sort(key=lambda i: i.score, reverse=True)
    except Exception:
        log.debug("discovery: resonant_peers source failed", exc_info=True)

    return items[:limit]


# ---------------------------------------------------------------------------
# Source C: Cross-Domain Bridges
# ---------------------------------------------------------------------------

def _collect_cross_domain_bridges(limit: int) -> list[DiscoveryItem]:
    """Cross-domain idea pairs from the CRK resonance engine."""
    from app.services import idea_service
    from app.services import idea_resonance_service as resonance_svc

    items: list[DiscoveryItem] = []
    try:
        portfolio = idea_service.list_ideas(limit=200, offset=0, read_only_guard=True)
        all_ideas = []
        for idea in (portfolio.ideas if hasattr(portfolio, "ideas") else []):
            all_ideas.append({
                "id": idea.id,
                "name": idea.name,
                "description": getattr(idea, "description", "") or "",
                "tags": getattr(idea, "tags", []) or [],
                "interfaces": getattr(idea, "interfaces", []) or [],
            })

        pairs = resonance_svc.get_cross_domain_pairs(
            all_ideas=all_ideas,
            limit=limit,
            min_coherence=0.08,
        )

        for pair in pairs:
            items.append(DiscoveryItem(
                kind="cross_domain",
                score=min(1.0, pair.coherence),
                title=f"{pair.name_a} <> {pair.name_b}",
                summary=f"Cross-domain bridge between {', '.join(pair.domain_a)} and {', '.join(pair.domain_b)}",
                entity_id=f"{pair.idea_id_a}:{pair.idea_id_b}",
                entity_type="idea",
                reason="These ideas from different domains share deep structural patterns",
                tags=list(set(pair.domain_a + pair.domain_b)),
                links={
                    "idea_a": f"/ideas/{pair.idea_id_a}",
                    "idea_b": f"/ideas/{pair.idea_id_b}",
                },
            ))
    except Exception:
        log.debug("discovery: cross_domain source failed", exc_info=True)

    return items[:limit]


# ---------------------------------------------------------------------------
# Source D: Resonant News
# ---------------------------------------------------------------------------

def _collect_resonant_news(
    contributor_id: str,
    limit: int,
) -> list[DiscoveryItem]:
    """News items that match the contributor's staked ideas."""
    from app.services import (
        contribution_ledger_service,
        idea_service,
        news_ingestion_service,
        news_resonance_service,
    )

    items: list[DiscoveryItem] = []
    try:
        # Get cached news items (do not fetch from network in a sync context)
        news_items = news_ingestion_service.get_cached_items()
        if not news_items:
            return items

        # Get contributor's staked idea IDs
        staked_idea_ids: set[str] = set()
        try:
            records = contribution_ledger_service.get_contributor_history(
                contributor_id, limit=500,
            )
            for rec in records:
                idea_id = rec.get("idea_id") if isinstance(rec, dict) else getattr(rec, "idea_id", None)
                if idea_id:
                    staked_idea_ids.add(idea_id)
        except Exception:
            pass

        # Build idea dicts
        portfolio = idea_service.list_ideas(limit=200, offset=0, read_only_guard=True)
        all_idea_objs = portfolio.ideas if hasattr(portfolio, "ideas") else []
        all_idea_dicts = [
            {
                "id": idea.id,
                "name": idea.name,
                "description": getattr(idea, "description", "") or "",
                "confidence": getattr(idea, "confidence", 0.5),
            }
            for idea in all_idea_objs
        ]

        if staked_idea_ids:
            filtered = [d for d in all_idea_dicts if d["id"] in staked_idea_ids]
        else:
            filtered = all_idea_dicts

        if not filtered:
            return items

        results = news_resonance_service.compute_resonance(
            news_items, filtered, top_n=5,
        )

        for idea_result in results:
            for match in idea_result.matches:
                news_dict = match.news_item
                items.append(DiscoveryItem(
                    kind="resonant_news",
                    score=min(1.0, match.resonance_score),
                    title=news_dict.get("title", ""),
                    summary=news_dict.get("description", ""),
                    entity_id=news_dict.get("url", ""),
                    entity_type="news",
                    reason=match.reason,
                    tags=match.matched_keywords[:5],
                    links={"url": news_dict.get("url", ""), "idea": f"/ideas/{match.idea_id}"},
                ))

        items.sort(key=lambda i: i.score, reverse=True)
    except Exception:
        log.debug("discovery: resonant_news source failed", exc_info=True)

    return items[:limit]


# ---------------------------------------------------------------------------
# Source E: Growth Edges
# ---------------------------------------------------------------------------

def _collect_growth_edges(limit: int) -> list[DiscoveryItem]:
    """Recent ontology concept suggestions as growth edges."""
    from app.services import accessible_ontology_service as onto_svc

    items: list[DiscoveryItem] = []
    try:
        suggestions = onto_svc.list_concept_suggestions(
            status="pending", limit=limit, offset=0,
        )
        # suggestions may be a dict with "items" key or a list
        if isinstance(suggestions, dict):
            suggestion_list = suggestions.get("items", [])
        elif isinstance(suggestions, list):
            suggestion_list = suggestions
        else:
            suggestion_list = []

        for sug in suggestion_list:
            if not isinstance(sug, dict):
                continue
            name = sug.get("name", "")
            desc = sug.get("plain_description", "") or sug.get("description", "")
            sug_id = sug.get("id", "")
            related = sug.get("related_to", [])

            items.append(DiscoveryItem(
                kind="growth_edge",
                score=0.5,  # neutral — not scored against profile
                title=name,
                summary=desc,
                entity_id=sug_id,
                entity_type="edge",
                reason=f"New concept suggestion that could extend the ontology{' — related to: ' + ', '.join(related[:3]) if related else ''}",
                tags=related[:5] if related else [],
                links={"ontology": f"/ontology/suggestions/{sug_id}"},
            ))
    except Exception:
        log.debug("discovery: growth_edges source failed", exc_info=True)

    return items[:limit]


# ---------------------------------------------------------------------------
# Profile summary helper
# ---------------------------------------------------------------------------

def _build_profile_summary(contributor_id: str) -> dict[str, Any]:
    """Return a compact profile summary for the discovery feed.

    Reads the graph node directly because graph_service.get_node() returns
    a flat dict (properties merged into top level), and we need to handle
    both nested and flat layouts.
    """
    from app.services import graph_service
    from app.models.belief import BeliefAxis

    _DEFAULT_AXES = {a.value: 0.0 for a in BeliefAxis}

    try:
        node_id = f"contributor:{contributor_id}" if not contributor_id.startswith("contributor:") else contributor_id
        node = graph_service.get_node(node_id)
        if not node:
            node = graph_service.get_node(contributor_id)
        if not node or node.get("type") != "contributor":
            raise ValueError("Contributor not found")

        # Handle both flat (to_dict merges properties) and nested layouts
        props = node.get("properties") or {}
        raw_axes = props.get("worldview_axes") or node.get("worldview_axes") or {}
        axes = dict(_DEFAULT_AXES)
        axes.update({k: float(v) for k, v in raw_axes.items() if k in _DEFAULT_AXES})

        raw_resonances = props.get("concept_resonances") or node.get("concept_resonances") or []
        concept_count = len([r for r in raw_resonances if isinstance(r, dict)])

        tags: list[str] = list(props.get("interest_tags") or node.get("interest_tags") or [])

        top_axes = sorted(axes.items(), key=lambda kv: kv[1], reverse=True)
        return {
            "worldview_axes": axes,
            "top_axes": [{"axis": k, "weight": v} for k, v in top_axes[:3]],
            "concept_count": concept_count,
            "interest_tags": tags,
        }
    except Exception:
        return {
            "worldview_axes": {},
            "top_axes": [],
            "concept_count": 0,
            "interest_tags": [],
            "note": "No belief profile found — showing general discovery",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_discovery_feed(contributor_id: str, limit: int = 30) -> DiscoveryFeed:
    """Build a unified, personalized discovery feed for a contributor.

    Collects items from five independent sources, merges them sorted by
    score, and returns the top ``limit`` items.  Each source is wrapped in
    try/except so a single failure never breaks the whole feed.
    """
    profile_summary = _build_profile_summary(contributor_id)

    # Budget per source — divide evenly then take top-limit overall
    per_source = max(5, limit)

    resonant_ideas = _collect_resonant_ideas(contributor_id, profile_summary, per_source)
    resonant_peers = _collect_resonant_peers(contributor_id, profile_summary, per_source)
    cross_domain = _collect_cross_domain_bridges(per_source)
    resonant_news = _collect_resonant_news(contributor_id, per_source)
    growth_edges = _collect_growth_edges(per_source)

    all_items: list[DiscoveryItem] = (
        resonant_ideas + resonant_peers + cross_domain + resonant_news + growth_edges
    )

    # Sort by score descending
    all_items.sort(key=lambda i: i.score, reverse=True)
    trimmed = all_items[:limit]

    return DiscoveryFeed(
        contributor_id=contributor_id,
        items=trimmed,
        total=len(trimmed),
        generated_at=datetime.now(timezone.utc).isoformat(),
        profile_summary=profile_summary,
    )


def get_profile_summary(contributor_id: str) -> dict[str, Any]:
    """Return just the belief profile summary for a contributor."""
    return _build_profile_summary(contributor_id)


# ---------------------------------------------------------------------------
# Cross-Domain Bridge Notifications
# ---------------------------------------------------------------------------

def notify_new_bridges(
    workspace_id: str = "coherence-network",
    min_coherence: float = 0.35,
) -> int:
    """Create activity events for new cross-domain resonance bridges.

    Scans idea pairs from the resonance service, checks for existing
    activity events to avoid duplicates, and creates new events for
    any strong bridges not yet notified.

    Returns the count of new notifications created.
    """
    from app.services import activity_service, idea_service
    from app.services import idea_resonance_service as resonance_svc

    new_count = 0

    try:
        # Get all ideas as dicts
        portfolio = idea_service.list_ideas(limit=200, offset=0, read_only_guard=True)
        all_ideas = []
        for idea in (portfolio.ideas if hasattr(portfolio, "ideas") else []):
            all_ideas.append({
                "id": idea.id,
                "name": idea.name,
                "description": getattr(idea, "description", "") or "",
                "tags": getattr(idea, "tags", []) or [],
                "interfaces": getattr(idea, "interfaces", []) or [],
            })

        # Get cross-domain pairs above threshold
        pairs = resonance_svc.get_cross_domain_pairs(
            all_ideas=all_ideas,
            limit=100,
            min_coherence=min_coherence,
        )

        if not pairs:
            return 0

        # Get existing bridge events to deduplicate
        existing_events = activity_service.list_events(
            workspace_id=workspace_id,
            limit=500,
            event_type="cross_domain_bridge",
        )
        existing_subjects: set[str] = set()
        for evt in existing_events:
            sid = evt.get("subject_id", "")
            if sid:
                existing_subjects.add(sid)

        for pair in pairs:
            # Canonical pair ID for deduplication
            pair_id = f"{min(pair.idea_id_a, pair.idea_id_b)}:{max(pair.idea_id_a, pair.idea_id_b)}"

            if pair_id in existing_subjects:
                continue

            summary = (
                f"New resonance bridge: '{pair.name_a}' <> '{pair.name_b}' "
                f"(coherence {pair.coherence:.0%})"
            )

            activity_service.record_event(
                workspace_id=workspace_id,
                event_type="cross_domain_bridge",
                subject_type="resonance_pair",
                subject_id=pair_id,
                subject_name=f"{pair.name_a} <> {pair.name_b}",
                summary=summary,
            )
            new_count += 1

    except Exception:
        log.debug("discovery: notify_new_bridges failed", exc_info=True)

    return new_count
