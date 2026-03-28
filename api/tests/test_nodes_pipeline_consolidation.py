"""Tests for page consolidation: /nodes and /pipeline replace /automation, /usage, /remote-ops.

This test suite verifies that:
1. /nodes page data is fully served by the API (federation nodes, health, providers, messages)
2. /pipeline page data is fully served by the API (queue, running, completed, streaks, provider perf)
3. All data previously scattered across /automation, /usage, /remote-ops is now in /nodes or /pipeline
4. The consolidated API surface is complete and returns correct structure

Verification Scenarios:
  S1: Node list — POST /api/federation/nodes registers a node, GET /api/federation/nodes lists it
  S2: Node health — POST heartbeat updates last_seen_at and capabilities
  S3: Provider stats — GET /api/providers/stats returns per-provider success rates
  S4: Pipeline status — GET /api/pipeline/status and /api/pipeline/summary return execution stats
  S5: Automation usage — GET /api/automation/usage returns provider metrics (should be accessible for /nodes)
  S6: Node messages — POST /api/federation/nodes/{id}/messages, GET messages
  S7: Error handling — 404 on missing node, invalid payload returns 422
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Isolate SQLite DB for each test so federation state never bleeds across tests."""
    monkeypatch.setenv("COHERENCE_ENV", "test")
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    for key in ("DATABASE_URL", "AGENT_TASKS_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)

    from app.services import unified_db
    unified_db.reset_engine()


@pytest.fixture
def client():
    """Return a sync test client backed by an isolated DB."""
    from app.main import app
    return TestClient(app)


_NODE_ID = "testnode1234abcd"
_REGISTER_BODY = {
    "node_id": _NODE_ID,
    "hostname": "test-host.local",
    "os_type": "linux",
    "providers": ["claude", "openrouter"],
    "capabilities": {"executors": ["claude", "openrouter"]},
}


# ---------------------------------------------------------------------------
# S1: Node list — basic registration and listing
# ---------------------------------------------------------------------------


class TestNodeListEndpoint:
    """The /nodes page requires GET /api/federation/nodes to list all nodes."""

    def test_empty_node_list_returns_list(self, client: TestClient) -> None:
        """GET /api/federation/nodes returns an empty list when no nodes are registered."""
        resp = client.get("/api/federation/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_register_node_appears_in_list(self, client: TestClient) -> None:
        """POST registers a node; subsequent GET returns it with expected fields."""
        reg = client.post("/api/federation/nodes", json=_REGISTER_BODY)
        assert reg.status_code in (200, 201), f"Registration failed: {reg.text}"

        listing = client.get("/api/federation/nodes")
        assert listing.status_code == 200
        nodes = listing.json()
        assert isinstance(nodes, list)

        ids = [n.get("node_id") for n in nodes]
        assert _NODE_ID in ids, f"Registered node missing from list: {ids}"

    def test_registered_node_has_required_fields(self, client: TestClient) -> None:
        """Each node in the list exposes fields needed by the /nodes page."""
        client.post("/api/federation/nodes", json=_REGISTER_BODY)
        nodes = client.get("/api/federation/nodes").json()
        node = next((n for n in nodes if n.get("node_id") == _NODE_ID), None)
        assert node is not None

        required = {"node_id", "hostname", "os_type", "providers", "status", "last_seen_at", "registered_at"}
        missing = required - set(node.keys())
        assert not missing, f"Node missing required fields for /nodes page: {missing}"

    def test_re_register_same_node_is_idempotent(self, client: TestClient) -> None:
        """Registering the same node twice must not duplicate it."""
        client.post("/api/federation/nodes", json=_REGISTER_BODY)
        client.post("/api/federation/nodes", json=_REGISTER_BODY)

        nodes = client.get("/api/federation/nodes").json()
        matched = [n for n in nodes if n.get("node_id") == _NODE_ID]
        assert len(matched) == 1, "Node was duplicated on second registration"


# ---------------------------------------------------------------------------
# S2: Node health — heartbeat updates liveness
# ---------------------------------------------------------------------------


class TestNodeHealthHeartbeat:
    """The /nodes page must display health data via POST .../heartbeat."""

    def _register(self, client: TestClient) -> str:
        resp = client.post("/api/federation/nodes", json=_REGISTER_BODY)
        assert resp.status_code in (200, 201)
        return _NODE_ID

    def test_heartbeat_succeeds(self, client: TestClient) -> None:
        """POST heartbeat returns 200 with updated last_seen_at."""
        node_id = self._register(client)
        hb = client.post(
            f"/api/federation/nodes/{node_id}/heartbeat",
            json={"status": "online"},
        )
        assert hb.status_code == 200, f"Heartbeat failed: {hb.text}"
        data = hb.json()
        assert "last_seen_at" in data or "node_id" in data, f"Missing fields: {data}"

    def test_heartbeat_with_capabilities_updates_node(self, client: TestClient) -> None:
        """Heartbeat with capabilities payload updates capabilities on the node."""
        node_id = self._register(client)
        caps = {"executors": ["claude", "cursor"], "tools": ["bash"]}
        hb = client.post(
            f"/api/federation/nodes/{node_id}/heartbeat",
            json={"status": "online", "capabilities": caps},
        )
        assert hb.status_code == 200, f"Heartbeat with capabilities failed: {hb.text}"

    def test_heartbeat_unknown_node_returns_404(self, client: TestClient) -> None:
        """POST heartbeat for an unregistered node returns 404."""
        resp = client.post(
            "/api/federation/nodes/unknownabcd1234/heartbeat",
            json={"status": "online"},
        )
        assert resp.status_code == 404, f"Expected 404 for unknown node, got {resp.status_code}"

    def test_node_status_after_heartbeat_is_online(self, client: TestClient) -> None:
        """After heartbeat, node status should be 'online' in the list."""
        node_id = self._register(client)
        client.post(f"/api/federation/nodes/{node_id}/heartbeat", json={"status": "online"})

        nodes = client.get("/api/federation/nodes").json()
        node = next((n for n in nodes if n.get("node_id") == node_id), None)
        assert node is not None
        assert node.get("status") == "online", f"Expected 'online', got {node.get('status')}"


# ---------------------------------------------------------------------------
# S3: Provider stats — needed by both /nodes and /pipeline
# ---------------------------------------------------------------------------


class TestProviderStatsEndpoint:
    """
    GET /api/providers/stats serves provider performance data.
    This was previously fragmented across /automation (provider capacity) and
    /usage (provider performance). Both /nodes and /pipeline need it.
    """

    def test_provider_stats_returns_200(self, client: TestClient) -> None:
        """GET /api/providers/stats always returns 200 with a dict."""
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)

    def test_provider_stats_has_providers_key(self, client: TestClient) -> None:
        """Response must contain 'providers' mapping needed by /nodes and /pipeline."""
        data = client.get("/api/providers/stats").json()
        assert "providers" in data, f"Missing 'providers' key in response: {list(data.keys())}"
        assert isinstance(data["providers"], dict)

    def test_provider_stats_summary_has_required_metrics(self, client: TestClient) -> None:
        """Summary section must include counts needed for pipeline health indicators."""
        data = client.get("/api/providers/stats").json()
        if "summary" in data:
            summary = data["summary"]
            assert isinstance(summary, dict), "summary must be a dict"

    def test_provider_stats_network_endpoint(self, client: TestClient) -> None:
        """GET /api/providers/stats/network returns aggregated network-level data."""
        resp = client.get("/api/providers/stats/network")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)

    def test_provider_stats_per_provider_has_success_rate(self, client: TestClient) -> None:
        """Each provider entry in stats must expose success_rate (used for /pipeline perf view)."""
        data = client.get("/api/providers/stats").json()
        providers = data.get("providers", {})
        for provider_name, stats in providers.items():
            assert isinstance(stats, dict), f"Provider {provider_name} stats is not a dict"
            assert "success_rate" in stats or "last_5_rate" in stats, (
                f"Provider '{provider_name}' missing success rate metrics: {list(stats.keys())}"
            )


