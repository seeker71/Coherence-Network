from __future__ import annotations

import io
from dataclasses import dataclass
import importlib.util
from pathlib import Path

import pytest

_AGENT_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_runner.py"
_spec = importlib.util.spec_from_file_location("agent_runner", _AGENT_RUNNER_PATH)
assert _spec and _spec.loader
agent_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent_runner)


@dataclass
class _Resp:
    status_code: int = 200

    def json(self):
        return {}


class _Client:
    def __init__(self):
        self.posts: list[tuple[str, dict]] = []
        self.patches: list[tuple[str, dict]] = []

    def patch(self, url: str, json: dict):
        self.patches.append((url, json))
        return _Resp(200)

    def post(self, url: str, json: dict, timeout: float | None = None):
        self.posts.append((url, json))
        return _Resp(201)


class _Proc:
    def __init__(self, *, returncode: int, stdout_text: str):
        self.returncode = returncode
        self.stdout = io.StringIO(stdout_text)

    def wait(self, timeout: float | None = None):
        return self.returncode

    def kill(self):
        self.returncode = -9


@pytest.mark.parametrize(
    "returncode,stdout_text,expect_friction",
    [
        (0, "this is enough output\n", False),
        (1, "error\n", True),
    ],
)
def test_agent_runner_posts_runtime_and_friction_events(monkeypatch, tmp_path, returncode, stdout_text, expect_friction):
    # Force deterministic timing (avoid 0ms runtime).
    t = [1000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)

    # Ensure runner writes logs to temp.
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))

    # Enable telemetry.
    monkeypatch.setenv("PIPELINE_TOOL_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("PIPELINE_TOOL_FAILURE_FRICTION_ENABLED", "1")

    def _popen(*args, **kwargs):
        return _Proc(returncode=returncode, stdout_text=stdout_text)

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_test",
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
    assert payload["runtime_ms"] > 0
    assert payload["idea_id"] == "coherence-network-agent-pipeline"
    assert payload["metadata"]["task_id"] == "task_test"
    assert payload["metadata"]["returncode"] == returncode

    friction_posts = [p for p in client.posts if p[0].endswith("/api/friction/events")]
    if expect_friction:
        assert len(friction_posts) == 1
        _furl, f = friction_posts[0]
        assert f["stage"] == "agent_runner"
        assert f["block_type"] == "tool_failure"
        assert f["status"] == "resolved"
        assert f["energy_loss_estimate"] >= 0
    else:
        assert friction_posts == []


def test_suspicious_zero_output_success_creates_friction(monkeypatch, tmp_path):
    # Zero output + returncode 0 should trigger suspicious failure path.
    t = [2000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("PIPELINE_TOOL_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("PIPELINE_TOOL_FAILURE_FRICTION_ENABLED", "1")

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


def test_agent_runner_runtime_event_includes_codex_execution_metadata(monkeypatch, tmp_path):
    t = [3000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("PIPELINE_TOOL_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex")

    def _popen(*args, **kwargs):
        return _Proc(returncode=0, stdout_text="codex execution output\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_codex",
        command='agent "Run implementation task" --model openrouter/free',
        log=log,
        verbose=False,
        task_type="impl",
        model="cursor/openrouter/free",
    )
    assert done is True

    runtime_posts = [p for p in client.posts if p[0].endswith("/api/runtime/events")]
    assert len(runtime_posts) == 1
    _, payload = runtime_posts[0]
    metadata = payload["metadata"]
    assert metadata["worker_id"] == "openai-codex"
    assert metadata["executor"] == "cursor"
    assert metadata["agent_id"] == "openai-codex"
    assert metadata["is_openai_codex"] is True


def test_infer_executor_detects_openclaw():
    assert agent_runner._infer_executor('openclaw run "task"', "openclaw/model") == "openclaw"


def test_parse_diff_manifestation_blocks_extracts_file_line_ranges():
    diff_text = """diff --git a/api/app/demo.py b/api/app/demo.py
index 1111111..2222222 100644
--- a/api/app/demo.py
+++ b/api/app/demo.py
@@ -10,0 +10,4 @@
+line_a
+line_b
+line_c
+line_d
@@ -30,2 +34,1 @@
-old_a
-old_b
+new_a
"""
    blocks = agent_runner._parse_diff_manifestation_blocks(diff_text, max_blocks=10)
    assert blocks == [
        {
            "file": "api/app/demo.py",
            "line": 10,
            "file_line_ref": "api/app/demo.py:10",
            "read_range": "10-13",
            "manifestation_range": "L10-L13",
        },
        {
            "file": "api/app/demo.py",
            "line": 34,
            "file_line_ref": "api/app/demo.py:34",
            "read_range": "34-34",
            "manifestation_range": "L34-L34",
        },
    ]


def test_append_agent_manifest_entry_writes_agent_doc_and_context(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_runner, "AGENT_MANIFESTS_DIR", str(tmp_path))
    monkeypatch.setattr(agent_runner, "AGENT_MANIFEST_ENABLED", True)
    monkeypatch.setattr(
        agent_runner,
        "_collect_manifestation_blocks",
        lambda _repo_path, *, max_blocks: [
            {
                "file": "api/app/service.py",
                "line": 42,
                "file_line_ref": "api/app/service.py:42",
                "read_range": "42-48",
                "manifestation_range": "L42-L48",
            }
        ],
    )

    payload = agent_runner._append_agent_manifest_entry(
        task_id="task_manifest",
        task_type="impl",
        task_direction="Implement measurable ROI provenance tracking",
        task_ctx={
            "task_agent": "dev-engineer",
            "idea_id": "coherence-network-agent-pipeline",
            "spec_ref": "specs/054-commit-provenance-contract-gate.md",
        },
        repo_path=str(tmp_path),
        executor="openai-codex",
    )

    manifest = payload.get("agent_manifest") or {}
    assert manifest.get("agent_name") == "dev-engineer"
    assert manifest.get("idea_id") == "coherence-network-agent-pipeline"
    doc_path = Path(str(manifest.get("doc_path") or ""))
    assert doc_path.exists()
    body = doc_path.read_text(encoding="utf-8")
    assert "Idea link" in body
    assert "api/app/service.py:42" in body
    assert "manifestation_range `L42-L48`" in body
