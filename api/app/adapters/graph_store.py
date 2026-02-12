"""GraphStore abstraction + in-memory backend — spec 019."""

from __future__ import annotations

import json
import os
from typing import Optional, Protocol, List

from pydantic import BaseModel

from app.models.project import Project, ProjectSummary


class Contributor(BaseModel):
    id: str
    source: str
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    contributions_count: int
    last_contribution_date: Optional[str] = None


class Organization(BaseModel):
    id: str
    login: str
    type: str


def _key(ecosystem: str, name: str) -> tuple[str, str]:
    return (ecosystem.lower(), name.lower())


class GraphStore(Protocol):
    """Protocol for graph storage. Implementations: InMemoryGraphStore, future Neo4j."""

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        ...

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        ...

    def upsert_project(self, project: Project) -> None:
        ...

    def add_dependency(
        self, from_eco: str, from_name: str, to_eco: str, to_name: str
    ) -> None:
        ...

    def count_projects(self) -> int:
        ...

    def count_dependents(self, ecosystem: str, name: str) -> int:
        """Count projects that depend on this one (reverse edges). For coherence downstream_impact."""
        ...

    def get_contributor(self, id: str) -> Optional[Contributor]:
        ...

    def upsert_contributor(self, contributor: Contributor) -> None:
        ...

    def get_organization(self, id: str) -> Optional[Organization]:
        ...

    def upsert_organization(self, org: Organization) -> None:
        ...

    def add_contributes_to(self, contributor_id: str, ecosystem: str, name: str) -> None:
        ...

    def add_maintains(self, contributor_id: str, ecosystem: str, name: str) -> None:
        ...

    def add_member_of(self, contributor_id: str, org_id: str) -> None:
        ...

    def get_project_contributors(self, ecosystem: str, name: str) -> list[Contributor]:
        ...

    def get_contributor_organization(self, contributor_id: str) -> Optional[Organization]:
        ...


class InMemoryGraphStore:
    """In-memory GraphStore. Optional JSON persistence for restart."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._projects: dict[tuple[str, str], Project] = {}
        self._edges: list[tuple[tuple[str, str], tuple[str, str]]] = []
        self._contributors: dict[str, Contributor] = {}
        self._organizations: dict[str, Organization] = {}
        self._contributes_to: list[tuple[str, tuple[str, str]]] = []
        self._maintains: list[tuple[str, tuple[str, str]]] = []
        self._member_of: list[tuple[str, str]] = []
        self._persist_path = persist_path
        if persist_path and os.path.isfile(persist_path):
            self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
            for p in data.get("projects", []):
                proj = Project(**p)
                self._projects[_key(proj.ecosystem, proj.name)] = proj
            for e in data.get("edges", []):
                if len(e) >= 2 and len(e[0]) >= 2 and len(e[1]) >= 2:
                    self._edges.append(
                        ((e[0][0], e[0][1]), (e[1][0], e[1][1]))
                    )
            for c in data.get("contributors", []):
                contrib = Contributor(**c)
                self._contributors[contrib.id] = contrib
            for o in data.get("organizations", []):
                org = Organization(**o)
                self._organizations[org.id] = org
            for e in data.get("contributes_to", []):
                if len(e) == 2 and isinstance(e[0], str) and len(e[1]) == 2:
                    self._contributes_to.append((e[0], _key(e[1][0], e[1][1])))
            for e in data.get("maintains", []):
                if len(e) == 2 and isinstance(e[0], str) and len(e[1]) == 2:
                    self._maintains.append((e[0], _key(e[1][0], e[1][1])))
            for e in data.get("member_of", []):
                if len(e) == 2 and isinstance(e[0], str) and isinstance(e[1], str):
                    self._member_of.append((e[0], e[1]))
            self._recompute_dependency_counts()
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
            "projects": [p.model_dump() for p in self._projects.values()],
            "edges": [[list(from_k), list(to_k)] for from_k, to_k in self._edges],
            "contributors": [c.model_dump() for c in self._contributors.values()],
            "organizations": [o.model_dump() for o in self._organizations.values()],
            "contributes_to": [[c_id, list(p_k)] for c_id, p_k in self._contributes_to],
            "maintains": [[c_id, list(p_k)] for c_id, p_k in self._maintains],
            "member_of": [[c, o] for c, o in self._member_of],
        }
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0)

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        return self._projects.get(_key(ecosystem, name))

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        q = query.lower().strip()
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
        k = _key(project.ecosystem, project.name)
        self._projects[k] = project
        self._recompute_dependency_counts()

    def add_dependency(
        self, from_eco: str, from_name: str, to_eco: str, to_name: str
    ) -> None:
        from_k = _key(from_eco, from_name)
        to_k = _key(to_eco, to_name)
        edge = (from_k, to_k)
        if edge not in self._edges:
            self._edges.append(edge)
            self._recompute_dependency_counts()

    def count_projects(self) -> int:
        return len(self._projects)

    def count_dependents(self, ecosystem: str, name: str) -> int:
        """Count projects that depend on this one (reverse edges)."""
        k = _key(ecosystem, name)
        return sum(1 for _from, _to in self._edges if _to == k)

    def get_contributor(self, id: str) -> Optional[Contributor]:
        return self._contributors.get(id)

    def upsert_contributor(self, contributor: Contributor) -> None:
        self._contributors[contributor.id] = contributor

    def get_organization(self, id: str) -> Optional[Organization]:
        return self._organizations.get(id)

    def upsert_organization(self, org: Organization) -> None:
        self._organizations[org.id] = org

    def add_contributes_to(self, contributor_id: str, ecosystem: str, name: str) -> None:
        p_k = _key(ecosystem, name)
        edge = (contributor_id, p_k)
        if edge not in self._contributes_to:
            self._contributes_to.append(edge)

    def add_maintains(self, contributor_id: str, ecosystem: str, name: str) -> None:
        p_k = _key(ecosystem, name)
        edge = (contributor_id, p_k)
        if edge not in self._maintains:
            self._maintains.append(edge)

    def add_member_of(self, contributor_id: str, org_id: str) -> None:
        edge = (contributor_id, org_id)
        if edge not in self._member_of:
            self._member_of.append(edge)

    def get_project_contributors(self, ecosystem: str, name: str) -> list[Contributor]:
        p_k = _key(ecosystem, name)
        out = []
        for c_id, proj_k in self._contributes_to:
            if proj_k == p_k:
                contrib = self._contributors.get(c_id)
                if contrib:
                    out.append(contrib)
        return out

    def get_contributor_organization(self, contributor_id: str) -> Optional[Organization]:
        for c_id, o_id in self._member_of:
            if c_id == contributor_id:
                return self._organizations.get(o_id)
        return None
