"""Flow-centric CLI tests: command registration, API coverage, API contract, and smoke tests.

Tests CLI command registration via static source analysis of cli/bin/coh.mjs,
verifies CLI files reference critical API endpoints, confirms API endpoint
response shapes via httpx AsyncClient, and runs end-to-end subprocess smoke
tests against a real uvicorn server.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn

from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLI_DIR = Path(__file__).resolve().parent.parent.parent / "cli"
CLI_BIN = CLI_DIR / "bin" / "coh.mjs"
CLI_COMMANDS_DIR = CLI_DIR / "lib" / "commands"
CLI_PACKAGE_JSON = CLI_DIR / "package.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# ---------------------------------------------------------------------------
# Command Registration Tests (static source analysis)
# ---------------------------------------------------------------------------


class TestCommandRegistration:
    """Static analysis of cli/bin/coh.mjs to verify command registration."""

    def test_cli_entrypoint_exists(self) -> None:
        """coh.mjs file exists and is executable."""
        assert CLI_BIN.exists(), f"Missing CLI entry point: {CLI_BIN}"
        assert os.access(CLI_BIN, os.X_OK), f"coh.mjs is not executable: {CLI_BIN}"

    def test_core_commands_registered(self) -> None:
        """COMMANDS map includes: ideas, identity, nodes, status, tasks, stake, fork, specs, help."""
        source = CLI_BIN.read_text(encoding="utf-8")
        required_commands = [
            "ideas", "identity", "nodes", "status", "tasks",
            "stake", "fork", "specs", "help",
        ]
        for cmd in required_commands:
            assert f"{cmd}:" in source or f"'{cmd}'" in source or f'"{cmd}"' in source, (
                f"Command '{cmd}' not found in COMMANDS map in coh.mjs"
            )

    def test_command_files_exist(self) -> None:
        """Each command name in the COMMANDS map references a .mjs file in cli/lib/commands/."""
        source = CLI_BIN.read_text(encoding="utf-8")
        # Extract import paths from coh.mjs that reference ../lib/commands/*.mjs
        import_pattern = re.compile(r'from\s+"\.\.\/lib\/commands\/([^"]+\.mjs)"')
        imported_files = set(import_pattern.findall(source))
        assert imported_files, "No command imports found in coh.mjs"
        for filename in imported_files:
            cmd_path = CLI_COMMANDS_DIR / filename
            assert cmd_path.exists(), f"Imported command file missing: {cmd_path}"

    def test_no_orphan_command_files(self) -> None:
        """Every .mjs file in commands/ is referenced in coh.mjs imports (known legacy orphans excluded)."""
        source = CLI_BIN.read_text(encoding="utf-8")
        import_pattern = re.compile(r'from\s+"\.\.\/lib\/commands\/([^"]+\.mjs)"')
        imported_files = set(import_pattern.findall(source))

        actual_files = {f.name for f in CLI_COMMANDS_DIR.glob("*.mjs")}
        # Legacy command files that exist but are not wired into coh.mjs
        known_orphans = {"federation.mjs", "inventory.mjs", "runtime.mjs"}
        orphans = actual_files - imported_files - known_orphans
        assert not orphans, (
            f"Orphan command files not imported in coh.mjs: {sorted(orphans)}"
        )

    def test_package_json_valid(self) -> None:
        """cli/package.json has name, version, and bin fields."""
        assert CLI_PACKAGE_JSON.exists(), f"Missing: {CLI_PACKAGE_JSON}"
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        assert "name" in pkg, "package.json missing 'name' field"
        assert "version" in pkg, "package.json missing 'version' field"
        assert "bin" in pkg, "package.json missing 'bin' field"
        assert isinstance(pkg["bin"], dict), "package.json 'bin' must be a dict"
        assert "coh" in pkg["bin"], "'coh' not found in package.json bin field"
        assert "cc" not in pkg["bin"], (
            "'cc' must not be registered (shadows Apple clang on macOS)"
        )


# ---------------------------------------------------------------------------
# API Coverage Tests (verify CLI files reference critical endpoints)
# ---------------------------------------------------------------------------


class TestAPICoverage:
    """Verify CLI command files reference all critical API endpoints."""

    @pytest.fixture(scope="class")
    def cli_source_combined(self) -> str:
        """Concatenate all CLI lib source files for endpoint searching."""
        parts = []
        for mjs in CLI_DIR.rglob("*.mjs"):
            try:
                parts.append(mjs.read_text(encoding="utf-8"))
            except Exception:
                pass
        return "\n".join(parts)

    def test_ideas_endpoints_covered(self, cli_source_combined: str) -> None:
        """CLI files reference /api/ideas endpoints."""
        assert "/api/ideas" in cli_source_combined, (
            "No reference to /api/ideas found in CLI source files"
        )

    def test_agent_endpoints_covered(self, cli_source_combined: str) -> None:
        """CLI files reference /api/agent/tasks endpoints."""
        assert "/api/agent/tasks" in cli_source_combined, (
            "No reference to /api/agent/tasks found in CLI source files"
        )

    def test_federation_endpoints_covered(self, cli_source_combined: str) -> None:
        """CLI files reference /api/federation endpoints."""
        assert "/api/federation" in cli_source_combined, (
            "No reference to /api/federation found in CLI source files"
        )

    def test_health_endpoint_covered(self, cli_source_combined: str) -> None:
        """CLI files reference /api/health or /api/ping."""
        has_health = "/api/health" in cli_source_combined
        has_ping = "/api/ping" in cli_source_combined
        assert has_health or has_ping, (
            "No reference to /api/health or /api/ping found in CLI source files"
        )


# ---------------------------------------------------------------------------
# API Contract Tests (httpx AsyncClient against app)
# ---------------------------------------------------------------------------


class TestAPIContract:
    """Verify HTTP endpoints that the CLI depends on exist and return expected shapes."""

    @pytest.mark.asyncio
    async def test_ideas_list_endpoint_shape(self) -> None:
        """GET /api/ideas returns dict with ideas list and pagination."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/ideas")
            assert r.status_code == 200
            body = r.json()
            # Response is a dict with ideas key containing the list
            assert isinstance(body, dict), f"Expected dict, got {type(body).__name__}"
            assert "ideas" in body, f"Missing 'ideas' key: {list(body.keys())}"
            assert isinstance(body["ideas"], list)

    @pytest.mark.asyncio
    async def test_tasks_list_endpoint_shape(self) -> None:
        """GET /api/agent/tasks returns {tasks, total}."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/tasks")
            assert r.status_code == 200
            body = r.json()
            assert "tasks" in body, f"Missing 'tasks' key in response: {list(body.keys())}"
            assert "total" in body, f"Missing 'total' key in response: {list(body.keys())}"

    @pytest.mark.asyncio
    async def test_nodes_list_endpoint_shape(self) -> None:
        """GET /api/federation/nodes returns list."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/federation/nodes")
            assert r.status_code == 200
            body = r.json()
            assert isinstance(body, list), f"Expected list, got {type(body).__name__}"

    @pytest.mark.asyncio
    async def test_health_endpoint_shape(self) -> None:
        """GET /api/health returns {status, version}."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/health")
            assert r.status_code == 200
            body = r.json()
            assert "status" in body, f"Missing 'status' key: {list(body.keys())}"
            assert "version" in body, f"Missing 'version' key: {list(body.keys())}"

    @pytest.mark.asyncio
    async def test_pipeline_status_shape(self) -> None:
        """GET /api/agent/pipeline-status returns expected keys."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/agent/pipeline-status")
            assert r.status_code == 200
            body = r.json()
            for key in ("running", "pending", "recent_completed"):
                assert key in body, f"Missing '{key}' key in pipeline-status response"

    @pytest.mark.asyncio
    async def test_providers_endpoint_shape(self) -> None:
        """GET /api/providers returns list of providers."""
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/providers")
            assert r.status_code == 200
            body = r.json()
            assert "providers" in body, f"Missing 'providers' key: {list(body.keys())}"
            assert isinstance(body["providers"], list)


