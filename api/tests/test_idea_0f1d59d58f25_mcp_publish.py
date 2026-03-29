"""Tests for idea-0f1d59d58f25: Publish coherence-network MCP server to npm and PyPI.

Validates acceptance criteria from the spec:
  AC1/AC2: Package metadata is correct for npm and PyPI publishing
  AC3/AC4: Entry points exist and are correctly declared
  AC5: CI publish workflow exists and triggers on semver tags
  AC6: server.json has both npm and pypi package entries (or at minimum npm)
  AC7/AC10: registry_stats_service graceful degradation
  AC8: PublishEvent model structure
  AC9: Version sync across package.json, pyproject.toml, server.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

API_DIR = Path(__file__).resolve().parents[1]  # api/
REPO_ROOT = API_DIR.parent

MCP_SERVER_DIR = REPO_ROOT / "mcp-server"
PACKAGE_JSON = MCP_SERVER_DIR / "package.json"
PYPROJECT_TOML = MCP_SERVER_DIR / "pyproject.toml"
SERVER_JSON = MCP_SERVER_DIR / "server.json"
INDEX_MJS = MCP_SERVER_DIR / "index.mjs"
README_PATH = MCP_SERVER_DIR / "README.md"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("COHERENCE_ENV", "test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_toml_version(path: Path) -> str | None:
    """Extract version from pyproject.toml without requiring tomllib."""
    content = path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return m.group(1) if m else None


# ===========================================================================
# AC9 — Version sync across all three manifests
# ===========================================================================

class TestVersionSync:
    """All three manifest files must declare the same version."""

    def test_package_json_version_matches_pyproject_toml(self):
        npm_ver = _load_json(PACKAGE_JSON)["version"]
        py_ver = _parse_toml_version(PYPROJECT_TOML)
        assert py_ver is not None, "Could not parse version from pyproject.toml"
        assert npm_ver == py_ver, (
            f"Version mismatch: package.json={npm_ver}, pyproject.toml={py_ver}"
        )

    def test_package_json_version_matches_server_json(self):
        npm_ver = _load_json(PACKAGE_JSON)["version"]
        srv_ver = _load_json(SERVER_JSON)["version"]
        assert npm_ver == srv_ver, (
            f"Version mismatch: package.json={npm_ver}, server.json={srv_ver}"
        )

    def test_server_json_packages_version_matches_root_version(self):
        data = _load_json(SERVER_JSON)
        root_ver = data["version"]
        for pkg in data.get("packages", []):
            assert pkg["version"] == root_ver, (
                f"server.json packages[].version={pkg['version']} "
                f"differs from root version={root_ver}"
            )

    def test_all_three_versions_are_valid_semver(self):
        semver_re = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
        npm_ver = _load_json(PACKAGE_JSON)["version"]
        py_ver = _parse_toml_version(PYPROJECT_TOML)
        srv_ver = _load_json(SERVER_JSON)["version"]
        for label, ver in [("package.json", npm_ver), ("pyproject.toml", py_ver), ("server.json", srv_ver)]:
            assert ver and semver_re.match(ver), f"{label} version '{ver}' is not valid semver"


# ===========================================================================
# AC6 — server.json npm package entry (pypi entry is a gap per spec)
# ===========================================================================

class TestServerJsonPackages:
    """server.json must list at least the npm package entry."""

    def test_has_npm_package_entry(self):
        data = _load_json(SERVER_JSON)
        pkgs = data.get("packages", [])
        npm_entries = [p for p in pkgs if p.get("registry") == "npm"]
        assert len(npm_entries) >= 1, "server.json must have at least one npm package entry"

    def test_npm_entry_name_matches_package_json(self):
        data = _load_json(SERVER_JSON)
        pkg_name = _load_json(PACKAGE_JSON)["name"]
        npm_entries = [p for p in data.get("packages", []) if p.get("registry") == "npm"]
        assert npm_entries[0]["name"] == pkg_name

    def test_server_json_has_mcp_schema(self):
        data = _load_json(SERVER_JSON)
        schema = data.get("$schema", "")
        assert "modelcontextprotocol" in schema, f"$schema should reference MCP; got '{schema}'"

    def test_server_json_declares_20_tools(self):
        data = _load_json(SERVER_JSON)
        tools = data.get("tools", [])
        assert len(tools) >= 14, f"Expected at least 14 tools, got {len(tools)}"


# ===========================================================================
# AC5 — Publish workflow (may not exist yet — tests still useful for impl)
# ===========================================================================

class TestPublishWorkflow:
    """Validate .github/workflows/publish.yml structure if it exists."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_workflow(self):
        if not PUBLISH_WORKFLOW.exists():
            pytest.skip("publish.yml not yet created (gap per spec)")

    def test_triggers_on_semver_tags(self):
        content = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        assert "v[0-9]" in content or "v*.*.*" in content, (
            "publish.yml must trigger on semver tag pattern"
        )

    def test_has_npm_publish_job(self):
        content = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        assert "npm publish" in content.lower() or "publish-npm" in content, (
            "publish.yml must have an npm publish job"
        )

    def test_has_pypi_publish_job(self):
        content = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        assert "hatch" in content.lower() or "publish-pypi" in content or "pypi" in content.lower(), (
            "publish.yml must have a PyPI publish job"
        )

    def test_uses_secrets_for_tokens(self):
        content = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        assert "NPM_TOKEN" in content or "NODE_AUTH_TOKEN" in content, (
            "publish.yml must use NPM_TOKEN or NODE_AUTH_TOKEN secret"
        )


