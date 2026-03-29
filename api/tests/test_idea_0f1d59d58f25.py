"""Tests for idea-0f1d59d58f25 — publish coherence-network MCP server to npm and PyPI.

Maps to acceptance criteria in ``specs/idea-fecc6d087c4e-mcp-npm-pypi-publish.md``:

- **AC9**: ``package.json``, ``mcp-server/pyproject.toml``, and ``server.json`` versions stay aligned.
- **AC6** (when dual publish is enabled): ``server.json`` ``packages[]`` includes both ``npm`` and ``pypi``
  with matching versions (skipped until the PyPI row exists).
- **AC5** (optional): release workflow ``publish.yml`` (skipped until added).

These checks are offline and read only files under ``mcp-server/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parent

MCP_DIR = REPO_ROOT / "mcp-server"
PACKAGE_JSON = MCP_DIR / "package.json"
SERVER_JSON = MCP_DIR / "server.json"
MCP_PYPROJECT = MCP_DIR / "pyproject.toml"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")


def _load_package_json() -> dict:
    assert PACKAGE_JSON.exists(), f"Missing {PACKAGE_JSON}"
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def _load_server_json() -> dict:
    assert SERVER_JSON.exists(), f"Missing {SERVER_JSON}"
    return json.loads(SERVER_JSON.read_text(encoding="utf-8"))


def _load_mcp_pyproject_version_and_name() -> tuple[str, str]:
    assert MCP_PYPROJECT.exists(), f"Missing {MCP_PYPROJECT}"
    import tomllib

    data = tomllib.loads(MCP_PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})
    version = project.get("version", "")
    name = project.get("name", "")
    assert version and name, "mcp-server/pyproject.toml must set project.name and project.version"
    return str(name), str(version)


def assert_versions_aligned(*, npm: str, pyproject: str, server: str, server_npm_pkg: str) -> None:
    """Raise AssertionError if any semver string differs (AC9)."""
    expected = {npm, pyproject, server, server_npm_pkg}
    assert len(expected) == 1, (
        "Version mismatch (AC9): "
        f"package.json={npm!r} pyproject={pyproject!r} "
        f"server.json.version={server!r} server.json npm package={server_npm_pkg!r}"
    )


class TestMcpPublishManifestAlignment:
    """Happy-path: in-repo artifacts for npm + PyPI packaging stay consistent."""

    def test_ac9_versions_match_across_package_json_pyproject_and_server_json(self) -> None:
        pkg = _load_package_json()
        srv = _load_server_json()
        py_name, py_ver = _load_mcp_pyproject_version_and_name()

        npm_ver = pkg["version"]
        top_ver = srv["version"]
        npm_rows = [p for p in srv.get("packages", []) if p.get("registry") == "npm"]
        assert npm_rows, "server.json must include an npm package row"
        server_npm_ver = npm_rows[0].get("version", "")

        assert py_name == pkg["name"] == "coherence-mcp-server"
        assert_versions_aligned(
            npm=npm_ver,
            pyproject=py_ver,
            server=top_ver,
            server_npm_pkg=server_npm_ver,
        )
        for label, ver in (
            ("npm", npm_ver),
            ("pyproject", py_ver),
            ("server", top_ver),
        ):
            assert SEMVER_RE.match(ver), f"{label} version {ver!r} is not semver-like"

    def test_mcp_pyproject_declares_cli_script_entry(self) -> None:
        text = MCP_PYPROJECT.read_text(encoding="utf-8")
        assert "[project.scripts]" in text
        assert "coherence-mcp-server" in text
        assert "coherence_mcp_server.__main__:main" in text

    def test_package_json_declares_npx_bin(self) -> None:
        pkg = _load_package_json()
        assert pkg.get("name") == "coherence-mcp-server"
        bin_map = pkg.get("bin", {})
        assert isinstance(bin_map, dict)
        assert bin_map.get("coherence-mcp-server") == "index.mjs"

    def test_server_json_has_official_registry_schema(self) -> None:
        srv = _load_server_json()
        schema = srv.get("$schema", "")
        assert "modelcontextprotocol.io" in schema or "registry.modelcontextprotocol" in schema

    def test_server_json_npm_package_matches_manifest_name(self) -> None:
        pkg = _load_package_json()
        srv = _load_server_json()
        npm_rows = [p for p in srv.get("packages", []) if p.get("registry") == "npm"]
        assert npm_rows[0]["name"] == pkg["name"]


class TestAc6PypiRegistryRow:
    """AC6: ``packages[]`` lists npm and pypi with matching versions."""

    def test_ac6_pypi_row_exists_with_matching_version(self) -> None:
        srv = _load_server_json()
        packages = srv.get("packages", [])
        registries = {p.get("registry") for p in packages}
        if "pypi" not in registries:
            pytest.skip(
                "AC6 pending: add a pypi entry to mcp-server/server.json "
                "when the PyPI package is ready (idea-0f1d59d58f25)."
            )
        pypi_rows = [p for p in packages if p.get("registry") == "pypi"]
        assert len(pypi_rows) == 1
        assert pypi_rows[0].get("name") == "coherence-mcp-server"
        assert pypi_rows[0].get("version") == srv["version"]


class TestAc5PublishWorkflow:
    """AC5: GitHub Actions workflow for tag-driven npm + PyPI publish."""

    def test_publish_workflow_present(self) -> None:
        if not PUBLISH_WORKFLOW.exists():
            pytest.skip(
                "AC5 pending: add .github/workflows/publish.yml for tag-driven npm + PyPI publish."
            )
        text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        assert "publish" in text.lower()
        assert "mcp-server" in text or "working-directory" in text


class TestVersionSyncEdgeCases:
    """Edge / error-style checks (pure helpers, no repo mutation)."""

    def test_assert_versions_aligned_detects_single_outlier(self) -> None:
        with pytest.raises(AssertionError, match="Version mismatch"):
            assert_versions_aligned(
                npm="0.3.1",
                pyproject="0.3.1",
                server="0.3.1",
                server_npm_pkg="0.9.9",
            )

    def test_package_rows_must_include_version_strings(self) -> None:
        srv = _load_server_json()
        for i, p in enumerate(srv.get("packages", [])):
            assert "registry" in p, f"packages[{i}] missing registry"
            assert p.get("version"), f"packages[{i}] missing version"
            assert isinstance(p["version"], str)