# ---------------------------------------------------------------------------
# Smoke Tests (subprocess against real CLI binary)
# ---------------------------------------------------------------------------

_NODE = shutil.which("node") or "/opt/homebrew/bin/node"
_NPM = shutil.which("npm") or "/opt/homebrew/bin/npm"


def _ensure_cli_deps() -> str | None:
    """Install cli/node_modules if missing. Returns a skip reason if install fails.

    Runs once per test session (idempotent if the lockfile hasn't changed) so the
    CLI subprocess tests don't silently fail from a missing dependency — the
    package-lock.json is the source of truth, and we keep the working tree
    aligned with it.
    """
    if (CLI_DIR / "node_modules" / "chalk").exists():
        return None
    if not Path(_NPM).exists():
        return "npm not found; cannot install CLI dependencies"
    try:
        result = subprocess.run(
            [_NPM, "install", "--prefer-offline", "--no-audit", "--no-fund"],
            cwd=str(CLI_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return f"npm install failed: {exc}"
    if result.returncode != 0:
        return f"npm install exited {result.returncode}: {result.stderr[-500:]}"
    return None


@pytest.fixture(scope="module", autouse=True)
def _cli_deps_installed():
    skip_reason = _ensure_cli_deps()
    if skip_reason:
        pytest.skip(skip_reason, allow_module_level=False)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_app():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[assignment]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("uvicorn test server exited before startup")
        if time.time() > deadline:
            raise RuntimeError("timed out waiting for uvicorn test server")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _write_cli_config(home_dir: Path, *, api_base: str | None = None) -> None:
    config_dir = home_dir / ".coherence-network"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    payload: dict = {}
    if api_base:
        payload["hub_url"] = api_base
    config_path.write_text(json.dumps(payload), encoding="utf-8")


def _run_cli(api_base: str, *args: str) -> subprocess.CompletedProcess:
    """Run the CLI binary via subprocess, returning the CompletedProcess."""
    with tempfile.TemporaryDirectory() as home:
        _write_cli_config(Path(home), api_base=api_base)
        env = os.environ.copy()
        env["HOME"] = home
        env.pop("COHERENCE_API_URL", None)
        env.pop("COHERENCE_HUB_URL", None)
        env.pop("COHERENCE_API_KEY", None)
        return subprocess.run(
            [_NODE, str(CLI_BIN), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=env,
        )


@pytest.mark.skipif(not Path(_NODE).exists(), reason="node not found")
class TestSmokeTests:
    """Run actual CLI binary via subprocess against a real uvicorn server."""

    def test_cli_help_exits_zero(self) -> None:
        """coh help exits 0."""
        with _serve_app() as api_base:
            result = _run_cli(api_base, "help")
        assert result.returncode == 0, (
            f"coh help exited {result.returncode}: {result.stderr}"
        )

    def test_cli_status_runs(self) -> None:
        """coh status exits 0 and outputs something."""
        with _serve_app() as api_base:
            result = _run_cli(api_base, "status")
        assert result.returncode == 0, (
            f"coh status exited {result.returncode}: {result.stderr}"
        )
        output = ANSI_RE.sub("", result.stdout)
        assert len(output.strip()) > 0, "coh status produced no output"

    def test_cli_ideas_list(self) -> None:
        """coh ideas hits the API and returns formatted output."""
        with _serve_app() as api_base:
            result = _run_cli(api_base, "ideas")
        assert result.returncode == 0, (
            f"coh ideas exited {result.returncode}: {result.stderr}"
        )
        output = ANSI_RE.sub("", result.stdout)
        assert len(output.strip()) > 0, "coh ideas produced no output"

    def test_cli_nodes_list(self) -> None:
        """coh nodes hits the API."""
        with _serve_app() as api_base:
            result = _run_cli(api_base, "nodes")
        assert result.returncode == 0, (
            f"coh nodes exited {result.returncode}: {result.stderr}"
        )

    def test_cli_identity_runs(self) -> None:
        """coh identity exits 0."""
        with _serve_app() as api_base:
            result = _run_cli(api_base, "identity")
        assert result.returncode == 0, (
            f"coh identity exited {result.returncode}: {result.stderr}"
        )
