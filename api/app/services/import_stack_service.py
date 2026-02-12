"""Import stack service — spec 022, 025. Parse lockfile/requirements, enrich with GraphStore."""

import json
import re
from typing import Any, Optional, Protocol

from app.models.import_stack import ImportPackage, RiskSummary
from app.models.project import Project
from app.services.coherence_service import compute_coherence


class GraphStoreForImport(Protocol):
    """GraphStore interface for import stack."""

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        ...

    def count_dependents(self, ecosystem: str, name: str) -> int:
        ...


def _package_name_from_path(path: str) -> Optional[str]:
    """Extract package name from packages key. node_modules/foo -> foo, node_modules/@scope/pkg -> @scope/pkg."""
    if not path or path == "":
        return None
    if path.startswith("node_modules/"):
        return path[len("node_modules/"):]
    return None


def _extract_packages_lockfile_v2_v3(packages: dict[str, Any]) -> dict[str, tuple[str, list[str]]]:
    """Extract name@version and dependencies from lockfileVersion 2/3 packages."""
    out: dict[str, tuple[str, list[str]]] = {}
    for key, pkg in packages.items():
        name = _package_name_from_path(key)
        if not name:
            continue
        version = pkg.get("version")
        if not version:
            continue
        deps_raw = pkg.get("dependencies") or {}
        deps: list[str] = [f"{k}@{v}" if isinstance(v, str) else f"{k}@{v.get('version', '')}" for k, v in deps_raw.items()]
        out[name] = (version, deps)
    return out


def _extract_packages_lockfile_v1(deps: dict[str, Any]) -> dict[str, tuple[str, list[str]]]:
    """Extract name@version from lockfileVersion 1 dependencies (recursive)."""
    out: dict[str, tuple[str, list[str]]] = {}

    def _walk(obj: dict[str, Any]) -> None:
        for name, meta in obj.items():
            if not isinstance(meta, dict):
                continue
            version = meta.get("version")
            if not version:
                continue
            child_deps = meta.get("dependencies") or {}
            child_list: list[str] = []
            for k, v in child_deps.items():
                if isinstance(v, dict):
                    child_list.append(f"{k}@{v.get('version', '')}")
            out[name] = (version, child_list)
            _walk(child_deps)

    _walk(deps)
    return out


def parse_lockfile(content: str) -> dict[str, tuple[str, list[str]]]:
    """Parse package-lock.json content. Returns dict of name -> (version, deps_list)."""
    data = json.loads(content)
    if "packages" in data:
        return _extract_packages_lockfile_v2_v3(data["packages"])
    if "dependencies" in data:
        return _extract_packages_lockfile_v1(data["dependencies"])
    return {}


def parse_requirements(content: str) -> dict[str, tuple[str, list[str]]]:
    """Parse requirements.txt. Returns dict of name -> (version, []). Spec 025."""
    out: dict[str, tuple[str, list[str]]] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # name==version, name>=x, name~=x, name[extra], name (PEP 508)
        m = re.match(r"^([a-zA-Z0-9_.-]+)(?:\s*\[[^\]]*\])?(?:\s*([=~<>!]+)\s*([^\s#]+))?", line)
        if m:
            name = m.group(1).lower().replace("_", "-")
            version = (m.group(3) or "").strip() if m.group(2) == "==" else ""
            if name and name not in out:
                out[name] = (version or "unknown", [])
    return out


def enrich_and_risk(
    store: GraphStoreForImport,
    name: str,
    version: str,
    deps: list[str],
    ecosystem: str = "npm",
) -> tuple[ImportPackage, str]:
    """Enrich package with coherence; return (ImportPackage, risk_bucket)."""
    proj = store.get_project(ecosystem, name)
    if proj:
        coh = compute_coherence(store, proj)
        score = coh["score"]
        # High coherence = healthy = low risk; low coherence = high risk
        if score >= 0.7:
            bucket = "low_risk"
        elif score >= 0.4:
            bucket = "medium_risk"
        else:
            bucket = "high_risk"
        return (
            ImportPackage(
                name=name,
                version=version,
                coherence=score,
                status="known",
                dependencies=deps,
            ),
            bucket,
        )
    return (
        ImportPackage(
            name=name,
            version=version,
            coherence=None,
            status="unknown",
            dependencies=deps,
        ),
        "unknown",
    )


def process_lockfile(store: GraphStoreForImport, content: str) -> dict:
    """Parse lockfile, enrich with GraphStore, return ImportStackResponse shape."""
    pkgs_data = parse_lockfile(content)
    packages: list[ImportPackage] = []
    risk: dict[str, int] = {"unknown": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}
    for name, (version, deps) in pkgs_data.items():
        imp_pkg, bucket = enrich_and_risk(store, name, version, deps, ecosystem="npm")
        packages.append(imp_pkg)
        risk[bucket] = risk.get(bucket, 0) + 1
    return {
        "packages": [p.model_dump() for p in packages],
        "risk_summary": RiskSummary(**risk).model_dump(),
    }


def process_requirements(store: GraphStoreForImport, content: str) -> dict:
    """Parse requirements.txt, enrich with GraphStore, return ImportStackResponse shape — spec 025."""
    pkgs_data = parse_requirements(content)
    packages: list[ImportPackage] = []
    risk: dict[str, int] = {"unknown": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}
    for name, (version, deps) in pkgs_data.items():
        imp_pkg, bucket = enrich_and_risk(store, name, version, deps, ecosystem="pypi")
        packages.append(imp_pkg)
        risk[bucket] = risk.get(bucket, 0) + 1
    return {
        "packages": [p.model_dump() for p in packages],
        "risk_summary": RiskSummary(**risk).model_dump(),
    }
