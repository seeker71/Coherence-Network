"""Belief System service (spec-169).

In-memory store for belief profiles and recommendation events.
Provides CRUD, resonance scoring, and ROI calculation.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from app.models.belief_profile import (
    BeliefAxis,
    BeliefProfile,
    BeliefProfilePatch,
    BeliefROI,
    ConceptResonance,
    ResonanceResult,
)

# --- In-memory stores (replaced by DB in production) ---
_profiles: dict[str, BeliefProfile] = {}

# RecommendationEvent: dict with keys:
#   contributor_id, idea_id, resonance_score, shown_at, engaged_at, engagement_type
_rec_events: list[dict] = []

# Axis -> keywords for inferring worldview from idea tags
_AXIS_KEYWORDS: dict[str, list[str]] = {
    BeliefAxis.scientific: ["empirical", "data", "experiment", "evidence", "research", "analysis", "study"],
    BeliefAxis.spiritual: ["spiritual", "sacred", "meaning", "soul", "transcendent", "consciousness", "mindfulness"],
    BeliefAxis.pragmatic: ["practical", "utility", "tooling", "workflow", "efficiency", "productivity", "solution"],
    BeliefAxis.holistic: ["systems", "network", "emergence", "interconnected", "holistic", "ecology", "complexity"],
    BeliefAxis.synthetic: ["integration", "bridge", "synthesis", "interdisciplinary", "cross-domain", "unified"],
    BeliefAxis.critical: ["power", "critique", "deconstruct", "justice", "bias", "equity", "structural"],
    BeliefAxis.imaginative: ["speculative", "futures", "innovation", "creative", "imagination", "vision", "design"],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_belief_profile(contributor_id: str) -> BeliefProfile:
    """Return the belief profile for a contributor, creating defaults if not yet set."""
    if contributor_id in _profiles:
        return _profiles[contributor_id]
    # Return empty default (not stored until first PATCH)
    return BeliefProfile(
        contributor_id=contributor_id,
        worldview_axes={},
        concept_resonances=[],
        tag_affinities={},
        primary_worldview=None,
        created_at=_now(),
        updated_at=_now(),
    )


def patch_belief_profile(contributor_id: str, patch: BeliefProfilePatch) -> BeliefProfile:
    """Apply a partial update to a contributor's belief profile."""
    existing = _profiles.get(contributor_id) or BeliefProfile(
        contributor_id=contributor_id,
        created_at=_now(),
        updated_at=_now(),
    )

    # Merge worldview_axes (don't replace, merge)
    if patch.worldview_axes is not None:
        merged_axes = dict(existing.worldview_axes)
        merged_axes.update(patch.worldview_axes)
        existing = existing.model_copy(update={"worldview_axes": merged_axes})

    if patch.concept_resonances is not None:
        existing = existing.model_copy(update={"concept_resonances": patch.concept_resonances})

    if patch.tag_affinities is not None:
        merged_tags = dict(existing.tag_affinities)
        merged_tags.update(patch.tag_affinities)
        existing = existing.model_copy(update={"tag_affinities": merged_tags})

    if patch.primary_worldview is not None:
        existing = existing.model_copy(update={"primary_worldview": patch.primary_worldview})

    updated = existing.model_copy(update={"updated_at": _now()})
    _profiles[contributor_id] = updated
    return updated


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two axis score dicts."""
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    mag_a = math.sqrt(sum(v ** 2 for v in a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return min(1.0, dot / (mag_a * mag_b))


def _infer_idea_worldview(tags: list[str], category: Optional[str] = None) -> dict[str, float]:
    """Map idea tags/category to BeliefAxis scores via keyword matching."""
    all_words = [t.lower().replace("-", " ") for t in tags]
    if category:
        all_words.append(category.lower())

    scores: dict[str, float] = {}
    for axis, keywords in _AXIS_KEYWORDS.items():
        hits = sum(1 for word in all_words for kw in keywords if kw in word or word in kw)
        if hits > 0:
            scores[axis] = min(1.0, hits * 0.3)
    return scores


def compute_resonance(
    contributor_id: str,
    idea_id: str,
    idea_tags: list[str],
    idea_concept_ids: list[str],
    idea_category: Optional[str] = None,
) -> ResonanceResult:
    """Compute belief-to-idea resonance score."""
    profile = get_belief_profile(contributor_id)

    # 1. Concept overlap (Jaccard)
    contributor_concepts = {r.concept_id for r in profile.concept_resonances if r.score >= 0.5}
    idea_concepts = set(idea_concept_ids)
    union = contributor_concepts | idea_concepts
    concept_overlap = len(contributor_concepts & idea_concepts) / len(union) if union else 0.0

    # 2. Worldview alignment (cosine similarity)
    idea_axes = _infer_idea_worldview(idea_tags, idea_category)
    worldview_alignment = _cosine_similarity(profile.worldview_axes, idea_axes)

    # 3. Tag match
    contributor_tags = {t for t, s in profile.tag_affinities.items() if s >= 0.4}
    idea_tag_set = set(idea_tags)
    tag_match = len(contributor_tags & idea_tag_set) / max(len(idea_tag_set), 1)

    overall = round(0.4 * concept_overlap + 0.4 * worldview_alignment + 0.2 * tag_match, 3)
    concept_overlap = round(concept_overlap, 3)
    worldview_alignment = round(worldview_alignment, 3)
    tag_match = round(tag_match, 3)

    # Build explanation
    explanation: list[str] = []
    if concept_overlap >= 0.5:
        explanation.append(f"Strong concept overlap ({concept_overlap:.0%}) — shared concepts with idea")
    elif concept_overlap > 0:
        explanation.append(f"Partial concept overlap ({concept_overlap:.0%})")
    if worldview_alignment >= 0.6:
        dominant = max(profile.worldview_axes.items(), key=lambda x: x[1], default=(None, 0))
        if dominant[0]:
            explanation.append(f"Strong worldview alignment on '{dominant[0]}' axis")
    if tag_match >= 0.5:
        matched = contributor_tags & idea_tag_set
        explanation.append(f"Tag match: {', '.join(sorted(matched)[:3])}")
    if not explanation:
        explanation.append("Low alignment — consider updating your belief profile")

    # Recommended action
    if overall >= 0.7:
        action = "Contribute"
    elif overall >= 0.4:
        action = "Follow"
    else:
        action = "Skip"

    return ResonanceResult(
        contributor_id=contributor_id,
        idea_id=idea_id,
        overall_score=overall,
        concept_overlap=concept_overlap,
        worldview_alignment=worldview_alignment,
        tag_match=tag_match,
        explanation=explanation,
        recommended_action=action,
    )


def _belief_completeness(profile: BeliefProfile) -> float:
    """Score 0.0–1.0 based on how much of the profile is filled in."""
    axes_score = min(1.0, len(profile.worldview_axes) / 7.0)
    concepts_score = min(1.0, len(profile.concept_resonances) / 5.0)
    tags_score = min(1.0, len(profile.tag_affinities) / 5.0)
    primary_score = 1.0 if profile.primary_worldview else 0.0
    return round((axes_score * 0.4 + concepts_score * 0.3 + tags_score * 0.2 + primary_score * 0.1), 3)


def get_belief_roi(contributor_id: str, days: int = 30) -> BeliefROI:
    """Compute engagement lift attributable to belief-driven recommendations."""
    now = _now()
    cutoff = now.timestamp() - (days * 86400)

    events = [
        e for e in _rec_events
        if e["contributor_id"] == contributor_id
        and e["shown_at"].timestamp() >= cutoff
    ]

    shown = len(events)
    engaged = sum(1 for e in events if e.get("engaged_at") is not None)
    rate = round(engaged / shown, 4) if shown > 0 else 0.0

    profile = get_belief_profile(contributor_id)
    completeness = _belief_completeness(profile)

    # Compute baseline: all events NOT for this contributor
    baseline_events = [
        e for e in _rec_events
        if e["contributor_id"] != contributor_id
        and e["shown_at"].timestamp() >= cutoff
    ]
    baseline_shown = len(baseline_events)
    baseline_engaged = sum(1 for e in baseline_events if e.get("engaged_at") is not None)
    baseline_rate: Optional[float] = None
    lift: Optional[float] = None
    note: Optional[str] = None

    if shown < 10:
        note = "Insufficient data — need at least 10 recommendations to compute lift"
    elif baseline_shown >= 10:
        baseline_rate = round(baseline_engaged / baseline_shown, 4)
        lift = round(rate - baseline_rate, 4)

    return BeliefROI(
        contributor_id=contributor_id,
        period_days=days,
        recommendations_shown=shown,
        recommendations_engaged=engaged,
        engagement_rate=rate,
        belief_completeness=completeness,
        baseline_engagement_rate=baseline_rate,
        lift=lift,
        note=note,
    )


def record_recommendation_shown(contributor_id: str, idea_id: str, resonance_score: float) -> str:
    """Record that a recommendation was shown (for ROI tracking). Returns event id."""
    import uuid
    event_id = f"rec_{uuid.uuid4().hex[:12]}"
    _rec_events.append({
        "id": event_id,
        "contributor_id": contributor_id,
        "idea_id": idea_id,
        "resonance_score": resonance_score,
        "shown_at": _now(),
        "engaged_at": None,
        "engagement_type": None,
    })
    return event_id


def record_engagement(event_id: str, engagement_type: str) -> bool:
    """Mark a recommendation event as engaged."""
    for event in _rec_events:
        if event["id"] == event_id:
            event["engaged_at"] = _now()
            event["engagement_type"] = engagement_type
            return True
    return False


def clear_all() -> None:
    """Clear all in-memory state (used in tests)."""
    _profiles.clear()
    _rec_events.clear()
