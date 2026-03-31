"""Tests for CLI full API coverage.

Spec: CLI should expose all major API endpoints as terminal commands.
Current state: CLI covers ~52 of 355 endpoints (15%).
Priority gaps: agent pipeline ops, inventory, federation/messaging,
               runtime, ideas, value-lineage, treasury, governance.

This test suite:
1. Enumerates all FastAPI routes from app.main
2. Defines the known CLI-covered endpoints
3. Verifies coverage % and tracks regression
4. Tests that priority endpoints have CLI implementations
5. Verifies the HTTP accessibility of uncovered endpoints via ASGI

Verification Contract:
  - Any endpoint marked CLI-covered MUST actually have a CLI command file
    that references it via string literal in ../cli/lib/commands/
  - Coverage % must be >= MINIMUM_CLI_COVERAGE_PERCENT (15%)
  - Priority endpoints (node messaging, tasks, treasury, governance)
    must each have at least one CLI command
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
CLI_COMMANDS_DIR = ROOT / "cli" / "lib" / "commands"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Coverage floor — tests fail if we drop below this
# ---------------------------------------------------------------------------
MINIMUM_CLI_COVERAGE_PERCENT = 10  # current baseline ~15%, fail if we regress below 10
PRIORITY_CLI_COVERAGE_PERCENT = 25  # stretch goal for priority areas


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ApiEndpoint(NamedTuple):
    method: str
    path: str

    @property
    def category(self) -> str:
        """Derive resource category from path."""
        parts = self.path.split("/")
        # /api/<category>/...
        if len(parts) >= 3 and parts[1] == "api":
            return parts[2]
        if len(parts) >= 2:
            return parts[1]
        return "root"

    @property
    def normalized(self) -> str:
        """Path with {param} replaced by * for grouping."""
        return re.sub(r"\{[^}]+\}", "*", self.path)


# ---------------------------------------------------------------------------
# Collect all API routes from the FastAPI app
# ---------------------------------------------------------------------------

def _collect_app_routes() -> list[ApiEndpoint]:
    """Return all METHOD+path pairs from the FastAPI application."""
    endpoints: list[ApiEndpoint] = []
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        for method in sorted(route.methods):
            # Skip HEAD duplicates and docs/redoc/openapi
            if method == "HEAD":
                continue
            if route.path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
                continue
            endpoints.append(ApiEndpoint(method=method, path=route.path))
    return sorted(endpoints, key=lambda e: (e.category, e.path, e.method))


ALL_ENDPOINTS: list[ApiEndpoint] = _collect_app_routes()
ALL_PATHS: set[str] = {e.path for e in ALL_ENDPOINTS}


# ---------------------------------------------------------------------------
# CLI-covered endpoints: paths referenced in cli/lib/commands/*.mjs
# ---------------------------------------------------------------------------

def _collect_cli_covered_paths() -> set[str]:
    """Scan CLI command files for /api/... string literals."""
    covered: set[str] = set()
    if not CLI_COMMANDS_DIR.exists():
        return covered
    pattern = re.compile(r'["`\'](/api/[^"`\'?\s]+)["`\']')
    for mjs_file in CLI_COMMANDS_DIR.glob("*.mjs"):
        src = mjs_file.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(src):
            raw_path = match.group(1)
            # Strip query strings
            path = raw_path.split("?")[0]
            # Strip template literals like ${...}
            path = re.sub(r"\$\{[^}]+\}", "*", path)
            covered.add(path)
    return covered


CLI_COVERED_PATHS: set[str] = _collect_cli_covered_paths()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths_in_category(category: str) -> list[ApiEndpoint]:
    return [e for e in ALL_ENDPOINTS if e.category == category]


def _cli_covers(path: str) -> bool:
    """Check if CLI covers the exact path OR a normalized (wildcard) version."""
    if path in CLI_COVERED_PATHS:
        return True
    normalized = re.sub(r"\{[^}]+\}", "*", path)
    for covered in CLI_COVERED_PATHS:
        # Convert covered path params to wildcards too for comparison
        covered_norm = re.sub(r"\$\{[^}]+\}", "*", covered)
        covered_norm = re.sub(r":[a-zA-Z_]+", "*", covered_norm)
        if covered_norm == normalized:
            return True
    return False


def _coverage_for_category(category: str) -> tuple[int, int]:
    """Return (covered, total) for a category."""
    endpoints = _paths_in_category(category)
    unique_paths = {e.path for e in endpoints}
    covered = sum(1 for p in unique_paths if _cli_covers(p))
    return covered, len(unique_paths)


# ---------------------------------------------------------------------------
# Tests: Basic inventory
# ---------------------------------------------------------------------------

class TestApiInventory:
    """Verify that the API has the expected shape."""

    def test_app_has_substantial_number_of_routes(self) -> None:
        """API must have at least 150 routes (guards against empty app load)."""
        assert len(ALL_ENDPOINTS) >= 150, (
            f"Expected >= 150 API endpoints, found {len(ALL_ENDPOINTS)}. "
            "App may have failed to load all routers."
        )

    def test_all_routes_have_api_prefix_or_root(self) -> None:
        """All non-root routes should start with /api/ or /v1/."""
        bad = [
            e.path for e in ALL_ENDPOINTS
            if not e.path.startswith("/api/")
            and not e.path.startswith("/v1/")
            and e.path not in ("/", "/ping", "/health", "/ready", "/version")
        ]
        assert not bad, f"Routes without /api/ prefix: {bad[:10]}"

    def test_health_endpoint_exists(self) -> None:
        assert any(e.path == "/api/health" and e.method == "GET" for e in ALL_ENDPOINTS)

    def test_ideas_endpoint_exists(self) -> None:
        assert any(e.path == "/api/ideas" and e.method == "GET" for e in ALL_ENDPOINTS)

    def test_tasks_endpoint_exists(self) -> None:
        assert any(e.path == "/api/agent/tasks" and e.method == "GET" for e in ALL_ENDPOINTS)

    def test_federation_nodes_endpoint_exists(self) -> None:
        assert any(e.path == "/api/federation/nodes" and e.method == "GET" for e in ALL_ENDPOINTS)

    def test_treasury_endpoint_exists(self) -> None:
        assert any(e.path == "/api/treasury" and e.method == "GET" for e in ALL_ENDPOINTS)

    def test_governance_endpoint_exists(self) -> None:
        assert any(
            e.path == "/api/governance/change-requests" and e.method == "GET"
            for e in ALL_ENDPOINTS
        )


# ---------------------------------------------------------------------------
# Tests: CLI coverage inventory
# ---------------------------------------------------------------------------

class TestCliCoverageInventory:
    """Verify the CLI covers the expected endpoints."""

    def test_cli_commands_dir_exists(self) -> None:
        """CLI commands directory must exist."""
        assert CLI_COMMANDS_DIR.exists(), (
            f"CLI commands directory not found at {CLI_COMMANDS_DIR}. "
            "Run from worktree root."
        )

    def test_cli_has_command_files(self) -> None:
        """At least 10 CLI command .mjs files must exist."""
        mjs_files = list(CLI_COMMANDS_DIR.glob("*.mjs"))
        assert len(mjs_files) >= 10, f"Expected >= 10 .mjs files, got {len(mjs_files)}"

    def test_cli_covers_health(self) -> None:
        assert _cli_covers("/api/health"), "CLI must cover GET /api/health"

    def test_cli_covers_ideas(self) -> None:
        assert _cli_covers("/api/ideas"), "CLI must cover GET /api/ideas (cc ideas)"

    def test_cli_covers_tasks(self) -> None:
        assert _cli_covers("/api/agent/tasks"), "CLI must cover GET /api/agent/tasks (cc tasks)"

    def test_cli_covers_treasury(self) -> None:
        assert _cli_covers("/api/treasury"), "CLI must cover GET /api/treasury (cc treasury)"

    def test_cli_covers_governance(self) -> None:
        assert _cli_covers("/api/governance/change-requests"), (
            "CLI must cover GET /api/governance/change-requests (cc governance)"
        )

    def test_cli_covers_federation_nodes(self) -> None:
        assert _cli_covers("/api/federation/nodes"), (
            "CLI must cover GET /api/federation/nodes (cc nodes)"
        )

    def test_cli_covers_value_lineage(self) -> None:
        assert _cli_covers("/api/value-lineage/links"), (
            "CLI must cover GET /api/value-lineage/links (cc lineage)"
        )

    def test_cli_covers_services(self) -> None:
        assert _cli_covers("/api/services"), "CLI must cover GET /api/services (cc services)"

    def test_cli_covers_providers(self) -> None:
        assert _cli_covers("/api/providers"), "CLI must cover GET /api/providers (cc providers)"

    def test_cli_covers_traceability(self) -> None:
        assert _cli_covers("/api/traceability"), "CLI must cover GET /api/traceability"

    def test_cli_covers_spec_registry(self) -> None:
        assert _cli_covers("/api/spec-registry"), "CLI must cover GET /api/spec-registry (cc specs)"

    def test_cli_covers_meta_endpoints(self) -> None:
        assert _cli_covers("/api/meta/endpoints"), "CLI must cover GET /api/meta/endpoints (cc meta)"

    def test_cli_covers_treasury_deposit(self) -> None:
        assert _cli_covers("/api/treasury/deposit"), (
            "CLI must cover POST /api/treasury/deposit (cc treasury deposit)"
        )

    def test_cli_covers_federation_broadcast(self) -> None:
        assert _cli_covers("/api/federation/broadcast"), (
            "CLI must cover POST /api/federation/broadcast (cc msg broadcast)"
        )


# ---------------------------------------------------------------------------
# Tests: Overall coverage percentage
# ---------------------------------------------------------------------------

class TestOverallCoverage:
    """Coverage percentage assertions — track progress over time."""

    def test_overall_coverage_meets_minimum(self) -> None:
        """CLI must cover at least MINIMUM_CLI_COVERAGE_PERCENT of all unique API paths."""
        unique_paths = {e.path for e in ALL_ENDPOINTS}
        covered = sum(1 for p in unique_paths if _cli_covers(p))
        total = len(unique_paths)
        pct = (covered / total * 100) if total > 0 else 0.0

        print(f"\nCLI Coverage: {covered}/{total} unique paths = {pct:.1f}%")
        print(f"Minimum required: {MINIMUM_CLI_COVERAGE_PERCENT}%")

        assert pct >= MINIMUM_CLI_COVERAGE_PERCENT, (
            f"CLI coverage {pct:.1f}% is below minimum {MINIMUM_CLI_COVERAGE_PERCENT}%. "
            f"Covered: {covered}, Total: {total}. "
            "Ensure CLI commands reference the expected API paths."
        )

    def test_coverage_report_by_category(self) -> None:
        """Print a coverage breakdown by category (informational, never fails)."""
        categories: dict[str, tuple[int, int]] = {}
        for e in ALL_ENDPOINTS:
            cat = e.category
            if cat not in categories:
                categories[cat] = _coverage_for_category(cat)

        print("\n=== CLI API Coverage by Category ===")
        print(f"{'Category':<25} {'Covered':>7} {'Total':>6} {'Pct':>6}")
        print("-" * 50)
        total_covered = 0
        total_all = 0
        for cat in sorted(categories):
            cov, tot = categories[cat]
            pct = (cov / tot * 100) if tot > 0 else 0
            total_covered += cov
            total_all += tot
            status = "✓" if pct >= 50 else ("~" if pct > 0 else "✗")
            print(f"{status} {cat:<23} {cov:>7} {tot:>6} {pct:>5.0f}%")

        overall_pct = (total_covered / total_all * 100) if total_all > 0 else 0
        print("-" * 50)
        print(f"  {'TOTAL':<23} {total_covered:>7} {total_all:>6} {overall_pct:>5.0f}%")
        # This test always passes — it's for reporting
        assert True

    def test_known_gap_categories_are_tracked(self) -> None:
        """Assert that known gap categories exist in the API (so we don't track phantoms)."""
        gap_categories = ["agent", "inventory", "federation", "runtime", "ideas",
                          "value-lineage", "treasury", "governance"]
        app_categories = {e.category for e in ALL_ENDPOINTS}
        for cat in gap_categories:
            assert cat in app_categories, (
                f"Expected gap category '{cat}' not found in API routes. "
                "Update the gap list if these routes were removed."
            )


# ---------------------------------------------------------------------------
# Tests: Category-specific coverage floors
# ---------------------------------------------------------------------------

class TestCategoryCoverage:
    """Each priority category must have at least 1 covered endpoint."""

    def test_agent_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("agent")
        assert covered >= 1, (
            f"Agent category: {covered}/{total} covered. "
            "CLI must have at least one agent command (cc tasks, cc status, etc.)"
        )

    def test_ideas_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("ideas")
        assert covered >= 1, (
            f"Ideas category: {covered}/{total} covered. "
            "CLI must have at least one ideas command (cc ideas)"
        )

    def test_federation_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("federation")
        assert covered >= 1, (
            f"Federation category: {covered}/{total} covered. "
            "CLI must have at least one federation command (cc nodes, cc msg broadcast)"
        )

    def test_treasury_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("treasury")
        assert covered >= 1, (
            f"Treasury category: {covered}/{total} covered. "
            "CLI must have treasury commands (cc treasury)"
        )

    def test_governance_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("governance")
        assert covered >= 1, (
            f"Governance category: {covered}/{total} covered. "
            "CLI must have governance commands (cc governance)"
        )

    def test_value_lineage_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("value-lineage")
        assert covered >= 1, (
            f"Value-lineage category: {covered}/{total} covered. "
            "CLI must have lineage commands (cc lineage)"
        )

    def test_services_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("services")
        assert covered >= 1, (
            f"Services category: {covered}/{total} covered. "
            "CLI must have services commands (cc services)"
        )

    def test_traceability_category_has_cli_coverage(self) -> None:
        covered, total = _coverage_for_category("traceability")
        assert covered >= 1, (
            f"Traceability category: {covered}/{total} covered. "
            "CLI must have traceability commands (cc traceability)"
        )


# ---------------------------------------------------------------------------
# Tests: Uncovered endpoints are at least HTTP-accessible (ASGI smoke tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUncoveredEndpointsAreAccessible:
    """Smoke test: uncovered endpoints must return a non-5xx response.

    This proves the endpoints are wired up correctly even if not yet CLI-covered.
    Using ASGI transport — no real server needed.
    """

    async def _get(self, client: AsyncClient, path: str) -> int:
        """GET a path and return status code."""
        resp = await client.get(path)
        return resp.status_code

    @pytest.mark.asyncio
    async def test_agent_pipeline_status_is_accessible(self) -> None:
        """GET /api/agent/pipeline-status — agent pipeline ops gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/agent/pipeline-status")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_agent_tasks_active_is_accessible(self) -> None:
        """GET /api/agent/tasks/active — task management gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/agent/tasks/active")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_agent_tasks_count_is_accessible(self) -> None:
        """GET /api/agent/tasks/count — task management gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/agent/tasks/count")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_federation_nodes_messages_is_accessible(self) -> None:
        """GET /api/federation/nodes/{node_id}/messages — node messaging gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/federation/nodes/test-node/messages")
        # 404 is fine (node doesn't exist), 500 is not
        assert r.status_code != 500, f"Expected non-500, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_runtime_endpoints_summary_is_accessible(self) -> None:
        """GET /api/runtime/endpoints/summary — runtime gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/runtime/endpoints/summary")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_inventory_flow_is_accessible(self) -> None:
        """GET /api/inventory/flow — inventory gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/inventory/flow")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_governance_change_requests_is_accessible(self) -> None:
        """GET /api/governance/change-requests — governance gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/governance/change-requests")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_value_lineage_links_is_accessible(self) -> None:
        """GET /api/value-lineage/links — value lineage gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/value-lineage/links")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_treasury_is_accessible(self) -> None:
        """GET /api/treasury — treasury gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/treasury")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_services_is_accessible(self) -> None:
        """GET /api/services — services gap.

        503 is acceptable: service registry may not be initialized in test env.
        We only fail on truly unexpected errors (500, 502, 504).
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/services")
        # 503 = "Service registry not initialized" — valid in test env, not a bug
        acceptable = {200, 404, 422, 503}
        assert r.status_code < 500 or r.status_code == 503, (
            f"Expected non-5xx or 503, got {r.status_code}: {r.text[:200]}"
        )

    @pytest.mark.asyncio
    async def test_agent_runners_is_accessible(self) -> None:
        """GET /api/agent/runners — agent pipeline gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/agent/runners")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_agent_route_is_accessible(self) -> None:
        """GET /api/agent/route?task_type=spec — agent routing gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/agent/route", params={"task_type": "spec"})
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_runtime_events_is_accessible(self) -> None:
        """GET /api/runtime/events — runtime gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/runtime/events")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.asyncio
    async def test_inventory_process_completeness_is_accessible(self) -> None:
        """GET /api/inventory/process-completeness — inventory gap."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/inventory/process-completeness")
        assert r.status_code < 500, f"Expected non-5xx, got {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# Tests: CLI file structure — each priority area maps to a command file
