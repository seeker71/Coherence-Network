from __future__ import annotations

import io
from dataclasses import dataclass
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta, timezone

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


def test_apply_codex_model_alias_uses_configured_map(monkeypatch):
    monkeypatch.setenv("AGENT_CODEX_MODEL_ALIAS_MAP", "gpt-5.3-codex:gpt-5-codex")
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."'
    )
    assert alias == {
        "requested_model": "gpt-5.3-codex",
        "effective_model": "gpt-5-codex",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model gpt-5.3-codex" not in remapped


def test_run_one_task_records_codex_model_alias_in_context_and_log(monkeypatch, tmp_path):
    t = [4000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_CODEX_MODEL_ALIAS_MAP", "gpt-5.3-codex:gpt-5-codex")
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:test-runner")

    def _popen(*args, **kwargs):
        return _Proc(returncode=0, stdout_text="MODEL_OK\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_alias",
        command='codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/openrouter/free",
    )
    assert done is True

    running_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_alias") and patch.get("status") == "running"
    )
    context = running_patch.get("context") or {}
    alias = context.get("runner_model_alias") or {}
    assert alias.get("requested_model") == "gpt-5.3-codex"
    assert alias.get("effective_model") == "gpt-5-codex"

    log_file = tmp_path / "task_task_alias.log"
    body = log_file.read_text(encoding="utf-8")
    assert "--model gpt-5-codex" in body
    assert "--model gpt-5.3-codex" not in body
    assert "runner-model-alias" in body


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


def test_observe_target_contract_detects_abort_evidence():
    contract = agent_runner._normalize_task_target_contract(
        {
            "target_state": "task completed with clean output",
            "success_evidence": ["all checks passed"],
            "abort_evidence": ["fatal", "panic"],
            "observation_window_sec": 120,
        },
        task_type="impl",
        task_direction="run task",
    )
    observed = agent_runner._observe_target_contract(
        contract=contract,
        output="step completed then fatal pipeline state reached",
        duration_seconds=140.0,
        attempt_status="completed",
    )
    assert observed["abort_evidence_met"] is True
    assert "fatal" in observed["abort_evidence_hits"]
    assert observed["observation_window_exceeded"] is True


def test_high_hold_pattern_score_requests_steering_and_suppresses_retry(monkeypatch, tmp_path):
    t = [4000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))

    def _popen(*args, **kwargs):
        return _Proc(returncode=1, stdout_text="run failed with blocker\n")

    diag_calls: list[dict[str, str]] = []

    def _run_diag(request, *, cwd, env):
        diag_calls.append({"command": str(request.get("command") or ""), "cwd": cwd})
        return {"id": request.get("id"), "status": "completed", "exit_code": 0, "output_tail": "diag ok"}

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setattr(agent_runner, "_run_diagnostic_request", _run_diag)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)
    done = agent_runner.run_one_task(
        client=client,
        task_id="task_hold_policy",
        command="pytest -q",
        log=log,
        verbose=False,
        task_type="impl",
        model="test-model",
        task_context={
            "runner_retry_max": 3,
            "runner_retry_delay_seconds": 1,
            "hold_pattern_score": 0.92,
            "hold_pattern_score_threshold": 0.8,
            "hold_pattern_diagnostic_command": "git status --porcelain --branch",
        },
    )
    assert done is True
    assert len(diag_calls) == 1
    assert "git status" in diag_calls[0]["command"]

    needs_decision_patches = [payload for _, payload in client.patches if payload.get("status") == "needs_decision"]
    assert len(needs_decision_patches) >= 1
    latest = needs_decision_patches[-1]
    assert latest.get("current_step") == "awaiting steering"
    context = latest.get("context") or {}
    hold_policy = context.get("hold_pattern_policy") or {}
    assert hold_policy.get("triggered") is True
    assert hold_policy.get("blind_retry_suppressed") is True
    assert context.get("runner_action_rate") == "reduced"


