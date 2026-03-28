"""Belief service — business logic for contributor belief profiles and resonance scoring.

Implements: spec-169 (belief-system-interface)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException

from app.models.belief import (
    BeliefAxis,
    BeliefPatch,
    BeliefProfile,
    BeliefROI,
    ConceptResonance,
    ResonanceBreakdown,
    ResonanceResult,
    WorldviewAxisStat,
)
from app.services import graph_service

log = logging.getLogger(__name__)

# Resonance algorithm weights — must sum to 1.0 (spec-169)
_CONCEPT_WEIGHT = 0.4
_WORLDVIEW_WEIGHT = 0.4
_TAG_WEIGHT = 0.2

# Default empty-profile axes — all 6 axes at 0.0
_DEFAULT_AXES: Dict[str, float] = {a.value: 0.0 for a in BeliefAxis}


def _contributor_node_id(contributor_id: str) -> str:
    """Normalise contributor ID to graph node ID."""
    if contributor_id.startswith("contributor:"):
        return contributor_id
    return f"contributor:{contributor_id}"


def _get_contributor_node(contributor_id: str) -> dict[str, Any]:
    """Return contributor node or raise 404."""
    node = graph_service.get_node(_contributor_node_id(contributor_id))
    if not node:
        # Try bare ID as well (UUID-style)
        node = graph_service.get_node(contributor_id)
    if not node or node.get("type") != "contributor":
        raise HTTPException(status_code=404, detail="Contributor not found")
    return node


def _node_to_belief_profile(node: dict[str, Any]) -> BeliefProfile:
    """Extract a BeliefProfile from a contributor graph node's properties."""
    props = node.get("properties") or {}
    raw_axes = props.get("worldview_axes") or {}
    # Fill missing axes with 0.0 so radar chart never gets empty data
    axes = dict(_DEFAULT_AXES)
    axes.update({k: float(v) for k, v in raw_axes.items() if k in _DEFAULT_AXES})

    raw_resonances = props.get("concept_resonances") or []
    resonances = [
        ConceptResonance(concept_id=r["concept_id"], weight=float(r["weight"]))
        for r in raw_resonances
        if isinstance(r, dict) and "concept_id" in r and "weight" in r
    ]

    tags: List[str] = list(props.get("interest_tags") or [])

    raw_updated = props.get("beliefs_updated_at")
    updated_at = datetime.now(timezone.utc)
    if raw_updated:
        try:
            updated_at = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    return BeliefProfile(
        contributor_id=node["id"].removeprefix("contributor:"),
        worldview_axes=axes,
        concept_resonances=resonances,
        interest_tags=tags,
        updated_at=updated_at,
    )


def get_belief_profile(contributor_id: str) -> BeliefProfile:
    node = _get_contributor_node(contributor_id)
    return _node_to_belief_profile(node)


def patch_belief_profile(contributor_id: str, patch: BeliefPatch) -> BeliefProfile:
    node = _get_contributor_node(contributor_id)
    props = dict(node.get("properties") or {})

    # --- worldview_axes merge ---
    if patch.worldview_axes is not None:
        existing_axes = dict(props.get("worldview_axes") or {})
        if patch.replace:
            existing_axes = dict(patch.worldview_axes)
        else:
            existing_axes.update(patch.worldview_axes)
        props["worldview_axes"] = existing_axes

    # --- concept_resonances merge ---
    if patch.concept_resonances is not None:
        new_resonances = [r.model_dump() for r in patch.concept_resonances]
        if patch.replace:
            props["concept_resonances"] = new_resonances
        else:
            existing = {r["concept_id"]: r for r in (props.get("concept_resonances") or [])}
            for r in new_resonances:
                existing[r["concept_id"]] = r
            props["concept_resonances"] = list(existing.values())

    # --- interest_tags merge ---
    if patch.interest_tags is not None:
        if patch.replace:
            props["interest_tags"] = list(patch.interest_tags)
        else:
            existing_tags = list(props.get("interest_tags") or [])
            for tag in patch.interest_tags:
                if tag not in existing_tags:
                    existing_tags.append(tag)
            props["interest_tags"] = existing_tags

    props["beliefs_updated_at"] = datetime.now(timezone.utc).isoformat()

    graph_service.update_node(node["id"], properties=props)

    # Re-fetch to return persisted state
    updated_node = graph_service.get_node(node["id"])
    if updated_node is None:
        raise HTTPException(status_code=500, detail="Failed to persist belief profile")
    return _node_to_belief_profile(updated_node)


