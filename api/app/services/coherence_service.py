"""Coherence score computation — spec 020.

Computes what we can from graph data. Components without data use 0.5 (neutral).
"""

from typing import Optional

from datetime import datetime, timezone

from app.models.project import Project
from app.services import graph_service


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


def _get_project_contributors(ecosystem: str, name: str) -> list[dict]:
    """Get contributor nodes linked to a project via graph edges."""
    project_id = f"project:{ecosystem}:{name}"
    edges = graph_service.get_edges(project_id, direction="incoming", edge_type="contributes_to")
    contributors = []
    for edge in edges:
        node = graph_service.get_node(edge["from_id"])
        if node and node.get("type") == "contributor":
            contributors.append(node)
    return contributors


def _count_dependents(ecosystem: str, name: str) -> int:
    """Count projects that depend on this one via graph edges."""
    project_id = f"project:{ecosystem}:{name}"
    edges = graph_service.get_edges(project_id, direction="incoming", edge_type="depends_on")
    return len(edges)


def compute_coherence(project: Project) -> dict:
    """Compute coherence score and components from available data."""
    components: dict[str, float] = {}

    # downstream_impact: count of projects that depend on this (real)
    dependents = _count_dependents(project.ecosystem, project.name)
    components["downstream_impact"] = min(1.0, dependents / 100.0)

    # dependency_health: fewer deps = less transitive risk (real-derived)
    dep_count = project.dependency_count or 0
    components["dependency_health"] = max(0.0, 1.0 - dep_count / 50.0)

    # contributor_diversity and activity_cadence
    contributors = _get_project_contributors(project.ecosystem, project.name)
    has_github_data = len(contributors) > 0
    if has_github_data:
        # contributor_diversity using 1 - HHI
        org_to_contribs: dict[str, int] = {}
        for contrib in contributors:
            org_key = contrib.get("organization", f"{contrib['id']}_individual")
            count = contrib.get("contributions_count", 1) or 1
            org_to_contribs[org_key] = org_to_contribs.get(org_key, 0) + count
        total_contribs = sum(org_to_contribs.values())
        if total_contribs > 0:
            hhi = sum((count / total_contribs) ** 2 for count in org_to_contribs.values())
            components["contributor_diversity"] = 1 - hhi
        else:
            components["contributor_diversity"] = 0.5

        # activity_cadence: fraction of contributors active in last 90 days
        active = 0
        now = datetime.now(timezone.utc)
        for contrib in contributors:
            last_date = contrib.get("last_contribution_date")
            if last_date:
                try:
                    last = datetime.fromisoformat(last_date)
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
