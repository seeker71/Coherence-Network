from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


@pytest.mark.parametrize("path", ["/mcp", "/api/mcp"])
@pytest.mark.asyncio
async def test_mcp_info_declares_no_auth_and_no_challenge(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert "www-authenticate" not in response.headers
    body = response.json()
    assert body["auth_required"] is False
    assert body["auth_schemes"] == ["none"]
    assert {"search", "fetch"} <= set(body["tools"])


@pytest.mark.parametrize("path", ["/mcp", "/api/mcp"])
@pytest.mark.asyncio
async def test_mcp_initialize_does_not_require_oauth(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            path,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )

    assert response.status_code == 200
    assert "www-authenticate" not in response.headers
    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "coherence-network"
    assert result["capabilities"]["tools"]["listChanged"] is False
    assert "Authentication type: none" in result["instructions"]


@pytest.mark.asyncio
async def test_mcp_tools_list_is_read_only_no_auth_surface():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": "tools", "method": "tools/list"},
        )

    assert response.status_code == 200
    tools = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {"search", "fetch", "browse_ideas", "browse_specs"} <= tools
    assert "publish_idea" not in tools
    assert "create_spec" not in tools


@pytest.mark.asyncio
async def test_mcp_search_call_returns_connector_shape_without_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "search",
                "method": "tools/call",
                "params": {"name": "search", "arguments": {"query": "coherence"}},
            },
        )

    assert response.status_code == 200
    assert "www-authenticate" not in response.headers
    content = response.json()["result"]["content"]
    assert content[0]["type"] == "text"
    parsed = json.loads(content[0]["text"])
    assert "results" in parsed
    assert isinstance(parsed["results"], list)
