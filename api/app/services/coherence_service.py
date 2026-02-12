"""Coherence score computation — spec 020.

Computes what we can from GraphStore. Components without data use 0.5 (neutral).
"""

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


def compute_coherence(store: GraphStoreWithDependents, project: Project) -> dict:
    """Compute coherence score and components from available data."""
    components: dict[str, float] = {}

    # downstream_impact: count of projects that depend on this (real)
    dependents = store.count_dependents(project.ecosystem, project.name)
    components["downstream_impact"] = min(1.0, dependents / 100.0)

    # dependency_health: fewer deps = less transitive risk (real-derived)
    dep_count = project.dependency_count or 0
    components["dependency_health"] = max(0.0, 1.0 - dep_count / 50.0)

    # No data for these; use neutral 0.5 per spec 018 (unknown, not fabricated)
    for c in COMPONENT_NAMES:
        if c not in components:
            components[c] = 0.5

    # Equal-weight average per spec 018
    score = sum(components[c] for c in COMPONENT_NAMES) / len(COMPONENT_NAMES)

    # Data confidence: only downstream_impact and dependency_health are real (spec 020)
    components_with_data = 2

    return {
        "score": round(score, 2),
        "components_with_data": components_with_data,
        "components": components,
    }
