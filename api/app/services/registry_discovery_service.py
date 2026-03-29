"""Registry submission readiness for MCP and skill discovery surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models.registry_discovery import (
    RegistrySubmissionInventory,
    RegistrySubmissionRecord,
    RegistrySubmissionStatus,
    RegistrySubmissionSummary,
)


@dataclass(frozen=True)
class _RegistryTarget:
    registry_id: str
    registry_name: str
    category: str
    asset_name: str
    install_hint: str
    required_files: tuple[str, ...]
    validator: Callable[[Path], bool]
    notes: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(repo_root: Path, rel_path: str) -> dict:
    path = repo_root / rel_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_text(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _smithery_ready(repo_root: Path) -> bool:
    smithery_yaml = _read_text(repo_root, "mcp-server/smithery.yaml")
    return (
        "name: coherence-mcp-server" in smithery_yaml
        and "install:" in smithery_yaml
        and "npx coherence-mcp-server" in smithery_yaml
    )


def _glama_ready(repo_root: Path) -> bool:
    glama = _read_json(repo_root, "mcp-server/glama.json")
    return (
        glama.get("name") == "coherence-network"
        and "url" in glama
        and "npx" in str(glama.get("install") or "")
    )


def _pulsemcp_ready(repo_root: Path) -> bool:
    pulsemcp = _read_json(repo_root, "mcp-server/pulsemcp.json")
    return (
        pulsemcp.get("slug") == "coherence-network"
        and bool(pulsemcp.get("npm_package"))
    )


def _mcp_manifest_ready(repo_root: Path) -> bool:
    manifest = _read_json(repo_root, "mcp-server/server.json")
    packages = manifest.get("packages")
    return (
        manifest.get("name") == "coherence-mcp-server"
        and "registry.modelcontextprotocol.io/schemas/server.json" in str(manifest.get("$schema") or "")
        and isinstance(packages, list)
        and any(
            isinstance(item, dict)
            and item.get("registry") == "npm"
            and item.get("name") == "coherence-mcp-server"
            for item in packages
        )
    )


def _npm_package_ready(repo_root: Path) -> bool:
    package_json = _read_json(repo_root, "mcp-server/package.json")
    bins = package_json.get("bin")
    return (
        package_json.get("name") == "coherence-mcp-server"
        and isinstance(bins, dict)
        and bins.get("coherence-mcp-server") == "index.mjs"
    )


def _skill_manifest_ready(repo_root: Path) -> bool:
    skill_md = _read_text(repo_root, "skills/coherence-network/SKILL.md")
    return (
        skill_md.startswith("<!-- AUTO-GENERATED")
        and "name: coherence-network" in skill_md
        and "metadata:" in skill_md
        and "cc inbox" in skill_md
    )


def _readme_install_ready(repo_root: Path) -> bool:
    readme = _read_text(repo_root, "README.md")
    return (
        "coherence-mcp-server" in readme
        and "coherence-cli" in readme
        and "ClawHub: coherence-network" in readme
    )


_TARGETS: tuple[_RegistryTarget, ...] = (
    _RegistryTarget(
        registry_id="modelcontextprotocol-registry",
        registry_name="Model Context Protocol Registry",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "mcp-server/README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _npm_package_ready(repo_root),
        notes="Canonical MCP registry submission built from the typed server manifest and npm package metadata.",
    ),
    _RegistryTarget(
        registry_id="npm",
        registry_name="npm",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/package.json", "mcp-server/README.md"),
        validator=lambda repo_root: _npm_package_ready(repo_root),
        notes="Package discovery for MCP clients that install the server directly from npm.",
    ),
    _RegistryTarget(
        registry_id="smithery",
        registry_name="Smithery",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/smithery.yaml", "mcp-server/package.json", "mcp-server/README.md"),
        validator=lambda repo_root: _smithery_ready(repo_root) and _npm_package_ready(repo_root),
        notes="Smithery auto-indexes npm packages with a smithery.yaml at the package root.",
    ),
    _RegistryTarget(
        registry_id="glama",
        registry_name="Glama",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/glama.json", "mcp-server/package.json"),
        validator=lambda repo_root: _glama_ready(repo_root) and _npm_package_ready(repo_root),
        notes="Glama ingests from awesome-mcp-servers; glama.json provides required listing metadata.",
    ),
    _RegistryTarget(
        registry_id="pulsemcp",
        registry_name="PulseMCP",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/pulsemcp.json", "mcp-server/package.json"),
        validator=lambda repo_root: _pulsemcp_ready(repo_root) and _npm_package_ready(repo_root),
        notes="PulseMCP indexes npm packages tagged with the mcp keyword; pulsemcp.json adds supplementary metadata.",
    ),
    _RegistryTarget(
        registry_id="mcp-so",
        registry_name="MCP.so",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _readme_install_ready(repo_root),
        notes="Directory discovery can reuse the same MCP manifest, package identity, and install instructions.",
    ),
    _RegistryTarget(
        registry_id="clawhub",
        registry_name="ClawHub",
        category="skill",
        asset_name="coherence-network",
        install_hint="clawhub install coherence-network",
        required_files=("skills/coherence-network/SKILL.md", "README.md"),
        validator=lambda repo_root: _skill_manifest_ready(repo_root) and _readme_install_ready(repo_root),
        notes="OpenClaw skill registry entry anchored to the published SKILL.md and repository install docs.",
    ),
    _RegistryTarget(
        registry_id="agentskills",
        registry_name="AgentSkills",
        category="skill",
        asset_name="coherence-network",
        install_hint="copy skills/coherence-network/SKILL.md into a compatible skills directory",
        required_files=("skills/coherence-network/SKILL.md", "README.md"),
        validator=lambda repo_root: _skill_manifest_ready(repo_root),
        notes="Portable skill packaging for AgentSkills-compatible discovery catalogs and workspace registries.",
    ),
)


def build_registry_submission_inventory() -> RegistrySubmissionInventory:
    repo_root = _repo_root()
    items: list[RegistrySubmissionRecord] = []

    for target in _TARGETS:
        missing_files = [rel_path for rel_path in target.required_files if not (repo_root / rel_path).exists()]
        ready = not missing_files and target.validator(repo_root)
        items.append(
            RegistrySubmissionRecord(
                registry_id=target.registry_id,
                registry_name=target.registry_name,
                category=target.category,
                asset_name=target.asset_name,
                status=(
                    RegistrySubmissionStatus.SUBMISSION_READY
                    if ready
                    else RegistrySubmissionStatus.MISSING_ASSETS
                ),
                install_hint=target.install_hint,
                source_paths=list(target.required_files),
                required_files=list(target.required_files),
                missing_files=missing_files,
                notes=target.notes,
            )
        )

    items.sort(key=lambda item: (item.category, item.registry_name.lower()))
    ready_count = sum(item.status == RegistrySubmissionStatus.SUBMISSION_READY for item in items)
    category_counts: dict[str, int] = {}
    for item in items:
        category_counts[item.category] = category_counts.get(item.category, 0) + 1

    return RegistrySubmissionInventory(
        summary=RegistrySubmissionSummary(
            target_count=len(items),
            submission_ready_count=ready_count,
            missing_asset_count=sum(bool(item.missing_files) for item in items),
            categories=category_counts,
            core_requirement_met=ready_count >= 5,
        ),
        items=items,
    )
