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


def _glama_metadata_ready(repo_root: Path) -> bool:
    glama = _read_json(repo_root, "mcp-server/glama.json")
    return (
        glama.get("name") == "coherence-network"
        and bool(glama.get("description"))
        and bool(glama.get("url"))
        and isinstance(glama.get("tags"), list)
    )


_TARGETS: tuple[_RegistryTarget, ...] = (
    _RegistryTarget(
        registry_id="smithery",
        registry_name="Smithery",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "mcp-server/README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _readme_install_ready(repo_root),
        notes="Smithery.ai MCP registry — submit via server.json PR or npm package discovery.",
    ),
    _RegistryTarget(
        registry_id="glama",
        registry_name="Glama (awesome-mcp-servers)",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "mcp-server/glama.json", "mcp-server/README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _glama_metadata_ready(repo_root),
        notes="Glama discovery via PR to punkpeye/awesome-mcp-servers. Requires glama.json metadata file.",
    ),
    _RegistryTarget(
        registry_id="pulsemcp",
        registry_name="PulseMCP",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "mcp-server/README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _npm_package_ready(repo_root),
        notes="PulseMCP catalog — submit via GitHub PR. Tracks install counts via public API.",
    ),
    _RegistryTarget(
        registry_id="mcp-so",
        registry_name="MCP.so",
        category="mcp",
        asset_name="coherence-mcp-server",
        install_hint="npx coherence-mcp-server",
        required_files=("mcp-server/server.json", "mcp-server/package.json", "README.md"),
        validator=lambda repo_root: _mcp_manifest_ready(repo_root) and _readme_install_ready(repo_root),
        notes="MCP.so directory — submitted via web form. Reuses MCP manifest and README install docs.",
    ),
    _RegistryTarget(
        registry_id="skills-sh",
        registry_name="skills.sh",
        category="skill",
        asset_name="coherence-network",
        install_hint="clawhub install coherence-network",
        required_files=("skills/coherence-network/SKILL.md", "README.md"),
        validator=lambda repo_root: _skill_manifest_ready(repo_root) and _readme_install_ready(repo_root),
        notes="skills.sh skill registry — submit via PR. SKILL.md manifest required.",
    ),
    _RegistryTarget(
        registry_id="askill-sh",
        registry_name="askill.sh",
        category="skill",
        asset_name="coherence-network",
        install_hint="clawhub install coherence-network",
        required_files=("skills/coherence-network/SKILL.md", "README.md"),
        validator=lambda repo_root: _skill_manifest_ready(repo_root),
        notes="askill.sh skill directory — submit via PR. Compatible with the standard SKILL.md format.",
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
