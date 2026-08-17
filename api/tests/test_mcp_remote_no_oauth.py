from __future__ import annotations

import asyncio
import json
import threading

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
    assert {
        "search",
        "fetch",
        "start_dialogue",
        "get_dialogue",
        "reply_dialogue",
        "get_dialogue_thread",
        "remove_dialogue",
    } <= set(body["tools"])


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
    assert {
        "search",
        "fetch",
        "browse_ideas",
        "browse_specs",
        "start_dialogue",
        "get_dialogue",
        "reply_dialogue",
        "get_dialogue_thread",
        "remove_dialogue",
    } <= set(tools)
    assert "publish_idea" not in tools
    assert "create_spec" not in tools
    assert tools["start_dialogue"]["annotations"]["readOnlyHint"] is False
    assert tools["start_dialogue"]["annotations"]["openWorldHint"] is True
    assert tools["start_dialogue"]["annotations"]["idempotentHint"] is False
    assert tools["get_dialogue"]["annotations"]["readOnlyHint"] is True
    assert tools["reply_dialogue"]["annotations"]["readOnlyHint"] is False
    assert tools["get_dialogue_thread"]["annotations"]["readOnlyHint"] is True
    assert tools["remove_dialogue"]["annotations"]["destructiveHint"] is True
    assert tools["start_dialogue"]["inputSchema"]["properties"][
        "public_disclosure_ack"
    ]["enum"] == ["public-unlisted-v1", "public-unlisted-thread-v2"]
    assert tools["reply_dialogue"]["inputSchema"]["properties"][
        "public_disclosure_ack"
    ]["const"] == "public-unlisted-thread-v2"


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
async def test_mcp_reply_and_thread_read_persist_both_directions(monkeypatch):
    from app.services import dialogue_service

    captured = {}

    def submit(**values):
        captured.update(values)
        return {
            "id": "dlg_reply",
            "state": "pending",
            "parent_dialogue_id": values["parent_dialogue_id"],
            "removal_token": "reply-removal-token-long-enough",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)
    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue_thread",
        lambda dialogue_id: {
            "root_dialogue_id": "dlg_root",
            "anchor_dialogue_id": dialogue_id,
            "turns": [
                {"id": "dlg_root", "question": "first"},
                {
                    "id": "dlg_reply",
                    "question": "second",
                    "parent_dialogue_id": "dlg_root",
                },
            ],
            "turn_count": 2,
            "truncated": False,
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        replied = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "reply",
                "method": "tools/call",
                "params": {
                    "name": "reply_dialogue",
                    "arguments": {
                        "dialogue_id": "dlg_root",
                        "question": "second",
                        "point_of_view": "water",
                        "locale": "en",
                        "public_disclosure_ack": "public-unlisted-thread-v2",
                    },
                },
            },
        )
        observed = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "thread",
                "method": "tools/call",
                "params": {
                    "name": "get_dialogue_thread",
                    "arguments": {"dialogue_id": "dlg_reply"},
                },
            },
        )

    reply_payload = replied.json()["result"]["structuredContent"]
    thread_payload = observed.json()["result"]["structuredContent"]
    assert reply_payload["parent_dialogue_id"] == "dlg_root"
    assert captured["parent_dialogue_id"] == "dlg_root"
    assert thread_payload["anchor_dialogue_id"] == "dlg_reply"
    assert [turn["question"] for turn in thread_payload["turns"]] == [
        "first",
        "second",
    ]
    assert "removal_token" not in json.dumps(thread_payload)


@pytest.mark.asyncio
async def test_mcp_thread_planner_contention_returns_retry_guidance(monkeypatch):
    from app.services import dialogue_service

    monkeypatch.setattr(
        dialogue_service,
        "get_dialogue_thread",
        lambda _dialogue_id: (_ for _ in ()).throw(
            dialogue_service.DialogueThreadPlannerBusyError()
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "thread-busy",
                "method": "tools/call",
                "params": {
                    "name": "get_dialogue_thread",
                    "arguments": {"dialogue_id": "dlg_busy"},
                },
            },
        )

    result = response.json()["result"]
    assert result["isError"] is True
    assert result["structuredContent"] == {
        "error": "Native dialogue thread planning is presently busy",
        "retry_after": 15,
    }