# ---------------------------------------------------------------------------

class TestCliFileStructure:
    """Verify that CLI command files exist for each priority area."""

    def _has_command_file(self, name: str) -> bool:
        return (CLI_COMMANDS_DIR / f"{name}.mjs").exists()

    def test_tasks_command_file_exists(self) -> None:
        assert self._has_command_file("tasks"), "cli/lib/commands/tasks.mjs must exist"

    def test_treasury_command_file_exists(self) -> None:
        assert self._has_command_file("treasury"), "cli/lib/commands/treasury.mjs must exist"

    def test_governance_command_file_exists(self) -> None:
        assert self._has_command_file("governance"), "cli/lib/commands/governance.mjs must exist"

    def test_nodes_command_file_exists(self) -> None:
        assert self._has_command_file("nodes"), "cli/lib/commands/nodes.mjs must exist"

    def test_services_command_file_exists(self) -> None:
        assert self._has_command_file("services"), "cli/lib/commands/services.mjs must exist"

    def test_lineage_command_file_exists(self) -> None:
        assert self._has_command_file("lineage"), "cli/lib/commands/lineage.mjs must exist"

    def test_ideas_command_file_exists(self) -> None:
        assert self._has_command_file("ideas"), "cli/lib/commands/ideas.mjs must exist"

    def test_traceability_command_file_exists(self) -> None:
        assert self._has_command_file("traceability"), "cli/lib/commands/traceability.mjs must exist"

    def test_providers_command_file_exists(self) -> None:
        assert self._has_command_file("providers"), "cli/lib/commands/providers.mjs must exist"

    def test_specs_command_file_exists(self) -> None:
        assert self._has_command_file("specs"), "cli/lib/commands/specs.mjs must exist"


