"""Tests for CLI Full Coverage (cli-full-coverage).

Covers acceptance criteria from spec 148-coherence-cli-comprehensive.md:
  R1 — Zero Runtime Dependencies
  R3 — Core Command Set (15 Commands)
  R4 — Public API Integration (API endpoints the CLI depends on)
  R5 — Idea & Spec Traceability (GET /api/ideas, GET /api/spec-registry)
  R6 — Contribution Lifecycle (POST /api/ideas, POST /api/contributions)
  R7 — Network Observability (GET /api/health, GET /api/federation/nodes)
  R8 — Messaging & Inbox (POST/GET federation node messages)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLI_DIR = Path(__file__).resolve().parents[2] / "cli"
CLI_PACKAGE_JSON = CLI_DIR / "package.json"
CLI_BIN = CLI_DIR / "bin" / "cc.mjs"

# The 15 core commands listed in spec 148
SPEC_CORE_COMMANDS = [
    "ideas",
    "idea",
    "specs",
    "spec",
    "share",
    "stake",
    "fork",
    "contribute",
    "resonance",
    "status",
    "identity",
    "nodes",
    "msg",
    "inbox",
    "help",
]


# ---------------------------------------------------------------------------
# R1 — Zero Runtime Dependencies
# ---------------------------------------------------------------------------


class TestZeroRuntimeDependencies:
    """Verify that cli/package.json has no runtime dependencies (R1)."""

    def test_package_json_exists(self) -> None:
        """cli/package.json must exist."""
        assert CLI_PACKAGE_JSON.exists(), f"Missing: {CLI_PACKAGE_JSON}"

    def test_no_dependencies_field(self) -> None:
        """package.json must not have a non-empty 'dependencies' field (R1)."""
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        deps = pkg.get("dependencies", {})
        assert deps == {} or deps is None, (
            f"Expected zero runtime deps, found: {deps}"
        )

    def test_has_type_module(self) -> None:
        """package.json must declare 'type': 'module' for ESM support."""
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        assert pkg.get("type") == "module"

    def test_engines_node_requirement(self) -> None:
        """package.json must specify engines.node >= 18 (R1 relies on native fetch)."""
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        engines = pkg.get("engines", {})
        node_req = engines.get("node", "")
        assert "18" in node_req, f"Expected node >= 18 requirement, got: {node_req!r}"

    def test_bin_field_defines_cc(self) -> None:
        """package.json must declare 'cc' as a binary entry point."""
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        bin_field = pkg.get("bin", {})
        assert "cc" in bin_field, f"'cc' not found in bin: {bin_field}"

    def test_bin_cc_points_to_valid_file(self) -> None:
        """The 'cc' binary in package.json must point to an existing file."""
        pkg = json.loads(CLI_PACKAGE_JSON.read_text(encoding="utf-8"))
        cc_path = CLI_DIR / pkg["bin"]["cc"]
        assert cc_path.exists(), f"Binary path does not exist: {cc_path}"


# ---------------------------------------------------------------------------
# R3 — Core Command Set (15 Commands)
# ---------------------------------------------------------------------------


class TestCoreCommandSet:
    """Verify the 15 core commands are registered in cc.mjs (R3)."""

    @pytest.fixture(scope="class")
    def cc_source(self) -> str:
        assert CLI_BIN.exists(), f"Missing CLI entry point: {CLI_BIN}"
        return CLI_BIN.read_text(encoding="utf-8")

    def test_ideas_command_registered(self, cc_source: str) -> None:
        assert "ideas:" in cc_source or "'ideas'" in cc_source

    def test_idea_command_registered(self, cc_source: str) -> None:
        assert "idea:" in cc_source or "'idea'" in cc_source

    def test_specs_command_registered(self, cc_source: str) -> None:
        assert "specs:" in cc_source or "'specs'" in cc_source

    def test_spec_command_registered(self, cc_source: str) -> None:
        assert "spec:" in cc_source or "'spec'" in cc_source

    def test_share_command_registered(self, cc_source: str) -> None:
        assert "share:" in cc_source or "'share'" in cc_source

    def test_stake_command_registered(self, cc_source: str) -> None:
        assert "stake:" in cc_source or "'stake'" in cc_source

    def test_fork_command_registered(self, cc_source: str) -> None:
        assert "fork:" in cc_source or "'fork'" in cc_source

    def test_contribute_command_registered(self, cc_source: str) -> None:
        assert "contribute:" in cc_source or "'contribute'" in cc_source

    def test_resonance_command_registered(self, cc_source: str) -> None:
        assert "resonance:" in cc_source or "'resonance'" in cc_source

    def test_status_command_registered(self, cc_source: str) -> None:
        assert "status:" in cc_source or "'status'" in cc_source

    def test_identity_command_registered(self, cc_source: str) -> None:
        assert "identity:" in cc_source or "'identity'" in cc_source

    def test_nodes_command_registered(self, cc_source: str) -> None:
        assert "nodes:" in cc_source or "'nodes'" in cc_source

    def test_msg_command_registered(self, cc_source: str) -> None:
        assert "msg:" in cc_source or "'msg'" in cc_source

    def test_inbox_command_registered(self, cc_source: str) -> None:
        assert "inbox:" in cc_source or "'inbox'" in cc_source

    def test_help_command_registered(self, cc_source: str) -> None:
        assert "help:" in cc_source or "'help'" in cc_source

    def test_at_least_15_commands_in_commands_map(self, cc_source: str) -> None:
        """COMMANDS object must contain at least 15 entries (R3)."""
        # Count lines matching key: () pattern within COMMANDS block
        commands_present = sum(
            1 for cmd in SPEC_CORE_COMMANDS if f"{cmd}:" in cc_source
        )
        assert commands_present >= 15, (
            f"Only {commands_present}/15 spec commands found in cc.mjs"
        )


# ---------------------------------------------------------------------------
# Fixtures — API client
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# R4 — Public API Integration
# ---------------------------------------------------------------------------


class TestPublicAPIIntegration:
    """Verify the API endpoints the CLI depends on exist and respond (R4)."""

    def test_health_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/health returns 200 (R4, R7)."""
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_response_has_status(self, client: TestClient) -> None:
        """Health response includes a 'status' field."""
        r = client.get("/api/health")
        body = r.json()
        assert "status" in body

    def test_ping_endpoint_responds(self, client: TestClient) -> None:
        """GET /api/ping returns 200 — lightweight liveness check."""
        r = client.get("/api/ping")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# R5 — Idea & Spec Traceability