@pytest.mark.asyncio
async def test_mcp_dialogue_storage_failures_stay_inside_each_tool_result(monkeypatch):
    from app.services import dialogue_service

    def unavailable(*_args, **_kwargs):
        raise ConnectionError("private database carrier detail")

    monkeypatch.setattr(dialogue_service, "get_dialogue", unavailable)
    monkeypatch.setattr(dialogue_service, "release_dialogue", unavailable)
    requests = [
        {
            "jsonrpc": "2.0",
            "id": "get-failed",
            "method": "tools/call",
            "params": {
                "name": "get_dialogue",
                "arguments": {"dialogue_id": "dlg_missing"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": "remove-failed",
            "method": "tools/call",
            "params": {
                "name": "remove_dialogue",
                "arguments": {
                    "dialogue_id": "dlg_missing",
                    "removal_token": "release-token-long-enough",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": "still-alive",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post("/mcp", json=requests)

    assert response.status_code == 200
    replies = {reply["id"]: reply for reply in response.json()}
    for request_id in ("get-failed", "remove-failed"):
        result = replies[request_id]["result"]
        assert result["isError"] is True
        assert result["structuredContent"] == {
            "error": "Dialogue storage is presently unavailable."
        }
        assert "private database carrier detail" not in str(result)
    assert replies["still-alive"]["result"]["serverInfo"]["name"] == "coherence-network"


@pytest.mark.asyncio
async def test_mcp_start_keeps_the_event_loop_available(monkeypatch):
    from app.services import dialogue_service

    started = threading.Event()
    read_completed = threading.Event()

    def submit(**_):
        started.set()
        read_completed.wait(2)
        return {
            "id": "dlg_concurrent",
            "state": "pending" if read_completed.is_set() else "blocked-loop",
        }

    monkeypatch.setattr(dialogue_service, "submit_dialogue", submit)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        start_task = asyncio.create_task(
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": "start-concurrent",
                    "method": "tools/call",
                    "params": {
                        "name": "start_dialogue",
                        "arguments": {
                            "question": "What does the river see?",
                            "point_of_view": "river",
                            "locale": "en",
                            "public_disclosure_ack": "public-unlisted-thread-v2",
                        },
                    },
                },
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await start_task
        finally:
            read_completed.set()
            if not start_task.done():
                await start_task

    payload = response.json()["result"]["structuredContent"]
    assert info.status_code == 200
    assert payload["state"] == "pending"


@pytest.mark.asyncio
async def test_mcp_poll_keeps_the_event_loop_available(monkeypatch):
    from app.services import dialogue_service

    started = threading.Event()
    read_completed = threading.Event()

    def get_dialogue(dialogue_id):
        started.set()
        read_completed.wait(2)
        return {
            "id": dialogue_id,
            "state": "miss" if read_completed.is_set() else "blocked-loop",
        }

    monkeypatch.setattr(dialogue_service, "get_dialogue", get_dialogue)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        poll_task = asyncio.create_task(
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": "poll-concurrent",
                    "method": "tools/call",
                    "params": {
                        "name": "get_dialogue",
                        "arguments": {"dialogue_id": "dlg_concurrent"},
                    },
                },
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await poll_task
        finally:
            read_completed.set()
            if not poll_task.done():
                await poll_task

    payload = response.json()["result"]["structuredContent"]
    assert info.status_code == 200
    assert payload["state"] == "miss"


@pytest.mark.asyncio
async def test_mcp_remove_keeps_the_event_loop_available(monkeypatch):
    from app.services import dialogue_service

    started = threading.Event()
    read_completed = threading.Event()

    def release(*_):
        started.set()
        read_completed.wait(2)
        return read_completed.is_set()

    monkeypatch.setattr(dialogue_service, "release_dialogue", release)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        remove_task = asyncio.create_task(
            client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": "remove-concurrent",
                    "method": "tools/call",
                    "params": {
                        "name": "remove_dialogue",
                        "arguments": {
                            "dialogue_id": "dlg_concurrent",
                            "removal_token": "release-token-long-enough",
                        },
                    },
                },
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            info = await client.get("/api/mcp")
            read_completed.set()
            response = await remove_task
        finally:
            read_completed.set()
            if not remove_task.done():
                await remove_task

    payload = response.json()["result"]["structuredContent"]
    assert info.status_code == 200
    assert payload["released"] is True


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", {"text": "hello"}),
        ("point_of_view", ["river"]),
        ("locale", True),
        ("public_disclosure_ack", 1),
        ("parent_dialogue_id", {"id": "dlg_parent"}),
    ],
)
@pytest.mark.asyncio
async def test_mcp_start_dialogue_rejects_non_string_fields_before_storage(
    field,
    value,
    monkeypatch,
):
    from app.services import dialogue_service

    def unexpected_submit(**_values):
        raise AssertionError("invalid MCP fields must not reach dialogue storage")

    monkeypatch.setattr(dialogue_service, "submit_dialogue", unexpected_submit)
    arguments = {
        "question": "hello",
        "point_of_view": "river",
        "locale": "en",
        "public_disclosure_ack": "public-unlisted-v1",
        "parent_dialogue_id": "dlg_parent",
    }
    arguments[field] = value

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": f"invalid-{field}",
                "method": "tools/call",
                "params": {"name": "start_dialogue", "arguments": arguments},
            },
        )

    result = response.json()["result"]
    assert response.status_code == 200
    assert result["isError"] is True
    assert result["structuredContent"] == {"error": f"{field} must be a string"}


@pytest.mark.parametrize(
    ("tool_name", "arguments", "field"),
    [
        ("get_dialogue", {"dialogue_id": ["dlg"]}, "dialogue_id"),
        ("get_dialogue_thread", {"dialogue_id": ["dlg"]}, "dialogue_id"),
        (
            "reply_dialogue",
            {
                "dialogue_id": {"id": "dlg"},
                "question": "hello",
                "point_of_view": "river",
                "locale": "en",
                "public_disclosure_ack": "public-unlisted-v1",
            },
            "dialogue_id",
        ),
        (
            "remove_dialogue",
            {"dialogue_id": "dlg", "removal_token": {"token": "release"}},
            "removal_token",
        ),
    ],
)
@pytest.mark.asyncio
async def test_mcp_dialogue_capability_fields_reject_non_strings(
    tool_name,
    arguments,
    field,
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": f"invalid-{field}",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )

    result = response.json()["result"]
    assert response.status_code == 200
    assert result["isError"] is True
    assert result["structuredContent"] == {"error": f"{field} must be a string"}


@pytest.mark.asyncio
async def test_mcp_start_dialogue_refuses_explicit_zero_timeout_before_admission():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "start-zero-timeout",
                "method": "tools/call",
                "params": {
                    "name": "start_dialogue",
                    "arguments": {
                        "question": "hello",
                        "point_of_view": "river",
                        "locale": "en",
                        "public_disclosure_ack": "public-unlisted-v1",
                        "channel_timeout_seconds": 0,
                    },
                },
            },
        )

    result = response.json()["result"]
    assert result["isError"] is True
    assert "channel_timeout_seconds must be between 10" in result["structuredContent"]["error"]


@pytest.mark.asyncio
async def test_mcp_start_dialogue_returns_structured_error_for_nonfinite_timeout():
    body = """{
      "jsonrpc":"2.0",
      "id":"start-infinite-timeout",
      "method":"tools/call",
      "params":{
        "name":"start_dialogue",
        "arguments":{
          "question":"hello",
          "point_of_view":"river",
          "locale":"en",
          "public_disclosure_ack":"public-unlisted-v1",
          "channel_timeout_seconds":1e309
        }
      }
    }"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post(
            "/mcp",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    result = response.json()["result"]
    assert response.status_code == 200
    assert result["isError"] is True
    assert result["structuredContent"] == {
        "error": "channel_timeout_seconds must be an integer"
    }


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
