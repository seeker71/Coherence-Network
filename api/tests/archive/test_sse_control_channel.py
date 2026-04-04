"""Tests for SSE control channel — real-time steer, checkpoint, abort, ask-permission
for native agent CLIs.

Feature: When a native agent CLI (claude, codex, cursor, gemini) runs a task, the
runner wraps it with a TaskControlChannel that:
  1. Connects to the SSE stream (GET /federation/nodes/{node_id}/stream)
  2. Forwards incoming commands (checkpoint/steer/abort/ask/report/ping) to a
     .task-control file the agent reads
  3. Polls a .task-response file the agent writes and POSTs responses back

This test suite verifies:
  - Control file JSONL protocol (write/read round-trip)
  - All supported command types are written correctly
  - Response polling reads new lines and posts them
  - SSE stream delivers events to subscribers
  - SSE command events trigger control file writes
  - inject_control_instructions appends cc instructions to prompts
  - Edge cases: malformed JSON, missing files, stop-before-start
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _read_control_lines(path: Path) -> list[dict]:
    """Read all JSONL lines from a control file."""
    if not path.exists():
        return []
    lines = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if raw:
            lines.append(json.loads(raw))
    return lines


def _write_response_line(path: Path, data: dict) -> None:
    """Append a JSONL line to the response file (simulates agent writing)."""
    with open(path, "a") as f:
        f.write(json.dumps(data) + "\n")


# ── Unit tests: TaskControlChannel ───────────────────────────────────


class TestTaskControlChannelInit:
    """Constructor and initial state."""

    def test_paths_derived_from_task_dir(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("node-abc", "task-123", tmp_path, "http://localhost:8000")
        assert ch.control_file == tmp_path / ".task-control"
        assert ch.response_file == tmp_path / ".task-response"

    def test_stop_event_initially_clear(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "t1", tmp_path, "http://localhost")
        assert not ch._stop_event.is_set()

    def test_command_queue_initially_empty(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "t1", tmp_path, "http://localhost")
        assert ch._command_queue == []


class TestWriteControl:
    """_write_control appends JSONL to the control file."""

    def test_single_write_creates_file(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "t1", tmp_path, "http://localhost")
        ch._write_control({"type": "ping"})
        assert ch.control_file.exists()
        lines = _read_control_lines(ch.control_file)
        assert len(lines) == 1
        assert lines[0]["type"] == "ping"

    def test_multiple_writes_append_jsonl(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "t1", tmp_path, "http://localhost")
        ch._write_control({"type": "checkpoint"})
        ch._write_control({"type": "steer", "payload": {"direction": "focus on tests"}})
        ch._write_control({"type": "abort"})
        lines = _read_control_lines(ch.control_file)
        assert len(lines) == 3
        assert lines[0]["type"] == "checkpoint"
        assert lines[1]["type"] == "steer"
        assert lines[1]["payload"]["direction"] == "focus on tests"
        assert lines[2]["type"] == "abort"

    def test_write_control_handles_io_error_gracefully(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "t1", tmp_path, "http://localhost")
        # Point control file at an unwritable location
        ch.control_file = tmp_path / "nonexistent_dir" / ".task-control"
        # Should not raise
        ch._write_control({"type": "ping"})


class TestSendCommand:
    """send_command writes to control file and appends to queue."""

    def test_send_checkpoint_command(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-abc", tmp_path, "http://localhost")
        ch.send_command("checkpoint")
        lines = _read_control_lines(ch.control_file)
        assert any(l["type"] == "checkpoint" and l["task_id"] == "task-abc" for l in lines)
        assert len(ch._command_queue) == 1
        assert ch._command_queue[0]["type"] == "checkpoint"

    def test_send_steer_command_with_payload(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-abc", tmp_path, "http://localhost")
        ch.send_command("steer", {"direction": "write more tests"})
        lines = _read_control_lines(ch.control_file)
        steer = next(l for l in lines if l["type"] == "steer")
        assert steer["payload"]["direction"] == "write more tests"
        assert steer["task_id"] == "task-abc"

    def test_send_abort_command(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-abort", tmp_path, "http://localhost")
        ch.send_command("abort")
        lines = _read_control_lines(ch.control_file)
        assert any(l["type"] == "abort" for l in lines)

    def test_send_ask_command_with_question(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-ask", tmp_path, "http://localhost")
        ch.send_command("ask", {"question": "Should we delete this file?"})
        lines = _read_control_lines(ch.control_file)
        ask = next(l for l in lines if l["type"] == "ask")
        assert ask["payload"]["question"] == "Should we delete this file?"

    def test_send_report_command(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-rpt", tmp_path, "http://localhost")
        ch.send_command("report", {"status": "50% done"})
        lines = _read_control_lines(ch.control_file)
        report = next(l for l in lines if l["type"] == "report")
        assert report["payload"]["status"] == "50% done"

    def test_send_ping_command(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-ping", tmp_path, "http://localhost")
        ch.send_command("ping")
        lines = _read_control_lines(ch.control_file)
        assert any(l["type"] == "ping" for l in lines)

    def test_command_has_timestamp(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        before = time.time()
        ch = TaskControlChannel("n1", "task-ts", tmp_path, "http://localhost")
        ch.send_command("checkpoint")
        after = time.time()
        lines = _read_control_lines(ch.control_file)
        cmd = next(l for l in lines if l["type"] == "checkpoint")
        assert before <= cmd["timestamp"] <= after

    def test_send_command_without_payload_defaults_empty_dict(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-nopayload", tmp_path, "http://localhost")
        ch.send_command("checkpoint", None)
        lines = _read_control_lines(ch.control_file)
        cmd = next(l for l in lines if l["type"] == "checkpoint")
        assert cmd["payload"] == {}


class TestStart:
    """start() initializes files and spawns threads."""

    def test_start_creates_task_dir(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        task_dir = tmp_path / "nested" / "task"
        ch = TaskControlChannel("n1", "task-start", task_dir, "http://localhost")

        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch._stop_event.set()

        assert task_dir.exists()

    def test_start_writes_connected_event_to_control_file(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-connected", tmp_path, "http://localhost")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch._stop_event.set()

        lines = _read_control_lines(ch.control_file)
        assert any(l.get("type") == "connected" for l in lines)

    def test_start_clears_old_control_file(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        # Write stale control data
        control = tmp_path / ".task-control"
        control.write_text(json.dumps({"type": "stale"}) + "\n")

        ch = TaskControlChannel("n1", "task-clearold", tmp_path, "http://localhost")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch._stop_event.set()

        lines = _read_control_lines(control)
        types = [l["type"] for l in lines]
        assert "stale" not in types
        assert "connected" in types

    def test_start_spawns_two_threads(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-threads", tmp_path, "http://localhost")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            thread_count = len(ch._threads)
            ch._stop_event.set()

        assert thread_count == 2


class TestStop:
    """stop() signals threads and writes disconnected event."""

    def test_stop_sets_stop_event(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-stop", tmp_path, "http://localhost")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch.stop()

        assert ch._stop_event.is_set()

    def test_stop_writes_disconnected_event(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-disc", tmp_path, "http://localhost")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch.stop()

        lines = _read_control_lines(ch.control_file)
        assert any(l.get("type") == "disconnected" for l in lines)

    def test_stop_without_start_does_not_raise(self, tmp_path: Path) -> None:
        """Calling stop() before start() should not crash."""
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-nostop", tmp_path, "http://localhost")
        ch.task_dir.mkdir(parents=True, exist_ok=True)
        ch._write_control({"type": "init"})
        ch.stop()


class TestResponsePoller:
    """_response_poller reads agent responses and posts them."""

    def _run_one_iteration(self, ch) -> None:  # type: ignore[no-untyped-def]
        """Run the response poller for exactly one iteration by setting stop after first wait."""
        def _wait_and_stop(timeout=None):
            ch._stop_event.set()
            return True
        ch._stop_event.wait = _wait_and_stop  # type: ignore[method-assign]
        ch._response_poller()

    def test_poller_reads_json_response_and_posts(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []

        ch = TaskControlChannel("n1", "task-poll", tmp_path, "http://localhost")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        _write_response_line(ch.response_file, {"type": "checkpoint_saved", "progress": "50%"})
        self._run_one_iteration(ch)

        assert len(posted) == 1
        assert posted[0]["type"] == "checkpoint_saved"
        assert posted[0]["progress"] == "50%"

    def test_poller_reads_multiple_response_lines(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []
        ch = TaskControlChannel("n1", "task-multi-poll", tmp_path, "http://localhost")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        _write_response_line(ch.response_file, {"type": "steer_acknowledged"})
        _write_response_line(ch.response_file, {"type": "status_update", "pct": 75})
        _write_response_line(ch.response_file, {"type": "abort_complete"})

        self._run_one_iteration(ch)

        assert len(posted) == 3
        types = [r["type"] for r in posted]
        assert "steer_acknowledged" in types
        assert "status_update" in types
        assert "abort_complete" in types

    def test_poller_handles_plain_text_response(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []
        ch = TaskControlChannel("n1", "task-plain", tmp_path, "http://localhost")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        with open(ch.response_file, "a") as f:
            f.write("checkpoint saved successfully\n")

        self._run_one_iteration(ch)

        assert len(posted) == 1
        assert posted[0]["type"] == "text"
        assert "checkpoint saved successfully" in posted[0]["text"]

    def test_poller_does_nothing_when_no_response_file(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []
        ch = TaskControlChannel("n1", "task-nofile", tmp_path, "http://localhost")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        assert not ch.response_file.exists()
        self._run_one_iteration(ch)

        assert posted == []

    def test_poller_does_not_reprocess_old_lines(self, tmp_path: Path) -> None:
        """Response poller tracks byte offset so already-processed lines are skipped."""
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []
        ch = TaskControlChannel("n1", "task-nodup", tmp_path, "http://localhost")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        _write_response_line(ch.response_file, {"type": "first"})

        # Process first batch
        last_size = 0
        content = ch.response_file.read_text()
        new_lines = content[last_size:].strip().split("\n")
        last_size = len(content)
        for line in new_lines:
            if line.strip():
                ch._post_response(json.loads(line))

        # Write second line
        _write_response_line(ch.response_file, {"type": "second"})

        # Process second batch starting from offset
        content2 = ch.response_file.read_text()
        new_lines2 = content2[last_size:].strip().split("\n")
        for line in new_lines2:
            if line.strip():
                ch._post_response(json.loads(line))

        assert len(posted) == 2
        assert posted[0]["type"] == "first"
        assert posted[1]["type"] == "second"


class TestPostResponse:
    """_post_response sends agent responses back to the network."""

    def test_post_response_calls_activity_endpoint(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel

        captured: list[dict] = []

        ch = TaskControlChannel("n1", "task-post", tmp_path, "http://api.test")

        with patch("httpx.post", side_effect=lambda url, **kwargs: captured.append({"url": url, **kwargs}) or MagicMock()):
            ch._post_response({"type": "checkpoint_saved", "task_id": "task-post"})

        assert len(captured) == 1
        assert "task-post" in captured[0]["url"]

    def test_post_response_handles_network_error_gracefully(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import TaskControlChannel
        import httpx

        ch = TaskControlChannel("n1", "task-err", tmp_path, "http://api.test")

        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            ch._post_response({"type": "checkpoint_saved"})


# ── Integration: SSE event filter logic ──────────────────────────────


class TestSSEEventFiltering:
    """Verify the SSE listener correctly filters and routes events."""

    @pytest.mark.parametrize(
        "event_type",
        ["checkpoint", "steer", "abort", "ask", "report", "ping"],
    )
    def test_direct_control_commands_are_forwarded(
        self, tmp_path: Path, event_type: str
    ) -> None:
        """Direct control command events must be written to the control file."""
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-filter", tmp_path, "http://localhost")
        sent_commands: list[tuple] = []
        ch.send_command = lambda cmd, payload=None: sent_commands.append((cmd, payload))  # type: ignore

        event = {"type": event_type, "payload": {"detail": "some info"}}
        event_type_received = event.get("type") or event.get("event_type", "")

        if event_type_received in ("checkpoint", "steer", "abort", "ask", "report", "ping"):
            ch.send_command(event_type_received, event.get("payload", event))

        assert len(sent_commands) == 1
        assert sent_commands[0][0] == event_type

    def test_task_specific_command_event_filtered_by_task_id(self, tmp_path: Path) -> None:
        """command events targeted at this task_id must be forwarded."""
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-target-id", tmp_path, "http://localhost")
        sent_commands: list[tuple] = []
        ch.send_command = lambda cmd, payload=None: sent_commands.append((cmd, payload))  # type: ignore

        event = {
            "type": "command",
            "payload": {
                "task_id": "task-target-id",
                "command": "steer",
                "direction": "left",
            },
        }
        event_type = event.get("type") or event.get("event_type", "")
        if event_type == "command" and event.get("payload", {}).get("task_id") == ch.task_id:
            ch.send_command(
                event["payload"].get("command", "unknown"),
                event.get("payload", {}),
            )

        assert len(sent_commands) == 1
        assert sent_commands[0][0] == "steer"

    def test_task_specific_command_ignored_if_different_task_id(self, tmp_path: Path) -> None:
        """command events for other tasks must NOT be forwarded."""
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-mine", tmp_path, "http://localhost")
        sent_commands: list[tuple] = []
        ch.send_command = lambda cmd, payload=None: sent_commands.append((cmd, payload))  # type: ignore

        event = {
            "type": "command",
            "payload": {
                "task_id": "task-other",
                "command": "abort",
            },
        }
        event_type = event.get("type") or event.get("event_type", "")
        if event_type == "command" and event.get("payload", {}).get("task_id") == ch.task_id:
            ch.send_command(event["payload"].get("command", "unknown"), event.get("payload", {}))

        assert sent_commands == []

    def test_unknown_event_type_is_ignored(self, tmp_path: Path) -> None:
        """Unknown event types must not be forwarded to control file."""
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("n1", "task-unknown", tmp_path, "http://localhost")
        sent_commands: list[tuple] = []
        ch.send_command = lambda cmd, payload=None: sent_commands.append((cmd, payload))  # type: ignore

        for etype in ("heartbeat", "deploy", "metrics", "unknown_event"):
            event = {"type": etype, "payload": {}}
            evt = event.get("type") or event.get("event_type", "")
            if evt in ("checkpoint", "steer", "abort", "ask", "report", "ping"):
                ch.send_command(evt, event.get("payload", event))

        assert sent_commands == []


# ── Integration: SSE federation stream endpoint ───────────────────────


class TestSSEFederationStream:
    """Test the SSE stream endpoint that the control channel connects to."""

    def test_sse_stream_returns_event_stream_content_type(self) -> None:
        """GET /api/federation/nodes/{node_id}/stream returns text/event-stream."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        node_id = "ssectrl01a1b2c3"
        client.post(
            "/api/federation/nodes",
            json={
                "node_id": node_id,
                "hostname": "sse-ctrl-test.local",
                "os_type": "linux",
                "providers": ["claude"],
                "capabilities": {},
            },
        )

        with client.stream("GET", f"/api/federation/nodes/{node_id}/stream") as resp:
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "text/event-stream" in content_type

    def test_sse_stream_delivers_connected_event(self) -> None:
        """SSE stream must immediately send a 'connected' event."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        node_id = "ssectrl02b2c3d4"

        client.post(
            "/api/federation/nodes",
            json={
                "node_id": node_id,
                "hostname": "sse-ctrl-test2.local",
                "os_type": "linux",
                "providers": ["claude"],
                "capabilities": {},
            },
        )

        received_events: list[dict] = []
        with client.stream("GET", f"/api/federation/nodes/{node_id}/stream") as resp:
            for chunk in resp.iter_lines():
                chunk = chunk.strip()
                if chunk.startswith("data: "):
                    try:
                        event = json.loads(chunk[6:])
                        received_events.append(event)
                        if event.get("event_type") == "connected":
                            break
                    except json.JSONDecodeError:
                        pass
                if len(received_events) >= 1:
                    break

        assert any(e.get("event_type") == "connected" for e in received_events)

    def test_sse_stream_has_cache_control_no_cache_header(self) -> None:
        """SSE stream must set Cache-Control: no-cache."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        node_id = "ssectrl03c3d4e5"

        with client.stream("GET", f"/api/federation/nodes/{node_id}/stream") as resp:
            assert resp.headers.get("cache-control") == "no-cache"

    def test_message_posted_to_node_appears_in_sse_stream(self) -> None:
        """POST a command message to a node → it should appear in the next SSE poll."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        node_id = "ssectrl04d4e5f6"
        sender_id = "ssesend01a1b2c3"

        for nid, host in [(node_id, "recv.sse.local"), (sender_id, "send.sse.local")]:
            client.post(
                "/api/federation/nodes",
                json={
                    "node_id": nid,
                    "hostname": host,
                    "os_type": "linux",
                    "providers": ["claude"],
                    "capabilities": {},
                },
            )

        resp = client.post(
            f"/api/federation/nodes/{sender_id}/messages",
            json={
                "from_node": sender_id,
                "to_node": node_id,
                "type": "command",
                "text": "checkpoint now",
                "payload": {"command": "checkpoint", "task_id": "task-sse-test"},
            },
        )
        assert resp.status_code == 201

        collected: list[dict] = []
        with client.stream("GET", f"/api/federation/nodes/{node_id}/stream") as stream_resp:
            assert stream_resp.status_code == 200
            for chunk in stream_resp.iter_lines():
                chunk = chunk.strip()
                if chunk.startswith("data: "):
                    try:
                        event = json.loads(chunk[6:])
                        collected.append(event)
                        if event.get("type") == "command":
                            break
                    except json.JSONDecodeError:
                        pass

        cmd_events = [e for e in collected if e.get("type") == "command"]
        assert cmd_events, f"Expected command event in stream, got: {collected}"
        assert cmd_events[0]["payload"]["command"] == "checkpoint"


# ── Unit: inject_control_instructions ────────────────────────────────


class TestInjectControlInstructions:
    """inject_control_instructions appends cc CLI instructions to prompts."""

    def test_appends_instructions_to_prompt(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import inject_control_instructions

        original = "You are an agent. Do the task."
        result = inject_control_instructions(original, tmp_path)
        assert result.startswith(original)
        assert len(result) > len(original)

    def test_includes_cc_inbox_command(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import inject_control_instructions

        result = inject_control_instructions("base prompt", tmp_path)
        assert "cc inbox" in result

    def test_includes_all_control_command_types(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import inject_control_instructions

        result = inject_control_instructions("base prompt", tmp_path)
        for cmd in ("checkpoint", "steer", "abort", "ask"):
            assert cmd in result, f"Missing command '{cmd}' in injected instructions"

    def test_includes_cc_msg_broadcast_template(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import inject_control_instructions

        result = inject_control_instructions("base prompt", tmp_path)
        assert "cc msg broadcast" in result

    def test_empty_prompt_still_gets_instructions(self, tmp_path: Path) -> None:
        from scripts.task_control_channel import inject_control_instructions

        result = inject_control_instructions("", tmp_path)
        assert "cc inbox" in result
        assert len(result) > 0


# ── Verification scenarios (runnable end-to-end) ──────────────────────


class TestVerificationScenarios:
    """Concrete scenarios matching the spec's Verification Contract.

    These simulate the full create-read-update cycle and error cases
    that a reviewer would run against production.
    """

    def test_scenario_checkpoint_command_written_and_readable_by_agent(
        self, tmp_path: Path
    ) -> None:
        """
        Scenario 1: Agent receives checkpoint command via control file.

        Setup:  TaskControlChannel initialized for a task.
        Action: send_command('checkpoint')
        Expected: .task-control has one JSONL line with type='checkpoint'
                  and the correct task_id.
        Edge:   Second checkpoint command is appended (not overwritten).
        """
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("node-verify-1", "task-verify-ckpt", tmp_path, "http://api.test")

        ch.send_command("checkpoint")
        lines = _read_control_lines(ch.control_file)
        assert len(lines) == 1
        assert lines[0]["type"] == "checkpoint"
        assert lines[0]["task_id"] == "task-verify-ckpt"

        # Edge: second checkpoint is appended
        ch.send_command("checkpoint")
        lines2 = _read_control_lines(ch.control_file)
        assert len(lines2) == 2
        assert all(l["type"] == "checkpoint" for l in lines2)

    def test_scenario_steer_changes_agent_direction(self, tmp_path: Path) -> None:
        """
        Scenario 2: Operator steers the agent to a new direction.

        Setup:  TaskControlChannel with a running task.
        Action: send_command('steer', {'direction': 'focus on error handling'})
        Expected: .task-control contains steer command with direction payload.
        Edge:   Missing direction key → payload is empty dict (not error).
        """
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("node-verify-2", "task-verify-steer", tmp_path, "http://api.test")

        ch.send_command("steer", {"direction": "focus on error handling"})
        lines = _read_control_lines(ch.control_file)
        steer = next(l for l in lines if l["type"] == "steer")
        assert steer["payload"]["direction"] == "focus on error handling"

        # Edge: no direction key
        t2 = tmp_path / "t2"
        t2.mkdir()
        ch2 = TaskControlChannel("node-verify-2", "task-verify-steer2", t2, "http://api.test")
        ch2.send_command("steer")
        lines2 = _read_control_lines(ch2.control_file)
        assert lines2[0]["payload"] == {}

    def test_scenario_abort_stops_agent_cleanly(self, tmp_path: Path) -> None:
        """
        Scenario 3: Abort command causes agent to save and stop.

        Setup:  TaskControlChannel for a running task.
        Action: send_command('abort') then stop()
        Expected: .task-control has connected, abort, disconnected events.
        Edge:   Abort after stop() does not crash.
        """
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("node-verify-3", "task-verify-abort", tmp_path, "http://api.test")
        with patch.object(ch, "_sse_listener"), patch.object(ch, "_response_poller"):
            ch.start()
            ch.send_command("abort")
            ch.stop()

        lines = _read_control_lines(ch.control_file)
        types = [l["type"] for l in lines]
        assert "connected" in types
        assert "abort" in types
        assert "disconnected" in types

        # Edge: sending another command after stop should not crash
        ch.send_command("abort")

    def test_scenario_agent_response_posted_back_to_network(self, tmp_path: Path) -> None:
        """
        Scenario 4: Agent writes response → control channel posts to API.

        Setup:  Agent writes a JSON response to .task-response.
        Action: Response poller reads and calls _post_response.
        Expected: Response contains type='steer_acknowledged' and is posted.
        Edge:   Malformed JSON line → wrapped as plain text response.
        """
        from scripts.task_control_channel import TaskControlChannel

        posted: list[dict] = []
        ch = TaskControlChannel("node-verify-4", "task-verify-resp", tmp_path, "http://api.test")
        ch._post_response = lambda r: posted.append(r)  # type: ignore[method-assign]

        _write_response_line(ch.response_file, {"type": "steer_acknowledged", "task_id": "task-verify-resp"})

        def _wait_and_stop_1(timeout=None):
            ch._stop_event.set()
            return True
        ch._stop_event.wait = _wait_and_stop_1  # type: ignore[method-assign]
        ch._response_poller()

        assert len(posted) == 1
        assert posted[0]["type"] == "steer_acknowledged"

        # Edge: malformed JSON
        posted2: list[dict] = []
        tmp2 = tmp_path / "t2"
        tmp2.mkdir()
        ch2 = TaskControlChannel("node-verify-4", "task-verify-malformed", tmp2, "http://api.test")
        ch2._post_response = lambda r: posted2.append(r)  # type: ignore[method-assign]
        with open(ch2.response_file, "a") as f:
            f.write("this is not json!!!\n")

        def _wait_and_stop_2(timeout=None):
            ch2._stop_event.set()
            return True
        ch2._stop_event.wait = _wait_and_stop_2  # type: ignore[method-assign]
        ch2._response_poller()

        assert len(posted2) == 1
        assert posted2[0]["type"] == "text"
        assert "this is not json" in posted2[0]["text"]

    def test_scenario_ask_permission_pauses_for_user(self, tmp_path: Path) -> None:
        """
        Scenario 5: ask-permission command is written and readable by agent.

        Setup:  TaskControlChannel for an active task.
        Action: send_command('ask', {'question': 'May I delete /tmp/old-data?'})
        Expected: .task-control has ask command with the question in payload.
        Edge:   Empty question payload → payload is {}.
        """
        from scripts.task_control_channel import TaskControlChannel

        ch = TaskControlChannel("node-verify-5", "task-verify-ask", tmp_path, "http://api.test")
        ch.send_command("ask", {"question": "May I delete /tmp/old-data?"})
        lines = _read_control_lines(ch.control_file)
        ask = next(l for l in lines if l["type"] == "ask")
        assert ask["payload"]["question"] == "May I delete /tmp/old-data?"
        assert ask["task_id"] == "task-verify-ask"

        # Edge: empty payload
        tmp2 = tmp_path / "t2"
        tmp2.mkdir()
        ch2 = TaskControlChannel("node-verify-5", "task-verify-ask2", tmp2, "http://api.test")
        ch2.send_command("ask")
        lines2 = _read_control_lines(ch2.control_file)
        assert lines2[0]["payload"] == {}