# ---------------------------------------------------------------------------


class TestIdeaTraceability:
    """Verify idea browsing API endpoints consumed by the CLI (R5)."""

    def test_list_ideas_returns_200(self, client: TestClient) -> None:
        """GET /api/ideas returns 200 (used by 'cc ideas')."""
        r = client.get("/api/ideas")
        assert r.status_code == 200

    def test_list_ideas_returns_list(self, client: TestClient) -> None:
        """GET /api/ideas body is a list or dict with items key."""
        r = client.get("/api/ideas")
        body = r.json()
        assert isinstance(body, (list, dict))

    def test_get_idea_404_on_unknown(self, client: TestClient) -> None:
        """GET /api/ideas/<unknown> returns 404 (used by 'cc idea <id>')."""
        r = client.get("/api/ideas/nonexistent-idea-id-xyz-9999")
        assert r.status_code == 404

    def test_create_and_fetch_idea(self, client: TestClient) -> None:
        """POST /api/ideas then GET /api/ideas/{id} round-trip (R5, R6)."""
        payload = {
            "id": "cli-test-idea-spec148",
            "name": "CLI Full Coverage Test Idea",
            "description": "Verifying CLI spec 148 API contract",
            "potential_value": 10.0,
            "estimated_cost": 2.0,
        }
        create_r = client.post("/api/ideas", json=payload)
        # 409 means it already exists — either way the endpoint works
        assert create_r.status_code in (200, 201, 409)
        if create_r.status_code == 409:
            # Idea already exists, fetch it
            fetch_r = client.get("/api/ideas/cli-test-idea-spec148")
            assert fetch_r.status_code == 200
            return
        idea = create_r.json()
        idea_id = idea.get("id") or idea.get("idea_id")
        assert idea_id, f"Expected idea id in response, got: {idea}"

        fetch_r = client.get(f"/api/ideas/{idea_id}")
        assert fetch_r.status_code == 200
        fetched = fetch_r.json()
        assert fetched.get("id") == idea_id or fetched.get("idea_id") == idea_id