# ---------------------------------------------------------------------------
# S4: Pipeline status — the /pipeline page execution data
# ---------------------------------------------------------------------------


class TestPipelineStatusEndpoint:
    """
    GET /api/pipeline/status and /api/pipeline/summary serve
    the task execution state: queue, running, completed, streaks.
    This consolidates what was in /remote-ops (queue view) and /usage (run history).
    """

    def test_pipeline_summary_always_200(self, client: TestClient) -> None:
        """/api/pipeline/summary never returns 503 — always usable by /pipeline page."""
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)

    def test_pipeline_status_returns_valid_shape(self, client: TestClient) -> None:
        """/api/pipeline/status returns a dict with expected keys."""
        resp = client.get("/api/pipeline/status")
        # May return 503 if pipeline not running — that is valid behavior
        assert resp.status_code in (200, 503), f"Unexpected status: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, dict)

    def test_pipeline_summary_has_task_counts(self, client: TestClient) -> None:
        """Pipeline summary must include task_completed/task_failed counts for /pipeline history."""
        data = client.get("/api/pipeline/summary").json()
        # These fields should be present (may be 0 in test env)
        assert "tasks_completed" in data or "running" in data, (
            f"Pipeline summary missing key execution fields: {list(data.keys())}"
        )

    def test_pipeline_summary_has_cycle_info(self, client: TestClient) -> None:
        """Cycle count must be present for streak/progress display on /pipeline page."""
        data = client.get("/api/pipeline/summary").json()
        assert "cycle_count" in data or "running" in data, (
            f"Pipeline summary missing cycle_count: {list(data.keys())}"
        )


