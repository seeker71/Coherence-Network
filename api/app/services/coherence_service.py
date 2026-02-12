"""Coherence score computation — spec 020.

Computes what we can from GraphStore. Components without data use 0.5 (neutral).
"""

from typing import Optional, Protocol

from datetime import datetime

from app.adapters.graph_store import Contributor, Organization
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

    def get_project_contributors(self, ecosystem: str, name: str) -> list[Contributor]:
        ...

    def get_contributor_organization(self, contributor_id: str) -> Optional[Organization]:
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

    # contributor_diversity and activity_cadence
    contributors = store.get_project_contributors(project.ecosystem, project.name)
    has_github_data = len(contributors) > 0
    if has_github_data:
        # contributor_diversity using 1 - HHI
        org_to_contribs: dict[str, int] = {}
        for contrib in contributors:
            org = store.get_contributor_organization(contrib.id)
            org_key = org.id if org else f"{contrib.id}_individual"
            org_to_contribs[org_key] = org_to_contribs.get(org_key, 0) + (contrib.contributions_count or 1)
        total_contribs = sum(org_to_contribs.values())
        if total_contribs > 0:
            hhi = sum((count / total_contribs) ** 2 for count in org_to_contribs.values())
            components["contributor_diversity"] = 1 - hhi
        else:
            components["contributor_diversity"] = 0.5

        # activity_cadence: fraction of contributors active in last 90 days
        active = 0
        now = datetime.utcnow()
        for contrib in contributors:
            if contrib.last_contribution_date:
                try:
                    last = datetime.fromisoformat(contrib.last_contribution_date)
                    if (now - last).days <= 90:
                        active += 1
                except ValueError:
                    pass
        components["activity_cadence"] = active / len(contributors) if contributors else 0.0
    else:
        components["contributor_diversity"] = 0.5
        components["activity_cadence"] = 0.5

    # No data for these; use neutral 0.5 per spec 018 (unknown, not fabricated)
    for c in COMPONENT_NAMES:
        if c not in components:
            components[c] = 0.5

    # Equal-weight average per spec 018
    score = sum(components[c] for c in COMPONENT_NAMES) / len(COMPONENT_NAMES)

    # Data confidence: downstream_impact and dependency_health are always real, plus 2 if github data
    components_with_data = 2 + (2 if has_github_data else 0)

    return {
        "score": round(score, 2),
        "components_with_data": components_with_data,
        "components": components,
    }
