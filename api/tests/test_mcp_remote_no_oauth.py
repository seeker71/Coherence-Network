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
    assert {"search", "fetch", "start_dialogue", "get_dialogue", "remove_dialogue"} <= set(body["tools"])


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
async def test_mcp_tools_list_marks_public_dialogue_read_and_write_surfaces():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": "tools", "method": "tools/list"},
        )

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
    assert {"search", "fetch", "browse_ideas", "browse_specs", "start_dialogue", "get_dialogue", "remove_dialogue"} <= set(tools)
    assert "publish_idea" not in tools
    assert "create_spec" not in tools
    assert tools["start_dialogue"]["annotations"]["readOnlyHint"] is False
    assert tools["start_dialogue"]["annotations"]["openWorldHint"] is True
    assert tools["start_dialogue"]["annotations"]["idempotentHint"] is False
    assert tools["get_dialogue"]["annotations"]["readOnlyHint"] is True
    assert tools["remove_dialogue"]["annotations"]["destructiveHint"] is True


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


@pytest.mark.asyncio
async def test_mcp_start_and_get_dialogue(monkeypatch):
    from app.services import dialogue_service

    monkeypatch.setattr(
        dialogue_service,
        "submit_dialogue",
        lambda **_: {"id": "task_dialogue", "state": "pending"},
    )
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue",
        lambda dialogue_id: {"id": dialogue_id, "state": "miss"},
    )
    monkeypatch.setattr(
        dialogue_service,
        "release_dialogue",
        lambda dialogue_id, token: dialogue_id == "task_dialogue" and token == "release-token-long-enough",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        started = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "start",
                "method": "tools/call",
                "params": {
                    "name": "start_dialogue",
                    "arguments": {
                        "question": "What does the river see?",
                        "point_of_view": "river",
                        "locale": "en",
                        "public_disclosure_ack": "public-unlisted-v1",
                    },
                },
            },
        )
        observed = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "get",
                "method": "tools/call",
                "params": {
                    "name": "get_dialogue",
                    "arguments": {"dialogue_id": "task_dialogue"},
                },
            },
        )
        released = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "remove",
                "method": "tools/call",
                "params": {
                    "name": "remove_dialogue",
                    "arguments": {
                        "dialogue_id": "task_dialogue",
                        "removal_token": "release-token-long-enough",
                    },
                },
            },
        )

    start_payload = json.loads(started.json()["result"]["content"][0]["text"])
    get_payload = json.loads(observed.json()["result"]["content"][0]["text"])
    release_payload = json.loads(released.json()["result"]["content"][0]["text"])
    assert start_payload == {"id": "task_dialogue", "state": "pending"}
    assert get_payload == {"id": "task_dialogue", "state": "miss"}
    assert release_payload == {"id": "task_dialogue", "state": "tombstoned", "released": True}
    assert observed.json()["result"]["structuredContent"] == get_payload


@pytest.mark.asyncio
async def test_mcp_start_dialogue_refuses_implicit_public_disclosure_ack():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "start",
                "method": "tools/call",
                "params": {
                    "name": "start_dialogue",
                    "arguments": {
                        "question": "hello",
                        "point_of_view": "river",
                        "locale": "en",
                    },
                },
            },
        )

    assert response.json()["result"]["isError"] is True


@pytest.mark.asyncio
async def test_mcp_start_dialogue_uses_the_shared_peer_pacing_gate(monkeypatch):
    from app.services import dialogue_service

    starts = []

    def paced_submit(**values):
        starts.append(values["network_peer"])
        if len(starts) > dialogue_service.STARTS_PER_WINDOW:
            raise dialogue_service.DialogueRateLimitError(42)
        return {"id": "dlg_paced", "state": "pending"}

    monkeypatch.setattr(
        dialogue_service,
        "submit_dialogue",
        paced_submit,
    )
    bodies = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        for index in range(dialogue_service.STARTS_PER_WINDOW + 1):
            response = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {
                        "name": "start_dialogue",
                        "arguments": {
                            "question": f"probe {index}",
                            "point_of_view": "probe",
                            "locale": "en",
                            "public_disclosure_ack": "public-unlisted-v1",
                        },
                    },
                },
            )
            bodies.append(response.json()["result"])

    assert all(result["isError"] is False for result in bodies[:-1])
    assert bodies[-1]["isError"] is True
    assert bodies[-1]["structuredContent"]["retry_after"] == 42
    assert len(set(starts)) == 1