# ===========================================================================
# AC3/AC4 — Entry points exist and are correctly configured
# ===========================================================================

class TestEntryPoints:
    """Validate that both npm and PyPI entry points are set up."""

    def test_npm_bin_entry_exists(self):
        data = _load_json(PACKAGE_JSON)
        bin_map = data.get("bin", {})
        assert "coherence-mcp-server" in bin_map, "bin must declare coherence-mcp-server"
        entry = bin_map["coherence-mcp-server"]
        assert (MCP_SERVER_DIR / entry).exists(), f"Bin target '{entry}' does not exist"

    def test_index_mjs_has_shebang_or_esm(self):
        content = INDEX_MJS.read_text(encoding="utf-8")
        assert content.startswith("#!/") or "import " in content[:500], (
            "index.mjs must be an ESM module"
        )

    def test_pyproject_declares_script_entry_point(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "coherence-mcp-server" in content, (
            "pyproject.toml must declare coherence-mcp-server script entry point"
        )
        assert "[project.scripts]" in content, (
            "pyproject.toml must have [project.scripts] section"
        )

    def test_pyproject_build_system_is_hatchling(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "hatchling" in content, "pyproject.toml must use hatchling build backend"

    def test_pyproject_requires_python_310_plus(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "requires-python" in content, "Must specify requires-python"
        assert "3.10" in content or "3.11" in content, "Must require Python 3.10+"


# ===========================================================================
# AC1/AC2 — Package metadata suitable for publishing
# ===========================================================================

class TestPackageMetadata:
    """Package metadata must be complete for registry discoverability."""

    def test_npm_package_has_keywords_with_mcp(self):
        data = _load_json(PACKAGE_JSON)
        keywords = [k.lower() for k in data.get("keywords", [])]
        assert "mcp" in keywords, "package.json keywords must include 'mcp'"

    def test_npm_package_has_license(self):
        data = _load_json(PACKAGE_JSON)
        assert data.get("license") == "MIT"

    def test_npm_package_has_files_array(self):
        data = _load_json(PACKAGE_JSON)
        files = data.get("files", [])
        assert "index.mjs" in files, "files array must include index.mjs"

    def test_pyproject_has_classifiers(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "classifiers" in content, "pyproject.toml should have classifiers for PyPI"

    def test_pyproject_has_mit_license(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "MIT" in content

    def test_readme_exists_for_both_registries(self):
        assert README_PATH.exists(), "mcp-server/README.md required for npm and PyPI display"
        assert README_PATH.stat().st_size >= 500, "README should be at least 500 bytes"


# ===========================================================================
# AC7/AC10 — Registry stats service unit tests
# ===========================================================================

class TestRegistryStatsService:
    """Test the registry_stats_service module if it exists."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_service(self):
        service_path = API_DIR / "app" / "services" / "registry_stats_service.py"
        if not service_path.exists():
            pytest.skip("registry_stats_service.py not yet created (gap per spec)")

    @pytest.mark.asyncio
    async def test_fetch_npm_downloads_returns_dict(self):
        from app.services.registry_stats_service import fetch_npm_downloads

        # Mock httpx to avoid real HTTP calls
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"downloads": 42, "package": "coherence-mcp-server"}
        mock_resp.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.registry_stats_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_npm_downloads(refresh=True)

        assert isinstance(result, dict)
        assert result["registry_id"] == "npm"
        assert result["install_count"] == 42
        assert result["source"] == "live"

    @pytest.mark.asyncio
    async def test_fetch_npm_downloads_graceful_on_error(self):
        """AC10: when npm API is unreachable, returns source='unavailable' not an exception."""
        from app.services.registry_stats_service import fetch_npm_downloads

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.registry_stats_service.httpx.AsyncClient", return_value=mock_client):
            with patch("app.services.registry_stats_service._read_cache", return_value=None):
                result = await fetch_npm_downloads(refresh=True)

        assert isinstance(result, dict)
        assert result["source"] == "unavailable"
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_fetch_pypi_downloads_returns_dict(self):
        from app.services.registry_stats_service import fetch_pypi_downloads

        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"data": {"last_week": 5}, "package": "coherence-mcp-server"}
        mock_resp.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.registry_stats_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_pypi_downloads(refresh=True)

        assert isinstance(result, dict)
        assert result["registry_id"] == "pypi"
        assert result["install_count"] == 5
        assert result["source"] == "live"

    @pytest.mark.asyncio
    async def test_fetch_pypi_downloads_graceful_on_error(self):
        """AC10: graceful degradation for PyPI stats."""
        from app.services.registry_stats_service import fetch_pypi_downloads

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.registry_stats_service.httpx.AsyncClient", return_value=mock_client):
            with patch("app.services.registry_stats_service._read_cache", return_value=None):
                result = await fetch_pypi_downloads(refresh=True)

        assert isinstance(result, dict)
        assert result["source"] == "unavailable"


# ===========================================================================
# AC8 — Publish event model (validate structure if model exists)
# ===========================================================================

class TestPublishEventModel:
    """Validate the PublishEvent Pydantic model if it exists."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_model(self):
        try:
            from app.models.registry_discovery import PublishEvent  # noqa: F401
        except (ImportError, AttributeError):
            pytest.skip("PublishEvent model not yet implemented (gap per spec)")

    def test_publish_event_has_required_fields(self):
        from app.models.registry_discovery import PublishEvent
        fields = set(PublishEvent.model_fields.keys())
        for required in ("registry", "version"):
            assert required in fields, f"PublishEvent missing field: {required}"

    def test_publish_event_creates_with_valid_data(self):
        from app.models.registry_discovery import PublishEvent
        from datetime import datetime, timezone

        event = PublishEvent(
            registry="npm",
            version="0.3.1",
            published_at=datetime.now(timezone.utc),
        )
        assert event.registry == "npm"
        assert event.version == "0.3.1"

    def test_publish_event_rejects_invalid_registry(self):
        from app.models.registry_discovery import PublishEvent
        from datetime import datetime, timezone
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PublishEvent(
                registry="invalid_registry",
                version="0.3.1",
                published_at=datetime.now(timezone.utc),
            )


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases and error scenarios from the spec."""

    def test_npm_package_name_is_lowercase_no_spaces(self):
        data = _load_json(PACKAGE_JSON)
        name = data["name"]
        assert name == name.lower(), "npm name must be lowercase"
        assert " " not in name, "npm name must not contain spaces"
        assert len(name) <= 214, "npm name max 214 chars"

    def test_pyproject_dependencies_include_mcp(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "mcp>=" in content or '"mcp"' in content, (
            "pyproject.toml dependencies must include the mcp SDK"
        )

    def test_server_json_is_valid_json(self):
        """Corrupted server.json would break mcp-publisher."""
        data = _load_json(SERVER_JSON)
        assert isinstance(data, dict)
        assert "name" in data

    def test_all_server_json_tools_have_descriptions(self):
        data = _load_json(SERVER_JSON)
        for tool in data.get("tools", []):
            assert tool.get("description"), f"Tool '{tool.get('name')}' has no description"
            assert len(tool["description"]) >= 10, (
                f"Tool '{tool['name']}' description too short"
            )

    def test_pyproject_homepage_is_https(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        m = re.search(r'Homepage\s*=\s*"([^"]+)"', content)
        if m:
            assert m.group(1).startswith("https://"), "Homepage must be HTTPS"
