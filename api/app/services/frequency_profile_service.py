"""Frequency profile service — vector representation of asset/reader resonance.

Every asset and every reader has a frequency profile: a vector across all
concept dimensions. Resonance between a reader and an asset is the cosine
similarity of their two profiles.

An asset's profile comes from:
  - Its concept tags (primary dimensions)
  - Its connected concepts via graph edges (secondary dimensions)
  - Its content's living frequency score (the "_living" dimension)

A reader's profile comes from:
  - Their explicit concept weights (manual resonance settings)
  - Their reading history (auto-computed from which concepts they read most)
  - Their contribution history (which concepts they create for)

CC flow between reader and creator is proportional to their resonance
(cosine similarity of profiles). This replaces percentage-based concept
weights with continuous, high-dimensional resonance matching.
"""

from __future__ import annotations

import math
from typing import Any

# Cache profiles in memory (invalidated on concept/edge changes)
_profile_cache: dict[str, dict[str, float]] = {}


def get_asset_profile(asset_id: str) -> dict[str, float]:
    """Compute the frequency profile vector for an asset.

    Returns {dimension: strength} where dimensions are concept IDs
    plus special dimensions like "_living" for content frequency.
    """
    if asset_id in _profile_cache:
        return _profile_cache[asset_id]

    profile: dict[str, float] = {}

    # Extract concept ID
    concept_id = _asset_to_concept(asset_id)
    if not concept_id:
        return profile

    # Primary: the asset's own concept
    profile[concept_id] = 1.0

    try:
        from app.services import concept_service

        # Secondary: connected concepts from graph edges
        edges = concept_service.get_concept_edges(concept_id)
        for edge in edges:
            connected = edge.get("to") if edge.get("from") == concept_id else edge.get("from", "")
            if connected and connected.startswith("lc-"):
                strength = float(edge.get("strength", 0.5))
                profile[connected] = max(profile.get(connected, 0), strength * 0.6)

        # Tertiary: sacred frequency family (concepts sharing the same Hz)
        concept = concept_service.get_concept(concept_id)
        if concept:
            hz = concept.get("sacred_frequency", {}).get("hz")
            if hz:
                profile[f"_hz_{hz}"] = 0.4  # frequency family dimension

            # Living frequency from content analysis
            story = concept.get("story_content", "")
            if story:
                try:
                    from app.services import frequency_scoring
                    result = frequency_scoring.score_frequency(story)
                    profile["_living"] = result.get("score", 0.5)
                except Exception:
                    pass
    except Exception:
        pass

    _profile_cache[asset_id] = profile
    return profile


def get_reader_profile(reader_id: str) -> dict[str, float]:
    """Compute the frequency profile vector for a reader.

    Blends explicit concept weights with auto-computed reading patterns.
    """
    profile: dict[str, float] = {}

    try:
        # Auto-compute from reading history
        from app.services import read_tracking_service
        from datetime import date, timedelta
        import json

        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        # Get all reads in the last 30 days
        # This is approximate — we aggregate across all assets
        from app.services.read_tracking_service import AssetReadDaily, _session, _ensure_ready
        _ensure_ready()

        with _session() as s:
            rows = (
                s.query(AssetReadDaily)
                .filter(AssetReadDaily.day >= thirty_days_ago)
                .all()
            )
            for row in rows:
                concepts = json.loads(row.concepts or "{}")
                for concept_id, count in concepts.items():
                    profile[concept_id] = profile.get(concept_id, 0) + count

        # Normalize to unit vector
        if profile:
            total = sum(profile.values())
            profile = {k: v / total for k, v in profile.items()}

    except Exception:
        pass

    return profile


def resonance(profile_a: dict[str, float], profile_b: dict[str, float]) -> float:
    """Cosine similarity between two frequency profiles.

    Returns 0.0 (no resonance) to 1.0 (perfect alignment).
    This is the core function that determines CC flow weighting.
    """
    if not profile_a or not profile_b:
        return 0.0

    # Dot product over shared dimensions
    shared = set(profile_a) & set(profile_b)
    if not shared:
        return 0.0

    dot = sum(profile_a[k] * profile_b[k] for k in shared)
    norm_a = math.sqrt(sum(v * v for v in profile_a.values()))
    norm_b = math.sqrt(sum(v * v for v in profile_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def magnitude(profile: dict[str, float]) -> float:
    """L2 norm — how strongly the profile resonates overall."""
    if not profile:
        return 0.0
    return math.sqrt(sum(v * v for v in profile.values()))


def top_dimensions(profile: dict[str, float], n: int = 10) -> list[tuple[str, float]]:
    """Top N strongest dimensions in a profile."""
    return sorted(profile.items(), key=lambda x: -x[1])[:n]


def invalidate_cache(asset_id: str | None = None) -> None:
    """Clear cached profiles. Call after concept/edge changes."""
    if asset_id:
        _profile_cache.pop(asset_id, None)
    else:
        _profile_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset_to_concept(asset_id: str) -> str | None:
    """Extract concept ID from an asset ID."""
    concept_id = asset_id
    if concept_id.startswith("visual-"):
        concept_id = concept_id[7:]
    if "-story-" in concept_id:
        concept_id = concept_id[:concept_id.index("-story-")]
    elif concept_id and concept_id[-1:].isdigit() and "-" in concept_id:
        concept_id = concept_id[:concept_id.rindex("-")]
    return concept_id if concept_id.startswith("lc-") else None
