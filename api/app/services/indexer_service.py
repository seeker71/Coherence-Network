"""Indexer: fetch npm/pypi packages from deps.dev + registries, write to GraphStore — spec 019, 024."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from app.adapters.graph_store import GraphStore
from app.models.project import Project

DEPS_DEV = "https://api.deps.dev"
NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_JSON = "https://pypi.org/pypi"
log = logging.getLogger(__name__)


def _npm_description(name: str) -> str:
    """Fetch description from npm registry."""
    try:
        r = httpx.get(f"{NPM_REGISTRY}/{quote(name, safe='')}", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            return (data.get("description") or "").strip()[:2000]
    except Exception as e:
        log.debug("npm registry fetch %s: %s", name, e)
    return ""


def _deps_dev_package(name: str) -> dict | None:
    """Fetch package info from deps.dev. Returns versions or None."""
    try:
        r = httpx.get(
            f"{DEPS_DEV}/v3/systems/npm/packages/{quote(name, safe='')}",
            timeout=15.0,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.debug("deps.dev package %s: %s", name, e)
    return None


def _deps_dev_dependencies(name: str, version: str) -> list[str]:
    """Fetch resolved dependencies from deps.dev. Returns list of dep package names."""
    deps: list[str] = []
    try:
        url = f"{DEPS_DEV}/v3/systems/npm/packages/{quote(name, safe='')}/versions/{quote(version, safe='')}:dependencies"
        r = httpx.get(url, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            nodes = data.get("nodes") or []
            for node in nodes[1:]:  # skip root
                vk = node.get("versionKey") or {}
                rel = node.get("relation") or ""
                if rel == "DIRECT" and vk.get("name"):
                    deps.append(vk["name"])
    except Exception as e:
        log.debug("deps.dev deps %s@%s: %s", name, version, e)
    return deps


def index_npm_packages(
    store: GraphStore,
    package_names: list[str],
    limit: int | None = None,
    target: int | None = None,
) -> int:
    """
    Index npm packages into GraphStore. Fetches from deps.dev + npm registry.
    If target is set, grow by adding discovered dependencies until count >= target.
    Returns count of packages successfully indexed this run.
    """
    indexed = 0
    queue: list[str] = list(package_names[:limit] if limit else package_names)
    processed: set[str] = set()
    in_queue: set[str] = {n.lower() for n in queue}
    while queue and (not target or store.count_projects() < target):
        name = queue.pop(0)
        key = name.lower()
        in_queue.discard(key)
        if key in processed:
            continue
        processed.add(key)
        existing = store.get_project("npm", name)
        if existing:
            if target and store.count_projects() < target:
                pkg = _deps_dev_package(name)
                if pkg:
                    versions = pkg.get("versions") or []
                    ver = "0.0.0"
                    for v in versions:
                        vk = v.get("versionKey") or {}
                        if vk.get("version"):
                            ver = vk["version"]
                            break
                    for dep in _deps_dev_dependencies(name, ver):
                        dk = dep.lower()
                        if dk not in processed and dk not in in_queue:
                            queue.append(dep)
                            in_queue.add(dk)
            continue
        pkg = _deps_dev_package(name)
        if not pkg:
            continue
        versions = pkg.get("versions") or []
        version = "0.0.0"
        for v in versions:
            vk = v.get("versionKey") or {}
            ver = vk.get("version")
            if ver:
                if v.get("isDefault"):
                    version = ver
                    break
                if version == "0.0.0":
                    version = ver
        if version == "0.0.0" and versions:
            vk = (versions[0] or {}).get("versionKey") or {}
            version = vk.get("version", "0.0.0")
        description = _npm_description(name)
        proj = Project(
            name=name,
            ecosystem="npm",
            version=version,
            description=description,
            dependency_count=0,
        )
        store.upsert_project(proj)
        deps = _deps_dev_dependencies(name, version)
        for dep in deps:
            store.add_dependency("npm", name, "npm", dep)
            dk = dep.lower()
            if target and dk not in processed and dk not in in_queue:
                queue.append(dep)
                in_queue.add(dk)
        indexed += 1
        if indexed % 50 == 0:
            log.info("indexed %d packages... (total %d)", indexed, store.count_projects())
    return indexed


# --- PyPI indexer — spec 024 ---


def _pypi_description(name: str) -> str:
    """Fetch description from PyPI JSON API."""
    try:
        r = httpx.get(f"{PYPI_JSON}/{quote(name, safe='')}/json", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            info = data.get("info") or {}
            return (info.get("summary") or "").strip()[:2000]
    except Exception as e:
        log.debug("PyPI fetch %s: %s", name, e)
    return ""


def _deps_dev_pypi_package(name: str) -> dict | None:
    """Fetch package info from deps.dev (PyPI). Returns versions or None."""
    try:
        r = httpx.get(
            f"{DEPS_DEV}/v3/systems/pypi/packages/{quote(name, safe='')}",
            timeout=15.0,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.debug("deps.dev pypi package %s: %s", name, e)
    return None


def _deps_dev_pypi_dependencies(name: str, version: str) -> list[str]:
    """Fetch resolved dependencies from deps.dev (PyPI). Returns list of dep names."""
    deps: list[str] = []
    try:
        url = f"{DEPS_DEV}/v3/systems/pypi/packages/{quote(name, safe='')}/versions/{quote(version, safe='')}:dependencies"
        r = httpx.get(url, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            nodes = data.get("nodes") or []
            for node in nodes[1:]:  # skip root
                vk = node.get("versionKey") or {}
                rel = node.get("relation") or ""
                if rel == "DIRECT" and vk.get("name"):
                    deps.append(vk["name"])
    except Exception as e:
        log.debug("deps.dev pypi deps %s@%s: %s", name, version, e)
    return deps


def index_pypi_packages(
    store: GraphStore,
    package_names: list[str],
    limit: int | None = None,
    target: int | None = None,
) -> int:
    """
    Index PyPI packages into GraphStore. Fetches from deps.dev + PyPI JSON API.
    If target is set, grow by adding discovered dependencies until count >= target.
    Returns count of packages successfully indexed this run.
    """
    indexed = 0
    queue: list[str] = list(package_names[:limit] if limit else package_names)
    processed: set[str] = set()
    in_queue: set[str] = {n.lower().replace("_", "-") for n in queue}
    while queue and (not target or store.count_projects() < target):
        name = queue.pop(0)
        key = name.lower().replace("_", "-")
        in_queue.discard(key)
        if key in processed:
            continue
        processed.add(key)
        existing = store.get_project("pypi", name)
        if existing:
            if target and store.count_projects() < target:
                pkg = _deps_dev_pypi_package(name)
                if pkg:
                    versions = pkg.get("versions") or []
                    ver = "0.0.0"
                    for v in versions:
                        vk = v.get("versionKey") or {}
                        if vk.get("version"):
                            ver = vk["version"]
                            break
                    for dep in _deps_dev_pypi_dependencies(name, ver):
                        dk = dep.lower().replace("_", "-")
                        if dk not in processed and dk not in in_queue:
                            queue.append(dep)
                            in_queue.add(dk)
            continue
        pkg = _deps_dev_pypi_package(name)
        if not pkg:
            continue
        versions = pkg.get("versions") or []
        version = "0.0.0"
        for v in versions:
            vk = v.get("versionKey") or {}
            ver = vk.get("version")
            if ver:
                if v.get("isDefault"):
                    version = ver
                    break
                if version == "0.0.0":
                    version = ver
        if version == "0.0.0" and versions:
            vk = (versions[0] or {}).get("versionKey") or {}
            version = vk.get("version", "0.0.0")
        description = _pypi_description(name)
        proj = Project(
            name=name,
            ecosystem="pypi",
            version=version,
            description=description,
            dependency_count=0,
        )
        store.upsert_project(proj)
        deps = _deps_dev_pypi_dependencies(name, version)
        for dep in deps:
            store.add_dependency("pypi", name, "pypi", dep)
            dk = dep.lower().replace("_", "-")
            if target and dk not in processed and dk not in in_queue:
                queue.append(dep)
                in_queue.add(dk)
        indexed += 1
        if indexed % 50 == 0:
            log.info("indexed %d pypi packages... (total %d)", indexed, store.count_projects())
    return indexed