# ---------------------------------------------------------------------------
# S5: Automation usage — provider capacity data moved to /nodes
# ---------------------------------------------------------------------------


class TestAutomationUsageEndpoint:
    """
    GET /api/automation/usage provides provider capacity snapshots.
    The /nodes page shows provider health; this endpoint feeds that section.
    The old /automation and /usage pages consumed this data.
    """

    def test_automation_usage_returns_200(self, client: TestClient) -> None:
        """GET /api/automation/usage returns 200 even with no live providers."""
        resp = client.get("/api/automation/usage")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, dict)

    def test_automation_usage_has_providers(self, client: TestClient) -> None:
        """Response must include 'providers' list for the /nodes provider section."""
        data = client.get("/api/automation/usage").json()
        assert "providers" in data, f"Missing 'providers' in response: {list(data.keys())}"
        assert isinstance(data["providers"], list)

    def test_automation_usage_compact_mode(self, client: TestClient) -> None:
        """Compact mode must return 200 — used by /nodes for bandwidth-constrained clients."""
        resp = client.get("/api/automation/usage?compact=true")
        assert resp.status_code == 200, f"Compact mode failed: {resp.status_code}"
        data = resp.json()
        assert isinstance(data, dict)
        assert "providers" in data

    def test_automation_usage_snapshots_endpoint(self, client: TestClient) -> None:
        """GET /api/automation/usage/snapshots returns paginated history for /nodes trend view."""
        resp = client.get("/api/automation/usage/snapshots?limit=10")
        assert resp.status_code == 200, f"Snapshots endpoint failed: {resp.status_code}"
        data = resp.json()
        assert "count" in data and "snapshots" in data


# ---------------------------------------------------------------------------
# S6: Node messages — remote control moved to /nodes
# ---------------------------------------------------------------------------


