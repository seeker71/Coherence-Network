from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from task_control_channel import TaskControlChannel


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _reset_service_caches_between_tests():
    yield


def test_sse_listener_writes_checkpoint_steer_abort_and_ask_commands(monkeypatch):
    control_path = ROOT / "task-control-test.jsonl"
    control_path.unlink(missing_ok=True)

    channel = TaskControlChannel(
        node_id="node-test-01",
        task_id="task-sse-01",
        task_dir=ROOT,
        api_base="https://example.test",
    )
    channel.control_file = control_path

    sse_lines = [
        'data: {"type": "checkpoint", "payload": {"requested_by": "qa"}}',
        'data: {"type": "steer", "payload": {"direction": "focus on the failing CLI step"}}',
        'data: {"type": "abort", "payload": {"reason": "operator requested stop"}}',
        'data: {"type": "ask", "payload": {"question": "May I run the native CLI with network access?"}}',
    ]

    class _FakeStream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            for line in sse_lines:
                yield line
            channel._stop_event.set()

    def _fake_stream(method, url, timeout=None, headers=None):
        assert method == "GET"
        assert url.endswith("/api/federation/nodes/node-test-01/stream")
        assert timeout is None
        assert headers == {"Accept": "text/event-stream"}
        return _FakeStream()

    monkeypatch.setattr(httpx, "stream", _fake_stream)

    try:
        channel._sse_listener()

        commands = _read_jsonl(channel.control_file)
        assert [command["type"] for command in commands] == ["checkpoint", "steer", "abort", "ask"]
        assert all(command["task_id"] == "task-sse-01" for command in commands)
        assert commands[0]["payload"] == {"requested_by": "qa"}
        assert commands[1]["payload"]["direction"] == "focus on the failing CLI step"
        assert commands[2]["payload"]["reason"] == "operator requested stop"
        assert commands[3]["payload"]["question"] == "May I run the native CLI with network access?"
    finally:
        control_path.unlink(missing_ok=True)
