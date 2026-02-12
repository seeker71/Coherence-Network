"""Coherence score computation — spec 020, 029.

Computes what we can from GraphStore. Components without data use 0.5 (neutral).
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.models.project import Project


COMPONENT_NAMES = [
    "contributor_diversity",
    "dependency_health",
    "activity_cadence",
    "documentation_quality",
    "community_responsiveness",
    "funding_sustainability",
    "security_posture",
    "downstream_impact",
]


class GraphStoreWithDependents(Protocol):
    """GraphStore plus count_dependents for coherence computation."""

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        ...

    def count_dependents(self, ecosystem: str, name: str) -> int:
        ...

    # Optional spec 029 hooks (duck-typed in compute_coherence)
    # contributors_for_project(project_eco, project_name) -> list[Contributor]
    # recent_activity_count(project_eco, project_name, window_days=30) -> int


def _compute_contributor_diversity(store: object, project: Project) -> float | None:
    fn = getattr(store, "contributors_for_project", None)
    if not callable(fn):
        return None
    try:
        contributors = fn(project.ecosystem, project.name)
        if not contributors:
            return None
        # Diversity proxy: unique contributors scaled, saturating at 50
        unique = len({getattr(c, "login", None) or getattr(c, "id", "") for c in contributors})
        return min(1.0, unique / 50.0)
    except Exception:
        return None


def _compute_activity_cadence(store: object, project: Project) -> float | None:
    fn = getattr(store, "recent_activity_count", None)
    if not callable(fn):
        return None
    try:
        commits_30d = int(fn(project.ecosystem, project.name, 30))
        # Scale: 0 commits -> 0.0, 20+ commits/30d -> 1.0
        return max(0.0, min(1.0, commits_30d / 20.0))
    except Exception:
        return None


def compute_coherence(store: GraphStoreWithDependents, project: Project) -> dict:
    """Compute coherence score and components from available data."""
    components: dict[str, float] = {}

    components_with_data = 0

    # downstream_impact: count of projects that depend on this (real)
    dependents = store.count_dependents(project.ecosystem, project.name)
    components["downstream_impact"] = min(1.0, dependents / 100.0)
    components_with_data += 1

    # dependency_health: fewer deps = less transitive risk (real-derived)
    dep_count = project.dependency_count or 0
    components["dependency_health"] = max(0.0, 1.0 - dep_count / 50.0)
    components_with_data += 1

    # spec 029: contributor_diversity + activity_cadence when GitHub data present
    cd = _compute_contributor_diversity(store, project)
    if cd is not None:
        components["contributor_diversity"] = cd
        components_with_data += 1

    ac = _compute_activity_cadence(store, project)
    if ac is not None:
        components["activity_cadence"] = ac
        components_with_data += 1

    # No data for these; use neutral 0.5 per spec 018 (unknown, not fabricated)
    for c in COMPONENT_NAMES:
        if c not in components:
            components[c] = 0.5

    # Equal-weight average per spec 018
    score = sum(components[c] for c in COMPONENT_NAMES) / len(COMPONENT_NAMES)

    return {
        "score": round(score, 2),
        "components_with_data": components_with_data,
        "components": components,
    }
