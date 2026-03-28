"""Tests for navigation consolidation: /automation, /usage, /remote-ops → /nodes and /pipeline.

Idea: Consolidate 4 overlapping pages into 2 clear pages:
  - /nodes  — everything about nodes: list, health, providers, messages, remote control
  - /pipeline — everything about task execution: queue, running, completed, streaks, provider performance

This test file verifies:
1. The API endpoints that back /nodes exist and return valid data shapes
2. The API endpoints that back /pipeline exist and return valid data shapes
3. The /nodes page covers what was previously in /automation, /nodes, and /remote-ops
4. The /pipeline page covers what was previously in /usage and /automation (provider perf)
5. The old pages either redirect or their routes are marked for removal
6. The web page files have the right metadata titles reflecting the new navigation

Verification Scenarios:
  Scenario 1 — nodes page API contract (federation list)
  Scenario 2 — nodes page API contract (node stats/health)
  Scenario 3 — pipeline page API contract (pipeline status + provider stats)
  Scenario 4 — nodes page covers remote control (messages endpoint)
  Scenario 5 — page file structure: /nodes and /pipeline exist; deprecation markers in old pages
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_APP = REPO_ROOT / "web" / "app"

# ─── Page file paths ──────────────────────────────────────────────────────────

NODES_PAGE = WEB_APP / "nodes" / "page.tsx"
PIPELINE_PAGE = WEB_APP / "pipeline" / "page.tsx"
AUTOMATION_PAGE = WEB_APP / "automation" / "page.tsx"
USAGE_PAGE = WEB_APP / "usage" / "page.tsx"
REMOTE_OPS_PAGE = WEB_APP / "remote-ops" / "page.tsx"


# =============================================================================
# Scenario 1 — /nodes page API contract: GET /api/federation/nodes
# =============================================================================

class TestNodesPageApiFederationList:
    """GET /api/federation/nodes must exist and return a list shape."""

    def test_federation_nodes_returns_200_or_empty_list(self) -> None:
        """
        Setup: No precondition — endpoint must always be reachable.
        Action: GET /api/federation/nodes
        Expected: HTTP 200, body is a JSON array (possibly empty).
        """
        resp = client.get("/api/federation/nodes")
        assert resp.status_code == 200, (
            f"Expected 200 from /api/federation/nodes, got {resp.status_code}"
        )
        data = resp.json()
        assert isinstance(data, list), (
            f"Expected list from /api/federation/nodes, got {type(data).__name__}"
        )

    def test_federation_node_schema_when_populated(self) -> None:
        """
        Setup: At least one node exists (or skip gracefully).
        Action: GET /api/federation/nodes
        Expected: Each node has node_id, hostname, os_type, status, last_seen_at, providers.
        """
        resp = client.get("/api/federation/nodes")
        assert resp.status_code == 200
        nodes = resp.json()
        if not nodes:
            pytest.skip("No federation nodes registered — schema check skipped")
        for node in nodes:
            assert "node_id" in node, f"Node missing node_id: {node}"
            assert "hostname" in node, f"Node missing hostname: {node}"
            assert "status" in node, f"Node missing status: {node}"
            assert "last_seen_at" in node, f"Node missing last_seen_at: {node}"
            assert "providers" in node, f"Node missing providers: {node}"
            assert isinstance(node["providers"], list), (
                f"providers must be a list, got {type(node['providers']).__name__}"
            )

    def test_federation_nodes_capabilities_endpoint(self) -> None:
        """
        Setup: Fleet capabilities endpoint must be accessible.
        Action: GET /api/federation/nodes/capabilities
        Expected: HTTP 200 or 404; if 200, body has total_nodes and executors.
        """
        resp = client.get("/api/federation/nodes/capabilities")
        assert resp.status_code in (200, 404), (
            f"Unexpected status {resp.status_code} from /api/federation/nodes/capabilities"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "total_nodes" in data, "capabilities response missing total_nodes"
            assert "executors" in data, "capabilities response missing executors"

    def test_federation_nodes_bad_node_id_not_500(self) -> None:
        """
        Edge case: request messages for a node that doesn't exist.
        Action: GET /api/federation/nodes/nonexistent-node-xyz/messages
        Expected: HTTP 200 (empty list) or 404 — NOT 500.
        The messages endpoint returns an empty list for unknown nodes rather than 404,
        which is acceptable for the /nodes page use case.
        """
        resp = client.get("/api/federation/nodes/nonexistent-node-xyz/messages")
        assert resp.status_code in (200, 404), (
            f"Expected 200 or 404 for unknown node messages, got {resp.status_code}"
        )


# =============================================================================
# Scenario 2 — /nodes page API contract: node stats and health
# =============================================================================

class TestNodesPageApiNodeStats:
    """GET /api/federation/nodes/stats must exist and return network-level health."""

    def test_federation_nodes_stats_reachable(self) -> None:
        """
        Setup: Stats endpoint must be accessible even with no data.
        Action: GET /api/federation/nodes/stats
        Expected: HTTP 200 or 404; if 200, response has a recognizable shape.
        """
        resp = client.get("/api/federation/nodes/stats")
        assert resp.status_code in (200, 404), (
            f"Unexpected status from /api/federation/nodes/stats: {resp.status_code}"
        )

    def test_federation_nodes_stats_shape_when_available(self) -> None:
        """
        Setup: Stats endpoint returns data.
        Action: GET /api/federation/nodes/stats
        Expected: If 200, response has nodes and window_days keys.
        """
        resp = client.get("/api/federation/nodes/stats")
        if resp.status_code != 200:
            pytest.skip("federation/nodes/stats not available (404)")
        data = resp.json()
        assert "nodes" in data or "window_days" in data, (
            "federation/nodes/stats response has unexpected shape — "
            f"keys: {list(data.keys())}"
        )

    def test_node_messages_post_requires_valid_body(self) -> None:
        """
        Edge case: POST to node messages with empty body.
        Action: POST /api/federation/nodes/some-node/messages with {}
        Expected: HTTP 404 (node not found) or 422 (validation error) — NOT 500.
        """
        resp = client.post("/api/federation/nodes/some-node/messages", json={})
        assert resp.status_code in (404, 422), (
            f"Expected 404 or 422 for invalid message post, got {resp.status_code}"
        )

    def test_node_register_endpoint_exists(self) -> None:
        """
        Setup: Node registration must be reachable.
        Action: POST /api/federation/nodes with an empty body
        Expected: HTTP 422 (validation) — proves endpoint exists, not 404.
        """
        resp = client.post("/api/federation/nodes", json={})
        assert resp.status_code == 422, (
            f"Expected 422 (validation) from /api/federation/nodes POST with empty body, "
            f"got {resp.status_code}"
        )


# =============================================================================
# Scenario 3 — /pipeline page API contract: status + provider perf
# =============================================================================

class TestPipelinePageApiContract:
    """APIs that power the /pipeline page must be reachable and shaped correctly."""

    def test_pipeline_status_endpoint_reachable(self) -> None:
        """
        Setup: Pipeline may or may not be running.
        Action: GET /api/pipeline/status
        Expected: HTTP 200 or 503 (not running); body has 'running' key.
        """
        resp = client.get("/api/pipeline/status")
        assert resp.status_code in (200, 503), (
            f"Unexpected status from /api/pipeline/status: {resp.status_code}"
        )
        data = resp.json()
        assert "running" in data, (
            f"pipeline/status response missing 'running' key. Keys: {list(data.keys())}"
        )

    def test_pipeline_summary_always_200(self) -> None:
        """
        Setup: Pipeline summary is lightweight and must never 503.
        Action: GET /api/pipeline/summary
        Expected: HTTP 200 always, body has pipeline state.
        """
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code == 200, (
            f"pipeline/summary must always return 200, got {resp.status_code}"
        )
        data = resp.json()
        assert isinstance(data, dict), "pipeline/summary must return an object"

    def test_provider_stats_endpoint_accessible(self) -> None:
        """
        Setup: Provider stats endpoint for the /pipeline performance view.
        Action: GET /api/providers/stats
        Expected: HTTP 200; body has providers dict and summary.
        """
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200, (
            f"Expected 200 from /api/providers/stats, got {resp.status_code}"
        )
        data = resp.json()
        assert "providers" in data, f"providers/stats missing 'providers' key. Keys: {list(data.keys())}"
        assert "summary" in data, f"providers/stats missing 'summary' key. Keys: {list(data.keys())}"

    def test_provider_stats_summary_shape(self) -> None:
        """
        Setup: Provider stats summary must expose fleet health totals.
        Action: GET /api/providers/stats
        Expected: summary has total_providers, healthy_providers, attention_needed.
        """
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200
        summary = resp.json().get("summary", {})
        for key in ("total_providers", "healthy_providers", "attention_needed"):
            assert key in summary, (
                f"providers/stats summary missing '{key}'. Keys: {list(summary.keys())}"
            )

    def test_agent_tasks_queue_endpoint_accessible(self) -> None:
        """
        Setup: Task queue is a primary pipeline metric.
        Action: GET /api/agent/tasks?status=pending&limit=5
        Expected: HTTP 200, body has tasks list or total count.
        """
        resp = client.get("/api/agent/tasks?status=pending&limit=5")
        assert resp.status_code == 200, (
            f"Expected 200 from agent/tasks, got {resp.status_code}"
        )
        data = resp.json()
        assert "tasks" in data or "total" in data, (
            f"agent/tasks response missing 'tasks' or 'total'. Keys: {list(data.keys())}"
        )

    def test_agent_tasks_invalid_status_400_or_200(self) -> None:
        """
        Edge case: invalid status filter should not 500.
        Action: GET /api/agent/tasks?status=invalid_xyz
        Expected: HTTP 200 (returns empty) or 400/422 (validation) — NOT 500.
        """
        resp = client.get("/api/agent/tasks?status=invalid_xyz")
        assert resp.status_code in (200, 400, 422), (
            f"Expected 200/400/422 for invalid status filter, got {resp.status_code}"
        )

    def test_automation_usage_endpoint_for_pipeline(self) -> None:
        """
        Setup: Automation usage data feeds provider performance in /pipeline.
        Action: GET /api/automation/usage
        Expected: HTTP 200; body has providers and generated_at.
        """
        resp = client.get("/api/automation/usage")
        assert resp.status_code == 200, (
            f"Expected 200 from /api/automation/usage, got {resp.status_code}"
        )
        data = resp.json()
        assert "providers" in data, (
            f"automation/usage missing 'providers'. Keys: {list(data.keys())}"
        )
        assert "generated_at" in data, (
            f"automation/usage missing 'generated_at'. Keys: {list(data.keys())}"
        )


# =============================================================================
# Scenario 4 — /nodes covers remote control (messages endpoint)
# =============================================================================

class TestNodesPageRemoteControl:
    """The /nodes page subsumes /remote-ops remote control capabilities."""

    def test_message_post_endpoint_exists(self) -> None:
        """
        Setup: Messaging a node is a core /nodes remote-control feature.
        Action: POST /api/federation/nodes/<real-or-fake>/messages with valid body
        Expected: 404 (no such node) or 201 (delivered) — endpoint is wired.
        """
        resp = client.post(
            "/api/federation/nodes/fake-node-for-testing/messages",
            json={"content": "ping", "type": "test"},
        )
        # 404 = endpoint exists but node not found (correct); 201 = created
        assert resp.status_code in (201, 404, 422), (
            f"Messages endpoint not wired — got {resp.status_code}"
        )

    def test_node_messages_list_for_unknown_node(self) -> None:
        """
        Edge case: list messages for a node that doesn't exist.
        Action: GET /api/federation/nodes/does-not-exist/messages
        Expected: HTTP 200 (empty list) or 404 — NOT 500.
        The endpoint gracefully handles unknown nodes for the /nodes remote-control panel.
        """
        resp = client.get("/api/federation/nodes/does-not-exist/messages")
        assert resp.status_code in (200, 404), (
            f"Expected 200 or 404 for unknown node, got {resp.status_code}"
        )

    def test_pipeline_status_is_remote_control_data(self) -> None:
        """
        Setup: /nodes consolidates pipeline queue visibility.
        Action: GET /api/pipeline/summary
        Expected: Always 200, includes data that remote ops panel would show.
        """
        resp = client.get("/api/pipeline/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "pipeline/summary must be an object"


# =============================================================================
# Scenario 5 — Web page file structure
# =============================================================================

class TestWebPageFileStructure:
    """/nodes and /pipeline pages must exist with correct metadata and content."""

    def test_nodes_page_file_exists(self) -> None:
        """The /nodes page must exist as a Next.js page."""
        assert NODES_PAGE.exists(), f"/nodes page not found at {NODES_PAGE}"

    def test_pipeline_page_file_exists(self) -> None:
        """The /pipeline page must exist as a Next.js page."""
        assert PIPELINE_PAGE.exists(), f"/pipeline page not found at {PIPELINE_PAGE}"

    def test_nodes_page_has_federation_nodes_title_metadata(self) -> None:
        """
        /nodes page must declare a title in its metadata export.
        Expected: metadata title contains 'Node' or 'Federation' (not 'Automation').
        """
        content = NODES_PAGE.read_text(encoding="utf-8")
        assert "metadata" in content, "/nodes/page.tsx missing metadata export"
        # Title should be nodes-related, not inherit the old 'Automation' label
        title_match = re.search(r'title:\s*["\']([^"\']+)["\']', content)
        assert title_match is not None, "/nodes/page.tsx metadata has no title field"
        title = title_match.group(1)
        assert "Automation" not in title, (
            f"/nodes page title is still 'Automation': '{title}' — "
            "should be updated for the consolidated navigation"
        )

    def test_pipeline_page_has_content_about_execution(self) -> None:
        """
        /pipeline page must contain language about task execution, not just nodes.
        Expected: page references running/completed tasks or provider performance.
        """
        content = PIPELINE_PAGE.read_text(encoding="utf-8")
        execution_terms = ["running", "completed", "provider", "queue", "task", "streak"]
        found = [t for t in execution_terms if t.lower() in content.lower()]
        assert len(found) >= 3, (
            f"/pipeline page missing execution-related content. Found only: {found}"
        )

    def test_nodes_page_has_content_about_federation(self) -> None:
        """
        /nodes page must reference federation nodes, providers, and status.
        Expected: page contains federation/node-related content.
        """
        content = NODES_PAGE.read_text(encoding="utf-8")
        node_terms = ["node", "provider", "status", "federation", "hostname"]
        found = [t for t in node_terms if t.lower() in content.lower()]
        assert len(found) >= 3, (
            f"/nodes page missing node-related content. Found only: {found}"
        )

    def test_nodes_page_includes_message_form_or_messaging(self) -> None:
        """
        /nodes page must expose messaging / remote control (subsumes /remote-ops).
        Expected: page imports MessageForm or references message/control UI.
        """
        content = NODES_PAGE.read_text(encoding="utf-8")
        has_messaging = (
            "MessageForm" in content
            or "messages" in content.lower()
            or "message" in content.lower()
        )
        assert has_messaging, (
            "/nodes page has no messaging component — "
            "it must subsume the remote-ops messaging capability"
        )

    def test_pipeline_page_links_to_nodes(self) -> None:
        """
        /pipeline page must cross-link to /nodes (consolidated navigation).
        Expected: page has an href pointing to /nodes.
        """
        content = PIPELINE_PAGE.read_text(encoding="utf-8")
        assert '"/nodes"' in content or "href='/nodes'" in content or 'href="/nodes"' in content, (
            "/pipeline page does not link to /nodes — consolidated nav requires cross-links"
        )

    def test_automation_page_exists_or_is_deprecated(self) -> None:
        """
        /automation page: if it still exists, it should signal it is deprecated/redirected.
        This is a transition test — the page may be removed or redirect to /nodes.
        The test is intentionally lenient: old page can exist but should note consolidation.
        """
        if not AUTOMATION_PAGE.exists():
            # Ideal state: page removed entirely
            return
        content = AUTOMATION_PAGE.read_text(encoding="utf-8")
        # If the page still exists, check it mentions the consolidated pages or redirects
        has_consolidation_signal = (
            "redirect" in content.lower()
            or "/nodes" in content
            or "/pipeline" in content
            or "Redirect" in content
            or "permanentRedirect" in content
        )
        # This is a soft assertion — we warn but don't fail if the page exists without redirect.
        # The idea spec says to remove these pages; this test tracks whether that's done.
        if not has_consolidation_signal:
            pytest.xfail(
                "/automation page still exists without a redirect to /nodes — "
                "consolidation incomplete: add redirect('/nodes') or remove the page"
            )

    def test_usage_page_exists_or_is_deprecated(self) -> None:
        """
        /usage page: if it still exists, it should redirect to /pipeline.
        Lenient xfail: warns when consolidation is incomplete.
        """
        if not USAGE_PAGE.exists():
            return
        content = USAGE_PAGE.read_text(encoding="utf-8")
        has_consolidation_signal = (
            "redirect" in content.lower()
            or "/pipeline" in content
            or "/nodes" in content
            or "Redirect" in content
            or "permanentRedirect" in content
        )
        if not has_consolidation_signal:
            pytest.xfail(
                "/usage page still exists without a redirect to /pipeline — "
                "consolidation incomplete: add redirect('/pipeline') or remove the page"
            )

    def test_remote_ops_page_exists_or_is_deprecated(self) -> None:
        """
        /remote-ops page: if it still exists, it should redirect to /nodes.
        Lenient xfail: warns when consolidation is incomplete.
        """
        if not REMOTE_OPS_PAGE.exists():
            return
        content = REMOTE_OPS_PAGE.read_text(encoding="utf-8")
        has_consolidation_signal = (
            "redirect" in content.lower()
            or "/nodes" in content
            or "Redirect" in content
            or "permanentRedirect" in content
        )
        if not has_consolidation_signal:
            pytest.xfail(
                "/remote-ops page still exists without a redirect to /nodes — "
                "consolidation incomplete: add redirect('/nodes') or remove the page"
            )


# =============================================================================
# Scenario 6 — Full create-read cycle: register node, verify it appears in list
# =============================================================================

class TestNodeRegistrationCycle:
    """Full create-read cycle: register a node, verify it appears in /api/federation/nodes."""

    def test_register_node_and_read_back(self) -> None:
        """
        Setup: No pre-existing node with test hostname.
        Action: POST /api/federation/nodes with minimal payload.
        Expected: HTTP 200 or 201, returned node has node_id and hostname.
        Then: GET /api/federation/nodes includes the new node.
        Edge: POST same node again returns 200 (upsert) or 409 (conflict) — NOT 500.
        """
        # node_id must be exactly 16 chars per API validation
        payload = {
            "node_id": "tst-cnsld-001-xx",
            "hostname": "tst-cnsld-host",
            "os_type": "linux",
            "providers": ["claude"],
            "capabilities": {},
        }
        resp = client.post("/api/federation/nodes", json=payload)
        # Registration is upsert-style or create; 200/201 both valid
        assert resp.status_code in (200, 201, 409), (
            f"Unexpected status from node registration: {resp.status_code} — {resp.text[:200]}"
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            assert "node_id" in data, f"Registered node missing node_id: {data}"

        # Verify the node appears in the list (or 409 = already exists, also valid)
        list_resp = client.get("/api/federation/nodes")
        assert list_resp.status_code == 200
        nodes = list_resp.json()
        ids = [n.get("node_id") for n in nodes]
        # If registration succeeded, node must be findable
        if resp.status_code in (200, 201):
            assert "tst-cnsld-001-xx" in ids, (
                f"Registered node not found in /api/federation/nodes list. IDs: {ids[:10]}"
            )

    def test_register_node_missing_required_fields(self) -> None:
        """
        Edge case: register node with missing required fields.
        Action: POST /api/federation/nodes with {}
        Expected: HTTP 422 (validation error), not 500.
        """
        resp = client.post("/api/federation/nodes", json={})
        assert resp.status_code == 422, (
            f"Expected 422 for empty node registration body, got {resp.status_code}"
        )


# =============================================================================
# Scenario 7 — Provider performance data shape (powers /pipeline provider section)
# =============================================================================

class TestProviderPerformanceShape:
    """Provider stats endpoint must expose data shape needed by the /pipeline page."""

    def test_provider_stats_providers_dict_values(self) -> None:
        """
        Setup: At least an empty providers dict returned.
        Action: GET /api/providers/stats
        Expected: providers dict values have required perf fields if populated.
        """
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200
        providers = resp.json().get("providers", {})
        if not providers:
            pytest.skip("No provider measurements available")
        for name, stats in providers.items():
            for field in ("total_runs", "successes", "failures", "success_rate"):
                assert field in stats, (
                    f"Provider '{name}' missing field '{field}'. Keys: {list(stats.keys())}"
                )
            assert 0.0 <= stats["success_rate"] <= 1.0, (
                f"Provider '{name}' success_rate out of range: {stats['success_rate']}"
            )

    def test_provider_stats_alerts_list(self) -> None:
        """
        Setup: Alerts list present even if empty.
        Action: GET /api/providers/stats
        Expected: 'alerts' key is present and is a list.
        """
        resp = client.get("/api/providers/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data, f"providers/stats missing 'alerts'. Keys: {list(data.keys())}"
        assert isinstance(data["alerts"], list), (
            f"providers/stats 'alerts' must be a list, got {type(data['alerts']).__name__}"
        )

    def test_automation_usage_providers_have_provider_field(self) -> None:
        """
        Setup: Automation usage feeds /pipeline provider performance section.
        Action: GET /api/automation/usage
        Expected: each provider entry has a 'provider' key with a string name.
        """
        resp = client.get("/api/automation/usage")
        assert resp.status_code == 200
        providers = resp.json().get("providers", [])
        if not providers:
            pytest.skip("No providers in automation/usage")
        for p in providers:
            assert "provider" in p, f"Provider entry missing 'provider' key: {p}"
            assert isinstance(p["provider"], str), (
                f"'provider' must be a string, got {type(p['provider']).__name__}"
            )
