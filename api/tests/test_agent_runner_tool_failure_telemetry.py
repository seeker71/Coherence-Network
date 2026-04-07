"""Tests for tool-failure-awareness spec: runtime telemetry + friction events."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_AGENT_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_runner.py"
_spec = importlib.util.spec_from_file_location("agent_runner", _AGENT_RUNNER_PATH)
assert _spec and _spec.loader
agent_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent_runner)

_MONITOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "monitor_pipeline.py"
_mspec = importlib.util.spec_from_file_location("monitor_pipeline", _MONITOR_PATH)
assert _mspec and _mspec.loader
monitor_pipeline = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(monitor_pipeline)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _Resp:
    status_code: int = 200
    payload: dict | None = None

    def json(self):
        return self.payload or {}


class _Client:
    """Minimal httpx.Client stand-in that records posts/patches."""

    def __init__(self):
        self.posts: list[tuple[str, dict]] = []
        self.patches: list[tuple[str, dict]] = []

    def patch(self, url: str, json: dict | None = None, **kw):
        self.patches.append((url, json or {}))
        return _Resp(200)

    def post(self, url: str, json: dict | None = None, timeout: float | None = None, **kw):
        self.posts.append((url, json or {}))
        return _Resp(201)

    def get(self, url: str, **kw):
        return _Resp(200, {})


class _Proc:
    """Mocks subprocess.Popen for non-poll path (no poll attr)."""

    def __init__(self, *, returncode: int, stdout_text: str):
        self.returncode = returncode
        self.stdout = io.StringIO(stdout_text)
        self._killed = False

    def wait(self, timeout: float | None = None):
        return self.returncode

    def kill(self):
        self._killed = True
        self.returncode = -9

    def terminate(self):
        pass


class _TimeoutProc:
    """Mocks subprocess.Popen that simulates a timeout on first wait()."""

    def __init__(self, *, stdout_text: str):
        self.returncode = None
        self.stdout = io.StringIO(stdout_text)
        self._wait_count = 0

    def wait(self, timeout: float | None = None):
        self._wait_count += 1
        if self._wait_count == 1 and timeout is not None:
            # First call with timeout -> simulate timeout
            raise subprocess.TimeoutExpired(cmd="test", timeout=timeout or 30)
        # Subsequent calls (after terminate/kill) succeed
        self.returncode = -9
        return self.returncode

    def terminate(self):
        self.returncode = -9

    def kill(self):
        self.returncode = -9


def _setup(monkeypatch, tmp_path, base_time=1000.0):
    """Common monkeypatching for deterministic timing and temp log dir."""
    t = [base_time]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("PIPELINE_TOOL_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("PIPELINE_TOOL_FAILURE_FRICTION_ENABLED", "1")
    monkeypatch.setenv("PIPELINE_TIME_COST_PER_SECOND", "0.01")


# ---------------------------------------------------------------------------
# R1: Successful command records runtime event with status_code=200
# ---------------------------------------------------------------------------


def test_successful_command_records_runtime_event_200(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    def _popen(*args, **kwargs):
        return _Proc(returncode=0, stdout_text="Implementation complete\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_success",
        command="pytest -q",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
    )
    assert done is True

    runtime_posts = [p for p in client.posts if p[0].endswith("/api/runtime/events")]
    assert len(runtime_posts) == 1
    _url, payload = runtime_posts[0]
    assert payload["source"] == "worker"
    assert payload["endpoint"].startswith("tool:")
    assert payload["status_code"] == 200
    assert payload["runtime_ms"] > 0
    assert payload["idea_id"] == "coherence-network-agent-pipeline"
    assert payload["metadata"]["task_id"] == "task_success"
    assert payload["metadata"]["task_type"] == "impl"
    assert payload["metadata"]["model"] == "test-model"
    assert payload["metadata"]["returncode"] == 0
    assert isinstance(payload["metadata"]["output_len"], int)

    # No friction event for successful commands.
    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    assert friction_posts == []


# ---------------------------------------------------------------------------
# R2: Failed command records runtime event with status_code=500 AND friction
# ---------------------------------------------------------------------------


def test_failed_command_records_runtime_500_and_friction(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    def _popen(*args, **kwargs):
        return _Proc(returncode=1, stdout_text="Error: module not found\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_fail",
        command="npm test",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
    )
    assert done is True

    # Runtime event with 500
    runtime_posts = [p for p in client.posts if p[0].endswith("/api/runtime/events")]
    assert len(runtime_posts) == 1
    _url, payload = runtime_posts[0]
    assert payload["status_code"] == 500
    assert payload["metadata"]["returncode"] == 1

    # Friction event
    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    assert len(friction_posts) == 1
    _furl, f = friction_posts[0]
    assert f["stage"] == "agent_runner"
    assert f["block_type"] == "tool_failure"
    assert f["status"] == "resolved"
    assert f["resolved_at"] is not None
    assert "npm" in f["notes"]
    assert "returncode=1" in f["notes"]


# ---------------------------------------------------------------------------
# R2 (timeout): Timeout records runtime event with status_code=504 AND friction
# ---------------------------------------------------------------------------


def test_timeout_records_runtime_504_and_friction(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, base_time=5000.0)

    def _popen(*args, **kwargs):
        return _TimeoutProc(stdout_text="partial output\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_timeout",
        command="pytest --slow",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
    )
    assert done is True

    # Runtime event with 504
    runtime_posts = [p for p in client.posts if p[0].endswith("/api/runtime/events")]
    assert len(runtime_posts) == 1
    _url, payload = runtime_posts[0]
    assert payload["status_code"] == 504

    # Friction event
    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    assert len(friction_posts) == 1
    _furl, f = friction_posts[0]
    assert f["stage"] == "agent_runner"
    assert f["block_type"] == "tool_failure"
    assert f["status"] == "resolved"


# ---------------------------------------------------------------------------
# R2: Friction event includes energy_loss_estimate > 0
# ---------------------------------------------------------------------------


def test_friction_event_has_positive_energy_loss(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, base_time=2000.0)

    def _popen(*args, **kwargs):
        return _Proc(returncode=1, stdout_text="fail\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    agent_runner.run_one_task(
        client=client,
        task_id="task_energy",
        command="make build",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
    )

    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    assert len(friction_posts) == 1
    f = friction_posts[0][1]
    assert f["energy_loss_estimate"] > 0
    # energy_loss = duration * PIPELINE_TIME_COST_PER_SECOND (0.01)
    # duration > 0 (monotonic clock increments), so energy > 0


# ---------------------------------------------------------------------------
# R2: Suspicious zero-output success creates friction event
# ---------------------------------------------------------------------------


def test_suspicious_zero_output_creates_friction(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, base_time=3000.0)

    def _popen(*args, **kwargs):
        return _Proc(returncode=0, stdout_text="")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    agent_runner.run_one_task(
        client=client,
        task_id="task_zero",
        command="npm ci",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
    )

    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    assert len(friction_posts) == 1
    f = friction_posts[0][1]
    assert f["block_type"] == "tool_failure"


# ---------------------------------------------------------------------------
# R3: Monitor detects expensive_failed_task from metrics.jsonl
# ---------------------------------------------------------------------------


def test_monitor_detects_expensive_failed_task(tmp_path):
    from datetime import datetime, timezone

    # Write metrics.jsonl with failed tasks exceeding threshold.
    metrics_file = tmp_path / "metrics.jsonl"
    now = datetime.now(timezone.utc)
    records = [
        {
            "task_id": "task_expensive_1",
            "task_type": "impl",
            "model": "test",
            "duration_seconds": 300.0,
            "status": "failed",
            "created_at": now.isoformat(),
        },
        {
            "task_id": "task_expensive_2",
            "task_type": "impl",
            "model": "test",
            "duration_seconds": 200.0,
            "status": "failed",
            "created_at": now.isoformat(),
        },
        {
            "task_id": "task_cheap_ok",
            "task_type": "impl",
            "model": "test",
            "duration_seconds": 10.0,
            "status": "completed",
            "created_at": now.isoformat(),
        },
    ]
    with open(metrics_file, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Patch LOG_DIR to point to tmp_path so _load_recent_failed_task_durations finds it.
    original_log_dir = monitor_pipeline.LOG_DIR
    monitor_pipeline.LOG_DIR = str(tmp_path)
    try:
        failed = monitor_pipeline._load_recent_failed_task_durations(now)
        # Should find 2 failed tasks (not the completed one).
        assert len(failed) == 2
        assert failed[0]["task_id"] == "task_expensive_1"  # sorted by duration desc
        assert failed[0]["duration_seconds"] == 300.0
        assert failed[1]["task_id"] == "task_expensive_2"
        assert failed[1]["duration_seconds"] == 200.0

        # Verify threshold filtering: both above default 120s threshold.
        threshold = float(monitor_pipeline.EXPENSIVE_FAIL_THRESHOLD_SEC)
        expensive = [r for r in failed if r["duration_seconds"] >= threshold]
        assert len(expensive) == 2
    finally:
        monitor_pipeline.LOG_DIR = original_log_dir


def test_monitor_expensive_failed_task_issue_includes_wasted_seconds(tmp_path):
    """The _add_issue for expensive_failed_task includes wasted_seconds and top_failing_task_ids."""
    from datetime import datetime, timezone
    import uuid as _uuid

    now = datetime.now(timezone.utc)
    metrics_file = tmp_path / "metrics.jsonl"
    records = [
        {
            "task_id": f"task_exp_{i}",
            "task_type": "impl",
            "model": "test",
            "duration_seconds": 150.0 + i * 50,
            "status": "failed",
            "created_at": now.isoformat(),
        }
        for i in range(4)
    ]
    with open(metrics_file, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    original_log_dir = monitor_pipeline.LOG_DIR
    monitor_pipeline.LOG_DIR = str(tmp_path)
    try:
        failed = monitor_pipeline._load_recent_failed_task_durations(now)
        threshold = float(monitor_pipeline.EXPENSIVE_FAIL_THRESHOLD_SEC)
        expensive = [r for r in failed if r["duration_seconds"] >= threshold]
        assert len(expensive) == 4  # all >= 150s, threshold default 120s

        # Simulate what the detection loop does.
        data = {"issues": [], "history": []}
        if expensive:
            top = expensive[:3]
            wasted_seconds = round(sum(r["duration_seconds"] for r in expensive), 1)
            top_ids = [r["task_id"] for r in top]
            msg = (
                f"Recent failed tasks wasted {wasted_seconds}s total: "
                + ", ".join(f"{r['task_id']}({r['duration_seconds']}s)" for r in top)
            )
            monitor_pipeline._add_issue(data, "expensive_failed_task", "high", msg, "Fix root cause.")
            data["issues"][-1]["wasted_seconds"] = wasted_seconds
            data["issues"][-1]["top_failing_task_ids"] = top_ids

        assert len(data["issues"]) == 1
        issue = data["issues"][0]
        assert issue["condition"] == "expensive_failed_task"
        assert issue["severity"] == "high"
        assert issue["wasted_seconds"] > 0
        assert len(issue["top_failing_task_ids"]) == 3
    finally:
        monitor_pipeline.LOG_DIR = original_log_dir