def test_record_observer_context_snapshot_tracks_state_delta(monkeypatch):
    captured: dict = {}

    def _fake_snapshot(_client, _task_id):
        return {
            "context": {
                "observer_context_snapshots": [
                    {
                        "transition": "claim",
                        "state": {"runner_state": "claimed", "last_attempt": 1},
                    }
                ]
            }
        }

    def _fake_patch_context(_client, *, task_id, context_patch):
        captured["task_id"] = task_id
        captured["context_patch"] = context_patch

    monkeypatch.setattr(agent_runner, "_safe_get_task_snapshot", _fake_snapshot)
    monkeypatch.setattr(agent_runner, "_patch_task_context", _fake_patch_context)

    agent_runner._record_observer_context_snapshot(
        _Client(),
        task_id="task_observer_delta",
        transition="start",
        run_id="run_abc",
        worker_id="worker_xyz",
        status="running",
        current_step="command started",
        context_hint={"runner_state": "running", "last_attempt": 2},
    )

    patch = captured.get("context_patch") or {}
    latest = patch.get("observer_context_last_snapshot") or {}
    assert latest.get("transition") == "start"
    delta = latest.get("delta") or {}
    assert delta.get("runner_state") == "running"
    assert delta.get("last_attempt") == 2
    assert patch.get("awareness_transition_total") == 1
    assert patch.get("awareness_successful_transition_total") == 1
    history = patch.get("observer_context_snapshots") or []
    assert len(history) == 2


def test_allow_intervention_frequency_blocks_when_limit_reached():
    now = datetime.now(timezone.utc)
    context = {
        "max_interventions_per_window": 1,
        "intervention_window_sec": 600,
        "runner_intervention_events": [
            {"kind": "diagnostic", "at": (now - timedelta(seconds=15)).isoformat()}
        ],
        "awareness_events_total": 3,
        "awareness_interventions_total": 1,
        "awareness_blocks_total": 0,
    }
    allowed, patch, limits, window_load = agent_runner._allow_intervention_frequency(
        context,
        kind="retry",
        now=now,
    )
    assert allowed is False
    assert window_load == 1
    assert limits["max_interventions_per_window"] == 1
    assert patch["awareness_events_total"] == 4
    assert patch["awareness_blocks_total"] == 1
    block = patch.get("cadence_last_block") or {}
    assert block.get("reason") == "max_interventions_per_window"


def test_awareness_patch_from_context_reports_quality_score():
    context = {
        "awareness_events_total": 4,
        "awareness_interventions_total": 2,
        "awareness_blocks_total": 1,
        "awareness_transition_total": 3,
        "awareness_successful_transition_total": 2,
        "awareness_hold_pattern_total": 1,
        "awareness_transition_cost_total": 4.0,
        "estimated_roi": 100.0,
        "measured_roi": 20.0,
        "observer_context_snapshots": [{"transition": "claim"}, {"transition": "start"}],
    }
    patch = agent_runner._awareness_patch_from_context(
        context,
        event_inc=1,
        intervention_inc=1,
        block_inc=0,
        transition_inc=1,
        successful_transition_inc=1,
        hold_pattern_inc=0,
        transition_cost_inc=2.0,
        snapshot_count_override=3,
    )
    quality = patch.get("awareness_quality") or {}
    assert patch["awareness_events_total"] == 5
    assert patch["awareness_interventions_total"] == 3
    assert patch["awareness_blocks_total"] == 1
    assert patch["awareness_transition_total"] == 4
    assert patch["awareness_successful_transition_total"] == 3
    assert patch["awareness_transition_cost_total"] == pytest.approx(6.0)
    assert quality.get("state_transition_quality") == pytest.approx(0.75, rel=1e-3)
    assert quality.get("hold_pattern_rate") == pytest.approx(0.25, rel=1e-3)
    assert quality.get("estimated_to_measured_roi_conversion") == pytest.approx(0.2, rel=1e-3)
    assert quality.get("cost_per_successful_transition") == pytest.approx(2.0, rel=1e-3)
    assert 0.0 <= float(quality.get("score", -1.0)) <= 1.0


def test_awareness_quality_tracks_requested_metrics():
    context = {
        "awareness_events_total": 2,
        "awareness_interventions_total": 1,
        "awareness_blocks_total": 0,
        "awareness_transition_total": 4,
        "awareness_successful_transition_total": 2,
        "awareness_hold_pattern_total": 1,
        "awareness_transition_cost_total": 10.0,
        "estimated_roi": 100.0,
        "measured_roi": 40.0,
        "observer_context_snapshots": [{"transition": "claim"}],
    }
    patch = agent_runner._awareness_patch_from_context(
        context,
        event_inc=1,
        transition_inc=1,
        successful_transition_inc=1,
        hold_pattern_inc=1,
        transition_cost_inc=2.5,
        snapshot_count_override=4,
    )
    quality = patch.get("awareness_quality") or {}
    assert quality.get("state_transition_quality") == pytest.approx(0.6, rel=1e-3)
    assert quality.get("hold_pattern_rate") == pytest.approx(0.4, rel=1e-3)
    assert quality.get("estimated_to_measured_roi_conversion") == pytest.approx(0.4, rel=1e-3)
    assert quality.get("cost_per_successful_transition") == pytest.approx(12.5 / 3.0, rel=1e-3)
