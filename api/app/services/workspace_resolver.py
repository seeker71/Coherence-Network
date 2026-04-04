"""WorkspaceResolver — the single swap point between co-located and truly isolated workspaces.

Today (Phase 1): CoLocatedResolver reads workspace bundles from workspaces/{slug}/
in this repo. The default workspace 'coherence-network' resolves to the repo
root for backward compat (ideas/, specs/, .claude/agents/ stay where they are).

Tomorrow (Phase N): RemoteRepoResolver fetches workspace bundles from the
workspace's own git repo. FederatedWorkspaceResolver resolves workspace_id
via federation peer lookup. Callers don't change — only the resolver.

A workspace bundle contains:
  workspaces/{slug}/
    workspace.yaml       — manifest (name, description, pillars, visibility)
    pillars.yaml         — taxonomy declaration (can override workspace.yaml)
    .agents/             — per-workspace agent personas (product-manager.md, dev-engineer.md, ...)
    templates/           — spec.md, idea.md, task.md templates
    guides/              — onboarding, contribution rules
    ideas/               — workspace-specific idea .md files (optional)
    specs/               — workspace-specific spec .md files (optional)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.models.workspace import DEFAULT_WORKSPACE_ID


COHERENCE_NETWORK_PILLARS = [
    "realization",
    "pipeline",
    "economics",
    "surfaces",
    "network",
    "foundation",
]


class WorkspaceResolver(Protocol):
    def get_bundle_root(self, workspace_id: str) -> Path: ...
    def get_pillars(self, workspace_id: str) -> list[str]: ...
    def get_agent_persona(self, workspace_id: str, agent_name: str) -> str | None: ...
    def get_template(self, workspace_id: str, kind: str) -> str | None: ...
    def get_guide(self, workspace_id: str, name: str) -> str | None: ...


def _repo_root() -> Path:
    """Repo root path — parent of api/."""
    env = os.environ.get("COHERENCE_REPO_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


class CoLocatedResolver:
    """Phase 1 — reads from workspaces/{slug}/ in this repo.

    The default workspace 'coherence-network' resolves to the repo root
    so existing ideas/, specs/, .claude/agents/, specs/TEMPLATE.md keep
    working without physical file moves.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = (repo_root or _repo_root()).resolve()

    def get_bundle_root(self, workspace_id: str) -> Path:
        if workspace_id == DEFAULT_WORKSPACE_ID:
            # Legacy default workspace — bundle is at repo root for backward compat.
            return self._repo_root
        return self._repo_root / "workspaces" / workspace_id

    def get_pillars(self, workspace_id: str) -> list[str]:
        # Default workspace has hardcoded pillars (the Coherence Network taxonomy).
        if workspace_id == DEFAULT_WORKSPACE_ID:
            pillars_file = self._repo_root / "workspaces" / workspace_id / "pillars.yaml"
            if pillars_file.is_file():
                return _parse_pillars_yaml(pillars_file.read_text(encoding="utf-8"))
            return list(COHERENCE_NETWORK_PILLARS)
        pillars_file = self.get_bundle_root(workspace_id) / "pillars.yaml"
        if not pillars_file.is_file():
            return []
        return _parse_pillars_yaml(pillars_file.read_text(encoding="utf-8"))

    def get_agent_persona(self, workspace_id: str, agent_name: str) -> str | None:
        # Workspace-specific persona first
        bundle_persona = self.get_bundle_root(workspace_id) / ".agents" / f"{agent_name}.md"
        if bundle_persona.is_file():
            return bundle_persona.read_text(encoding="utf-8")
        # Legacy platform-level fallback for the default workspace
        if workspace_id == DEFAULT_WORKSPACE_ID:
            legacy = self._repo_root / ".claude" / "agents" / f"{agent_name}.md"
            if legacy.is_file():
                return legacy.read_text(encoding="utf-8")
        return None

    def get_template(self, workspace_id: str, kind: str) -> str | None:
        candidates = [
            self.get_bundle_root(workspace_id) / "templates" / f"{kind}.md",
        ]
        if workspace_id == DEFAULT_WORKSPACE_ID:
            # Legacy location for the default workspace
            if kind == "spec":
                candidates.append(self._repo_root / "specs" / "TEMPLATE.md")
        for c in candidates:
            if c.is_file():
                return c.read_text(encoding="utf-8")
        return None

    def get_guide(self, workspace_id: str, name: str) -> str | None:
        guide = self.get_bundle_root(workspace_id) / "guides" / f"{name}.md"
        if guide.is_file():
            return guide.read_text(encoding="utf-8")
        return None


def _parse_pillars_yaml(content: str) -> list[str]:
    """Minimal YAML list parser — accepts either a top-level list or pillars: list."""
    pillars: list[str] = []
    in_list = False
    for raw in content.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("pillars:"):
            in_list = True
            rest = stripped[len("pillars:"):].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1]
                return [p.strip().strip('"\'') for p in inner.split(",") if p.strip()]
            continue
        if stripped.startswith("- "):
            val = stripped[2:].strip()
            # Strip inline comments — "- realization   # explanation" → "realization"
            if "#" in val:
                val = val.split("#", 1)[0].strip()
            val = val.strip('"\'')
            if val:
                pillars.append(val)
            continue
        if not in_list and not stripped.startswith("- "):
            # Top-level list form — just collect bare "- value" lines later
            pass
    return pillars


# Module-level resolver singleton — simple for now, swappable via set_resolver()
_resolver: WorkspaceResolver = CoLocatedResolver()


def get_resolver() -> WorkspaceResolver:
    return _resolver


def set_resolver(resolver: WorkspaceResolver) -> None:
    """Swap the resolver at runtime (for tests, or Phase N migration)."""
    global _resolver
    _resolver = resolver
