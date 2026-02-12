"""GraphStore abstraction + in-memory backend — spec 019, 029.

Adds:
- Contributor and Organization nodes
- edges: CONTRIBUTES_TO, MAINTAINS, MEMBER_OF
- helper queries used by coherence_service (spec 029)
"""

from __future__ import annotations

import json
import os
from typing import Optional, Protocol

from pydantic import BaseModel

from app.models.project import Project, ProjectSummary


def _key(ecosystem: str, name: str) -> tuple[str, str]:
    return (ecosystem.lower(), name.lower())


class Contributor(BaseModel):
    """Contributor node — spec 029."""
    id: str  # github:login or npm:username
    source: str  # github | npm
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    contributions_count: int = 0


class Organization(BaseModel):
    """Organization node — spec 029."""
    id: str
    login: str
    type: str  # Organization, User


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

    # --- GitHub / identity graph (spec 029) ---

    def upsert_contributor(self, contributor: Contributor) -> None:
        ...

    def upsert_organization(self, organization: Organization) -> None:
        ...

    def add_contributes_to(self, contributor_id: str, project_eco: str, project_name: str) -> None:
        ...

    def add_maintains(self, contributor_id: str, project_eco: str, project_name: str) -> None:
        ...

    def add_member_of(self, contributor_id: str, org_id: str) -> None:
        ...

    def contributors_for_project(self, project_eco: str, project_name: str) -> list[Contributor]:
        ...

    def recent_activity_count(self, project_eco: str, project_name: str, window_days: int = 30) -> int:
        ...

    def set_project_github_repo(self, project_eco: str, project_name: str, owner: str, repo: str) -> None:
        ...

    def get_project_github_repo(self, project_eco: str, project_name: str) -> tuple[str, str] | None:
        ...

    def set_project_recent_commits(self, project_eco: str, project_name: str, window_days: int, count: int) -> None:
        ...

    def iter_projects(self) -> list[Project]:
        ...


class InMemoryGraphStore:
    """In-memory GraphStore. Optional JSON persistence for restart."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._projects: dict[tuple[str, str], Project] = {}
        self._edges: list[tuple[tuple[str, str], tuple[str, str]]] = []
        self._persist_path = persist_path

        # Spec 029: identity nodes + typed edges
        self._contributors: dict[str, Contributor] = {}
        self._orgs: dict[str, Organization] = {}
        self._typed_edges: set[tuple[str, str, str]] = set()  # (type, from_id, to_id)

        # Project -> GitHub repo mapping (owner, repo)
        self._project_github: dict[tuple[str, str], tuple[str, str]] = {}

        # Project recent activity counts (by window_days)
        self._project_recent_commits: dict[tuple[str, str, int], int] = {}

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

            # --- spec 029 data ---
            for c in data.get("contributors", []):
                try:
                    cc = Contributor(**c)
                    self._contributors[cc.id] = cc
                except Exception:
                    pass
            for o in data.get("organizations", []):
                try:
                    oo = Organization(**o)
                    self._orgs[oo.id] = oo
                except Exception:
                    pass
            for te in data.get("typed_edges", []):
                if isinstance(te, list) and len(te) >= 3:
                    t, a, b = te[0], te[1], te[2]
                    if isinstance(t, str) and isinstance(a, str) and isinstance(b, str):
                        self._typed_edges.add((t, a, b))

            for k, v in (data.get("project_github") or {}).items():
                if isinstance(k, str) and isinstance(v, list) and len(v) >= 2:
                    parts = k.split("|", 1)
                    if len(parts) == 2 and isinstance(v[0], str) and isinstance(v[1], str):
                        self._project_github[(parts[0], parts[1])] = (v[0], v[1])

            for k, v in (data.get("project_recent_commits") or {}).items():
                if isinstance(k, str) and isinstance(v, int):
                    parts = k.split("|")
                    if len(parts) == 3:
                        eco, name, win = parts[0], parts[1], parts[2]
                        try:
                            win_i = int(win)
                        except ValueError:
                            continue
                        self._project_recent_commits[(eco, name, win_i)] = v

            self._recompute_dependency_counts()
        except (json.JSONDecodeError, IOError, KeyError):
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
            "organizations": [o.model_dump() for o in self._orgs.values()],
            "typed_edges": [list(t) for t in sorted(self._typed_edges)],
            "project_github": {
                f"{k[0]}|{k[1]}": [v[0], v[1]] for k, v in self._project_github.items()
            },
            "project_recent_commits": {
                f"{k[0]}|{k[1]}|{k[2]}": v for k, v in self._project_recent_commits.items()
            },
        }
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0)

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        return self._projects.get(_key(ecosystem, name))

    def iter_projects(self) -> list[Project]:
        return list(self._projects.values())

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

    # --- spec 029: identity nodes + edges ---

    def upsert_contributor(self, contributor: Contributor) -> None:
        self._contributors[contributor.id] = contributor

    def upsert_organization(self, organization: Organization) -> None:
        self._orgs[organization.id] = organization

    def _project_node_id(self, eco: str, name: str) -> str:
        k = _key(eco, name)
        return f"project:{k[0]}:{k[1]}"

    def add_contributes_to(self, contributor_id: str, project_eco: str, project_name: str) -> None:
        to_id = self._project_node_id(project_eco, project_name)
        self._typed_edges.add(("CONTRIBUTES_TO", contributor_id, to_id))

    def add_maintains(self, contributor_id: str, project_eco: str, project_name: str) -> None:
        to_id = self._project_node_id(project_eco, project_name)
        self._typed_edges.add(("MAINTAINS", contributor_id, to_id))

    def add_member_of(self, contributor_id: str, org_id: str) -> None:
        self._typed_edges.add(("MEMBER_OF", contributor_id, org_id))

    def contributors_for_project(self, project_eco: str, project_name: str) -> list[Contributor]:
        to_id = self._project_node_id(project_eco, project_name)
        out: list[Contributor] = []
        for t, from_id, to in self._typed_edges:
            if t == "CONTRIBUTES_TO" and to == to_id:
                c = self._contributors.get(from_id)
                if c:
                    out.append(c)
        out.sort(key=lambda x: x.contributions_count, reverse=True)
        return out

    def set_project_github_repo(self, project_eco: str, project_name: str, owner: str, repo: str) -> None:
        self._project_github[_key(project_eco, project_name)] = (owner, repo)

    def get_project_github_repo(self, project_eco: str, project_name: str) -> tuple[str, str] | None:
        return self._project_github.get(_key(project_eco, project_name))

    def set_project_recent_commits(self, project_eco: str, project_name: str, window_days: int, count: int) -> None:
        k = _key(project_eco, project_name)
        self._project_recent_commits[(k[0], k[1], int(window_days))] = int(count)

    def recent_activity_count(self, project_eco: str, project_name: str, window_days: int = 30) -> int:
        k = _key(project_eco, project_name)
        return int(self._project_recent_commits.get((k[0], k[1], int(window_days)), 0))
