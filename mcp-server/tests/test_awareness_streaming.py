from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coherence_mcp_server import server as mcp_server  # noqa: E402


def test_awareness_tools_are_registered() -> None:
    required = {
        "coherence_awareness_publish",
        "coherence_awareness_stream",
        "coherence_node_message_send",
        "coherence_node_messages",
    }

    assert required <= set(mcp_server.TOOL_MAP)


def test_decode_sse_events_handles_json_keepalive_and_raw_text() -> None:
    events = mcp_server.decode_sse_events(
        [
            ": keepalive",
            "",
            'data: {"event_type":"heartbeat","message":"awake"}',
            "",
            "data: plain awareness",
            "",
        ]
    )

    assert events == [
        {"event_type": "heartbeat", "message": "awake"},
        {"raw": "plain awareness"},
    ]


def test_awareness_publish_routes_to_diagnostic_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_post(path: str, body: dict) -> dict:
        calls.append((path, body))
        return {"ok": True}

    monkeypatch.setattr(mcp_server, "api_post", fake_post)

    result = mcp_server.dispatch(
        "coherence_awareness_publish",
        {
            "node_id": "node-1",
            "event_type": "reasoning",
            "message": "listening",
            "data": {"thread": "abc"},
        },
    )

    assert result == {"ok": True}
    assert calls == [
        (
            "/api/federation/nodes/node-1/diag",
            {
                "event_type": "reasoning",
                "message": "listening",
                "data": {"thread": "abc"},
                "source": "mcp",
            },
        )
    ]


def test_awareness_stream_routes_diagnostic_sse(monkeypatch) -> None:
    calls: list[tuple[str, dict, float, int]] = []

    def fake_sse(path: str, params: dict | None = None, *, duration_seconds: float, max_events: int) -> dict:
        calls.append((path, params or {}, duration_seconds, max_events))
        return {"events": [{"event_type": "subscribed"}], "count": 1}

    monkeypatch.setattr(mcp_server, "api_sse", fake_sse)

    result = mcp_server.dispatch(
        "coherence_awareness_stream",
        {
            "stream_type": "diagnostics",
            "node_id": "*",
            "duration_seconds": 2,
            "max_events": 3,
        },
    )

    assert result["count"] == 1
    assert calls == [("/api/federation/nodes/*/diag/stream", {}, 2, 3)]


def test_node_message_tools_route_to_federation_endpoints(monkeypatch) -> None:
    post_calls: list[tuple[str, dict]] = []
    get_calls: list[tuple[str, dict]] = []

    def fake_post(path: str, body: dict) -> dict:
        post_calls.append((path, body))
        return {"id": "msg_1"}

    def fake_get(path: str, params: dict | None = None) -> dict:
        get_calls.append((path, params or {}))
        return {"messages": []}

    monkeypatch.setattr(mcp_server, "api_post", fake_post)
    monkeypatch.setattr(mcp_server, "api_get", fake_get)

    assert mcp_server.dispatch(
        "coherence_node_message_send",
        {
            "from_node_id": "node-a",
            "to_node_id": "node-b",
            "type": "text",
            "text": "hello",
            "payload": {"mood": "kind"},
        },
    ) == {"id": "msg_1"}
    assert mcp_server.dispatch(
        "coherence_node_messages",
        {"node_id": "node-b", "unread_only": False, "limit": 10},
    ) == {"messages": []}

    assert post_calls == [
        (
            "/api/federation/nodes/node-a/messages",
            {
                "to_node": "node-b",
                "type": "text",
                "text": "hello",
                "payload": {"mood": "kind"},
            },
        )
    ]
    assert get_calls == [
        (
            "/api/federation/nodes/node-b/messages",
            {"since": None, "unread_only": False, "limit": 10},
        )
    ]


def test_api_sse_read_timeout_returns_partial_events(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield 'data: {"event_type":"subscribed"}'
            yield ""
            raise mcp_server.httpx.ReadTimeout("quiet stream")

    class FakeStream:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mcp_server.httpx, "stream", lambda *args, **kwargs: FakeStream())

    result = mcp_server.api_sse("/api/federation/nodes/*/diag/stream", duration_seconds=1, max_events=5)

    assert result["ended_by"] == "read_timeout"
    assert result["events"] == [{"event_type": "subscribed"}]
