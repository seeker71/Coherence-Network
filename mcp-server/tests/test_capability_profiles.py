"""Observe capability admission before tool arguments or effects are reached."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coherence_mcp_server import form_cli_tools, server


@pytest.fixture(autouse=True)
def companion_profile(monkeypatch):
    monkeypatch.setitem(server._SETTINGS, "capability_profile", "companion")


def forbid(*args, **kwargs):
    pytest.fail("A denied capability reached input processing, network, native execution, or storage")


@pytest.mark.asyncio
async def test_companion_discovery_is_small_and_describes_real_effects():
    tools = await server.handle_list_tools()
    assert len(tools) == 10
    assert {tool.name for tool in tools} == set(server.COMPANION_TOOLS)
    for tool in tools:
        assert tool.annotations.title
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is (tool.name != "coherence_transmute")
        if tool.name != "coherence_transmute":
            assert "send public context only" in tool.description


@pytest.mark.parametrize("name", sorted(set(server.TOOL_MAP) - set(server.COMPANION_TOOLS)))
def test_every_hidden_tool_is_denied_before_arguments_or_effects(name, monkeypatch):
    class UnreadArguments(dict):
        get = forbid
        __getitem__ = forbid
    for operation in ("api_get", "api_post", "api_patch", "api_put", "api_sse"):
        monkeypatch.setattr(server, operation, forbid)
    monkeypatch.setattr(form_cli_tools, "catalog_capture", forbid)
    monkeypatch.setattr(form_cli_tools, "kernel_route", forbid)
    result = server.dispatch(name, UnreadArguments())
    assert result["error_code"] == "capability_profile_denied"
    assert "does not authorize" in result["next_step"]


@pytest.mark.asyncio
async def test_mcp_denial_is_an_error_and_tool_arguments_cannot_enable_advanced(monkeypatch):
    monkeypatch.setattr(server, "api_post", forbid)
    result = await server.handle_call_tool("coherence_create_idea", {
        "name": "not published", "capability_profile": "advanced",
        "mcp": {"capability_profile": "advanced"},
    })
    assert result.isError is True
    assert json.loads(result.content[0].text)["error_code"] == "capability_profile_denied"


@pytest.mark.asyncio
async def test_advanced_opt_in_reveals_catalog_but_does_not_grant_learning_consent(monkeypatch):
    monkeypatch.setitem(server._SETTINGS, "capability_profile", "advanced")
    assert {tool.name for tool in await server.handle_list_tools()} == set(server.TOOL_MAP)
    monkeypatch.setattr(form_cli_tools, "load_settings", forbid)
    denied = await server.handle_call_tool("coherence_capture", {
        "request": "selected", "raw": "original", "transmuted": "reviewed",
    })
    assert denied.isError is True
    assert json.loads(denied.content[0].text)["captured"] is False


def test_advanced_dispatch_preserves_existing_explicit_tool_contract(monkeypatch):
    monkeypatch.setitem(server._SETTINGS, "capability_profile", "advanced")
    calls = []
    monkeypatch.setattr(server, "api_post", lambda path, body: calls.append((path, body)) or {"created": True})
    result = server.dispatch("coherence_create_idea", {"id": "selected-public-idea", "name": "selected public idea", "description": "selected public description"})
    assert result["created"] is True
    assert calls[0][0] == "/api/ideas"


def test_default_public_read_needs_no_credential(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "API_KEY", "")
    def get(url, **kwargs):
        calls.append((url, kwargs))
        class Reply:
            def raise_for_status(self):
                pass
            def json(self):
                return {"blueprints": []}
        return Reply()
    monkeypatch.setattr(server.httpx, "get", get)
    assert server.dispatch("coherence_list_blueprints", {}) == {"blueprints": []}
    assert calls[0][0].endswith("/api/blueprints")
    assert "X-API-Key" not in calls[0][1]["headers"]
    assert "Authorization" not in calls[0][1]["headers"]


@pytest.mark.parametrize("name,field", [
    ("coherence_get_idea", "idea_id"),
    ("coherence_idea_progress", "idea_id"),
    ("coherence_get_spec", "spec_id"),
])
@pytest.mark.parametrize("identifier", ["..", "../agent/tasks/next", "%2e%2e%2fadmin", "x\\..\\admin", "", None, "x\nheader"])
def test_allowed_read_cannot_escape_its_route(name, field, identifier, monkeypatch):
    monkeypatch.setattr(server, "api_get", forbid)
    assert "error" in server.dispatch(name, {field: identifier})


def test_public_id_is_encoded_as_one_segment(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "api_get", lambda path: calls.append(path) or {})
    server.dispatch("coherence_get_idea", {"idea_id": "café?view=all#part"})
    assert calls == ["/api/ideas/caf%C3%A9%3Fview%3Dall%23part"]


@pytest.mark.asyncio
async def test_invalid_runtime_profile_stays_closed(monkeypatch):
    monkeypatch.setitem(server._SETTINGS, "capability_profile", "unexpected")
    monkeypatch.setattr(server, "api_get", forbid)
    assert await server.handle_list_tools() == []
    assert server.dispatch("coherence_list_blueprints", {})["error_code"] == "capability_profile_denied"
