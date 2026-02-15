"""GraphStore abstraction + in-memory backend — extended for Coherence Contribution Network.

This version preserves the existing project/dependency API and adds:
- Contributors
- Assets
- Contributions

All money uses Decimal. Store is in-memory with optional JSON persistence.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Optional, Protocol
from uuid import UUID

from app.models.asset import Asset
from app.models.contribution import Contribution
from app.models.contributor import Contributor
from app.models.github_contributor import GitHubContributor
from app.models.github_organization import GitHubOrganization
from app.models.project import Project, ProjectSummary


def _key(ecosystem: str, name: str) -> tuple[str, str]:
    return (ecosystem.lower(), name.lower())


class GraphStore(Protocol):
    """Protocol for graph storage. Implementations: InMemoryGraphStore, future Neo4j."""

    # ---- existing project API ----
    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        ...

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        ...

    def upsert_project(self, project: Project) -> None:
        ...

    def add_dependency(self, from_eco: str, from_name: str, to_eco: str, to_name: str) -> None:
        ...

    def count_projects(self) -> int:
        ...

    def count_dependents(self, ecosystem: str, name: str) -> int:
        """Count projects that depend on this one (reverse edges)."""
        ...

    # ---- contribution network API ----
    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        """Get contributor by ID."""
        ...

    def create_contributor(self, contributor: Contributor) -> Contributor:
        """Create new contributor."""
        ...

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        """List all contributors."""
        ...

    def get_asset(self, asset_id: UUID) -> Asset | None:
        """Get asset by ID."""
        ...

    def create_asset(self, asset: Asset) -> Asset:
        """Create new asset."""
        ...

    def list_assets(self, limit: int = 100) -> list[Asset]:
        """List all assets."""
        ...

    def create_contribution(
        self,
        contributor_id: UUID,
        asset_id: UUID,
        cost_amount: Decimal,
        coherence_score: float,
        metadata: dict,
    ) -> Contribution:
        """Record a contribution."""
        ...

    def get_contribution(self, contribution_id: UUID) -> Contribution | None:
        """Get contribution by ID."""
        ...

    def get_asset_contributions(self, asset_id: UUID) -> list[Contribution]:
        """Get all contributions to an asset."""
        ...

    def get_contributor_contributions(self, contributor_id: UUID) -> list[Contribution]:
        """Get all contributions by a contributor."""
        ...

    # ---- GitHub integration API (spec 029) ----
    def upsert_github_contributor(self, github_contributor: GitHubContributor) -> GitHubContributor:
        """Upsert GitHub contributor node."""
        ...

    def get_github_contributor(self, contributor_id: str) -> GitHubContributor | None:
        """Get GitHub contributor by ID (github:login)."""
        ...

    def list_github_contributors(self, limit: int = 100) -> list[GitHubContributor]:
        """List all GitHub contributors."""
        ...

    def upsert_github_organization(self, organization: GitHubOrganization) -> GitHubOrganization:
        """Upsert GitHub organization node."""
        ...

    def get_github_organization(self, organization_id: str) -> GitHubOrganization | None:
        """Get GitHub organization by ID (github:login)."""
        ...

    def add_github_contributes_to(self, contributor_id: str, ecosystem: str, project_name: str) -> None:
        """Add CONTRIBUTES_TO edge from GitHub contributor to project."""
        ...

    def get_project_github_contributors(self, ecosystem: str, project_name: str) -> list[GitHubContributor]:
        """Get all GitHub contributors for a project."""
        ...


class InMemoryGraphStore:
    """In-memory GraphStore. Optional JSON persistence for restart."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        # existing graph data
        self._projects: dict[tuple[str, str], Project] = {}
        self._edges: list[tuple[tuple[str, str], tuple[str, str]]] = []

        # contribution network data
        self._contributors: dict[UUID, Contributor] = {}
        self._assets: dict[UUID, Asset] = {}
        self._contributions: dict[UUID, Contribution] = {}

        # GitHub integration data (spec 029)
        self._github_contributors: dict[str, GitHubContributor] = {}  # key: github:login
        self._github_organizations: dict[str, GitHubOrganization] = {}  # key: github:login
        self._github_contributes_to: list[tuple[str, tuple[str, str]]] = []  # (contributor_id, project_key)

        self._persist_path = persist_path
        if persist_path and os.path.isfile(persist_path):
            self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)

            # projects
            for p in data.get("projects", []):
                proj = Project(**p)
                self._projects[_key(proj.ecosystem, proj.name)] = proj
            for e in data.get("edges", []):
                if len(e) >= 2 and len(e[0]) >= 2 and len(e[1]) >= 2:
                    self._edges.append(((e[0][0], e[0][1]), (e[1][0], e[1][1])))
            self._recompute_dependency_counts()

            # contribution network
            for c in data.get("contributors", []):
                contrib = Contributor(**c)
                self._contributors[contrib.id] = contrib
            for a in data.get("assets", []):
                asset = Asset(**a)
                self._assets[asset.id] = asset
            for cn in data.get("contributions", []):
                contribn = Contribution(**cn)
                self._contributions[contribn.id] = contribn

            # GitHub integration (spec 029)
            for gc in data.get("github_contributors", []):
                ghc = GitHubContributor(**gc)
                self._github_contributors[ghc.id] = ghc
            for go in data.get("github_organizations", []):
                gho = GitHubOrganization(**go)
                self._github_organizations[gho.id] = gho
            for edge in data.get("github_contributes_to", []):
                if len(edge) >= 2 and isinstance(edge[1], list) and len(edge[1]) >= 2:
                    self._github_contributes_to.append((edge[0], (edge[1][0], edge[1][1])))

        except (json.JSONDecodeError, IOError, KeyError, ValueError):
            pass

    def _recompute_dependency_counts(self) -> None:
        counts: dict[tuple[str, str], int] = {k: 0 for k in self._projects}
        for from_k, _to_k in self._edges:
            if from_k in counts:
                counts[from_k] += 1
        for k, proj in self._projects.items():
            proj.dependency_count = counts.get(k, 0)

    def save(self) -> None:
        """Persist to JSON if path set."""
        if not self._persist_path:
            return
        os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
        data = {
            "projects": [p.model_dump(mode="json") for p in self._projects.values()],
            "edges": [[list(from_k), list(to_k)] for from_k, to_k in self._edges],
            "contributors": [c.model_dump(mode="json") for c in self._contributors.values()],
            "assets": [a.model_dump(mode="json") for a in self._assets.values()],
            "contributions": [c.model_dump(mode="json") for c in self._contributions.values()],
            "github_contributors": [gc.model_dump(mode="json") for gc in self._github_contributors.values()],
            "github_organizations": [go.model_dump(mode="json") for go in self._github_organizations.values()],
            "github_contributes_to": [[contrib_id, list(proj_k)] for contrib_id, proj_k in self._github_contributes_to],
        }
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0)

    # ----------------------------
    # Existing project API
    # ----------------------------
    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        return self._projects.get(_key(ecosystem, name))

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        q = (query or "").strip().lower()
        if not q:
            return []
        out: list[ProjectSummary] = []
        for proj in self._projects.values():
            if q in proj.name.lower() or q in (proj.description or "").lower():
                out.append(
                    ProjectSummary(
                        name=proj.name,
                        ecosystem=proj.ecosystem,
                        description=proj.description or "",
                    )
                )
                if len(out) >= limit:
                    break
        return out

    def upsert_project(self, project: Project) -> None:
        self._projects[_key(project.ecosystem, project.name)] = project
        self._recompute_dependency_counts()

    def add_dependency(self, from_eco: str, from_name: str, to_eco: str, to_name: str) -> None:
        from_k = _key(from_eco, from_name)
        to_k = _key(to_eco, to_name)
        edge = (from_k, to_k)
        if edge not in self._edges:
            self._edges.append(edge)
            self._recompute_dependency_counts()

    def count_projects(self) -> int:
        return len(self._projects)

    def count_dependents(self, ecosystem: str, name: str) -> int:
        target = _key(ecosystem, name)
        return sum(1 for _from_k, to_k in self._edges if to_k == target)

    # ----------------------------
    # Contribution network API
    # ----------------------------
    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        return self._contributors.get(contributor_id)

    def create_contributor(self, contributor: Contributor) -> Contributor:
        self._contributors[contributor.id] = contributor
        return contributor

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        items = sorted(self._contributors.values(), key=lambda c: c.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def get_asset(self, asset_id: UUID) -> Asset | None:
        return self._assets.get(asset_id)

    def create_asset(self, asset: Asset) -> Asset:
        self._assets[asset.id] = asset
        return asset

    def list_assets(self, limit: int = 100) -> list[Asset]:
        items = sorted(self._assets.values(), key=lambda a: a.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def create_contribution(
        self,
        contributor_id: UUID,
        asset_id: UUID,
        cost_amount: Decimal,
        coherence_score: float,
        metadata: dict,
    ) -> Contribution:
        contrib = Contribution(
            contributor_id=contributor_id,
            asset_id=asset_id,
            cost_amount=cost_amount,
            coherence_score=coherence_score,
            metadata=metadata or {},
        )
        self._contributions[contrib.id] = contrib

        asset = self._assets.get(asset_id)
        if asset:
            asset.total_cost = (asset.total_cost or Decimal("0.00")) + cost_amount

        return contrib

    def get_contribution(self, contribution_id: UUID) -> Contribution | None:
        return self._contributions.get(contribution_id)

    def get_asset_contributions(self, asset_id: UUID) -> list[Contribution]:
        out = [c for c in self._contributions.values() if c.asset_id == asset_id]
        out.sort(key=lambda c: c.timestamp)
        return out

    def get_contributor_contributions(self, contributor_id: UUID) -> list[Contribution]:
        out = [c for c in self._contributions.values() if c.contributor_id == contributor_id]
        out.sort(key=lambda c: c.timestamp)
        return out

    # ----------------------------
    # GitHub integration API (spec 029)
    # ----------------------------
    def upsert_github_contributor(self, github_contributor: GitHubContributor) -> GitHubContributor:
        """Upsert GitHub contributor. ID format: github:login."""
        self._github_contributors[github_contributor.id] = github_contributor
        return github_contributor

    def get_github_contributor(self, contributor_id: str) -> GitHubContributor | None:
        """Get GitHub contributor by ID (github:login)."""
        return self._github_contributors.get(contributor_id)

    def list_github_contributors(self, limit: int = 100) -> list[GitHubContributor]:
        """List all GitHub contributors."""
        items = sorted(self._github_contributors.values(), key=lambda c: c.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def upsert_github_organization(self, organization: GitHubOrganization) -> GitHubOrganization:
        """Upsert GitHub organization. ID format: github:login."""
        self._github_organizations[organization.id] = organization
        return organization

    def get_github_organization(self, organization_id: str) -> GitHubOrganization | None:
        """Get GitHub organization by ID (github:login)."""
        return self._github_organizations.get(organization_id)

    def add_github_contributes_to(self, contributor_id: str, ecosystem: str, project_name: str) -> None:
        """Add CONTRIBUTES_TO edge from GitHub contributor to project."""
        proj_key = _key(ecosystem, project_name)
        edge = (contributor_id, proj_key)
        if edge not in self._github_contributes_to:
            self._github_contributes_to.append(edge)

    def get_project_github_contributors(self, ecosystem: str, project_name: str) -> list[GitHubContributor]:
        """Get all GitHub contributors for a project."""
        proj_key = _key(ecosystem, project_name)
        contributor_ids = [cid for cid, pk in self._github_contributes_to if pk == proj_key]
        return [self._github_contributors[cid] for cid in contributor_ids if cid in self._github_contributors]
