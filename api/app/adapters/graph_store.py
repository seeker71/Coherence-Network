"""GraphStore abstraction + in-memory backend — spec 019."""

from __future__ import annotations

import json
import os
from typing import Optional, Protocol

from app.models.project import Project, ProjectSummary


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


class InMemoryGraphStore:
    """In-memory GraphStore. Optional JSON persistence for restart."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._projects: dict[tuple[str, str], Project] = {}
        self._edges: list[tuple[tuple[str, str], tuple[str, str]]] = []
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