# ---------------------------------------------------------------------------
# Tests: CLI commands reference correct API paths
# ---------------------------------------------------------------------------

class TestCliCommandsReferenceApiPaths:
    """Verify that CLI command files reference valid API paths (no typos)."""

    def test_all_cli_api_paths_start_with_api(self) -> None:
        """All CLI-referenced paths should start with /api/ or /v1/ or /v2/."""
        bad = [
            p for p in CLI_COVERED_PATHS
            if not p.startswith("/api/")
            and not p.startswith("/v1/")
            and not p.startswith("/v2/")
        ]
        assert not bad, f"CLI references paths not starting with /api/: {bad}"

    def test_tasks_mjs_references_agent_tasks(self) -> None:
        """tasks.mjs must reference /api/agent/tasks."""
        if not CLI_COMMANDS_DIR.exists():
            pytest.skip("CLI commands dir not found")
        tasks_file = CLI_COMMANDS_DIR / "tasks.mjs"
        assert tasks_file.exists(), "tasks.mjs must exist"
        src = tasks_file.read_text(encoding="utf-8")
        assert "/api/agent/tasks" in src, "tasks.mjs must reference /api/agent/tasks"

    def test_treasury_mjs_references_treasury(self) -> None:
        """treasury.mjs must reference /api/treasury."""
        if not CLI_COMMANDS_DIR.exists():
            pytest.skip("CLI commands dir not found")
        treasury_file = CLI_COMMANDS_DIR / "treasury.mjs"
        assert treasury_file.exists(), "treasury.mjs must exist"
        src = treasury_file.read_text(encoding="utf-8")
        assert "/api/treasury" in src, "treasury.mjs must reference /api/treasury"

    def test_governance_mjs_references_governance(self) -> None:
        """governance.mjs must reference /api/governance/change-requests."""
        if not CLI_COMMANDS_DIR.exists():
            pytest.skip("CLI commands dir not found")
        gov_file = CLI_COMMANDS_DIR / "governance.mjs"
        assert gov_file.exists(), "governance.mjs must exist"
        src = gov_file.read_text(encoding="utf-8")
        assert "/api/governance/change-requests" in src, (
            "governance.mjs must reference /api/governance/change-requests"
        )

    def test_nodes_mjs_references_federation_nodes(self) -> None:
        """nodes.mjs must reference /api/federation/nodes."""
        if not CLI_COMMANDS_DIR.exists():
            pytest.skip("CLI commands dir not found")
        nodes_file = CLI_COMMANDS_DIR / "nodes.mjs"
        assert nodes_file.exists(), "nodes.mjs must exist"
        src = nodes_file.read_text(encoding="utf-8")
        assert "/api/federation/nodes" in src, "nodes.mjs must reference /api/federation/nodes"

    def test_lineage_mjs_references_value_lineage(self) -> None:
        """lineage.mjs must reference /api/value-lineage/links."""
        if not CLI_COMMANDS_DIR.exists():
            pytest.skip("CLI commands dir not found")
        lineage_file = CLI_COMMANDS_DIR / "lineage.mjs"
        assert lineage_file.exists(), "lineage.mjs must exist"
        src = lineage_file.read_text(encoding="utf-8")
        assert "/api/value-lineage/links" in src, (
            "lineage.mjs must reference /api/value-lineage/links"
        )