def compute_resonance(contributor_id: str, idea_id: str) -> ResonanceResult:
    """Compute resonance between a contributor's beliefs and an idea."""
    node = _get_contributor_node(contributor_id)
    profile = _node_to_belief_profile(node)

    # Fetch idea node
    idea_node = graph_service.get_node(idea_id)
    if not idea_node:
        idea_node = graph_service.get_node(f"idea:{idea_id}")
    if not idea_node:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea_props = idea_node.get("properties") or {}
    idea_tags: List[str] = list(idea_props.get("tags") or idea_props.get("interest_tags") or [])
    idea_concept_ids: List[str] = list(idea_props.get("concept_ids") or idea_props.get("concepts") or [])
    # Also treat idea's tags as concept ids for overlap calc
    all_idea_concepts = list(set(idea_concept_ids + idea_tags))

    contributor_concept_ids = [r.concept_id for r in profile.concept_resonances]
    contributor_weights = {r.concept_id: r.weight for r in profile.concept_resonances}

    # --- concept_overlap (Jaccard-weighted) ---
    matched_concepts: List[str] = []
    if not all_idea_concepts or not contributor_concept_ids:
        concept_overlap = 0.5  # neutral when no data
    else:
        overlap = [c for c in contributor_concept_ids if c in all_idea_concepts]
        matched_concepts = overlap
        if not overlap:
            concept_overlap = 0.0
        else:
            union = list(set(contributor_concept_ids + all_idea_concepts))
            weighted_overlap = sum(contributor_weights.get(c, 1.0) for c in overlap)
            weighted_union = sum(contributor_weights.get(c, 1.0) for c in union)
            concept_overlap = weighted_overlap / weighted_union if weighted_union > 0 else 0.5

    # --- worldview_alignment (dot-product normalized) ---
    idea_axes: Dict[str, float] = {}
    raw_idea_axes = idea_props.get("worldview_axes") or {}
    if raw_idea_axes:
        idea_axes = {k: float(v) for k, v in raw_idea_axes.items() if k in _DEFAULT_AXES}

    matched_axes: List[str] = []
    if not idea_axes:
        worldview_alignment = 0.5  # neutral
    else:
        dot = 0.0
        norm_contributor = 0.0
        norm_idea = 0.0
        for axis in BeliefAxis:
            cv = profile.worldview_axes.get(axis.value, 0.0)
            iv = idea_axes.get(axis.value, 0.0)
            dot += cv * iv
            norm_contributor += cv * cv
            norm_idea += iv * iv
            if cv > 0.3 and iv > 0.3:
                matched_axes.append(axis.value)
        denom = (norm_contributor ** 0.5) * (norm_idea ** 0.5)
        worldview_alignment = dot / denom if denom > 0 else 0.5
        worldview_alignment = max(0.0, min(1.0, worldview_alignment))

    # --- tag_match ---
    contributor_tags = set(profile.interest_tags)
    idea_tag_set = set(idea_tags)
    if not contributor_tags or not idea_tag_set:
        tag_match = 0.5  # neutral
    else:
        matched = contributor_tags & idea_tag_set
        tag_match = len(matched) / len(contributor_tags)
        tag_match = max(0.0, min(1.0, tag_match))

    # --- final score ---
    resonance_score = (
        _CONCEPT_WEIGHT * concept_overlap
        + _WORLDVIEW_WEIGHT * worldview_alignment
        + _TAG_WEIGHT * tag_match
    )
    resonance_score = max(0.0, min(1.0, resonance_score))

    return ResonanceResult(
        contributor_id=contributor_id,
        idea_id=idea_id,
        resonance_score=round(resonance_score, 4),
        breakdown=ResonanceBreakdown(
            concept_overlap=round(concept_overlap, 4),
            worldview_alignment=round(worldview_alignment, 4),
            tag_match=round(tag_match, 4),
        ),
        matched_concepts=matched_concepts,
        matched_axes=matched_axes,
    )


def get_roi() -> BeliefROI:
    """Aggregate network belief stats."""
    result = graph_service.list_nodes(type="contributor", limit=1000)
    all_contributors = result.get("nodes") or []
    total = len(all_contributors)

    axis_sums: Dict[str, float] = {a.value: 0.0 for a in BeliefAxis}
    axis_counts: Dict[str, int] = {a.value: 0 for a in BeliefAxis}
    contributors_with_profiles = 0
    total_concept_resonances = 0

    for node in all_contributors:
        props = node.get("properties") or {}
        axes = props.get("worldview_axes") or {}
        tags = props.get("interest_tags") or []
        resonances = props.get("concept_resonances") or []
        has_profile = bool(axes) or bool(tags) or bool(resonances)
        if has_profile:
            contributors_with_profiles += 1
        for axis, weight in axes.items():
            if axis in axis_sums:
                axis_sums[axis] += float(weight)
                axis_counts[axis] += 1
        total_concept_resonances += len(resonances)

    top_axes: List[WorldviewAxisStat] = []
    for axis in BeliefAxis:
        if axis_counts[axis.value] > 0:
            avg = axis_sums[axis.value] / axis_counts[axis.value]
            top_axes.append(WorldviewAxisStat(axis=axis.value, avg_weight=round(avg, 4)))
    top_axes.sort(key=lambda x: x.avg_weight, reverse=True)

    adoption_rate = contributors_with_profiles / total if total > 0 else 0.0
    # avg_resonance_match_rate: proxy — ratio of contributors with any resonances set
    resonance_contributors = sum(
        1 for n in all_contributors
        if (n.get("properties") or {}).get("concept_resonances")
    )
    avg_match_rate = resonance_contributors / total if total > 0 else 0.0

    return BeliefROI(
        contributors_with_profiles=contributors_with_profiles,
        contributors_total=total,
        profile_adoption_rate=round(adoption_rate, 4),
        top_worldview_axes=top_axes,
        avg_resonance_match_rate=round(avg_match_rate, 4),
        concept_resonances_total=total_concept_resonances,
        spec_ref="spec-169",
    )
