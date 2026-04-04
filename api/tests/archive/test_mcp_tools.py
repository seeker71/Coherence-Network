"""Tests for MCP tool handlers.

Tests call handler functions directly (not via MCP protocol) against the
real service layer backed by an in-memory SQLite store.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure api/ is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("COHERENCE_ENV", "test")


# ---------------------------------------------------------------------------
# Helpers to seed test data
# ---------------------------------------------------------------------------

def _seed_idea(idea_id: str = "test-idea-1", name: str = "Test Idea") -> None:
    """Create an idea directly via the service layer."""
    from app.services import idea_service

    idea_service.create_idea(
        idea_id=idea_id,
        name=name,
        description="A test idea for MCP tool testing",
        potential_value=10.0,
        estimated_cost=2.0,
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# Tests: read-only tools
# ---------------------------------------------------------------------------

class TestBrowseIdeas:
    def test_returns_list_with_expected_fields(self):
        from app.services.mcp_tool_registry import browse_ideas_handler

        result = browse_ideas_handler({"limit": 5})
        assert isinstance(result, dict)
        assert "ideas" in result
        assert isinstance(result["ideas"], list)
        # Should have summary and pagination keys
        assert "summary" in result
        assert "pagination" in result


class TestGetIdea:
    def test_returns_full_idea(self):
        from app.services.mcp_tool_registry import get_idea_handler

        _seed_idea("get-idea-test", "Get Idea Test")
        result = get_idea_handler({"idea_id": "get-idea-test"})
        assert isinstance(result, dict)
        assert result.get("id") == "get-idea-test"
        assert "open_questions" in result
        assert "stage" in result

    def test_returns_error_for_missing_id(self):
        from app.services.mcp_tool_registry import get_idea_handler

        result = get_idea_handler({"idea_id": "nonexistent-idea-xyz"})
        assert isinstance(result, dict)
        assert "error" in result


class TestBrowseSpecs:
    def test_returns_list(self):
        from app.services.mcp_tool_registry import browse_specs_handler

        result = browse_specs_handler({"limit": 5})
        assert isinstance(result, list)


class TestGetStrategies:
    def test_returns_strategies_structure(self):
        from app.services.mcp_tool_registry import get_strategies_handler

        result = get_strategies_handler({})
        assert isinstance(result, dict)
        assert "strategies" in result
        assert "total" in result


class TestGetProviderStats:
    def test_returns_stats_structure(self):
        from app.services.mcp_tool_registry import get_provider_stats_handler

        result = get_provider_stats_handler({})
        assert isinstance(result, dict)
        assert "decision_point" in result


# ---------------------------------------------------------------------------
# Tests: write tools
# ---------------------------------------------------------------------------

class TestPublishIdea:
    def test_creates_governance_change_request(self):
        from app.services.mcp_tool_registry import publish_idea_handler

        result = publish_idea_handler({
            "name": "MCP Published Idea",
            "description": "Created via MCP tool",
            "potential_value": 15.0,
            "estimated_cost": 3.0,
            "confidence": 0.7,
            "contributor_id": "mcp-test-agent",
        })
        assert isinstance(result, dict)
        assert result.get("request_type") == "idea_create"
        assert result.get("status") == "open"
        assert "id" in result


class TestForkIdea:
    def test_creates_new_idea_with_parent(self):
        from app.services.mcp_tool_registry import fork_idea_handler

        _seed_idea("fork-source", "Fork Source Idea")
        result = fork_idea_handler({
            "source_idea_id": "fork-source",
            "contributor_id": "mcp-test-agent",
            "adaptation_notes": "Testing fork",
        })
        assert isinstance(result, dict)
        assert result.get("parent_idea_id") == "fork-source"
        assert "id" in result

    def test_returns_error_for_missing_source(self):
        from app.services.mcp_tool_registry import fork_idea_handler

        result = fork_idea_handler({
            "source_idea_id": "nonexistent-source-xyz",
            "contributor_id": "mcp-test-agent",
        })
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: coordination tools
# ---------------------------------------------------------------------------

class TestListOpenChanges:
    def test_returns_list(self):
        from app.services.mcp_tool_registry import list_open_changes_handler

        result = list_open_changes_handler({"limit": 10})
        assert isinstance(result, list)


class TestGetResonanceFeed:
    def test_returns_feed_structure(self):
        from app.services.mcp_tool_registry import get_resonance_feed_handler

        result = get_resonance_feed_handler({"limit": 5})
        assert isinstance(result, dict)
        assert "ideas" in result