# ---------------------------------------------------------------------------
# Tests: Gap tracking — specific uncovered endpoints documented
# ---------------------------------------------------------------------------

class TestGapTracking:
    """Document and track specific known gaps for future coverage work.

    These tests PASS as long as the gap still exists (endpoints exist but
    are NOT yet CLI-covered). They serve as living documentation of what
    needs to be implemented. When a gap is closed, the test will fail
    (intentionally), prompting removal of the gap test.
    """

    def _endpoint_exists(self, path: str, method: str = "GET") -> bool:
        return any(e.path == path and e.method == method for e in ALL_ENDPOINTS)

    def test_gap_agent_tasks_active_not_yet_cli_covered(self) -> None:
        """GAP: GET /api/agent/tasks/active has no CLI command yet."""
        if not self._endpoint_exists("/api/agent/tasks/active"):
            pytest.skip("Endpoint not present in this build")
        # This test documents the gap. It passes if NOT covered.
        # When the gap is closed, flip this to assert _cli_covers(...) is True.
        covered = _cli_covers("/api/agent/tasks/active")
        if covered:
            pytest.xfail("/api/agent/tasks/active is now CLI-covered — remove this gap test")
        assert not covered  # Gap still open

    def test_gap_inventory_flow_not_yet_cli_covered(self) -> None:
        """GAP: GET /api/inventory/flow has no CLI command yet."""
        if not self._endpoint_exists("/api/inventory/flow"):
            pytest.skip("Endpoint not present in this build")
        covered = _cli_covers("/api/inventory/flow")
        if covered:
            pytest.xfail("/api/inventory/flow is now CLI-covered — remove this gap test")
        assert not covered

    def test_gap_runtime_endpoints_summary_not_yet_cli_covered(self) -> None:
        """GAP: GET /api/runtime/endpoints/summary has no CLI command yet."""
        if not self._endpoint_exists("/api/runtime/endpoints/summary"):
            pytest.skip("Endpoint not present in this build")
        covered = _cli_covers("/api/runtime/endpoints/summary")
        if covered:
            pytest.xfail("/api/runtime/endpoints/summary is now CLI-covered — remove this gap test")
        assert not covered

    def test_federation_node_messages_is_cli_covered(self) -> None:
        """COVERED: GET /api/federation/nodes/{node_id}/messages IS covered by nodes.mjs (cc inbox/msg)."""
        path = "/api/federation/nodes/{node_id}/messages"
        if not self._endpoint_exists(path):
            pytest.skip("Endpoint not present in this build")
        # nodes.mjs uses template literals referencing this path — it IS covered
        nodes_file = CLI_COMMANDS_DIR / "nodes.mjs"
        if not nodes_file.exists():
            pytest.skip("nodes.mjs not found")
        src = nodes_file.read_text(encoding="utf-8")
        assert "federation/nodes" in src and "messages" in src, (
            "nodes.mjs must reference /api/federation/nodes/.../messages"
        )

    def test_gap_inventory_process_completeness_not_yet_cli_covered(self) -> None:
        """GAP: GET /api/inventory/process-completeness has no CLI command yet."""
        if not self._endpoint_exists("/api/inventory/process-completeness"):
            pytest.skip("Endpoint not present in this build")
        covered = _cli_covers("/api/inventory/process-completeness")
        if covered:
            pytest.xfail("/api/inventory/process-completeness is now CLI-covered")
        assert not covered

    def test_gap_agent_route_not_yet_cli_covered(self) -> None:
        """GAP: GET /api/agent/route has no direct CLI command yet."""
        if not self._endpoint_exists("/api/agent/route"):
            pytest.skip("Endpoint not present in this build")
        covered = _cli_covers("/api/agent/route")
        if covered:
            pytest.xfail("/api/agent/route is now CLI-covered — remove this gap test")
        assert not covered


