"""Tests for SSE control channel — steer, checkpoint, abort, ask, report for native agent CLIs.

Covers:
- ``scripts/task_control_channel.TaskControlChannel`` — JSONL control file protocol
- ``POST /api/agent/tasks/{task_id}/activity`` — responses from agents back to the network
- ``GET /api/agent/tasks/{task_id}/stream`` — task event history
- ``GET /api/agent/tasks/{task_id}/events`` — SSE media type and initial payload shape

The runner connects ``TaskControlChannel`` to ``GET /api/federation/nodes/{node_id}/stream``;
integration with federation SSE is exercised via mocked ``httpx.stream`` line delivery.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.task_control_channel import TaskControlChannel, inject_control_instructions


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _patch_background_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid real HTTP in SSE listener and speed up response poller."""

    def _wait_until_stop(self: TaskControlChannel) -> None:
        self._stop_event.wait()

    monkeypatch.setattr(TaskControlChannel, "_sse_listener", _wait_until_stop)
    monkeypatch.setattr(
        "scripts.task_control_channel._RESPONSE_POLL_INTERVAL",
        0.05,
    )


def test_inject_control_instructions_documents_checkpoint_steer_abort_ask() -> None:
    """Prompt injection lists operator commands agents must honor."""
    out = inject_control_instructions("BASE PROMPT", Path("/tmp"))
    assert "BASE PROMPT" in out
    for token in ("checkpoint", "steer", "abort", "ask", "cc inbox", "cc msg"):
        assert token in out, f"missing instruction fragment: {token}"


def test_task_control_channel_writes_connected_and_control_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Start creates JSONL .task-control; send_command appends steer/checkpoint/abort/ask."""
    _patch_background_threads(monkeypatch)

    task_id = "t-sse-control-01"
    ch = TaskControlChannel(
        node_id="n0de1111111111",
        task_id=task_id,
        task_dir=tmp_path,
        api_base="http://127.0.0.1:9",
    )
    ch.start()
    try:
        ctrl = tmp_path / ".task-control"
        assert ctrl.is_file()
        lines = [json.loads(x) for x in ctrl.read_text().strip().split("\n")]
        assert lines[0]["type"] == "connected"
        assert lines[0]["task_id"] == task_id

        ch.send_command("checkpoint", {})
        ch.send_command("steer", {"direction": "focus on tests only"})
        ch.send_command("abort", {"reason": "user cancelled"})
        ch.send_command("ask", {"question": "approve schema change?"})
        ch.send_command("report", {"status": "50%"})

        tail = [json.loads(x) for x in ctrl.read_text().strip().split("\n")]
        types = [x["type"] for x in tail]
        assert types == [
            "connected",
            "checkpoint",
            "steer",
            "abort",
            "ask",
            "report",
        ]
        steer = tail[types.index("steer")]
        assert steer["payload"]["direction"] == "focus on tests only"
    finally:
        ch.stop()

    final_lines = [json.loads(x) for x in (tmp_path / ".task-control").read_text().strip().split("\n")]
    assert final_lines[-1]["type"] == "disconnected"


def test_task_control_channel_posts_agent_response_via_httpx(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_post_response sends activity to POST .../activity with event_type prefix."""
    posts: list[tuple[str, dict]] = []

    def _capture_post(url: str, json: dict | None = None, **kwargs: object) -> MagicMock:
        posts.append((url, json or {}))
        m = MagicMock()
        m.status_code = 201
        return m

    monkeypatch.setattr(httpx, "post", _capture_post)

    ch = TaskControlChannel("n0de2222222222", "task-post-1", tmp_path, "http://api.test")
    ch._post_response({"type": "checkpoint_ack", "note": "saved"})

    assert len(posts) == 1
    url, body = posts[0]
    assert url.endswith("/api/agent/tasks/task-post-1/activity")
    assert body["event_type"] == "control_response_checkpoint_ack"
    assert body["data"]["note"] == "saved"


def test_sse_listener_accepts_event_type_and_type_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Federation-style ``event_type`` and alternate ``type`` both dispatch to send_command."""
    sent: list[tuple[str, dict]] = []

    def _capture_send(self: TaskControlChannel, command: str, payload: dict | None = None) -> None:
        sent.append((command, payload or {}))

    monkeypatch.setattr(TaskControlChannel, "send_command", _capture_send)
    monkeypatch.setattr(
        "scripts.task_control_channel._RESPONSE_POLL_INTERVAL",
        0.05,
    )

    ch = TaskControlChannel("n0de3333333333", "tid-match", tmp_path, "http://api.test")

    def fake_stream(
        method: str,
        url: str,
        *,
        timeout: object = None,
        headers: dict | None = None,
    ) -> object:
        class _Resp:
            status_code = 200

            def __enter__(self) -> _Resp:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def iter_lines(self) -> object:
                yield 'data: {"event_type":"checkpoint","payload":{}}'
                yield 'data: {"type":"steer","payload":{"direction":"x"}}'
                yield 'data: {"event_type":"command","payload":{"task_id":"tid-match","command":"abort"}}'
                while not ch._stop_event.is_set():
                    ch._stop_event.wait(0.05)

        return _Resp()

    monkeypatch.setattr(httpx, "stream", fake_stream)

    ch.start()
    try:
        deadline = time.monotonic() + 5.0
        while len(sent) < 3 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(sent) >= 3
    finally:
        ch.stop()

    cmds = [c for c, _ in sent]
    assert "checkpoint" in cmds
    assert "steer" in cmds
    assert "abort" in cmds


def test_post_activity_and_get_task_stream_round_trip(client: TestClient) -> None:
    """POST activity → GET stream returns persisted events (create-read)."""
    task_id = "t-activity-roundtrip-1"
    r = client.post(
        f"/api/agent/tasks/{task_id}/activity",
        json={
            "event_type": "progress",
            "node_id": "worker-1",
            "data": {"pct": 40, "phase": "testing"},
        },
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["task_id"] == task_id
    assert ev["event_type"] == "progress"
    assert ev["data"]["pct"] == 40

    stream = client.get(f"/api/agent/tasks/{task_id}/stream")
    assert stream.status_code == 200
    body = stream.json()
    assert len(body) >= 1
    assert body[-1]["event_type"] == "progress"


def test_post_activity_rejects_empty_event_type(client: TestClient) -> None:
    """Validation error on missing event_type (error handling)."""
    r = client.post(
        "/api/agent/tasks/t-bad-activity/activity",
        json={"data": {}},
    )
    assert r.status_code in (400, 422)


def test_task_events_sse_returns_event_stream(client: TestClient) -> None:
    """SSE endpoint advertises text/event-stream and emits data lines."""
    task_id = "t-sse-events-1"
    log = client.post(
        f"/api/agent/tasks/{task_id}/activity",
        json={"event_type": "executing", "data": {"provider": "codex"}},
    )
    assert log.status_code == 201, log.text

    done = client.post(
        f"/api/agent/tasks/{task_id}/activity",
        json={"event_type": "completed", "data": {"ok": True}},
    )
    assert done.status_code == 201, done.text

    with client.stream("GET", f"/api/agent/tasks/{task_id}/events") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in (resp.headers.get("content-type") or "")
        raw = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")
        assert "data:" in raw
        assert "completed" in raw or "end" in raw