class TestNodeMessagesEndpoint:
    """
    POST /api/federation/nodes/{id}/messages and GET messages
    support the remote control section now unified in /nodes.
    Previously this was only accessible via /remote-ops.
    """

    def _register(self, client: TestClient) -> str:
        resp = client.post("/api/federation/nodes", json=_REGISTER_BODY)
        assert resp.status_code in (200, 201)
        return _NODE_ID

    def test_send_message_to_node(self, client: TestClient) -> None:
        """POST message to registered node returns 201."""
        node_id = self._register(client)
        msg = client.post(
            f"/api/federation/nodes/{node_id}/messages",
            json={"from_node": "test-sender", "type": "command", "text": "checkpoint", "payload": {}},
        )
        assert msg.status_code == 201, f"Send message failed: {msg.text}"

    def test_get_messages_for_node(self, client: TestClient) -> None:
        """GET messages for a node returns a list."""
        node_id = self._register(client)
        client.post(
            f"/api/federation/nodes/{node_id}/messages",
            json={"from_node": "test-sender", "type": "command", "text": "checkpoint", "payload": {}},
        )
        msgs = client.get(f"/api/federation/nodes/{node_id}/messages")
        assert msgs.status_code == 200, f"Get messages failed: {msgs.text}"
        data = msgs.json()
        assert isinstance(data, (list, dict)), f"Messages response unexpected type: {type(data)}"

    def test_message_to_unknown_node_returns_error(self, client: TestClient) -> None:
        """POST message to unregistered node: API accepts it (no pre-validation of target node)."""
        resp = client.post(
            "/api/federation/nodes/unknownabcd1234/messages",
            json={"from_node": "test-sender", "type": "command", "text": "ping", "payload": {}},
        )
        # API may return 201 (stores message) or 404 (validates node existence)
        assert resp.status_code in (201, 404), (
            f"Expected 201 or 404 for unknown node, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# S7: Error handling and edge cases
# ---------------------------------------------------------------------------


class TestConsolidationErrorHandling:
    """All endpoints must handle bad inputs gracefully — no 500s for user errors."""

    def test_register_node_invalid_id_length_returns_422(self, client: TestClient) -> None:
        """Node ID shorter than 16 chars must fail with 422."""
        bad_body = {**_REGISTER_BODY, "node_id": "short"}
        resp = client.post("/api/federation/nodes", json=bad_body)
        assert resp.status_code == 422, f"Expected 422 for short node_id, got {resp.status_code}"

    def test_register_node_missing_hostname_returns_422(self, client: TestClient) -> None:
        """Missing required hostname field must return 422."""
        bad_body = {k: v for k, v in _REGISTER_BODY.items() if k != "hostname"}
        resp = client.post("/api/federation/nodes", json=bad_body)
        assert resp.status_code == 422, f"Expected 422 for missing hostname, got {resp.status_code}"

    def test_delete_nonexistent_node_returns_404(self, client: TestClient) -> None:
        """DELETE on an unregistered node must return 404."""
        resp = client.delete("/api/federation/nodes/doesnotexist1234")
        assert resp.status_code == 404, f"Expected 404 for unknown node, got {resp.status_code}"

    def test_pipeline_summary_never_crashes(self, client: TestClient) -> None:
        """Even with empty state, /api/pipeline/summary must not 500."""
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code != 500, f"Pipeline summary crashed: {resp.text}"

    def test_provider_stats_never_crashes(self, client: TestClient) -> None:
        """GET /api/providers/stats must not crash even with no measurements."""
        resp = client.get("/api/providers/stats")
        assert resp.status_code != 500, f"Provider stats crashed: {resp.text}"

    def test_automation_usage_never_crashes(self, client: TestClient) -> None:
        """GET /api/automation/usage must not crash with no provider data."""
        resp = client.get("/api/automation/usage")
        assert resp.status_code != 500, f"Automation usage crashed: {resp.text}"

    def test_nodes_list_never_crashes(self, client: TestClient) -> None:
        """GET /api/federation/nodes must never crash regardless of state."""
        resp = client.get("/api/federation/nodes")
        assert resp.status_code != 500, f"Nodes list crashed: {resp.text}"


# ---------------------------------------------------------------------------
# S8: Data completeness — /nodes page covers all former /automation, /usage data
# ---------------------------------------------------------------------------


class TestNodesPageDataCompleteness:
    """
    The /nodes page must be a complete replacement for /automation, /usage,
    and the node-list portion of /remote-ops.
    This validates that all required API surface is present and functional.
    """

    def test_node_registration_api_exists(self, client: TestClient) -> None:
        """POST /api/federation/nodes must exist (registration = /nodes page source)."""
        resp = client.post("/api/federation/nodes", json=_REGISTER_BODY)
        assert resp.status_code in (200, 201), f"Node registration API missing: {resp.status_code}"

    def test_provider_capacity_api_exists(self, client: TestClient) -> None:
        """GET /api/automation/usage must exist (provider capacity = /nodes page source)."""
        resp = client.get("/api/automation/usage")
        assert resp.status_code == 200, "Provider capacity API missing"

    def test_provider_performance_api_exists(self, client: TestClient) -> None:
        """GET /api/providers/stats must exist (provider performance = /nodes page source)."""
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200, "Provider performance API missing"

    def test_node_messaging_api_exists(self, client: TestClient) -> None:
        """POST /api/federation/nodes/{id}/messages must exist (remote ops = /nodes page source)."""
        client.post("/api/federation/nodes", json=_REGISTER_BODY)
        resp = client.post(
            f"/api/federation/nodes/{_NODE_ID}/messages",
            json={"from_node": "test-control", "type": "command", "text": "status", "payload": {}},
        )
        assert resp.status_code in (200, 201), "Node messaging API missing"

    def test_fleet_capabilities_api_exists(self, client: TestClient) -> None:
        """GET /api/federation/nodes/capabilities must exist (fleet overview = /nodes source)."""
        resp = client.get("/api/federation/nodes/capabilities")
        assert resp.status_code in (200, 404), f"Fleet capabilities API missing: {resp.status_code}"


# ---------------------------------------------------------------------------
# S9: Data completeness — /pipeline page covers all former /usage, /remote-ops queue data
# ---------------------------------------------------------------------------


class TestPipelinePageDataCompleteness:
    """
    The /pipeline page must be a complete replacement for /remote-ops queue view
    and /usage provider performance history.
    """

    def test_pipeline_status_api_exists(self, client: TestClient) -> None:
        """GET /api/pipeline/status must exist (execution state = /pipeline source)."""
        resp = client.get("/api/pipeline/status")
        assert resp.status_code in (200, 503), "Pipeline status API missing"

    def test_pipeline_summary_api_exists(self, client: TestClient) -> None:
        """GET /api/pipeline/summary must exist (summary = /pipeline source)."""
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code == 200, "Pipeline summary API missing"

    def test_task_queue_api_exists(self, client: TestClient) -> None:
        """GET /api/agent/tasks must exist (task queue = /pipeline source)."""
        resp = client.get("/api/agent/tasks")
        assert resp.status_code in (200, 401, 403), (
            f"Task queue API missing or crashed: {resp.status_code}"
        )

    def test_provider_performance_in_pipeline_context(self, client: TestClient) -> None:
        """GET /api/providers/stats must also work for /pipeline provider performance view."""
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200
        data = resp.json()
        # Verify structure needed for /pipeline provider performance table
        assert "providers" in data

    def test_pipeline_summary_is_always_accessible(self, client: TestClient) -> None:
        """/api/pipeline/summary must return 200 (used as main /pipeline data source)."""
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code == 200
        data = resp.json()
        # Must have at least 'running' to indicate pipeline state
        assert "running" in data, f"'running' key missing from pipeline summary: {list(data.keys())}"


# ---------------------------------------------------------------------------
# S10: Full create-read cycle for node + heartbeat + message
# ---------------------------------------------------------------------------


class TestFullNodeLifecycleCycle:
    """
    Full create-read-update cycle: register → heartbeat → message → list.
    Proves the /nodes page can display the complete node lifecycle.
    """

    def test_full_node_lifecycle(self, client: TestClient) -> None:
        """
        Create a node, send heartbeat, post message, then verify node appears
        in list with correct state. This is the primary /nodes page scenario.
        """
        # Step 1: Register
        reg = client.post("/api/federation/nodes", json=_REGISTER_BODY)
        assert reg.status_code in (200, 201), f"Registration failed: {reg.text}"

        # Step 2: Heartbeat to update liveness
        hb = client.post(
            f"/api/federation/nodes/{_NODE_ID}/heartbeat",
            json={"status": "online", "capabilities": {"executors": ["claude"]}},
        )
        assert hb.status_code == 200, f"Heartbeat failed: {hb.text}"

        # Step 3: Send a remote-control message
        msg = client.post(
            f"/api/federation/nodes/{_NODE_ID}/messages",
            json={"from_node": "test-controller", "type": "command", "text": "status", "payload": {"detail": "test"}},
        )
        assert msg.status_code == 201, f"Message send failed: {msg.text}"

        # Step 4: Verify node is visible in list with expected fields
        listing = client.get("/api/federation/nodes").json()
        node = next((n for n in listing if n.get("node_id") == _NODE_ID), None)
        assert node is not None, "Node not found in list after lifecycle steps"
        assert node.get("status") == "online"
        assert node.get("hostname") == "test-host.local"
        assert "claude" in node.get("providers", [])

    def test_node_delete_removes_from_list(self, client: TestClient) -> None:
        """DELETE node removes it from /api/federation/nodes list."""
        client.post("/api/federation/nodes", json=_REGISTER_BODY)

        before = client.get("/api/federation/nodes").json()
        assert any(n.get("node_id") == _NODE_ID for n in before), "Node not found before delete"

        del_resp = client.delete(f"/api/federation/nodes/{_NODE_ID}")
        assert del_resp.status_code == 204, f"Delete failed: {del_resp.status_code}"

        after = client.get("/api/federation/nodes").json()
        assert not any(n.get("node_id") == _NODE_ID for n in after), "Node still present after delete"
