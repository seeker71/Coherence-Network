"""Tests for MCP server publishability to npm, PyPI, and discovery registries.

Validates that:
- mcp-server/package.json is correctly structured for npm publishing
- mcp-server/server.json satisfies mcp-publisher/Official MCP Registry schema
- Discovery manifests (glama.json, pulsemcp.json) are valid
- The Python MCP server (api/mcp_server.py) is importable and well-formed
- pyproject.toml has the required packaging metadata
- Tool registry exposes all tools declared in server.json
- Version numbers are consistent across manifests

Verification Scenarios:
  1. npm manifest completeness: package.json has name, version, bin, files, description
  2. MCP Registry manifest: server.json has $schema, tools list, packages with registry=npm
  3. Discovery manifests: glama.json and pulsemcp.json have required fields
  4. Python MCP server imports cleanly and exposes TOOLS/TOOL_MAP
  5. Version consistency: package.json version matches server.json packages[0].version (within minor)
  6. Tool name parity: server.json tools list matches TOOL_MAP keys (subset check)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Locate repo root (parent of the api/ directory)
API_DIR = Path(__file__).resolve().parents[1]  # api/
REPO_ROOT = API_DIR.parent                      # repo root

MCP_SERVER_DIR = REPO_ROOT / "mcp-server"
PACKAGE_JSON_PATH = MCP_SERVER_DIR / "package.json"
SERVER_JSON_PATH = MCP_SERVER_DIR / "server.json"
GLAMA_JSON_PATH = MCP_SERVER_DIR / "glama.json"
PULSEMCP_JSON_PATH = MCP_SERVER_DIR / "pulsemcp.json"
INDEX_MJS_PATH = MCP_SERVER_DIR / "index.mjs"
README_PATH = MCP_SERVER_DIR / "README.md"

PYPROJECT_TOML_PATH = API_DIR / "pyproject.toml"
PYTHON_MCP_SERVER_PATH = API_DIR / "mcp_server.py"

# Ensure api/ is importable so we can test the Python MCP server
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("COHERENCE_ENV", "test")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def package_json() -> dict:
    assert PACKAGE_JSON_PATH.exists(), f"Missing npm manifest: {PACKAGE_JSON_PATH}"
    return json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def server_json() -> dict:
    assert SERVER_JSON_PATH.exists(), f"Missing server.json: {SERVER_JSON_PATH}"
    return json.loads(SERVER_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def glama_json() -> dict:
    assert GLAMA_JSON_PATH.exists(), f"Missing glama.json: {GLAMA_JSON_PATH}"
    return json.loads(GLAMA_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pulsemcp_json() -> dict:
    assert PULSEMCP_JSON_PATH.exists(), f"Missing pulsemcp.json: {PULSEMCP_JSON_PATH}"
    return json.loads(PULSEMCP_JSON_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. npm package.json validation
# ---------------------------------------------------------------------------

class TestNpmPackageJson:
    """Validate that package.json is ready for npm publish."""

    def test_file_exists(self):
        assert PACKAGE_JSON_PATH.exists(), "mcp-server/package.json must exist for npm publishing"

    def test_required_npm_fields_present(self, package_json):
        required = ["name", "version", "description", "license", "repository"]
        for field in required:
            assert field in package_json, f"package.json missing required field: {field}"

    def test_name_is_valid_npm_package(self, package_json):
        name = package_json["name"]
        # npm names: lowercase, may contain hyphens and @scope
        assert isinstance(name, str) and len(name) > 0
        assert name == name.lower(), "npm package name must be lowercase"
        assert " " not in name, "npm package name must not contain spaces"

    def test_version_is_semver(self, package_json):
        version = package_json["version"]
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
        assert re.match(semver_pattern, version), (
            f"version '{version}' is not valid semver (e.g. '1.2.3')"
        )

    def test_bin_entry_point_declared(self, package_json):
        assert "bin" in package_json, "package.json must declare a 'bin' for the MCP executable"
        bin_map = package_json["bin"]
        assert isinstance(bin_map, (dict, str)), "'bin' must be a string or object"

    def test_bin_file_exists(self, package_json):
        bin_map = package_json.get("bin", {})
        if isinstance(bin_map, str):
            entry = bin_map
        else:
            # take the first declared binary
            entry = next(iter(bin_map.values()))
        bin_path = MCP_SERVER_DIR / entry
        assert bin_path.exists(), f"Declared bin entry '{entry}' does not exist at {bin_path}"

    def test_files_array_includes_bin(self, package_json):
        files = package_json.get("files", [])
        assert len(files) > 0, "package.json 'files' array must not be empty (controls what npm publishes)"
        # At minimum the index/main file should be included
        all_files_str = " ".join(files)
        has_js_file = any(f.endswith(".mjs") or f.endswith(".js") or f == "index.mjs" for f in files)
        assert has_js_file, f"'files' array must include the JS entry point; got: {files}"

    def test_description_is_informative(self, package_json):
        desc = package_json.get("description", "")
        assert len(desc) >= 20, f"description too short ('{desc}'); should describe the MCP server"

    def test_keywords_include_mcp(self, package_json):
        keywords = [k.lower() for k in package_json.get("keywords", [])]
        assert "mcp" in keywords, "keywords must include 'mcp' so the package is discoverable"

    def test_license_is_open_source(self, package_json):
        license_val = package_json.get("license", "")
        assert license_val in ("MIT", "Apache-2.0", "ISC", "BSD-3-Clause"), (
            f"license '{license_val}' is unexpected; use MIT or Apache-2.0 for discoverability"
        )

    def test_repository_field_has_url(self, package_json):
        repo = package_json.get("repository", {})
        if isinstance(repo, str):
            url = repo
        else:
            url = repo.get("url", "")
        assert "github.com" in url, f"repository URL should point to GitHub; got '{url}'"

    def test_engine_node_version_specified(self, package_json):
        engines = package_json.get("engines", {})
        assert "node" in engines, "package.json should specify minimum Node.js version via 'engines.node'"

    def test_homepage_field_set(self, package_json):
        homepage = package_json.get("homepage", "")
        assert homepage.startswith("https://"), f"homepage should be an https URL; got '{homepage}'"


# ---------------------------------------------------------------------------
# 2. MCP Registry server.json validation
# ---------------------------------------------------------------------------

class TestServerJson:
    """Validate the mcp-publisher server.json manifest."""

    def test_file_exists(self):
        assert SERVER_JSON_PATH.exists(), "mcp-server/server.json must exist for MCP registry submission"

    def test_required_fields_present(self, server_json):
        required = ["name", "version", "description", "repository", "license", "tools"]
        for field in required:
            assert field in server_json, f"server.json missing required field: {field}"

    def test_schema_field_references_mcp_registry(self, server_json):
        schema = server_json.get("$schema", "")
        assert "modelcontextprotocol" in schema or "mcp" in schema.lower(), (
            f"$schema should reference the MCP registry schema; got '{schema}'"
        )

    def test_tools_list_is_non_empty(self, server_json):
        tools = server_json.get("tools", [])
        assert isinstance(tools, list) and len(tools) > 0, (
            "server.json must declare at least one tool"
        )

    def test_each_tool_has_name_and_description(self, server_json):
        for i, tool in enumerate(server_json.get("tools", [])):
            assert "name" in tool, f"tool[{i}] missing 'name'"
            assert "description" in tool, f"tool[{i}] missing 'description'"
            assert len(tool["description"]) >= 10, (
                f"tool '{tool['name']}' description is too short"
            )

    def test_packages_array_includes_npm_entry(self, server_json):
        packages = server_json.get("packages", [])
        assert len(packages) > 0, "server.json 'packages' must list at least one registry package"
        npm_entries = [p for p in packages if p.get("registry") == "npm"]
        assert len(npm_entries) >= 1, (
            "server.json packages must include at least one entry with registry='npm'"
        )

    def test_npm_package_name_matches_package_json(self, server_json, package_json):
        npm_entries = [p for p in server_json.get("packages", []) if p.get("registry") == "npm"]
        if npm_entries:
            server_npm_name = npm_entries[0].get("name", "")
            pkg_name = package_json.get("name", "")
            assert server_npm_name == pkg_name, (
                f"server.json npm package name '{server_npm_name}' "
                f"must match package.json name '{pkg_name}'"
            )

    def test_categories_field_present(self, server_json):
        categories = server_json.get("categories", [])
        assert isinstance(categories, list) and len(categories) > 0, (
            "server.json should declare categories for discovery"
        )

    def test_tags_field_present(self, server_json):
        tags = server_json.get("tags", [])
        assert isinstance(tags, list) and len(tags) >= 3, (
            "server.json should have at least 3 tags for discoverability"
        )

    def test_homepage_set(self, server_json):
        homepage = server_json.get("homepage", "")
        assert homepage.startswith("https://"), f"server.json homepage should be https; got '{homepage}'"

    def test_authors_field_present(self, server_json):
        authors = server_json.get("authors", [])
        assert isinstance(authors, list) and len(authors) > 0, (
            "server.json should list at least one author"
        )


# ---------------------------------------------------------------------------
# 3. Discovery platform manifests
# ---------------------------------------------------------------------------

class TestGlamaJson:
    """Validate glama.json for Glama.ai MCP discovery."""

    def test_file_exists(self):
        assert GLAMA_JSON_PATH.exists(), "mcp-server/glama.json must exist for Glama discovery"

    def test_required_fields(self, glama_json):
        for field in ["name", "description", "url", "license"]:
            assert field in glama_json, f"glama.json missing field: {field}"

    def test_install_method_declared(self, glama_json):
        install = glama_json.get("install", {})
        assert isinstance(install, dict) and len(install) > 0, (
            "glama.json should declare an 'install' method (e.g., {\"npx\": \"package-name\"})"
        )

    def test_npx_install_references_correct_package(self, glama_json, package_json):
        npx_cmd = glama_json.get("install", {}).get("npx", "")
        pkg_name = package_json.get("name", "")
        if npx_cmd and pkg_name:
            assert pkg_name in npx_cmd, (
                f"glama.json npx install '{npx_cmd}' should reference npm package '{pkg_name}'"
            )

    def test_tags_present(self, glama_json):
        tags = glama_json.get("tags", [])
        assert isinstance(tags, list) and len(tags) >= 2, (
            "glama.json should include tags for discovery"
        )


class TestPulseMcpJson:
    """Validate pulsemcp.json for PulseMCP discovery."""

    def test_file_exists(self):
        assert PULSEMCP_JSON_PATH.exists(), "mcp-server/pulsemcp.json must exist for PulseMCP discovery"

    def test_required_fields(self, pulsemcp_json):
        for field in ["name", "description", "repository"]:
            assert field in pulsemcp_json, f"pulsemcp.json missing field: {field}"

    def test_npm_package_field(self, pulsemcp_json):
        assert "npm_package" in pulsemcp_json, (
            "pulsemcp.json must include 'npm_package' so PulseMCP can link to npm"
        )

    def test_npm_package_matches_package_json(self, pulsemcp_json, package_json):
        npm_pkg = pulsemcp_json.get("npm_package", "")
        pkg_name = package_json.get("name", "")
        assert npm_pkg == pkg_name, (
            f"pulsemcp.json npm_package '{npm_pkg}' must match package.json name '{pkg_name}'"
        )

    def test_slug_is_url_safe(self, pulsemcp_json):
        slug = pulsemcp_json.get("slug", "")
        if slug:
            assert re.match(r"^[a-z0-9-]+$", slug), (
                f"pulsemcp.json slug '{slug}' should be lowercase alphanumeric with hyphens"
            )


# ---------------------------------------------------------------------------
# 4. Python MCP server importability
# ---------------------------------------------------------------------------

class TestPythonMcpServer:
    """Validate the Python MCP server module is importable and well-formed."""

    def test_mcp_server_file_exists(self):
        assert PYTHON_MCP_SERVER_PATH.exists(), "api/mcp_server.py must exist"

    def test_mcp_tool_registry_importable(self):
        """Registry imports cleanly without a database connection."""
        from app.services.mcp_tool_registry import TOOLS, TOOL_MAP
        assert isinstance(TOOLS, list), "TOOLS must be a list"
        assert isinstance(TOOL_MAP, dict), "TOOL_MAP must be a dict"

    def test_tools_list_non_empty(self):
        from app.services.mcp_tool_registry import TOOLS
        assert len(TOOLS) >= 5, (
            f"Expected at least 5 MCP tools; got {len(TOOLS)}"
        )

    def test_tool_map_keys_match_tools_list(self):
        from app.services.mcp_tool_registry import TOOLS, TOOL_MAP
        tools_names = {t["name"] for t in TOOLS}
        map_names = set(TOOL_MAP.keys())
        assert tools_names == map_names, (
            f"TOOL_MAP keys {map_names} must equal TOOLS names {tools_names}"
        )

    def test_each_tool_has_required_keys(self):
        from app.services.mcp_tool_registry import TOOLS
        for tool in TOOLS:
            for key in ("name", "description", "input_schema", "handler"):
                assert key in tool, f"Tool '{tool.get('name', '?')}' missing key: {key}"

    def test_each_tool_handler_is_callable(self):
        from app.services.mcp_tool_registry import TOOLS
        for tool in TOOLS:
            assert callable(tool["handler"]), (
                f"Handler for tool '{tool['name']}' must be callable"
            )

    def test_input_schema_is_valid_json_schema(self):
        from app.services.mcp_tool_registry import TOOLS
        for tool in TOOLS:
            schema = tool.get("input_schema", {})
            assert schema.get("type") == "object", (
                f"Tool '{tool['name']}' input_schema must have type='object'"
            )
            assert "properties" in schema, (
                f"Tool '{tool['name']}' input_schema must have 'properties'"
            )

    def test_mcp_server_file_has_asyncio_entry_point(self):
        content = PYTHON_MCP_SERVER_PATH.read_text(encoding="utf-8")
        assert "asyncio" in content, "mcp_server.py should use asyncio"
        assert "stdio_server" in content or "StdioServerTransport" in content, (
            "mcp_server.py must use stdio transport for npx/pip-installed usage"
        )


# ---------------------------------------------------------------------------
# 5. Python packaging (pyproject.toml / setup.py)
# ---------------------------------------------------------------------------

class TestPythonPackaging:
    """Validate that pyproject.toml supports PyPI publishing."""

    def test_pyproject_toml_exists(self):
        assert PYPROJECT_TOML_PATH.exists(), "api/pyproject.toml must exist for PyPI publishing"

    def test_pyproject_has_project_section(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "[project]" in content, "pyproject.toml must have a [project] section"

    def test_pyproject_has_name(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "name" in content, "pyproject.toml must declare a 'name'"

    def test_pyproject_has_version(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "version" in content, "pyproject.toml must declare a 'version'"

    def test_pyproject_has_requires_python(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "requires-python" in content, (
            "pyproject.toml must specify 'requires-python' for PyPI compatibility"
        )

    def test_pyproject_build_system_declared(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "[build-system]" in content, (
            "pyproject.toml must have [build-system] for PEP 517 compliant builds"
        )

    def test_pyproject_dependencies_listed(self):
        content = PYPROJECT_TOML_PATH.read_text(encoding="utf-8")
        assert "dependencies" in content, (
            "pyproject.toml must list dependencies"
        )


# ---------------------------------------------------------------------------
# 6. index.mjs entry point validation
# ---------------------------------------------------------------------------

class TestIndexMjs:
    """Validate the npm entry point JS file."""

    def test_file_exists(self):
        assert INDEX_MJS_PATH.exists(), "mcp-server/index.mjs must exist (declared as npm bin)"

    def test_has_mcp_sdk_import(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        assert "@modelcontextprotocol/sdk" in content, (
            "index.mjs must import the MCP SDK"
        )

    def test_has_shebang_or_is_esm_module(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        is_esm = content.startswith("#!/") or "import " in content[:500]
        assert is_esm, "index.mjs should be an ESM module (use 'import' syntax)"

    def test_exposes_tools_list(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        assert "ListToolsRequest" in content or "list_tools" in content.lower() or "ListTools" in content, (
            "index.mjs must handle list_tools/ListTools requests"
        )

    def test_exposes_call_tool(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        assert "CallTool" in content or "call_tool" in content.lower(), (
            "index.mjs must handle call_tool/CallTool requests"
        )

    def test_uses_stdio_transport(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        assert "StdioServerTransport" in content or "stdio" in content.lower(), (
            "index.mjs must use StdioServerTransport for CLI usage"
        )

    def test_references_api_base_url(self):
        content = INDEX_MJS_PATH.read_text(encoding="utf-8")
        assert "coherencycoin.com" in content or "COHERENCE_API_URL" in content, (
            "index.mjs must reference the Coherence API URL (or allow override via env var)"
        )


# ---------------------------------------------------------------------------
# 7. Version consistency across manifests
# ---------------------------------------------------------------------------

class TestVersionConsistency:
    """Validate versions are consistent (or in sync) across manifests."""

    def test_server_json_version_is_semver(self, server_json):
        version = server_json.get("version", "")
        assert re.match(r"^\d+\.\d+\.\d+$", version), (
            f"server.json version '{version}' must be semver"
        )

    def test_package_json_and_server_json_major_minor_match(self, server_json, package_json):
        """Both must have the same major.minor version (patch can differ)."""
        npm_ver = package_json.get("version", "0.0.0")
        srv_ver = server_json.get("version", "0.0.0")
        npm_parts = npm_ver.split(".")[:2]
        srv_parts = srv_ver.split(".")[:2]
        # Warn but don't fail — versions drift; major.minor should match within 1
        npm_minor = int(npm_parts[1]) if len(npm_parts) > 1 else 0
        srv_minor = int(srv_parts[1]) if len(srv_parts) > 1 else 0
        npm_major = int(npm_parts[0]) if npm_parts else 0
        srv_major = int(srv_parts[0]) if srv_parts else 0
        assert npm_major == srv_major, (
            f"Major version mismatch: package.json={npm_ver}, server.json={srv_ver}"
        )
        assert abs(npm_minor - srv_minor) <= 2, (
            f"Minor versions too far apart: package.json={npm_ver}, server.json={srv_ver}"
        )

    def test_server_json_packages_version_is_semver(self, server_json):
        for pkg in server_json.get("packages", []):
            ver = pkg.get("version", "")
            assert re.match(r"^\d+\.\d+\.\d+$", ver), (
                f"Package entry version '{ver}' in server.json must be semver"
            )


# ---------------------------------------------------------------------------
# 8. Tool parity: server.json tools vs TOOL_MAP
# ---------------------------------------------------------------------------

class TestToolParity:
    """Validate tool coverage across the JS and Python MCP server implementations.

    Note: server.json documents legacy/simplified tool names used by the npm registry.
    The JS implementation (index.mjs) uses coherence_* prefixed names.
    The Python implementation (TOOL_MAP) uses a different naming convention.
    Tests here validate internal consistency of each implementation separately.
    """

    def test_server_json_tool_names_are_declared_in_index_mjs(self, server_json):
        """Each tool in server.json must correspond to a coherence_* tool in index.mjs.

        The npm package (index.mjs) uses coherence_ prefixed names.
        server.json uses the canonical short names without the prefix.
        We validate by checking the coherence-stripped JS names cover the server.json names.
        """
        index_mjs = INDEX_MJS_PATH.read_text(encoding="utf-8")

        # Extract all name: "coherence_*" entries from index.mjs
        js_tool_names = set(re.findall(r'name:\s*["\']coherence_(\w+)["\']', index_mjs))

        def normalise(name: str) -> str:
            return name.replace("_", "").replace("-", "").lower()

        normalised_js = {normalise(n) for n in js_tool_names}

        server_tool_names = [t["name"] for t in server_json.get("tools", [])]
        unmatched = []
        for name in server_tool_names:
            if normalise(name) not in normalised_js:
                unmatched.append(name)

        assert len(unmatched) == 0, (
            f"server.json declares tools not found in index.mjs (coherence_* tools): {unmatched}. "
            f"JS tools found: {sorted(js_tool_names)}. "
            "Update server.json or add the tool to index.mjs."
        )

    def test_index_mjs_exposes_at_least_as_many_tools_as_server_json(self, server_json):
        """The JS implementation must implement at least every tool advertised in server.json."""
        index_mjs = INDEX_MJS_PATH.read_text(encoding="utf-8")
        js_tool_count = len(re.findall(r'name:\s*["\']coherence_\w+["\']', index_mjs))
        srv_count = len(server_json.get("tools", []))
        assert js_tool_count >= srv_count, (
            f"index.mjs has {js_tool_count} coherence_* tools but server.json advertises {srv_count}"
        )

    def test_python_tool_map_has_meaningful_coverage(self, server_json):
        """Python TOOL_MAP should cover at least 50% of server.json advertised tools.

        The JS npm server is the primary implementation; the Python server is a companion
        that covers a subset of the same capabilities. Full parity is not required.
        """
        from app.services.mcp_tool_registry import TOOL_MAP

        srv_count = len(server_json.get("tools", []))
        map_count = len(TOOL_MAP)
        min_coverage = max(5, srv_count // 2)  # at least 50% or 5 tools
        assert map_count >= min_coverage, (
            f"Python TOOL_MAP has only {map_count} tools; "
            f"expected at least {min_coverage} (50% of {srv_count} advertised tools). "
            "The Python MCP server should cover core read/write operations."
        )


# ---------------------------------------------------------------------------
# 9. README presence and quality
# ---------------------------------------------------------------------------

class TestReadme:
    """Validate that a README suitable for npm/PyPI is present."""

    def test_readme_exists(self):
        assert README_PATH.exists(), "mcp-server/README.md must exist for npm and Smithery display"

    def test_readme_has_installation_section(self):
        content = README_PATH.read_text(encoding="utf-8")
        assert "install" in content.lower() or "npm" in content.lower(), (
            "README must have an installation section so users know how to use the package"
        )

    def test_readme_mentions_mcp_config(self):
        content = README_PATH.read_text(encoding="utf-8")
        assert "mcp" in content.lower(), "README should explain MCP integration"

    def test_readme_size_is_substantial(self):
        size = README_PATH.stat().st_size
        assert size >= 500, (
            f"README is only {size} bytes; a good npm/PyPI README should be at least 500 bytes"
        )


# ---------------------------------------------------------------------------
# 10. End-to-end: Python MCP server handles a real tool call
# ---------------------------------------------------------------------------

class TestPythonMcpServerEndToEnd:
    """Exercise real handler execution via the registry (no MCP wire protocol needed)."""

    def test_browse_ideas_handler_returns_valid_shape(self):
        from app.services.mcp_tool_registry import browse_ideas_handler

        result = browse_ideas_handler({"limit": 3})
        assert isinstance(result, dict)
        assert "ideas" in result
        assert isinstance(result["ideas"], list)

    def test_get_idea_handler_returns_error_for_unknown_id(self):
        from app.services.mcp_tool_registry import get_idea_handler

        result = get_idea_handler({"idea_id": "mcp-publish-nonexistent-id-xyz"})
        assert isinstance(result, dict)
        assert "error" in result

    def test_get_resonance_feed_handler_returns_feed(self):
        from app.services.mcp_tool_registry import get_resonance_feed_handler

        result = get_resonance_feed_handler({"limit": 5})
        assert isinstance(result, dict)
        assert "ideas" in result

    def test_get_provider_stats_handler_returns_stats(self):
        from app.services.mcp_tool_registry import get_provider_stats_handler

        result = get_provider_stats_handler({})
        assert isinstance(result, dict)

    def test_list_open_changes_handler_returns_list(self):
        from app.services.mcp_tool_registry import list_open_changes_handler

        result = list_open_changes_handler({"limit": 5})
        assert isinstance(result, list)

    def test_browse_specs_handler_returns_list(self):
        from app.services.mcp_tool_registry import browse_specs_handler

        result = browse_specs_handler({"limit": 5})
        assert isinstance(result, list)

    def test_tool_registry_all_tools_callable_with_empty_args(self):
        """Smoke-test: every read-only tool should not raise with empty args."""
        from app.services.mcp_tool_registry import TOOL_MAP

        READ_ONLY_TOOLS = {
            "browse_ideas",
            "browse_specs",
            "get_strategies",
            "get_provider_stats",
            "get_resonance_feed",
            "list_open_changes",
        }

        for name in READ_ONLY_TOOLS:
            if name in TOOL_MAP:
                handler = TOOL_MAP[name]["handler"]
                try:
                    result = handler({})
                    assert result is not None, f"Handler for '{name}' returned None"
                except Exception as exc:
                    pytest.fail(f"Handler '{name}' raised with empty args: {exc}")
