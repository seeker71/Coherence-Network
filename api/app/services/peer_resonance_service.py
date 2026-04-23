"""Peer resonance scoring shared by discovery and peer routes."""

from __future__ import annotations

from app.models.belief import BeliefProfile

WORLDVIEW_AXES = ("scientific", "spiritual", "pragmatic", "holistic", "relational", "systemic")


def compute_peer_resonance(profile_a: BeliefProfile, profile_b: BeliefProfile) -> float:
    """Compute structural resonance score between two contributor profiles."""
    tags_a = set(profile_a.interest_tags)
    tags_b = set(profile_b.interest_tags)
    tag_score = 0.5
    if tags_a or tags_b:
        union = tags_a | tags_b
        intersection = tags_a & tags_b
        tag_score = len(intersection) / len(union) if union else 0.5

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for axis in WORLDVIEW_AXES:
        value_a = profile_a.worldview_axes.get(axis, 0.0)
        value_b = profile_b.worldview_axes.get(axis, 0.0)
        dot += value_a * value_b
        norm_a += value_a * value_a
        norm_b += value_b * value_b

    denom = (norm_a**0.5) * (norm_b**0.5)
    worldview_score = dot / denom if denom > 0 else 0.5

    concepts_a = {resonance.concept_id: resonance.weight for resonance in profile_a.concept_resonances}
    concepts_b = {resonance.concept_id: resonance.weight for resonance in profile_b.concept_resonances}
    concept_score = 0.5
    if concepts_a and concepts_b:
        shared = set(concepts_a) & set(concepts_b)
        if shared:
            weighted_intersection = sum(min(concepts_a[concept], concepts_b[concept]) for concept in shared)
            weighted_union = sum(
                max(concepts_a.get(concept, 0.0), concepts_b.get(concept, 0.0))
                for concept in set(concepts_a) | set(concepts_b)
            )
            concept_score = weighted_intersection / weighted_union if weighted_union > 0 else 0.0
        else:
            concept_score = 0.0

    return round((tag_score * 0.2) + (worldview_score * 0.4) + (concept_score * 0.4), 4)