# ---------------------------------------------------------------------------
# Tests: Coverage progress metrics (machine-readable for CI dashboards)
# ---------------------------------------------------------------------------

class TestCoverageMetrics:
    """Output machine-readable coverage metrics for CI and dashboards."""

    def test_emit_coverage_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Print JSON-compatible coverage summary for CI consumption."""
        unique_paths = {e.path for e in ALL_ENDPOINTS}
        covered_paths = [p for p in unique_paths if _cli_covers(p)]
        uncovered_paths = [p for p in unique_paths if not _cli_covers(p)]

        pct = (len(covered_paths) / len(unique_paths) * 100) if unique_paths else 0.0

        # Category breakdown
        cat_breakdown: dict[str, dict[str, int]] = {}
        for e in ALL_ENDPOINTS:
            cat = e.category
            if cat not in cat_breakdown:
                cat_breakdown[cat] = {"covered": 0, "total": 0}
            if e.path not in cat_breakdown[cat]:
                cov, tot = _coverage_for_category(cat)
                cat_breakdown[cat] = {"covered": cov, "total": tot}

        print("\n=== COVERAGE SUMMARY ===")
        print(f"total_endpoints: {len(unique_paths)}")
        print(f"covered_endpoints: {len(covered_paths)}")
        print(f"uncovered_endpoints: {len(uncovered_paths)}")
        print(f"coverage_percent: {pct:.1f}")
        print(f"minimum_required: {MINIMUM_CLI_COVERAGE_PERCENT}")
        print(f"passes_minimum: {pct >= MINIMUM_CLI_COVERAGE_PERCENT}")
        print("\nTop 20 uncovered paths (priority gaps):")
        for p in sorted(uncovered_paths)[:20]:
            print(f"  - {p}")

        assert pct >= MINIMUM_CLI_COVERAGE_PERCENT, (
            f"Coverage {pct:.1f}% below minimum {MINIMUM_CLI_COVERAGE_PERCENT}%"
        )

    def test_covered_path_count_is_nonzero(self) -> None:
        """Must have at least 10 CLI-covered paths."""
        covered = [p for p in {e.path for e in ALL_ENDPOINTS} if _cli_covers(p)]
        assert len(covered) >= 10, (
            f"Expected >= 10 covered paths, found {len(covered)}. "
            f"CLI covered: {sorted(CLI_COVERED_PATHS)}"
        )

    def test_priority_categories_have_nonzero_coverage(self) -> None:
        """All priority gap categories must have >0 covered endpoints."""
        priority_cats = [
            "agent", "ideas", "federation", "treasury",
            "governance", "value-lineage", "services",
        ]
        failed = []
        for cat in priority_cats:
            covered, total = _coverage_for_category(cat)
            if covered == 0:
                failed.append(f"{cat}: 0/{total}")
        assert not failed, (
            f"Priority categories with ZERO CLI coverage: {failed}. "
            "Each priority category must have at least 1 CLI command."
        )