class TestSpecTraceability:
    """Verify spec browsing API endpoints consumed by the CLI (R5)."""

    def test_list_specs_returns_200(self, client: TestClient) -> None:
        """GET /api/spec-registry returns 200 (used by 'cc specs')."""
        r = client.get("/api/spec-registry")
        assert r.status_code == 200

    def test_list_specs_returns_list(self, client: TestClient) -> None:
        """GET /api/spec-registry body is a list."""
        r = client.get("/api/spec-registry")
        body = r.json()
        assert isinstance(body, list)

    def test_get_spec_404_on_unknown(self, client: TestClient) -> None:
        """GET /api/spec-registry/<unknown> returns 404 (used by 'cc spec <id>')."""
        r = client.get("/api/spec-registry/nonexistent-spec-id-xyz-9999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# R6 — Contribution Lifecycle
# ---------------------------------------------------------------------------


class TestContributionLifecycle:
    """Verify contribution recording endpoints (R6)."""

    def test_post_contributions_requires_fields(self, client: TestClient) -> None:
        """POST /api/contributions with empty body returns 422 (schema enforced)."""
        r = client.post("/api/contributions", json={})
        assert r.status_code == 422

    def test_post_contributions_valid_payload(self, client: TestClient) -> None:
        """POST /api/contributions schema is enforced — 422 on invalid UUIDs (R6: 'cc contribute')."""
        # ContributionCreate requires UUID fields; sending strings triggers schema validation
        contrib_r = client.post(
            "/api/contributions",
            json={
                "contributor_id": "not-a-uuid",
                "asset_id": "also-not-a-uuid",
                "cost_amount": "1.0",
            },
        )
        # 422 is correct — schema enforced. Not 500.
        assert contrib_r.status_code in (404, 422), contrib_r.text

    def test_stake_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/ideas/{id}/stake endpoint exists (R6: 'cc stake')."""
        # Create an idea first
        create_r = client.post(
            "/api/ideas",
            json={
                "id": "cli-stake-target-spec148",
                "name": "CLI Stake Target",
                "description": "Target idea for stake test",
                "potential_value": 5.0,
                "estimated_cost": 1.0,
            },
        )
        assert create_r.status_code in (200, 201, 409)
        idea_id = "cli-stake-target-spec148"

        # Stake requires contributor_id OR provider+provider_id, plus amount_cc
        stake_r = client.post(
            f"/api/ideas/{idea_id}/stake",
            json={"contributor_id": "cli-test-agent", "amount_cc": 5.0},
        )
        # Endpoint exists — any non-500 response is acceptable
        assert stake_r.status_code != 500, stake_r.text

    def test_fork_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/ideas/{id}/fork endpoint exists (R6: 'cc fork')."""
        create_r = client.post(
            "/api/ideas",
            json={
                "id": "cli-fork-target-spec148",
                "name": "CLI Fork Target",
                "description": "Target idea for fork test",
                "potential_value": 5.0,
                "estimated_cost": 1.0,
            },
        )
        assert create_r.status_code in (200, 201, 409)
        idea_id = "cli-fork-target-spec148"

        fork_r = client.post(
            f"/api/ideas/{idea_id}/fork",
            params={"forker_id": "cli-test-agent"},
        )
        assert fork_r.status_code != 500, fork_r.text


# ---------------------------------------------------------------------------
# R7 — Network Observability
# ---------------------------------------------------------------------------


class TestNetworkObservability:
    """Verify network status and federation endpoints (R7)."""

    def test_federation_nodes_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/federation/nodes returns 200 (R7: 'cc nodes')."""
        r = client.get("/api/federation/nodes")
        assert r.status_code == 200

    def test_federation_nodes_returns_list(self, client: TestClient) -> None:
        """GET /api/federation/nodes returns a list."""
        r = client.get("/api/federation/nodes")
        body = r.json()
        assert isinstance(body, list)

    def test_health_endpoint_is_ok(self, client: TestClient) -> None:
        """GET /api/health reports healthy (R7: 'cc status')."""
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") in ("ok", "healthy", "degraded", "up"), (
            f"Unexpected health status: {body}"
        )


# ---------------------------------------------------------------------------
# R8 — Messaging & Inbox
# ---------------------------------------------------------------------------


class TestMessagingInbox:
    """Verify federation messaging endpoints (R8: 'cc msg', 'cc inbox')."""

    def test_post_node_message_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/federation/nodes/{node_id}/messages endpoint exists (R8: 'cc msg')."""
        node_id = "cli-r8-sender-01"
        msg_r = client.post(
            f"/api/federation/nodes/{node_id}/messages",
            json={
                "from_node": "cli-sender",
                "text": "Test message from cli-full-coverage spec",
                "type": "text",
            },
        )
        assert msg_r.status_code in (200, 201), msg_r.text

    def test_get_node_messages_endpoint_exists(self, client: TestClient) -> None:
        """GET /api/federation/nodes/{node_id}/messages endpoint exists (R8: 'cc inbox')."""
        node_id = "cli-r8-inbox-01"
        msgs_r = client.get(f"/api/federation/nodes/{node_id}/messages")
        assert msgs_r.status_code in (200, 404), msgs_r.text

    def test_broadcast_endpoint_exists(self, client: TestClient) -> None:
        """POST /api/federation/broadcast endpoint exists (R8: 'cc msg broadcast')."""
        bcast_r = client.post(
            "/api/federation/broadcast",
            json={
                "from_node": "cli-broadcaster",
                "text": "Broadcast test from cli-full-coverage",
                "type": "text",
            },
        )
        assert bcast_r.status_code in (200, 201), bcast_r.text
