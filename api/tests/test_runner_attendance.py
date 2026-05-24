"""Tests for runner-attendance-loop spec.

The spec says: the runner attends, the reaper releases. These tests pin down
the reaper-side release contract (the surface the spec calls out: is_runner_alive,
smart_reap_task, build_reap_diagnosis) plus the runner-side attendance surface
(_post_activity, _kill_process_tree, execute_with_provider) that the loop
revision will use to publish liveness signals.

The reaper is the single source of release decisions: when a runner has not
been seen recently (no heartbeat / no attendance signal), the reaper transitions
the task per its existing thresholds (extend → reap → needs_human_attention).
When a runner IS alive, the reaper extends rather than killing.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from app.services import smart_reaper_service as reaper


# ---------------------------------------------------------------------------
# Lazy-load the runner module — it lives under api/scripts/, not api/app/
# ---------------------------------------------------------------------------

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "local_runner.py"
_spec = importlib.util.spec_from_file_location("local_runner", _RUNNER_PATH)
assert _spec and _spec.loader
local_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(local_runner)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _runner(runner_id: str, seen_seconds_ago: float) -> dict[str, Any]:
    last_seen = datetime.now(timezone.utc) - timedelta(seconds=seen_seconds_ago)
    return {"runner_id": runner_id, "last_seen_at": _iso(last_seen)}


def _task(
    *,
    task_id: str = "t-attend",
    claimed_by: str | None = "runner-a",
    created_seconds_ago: float = 60.0,
    extensions: int = 0,
    extra_ctx: dict | None = None,
) -> dict[str, Any]:
    created = datetime.now(timezone.utc) - timedelta(seconds=created_seconds_ago)
    ctx: dict[str, Any] = {"idea_id": "pipeline-reliability", "provider": "claude"}
    if extensions:
        ctx["reap_extensions"] = extensions
    if extra_ctx:
        ctx.update(extra_ctx)
    return {
        "id": task_id,
        "task_type": "impl",
        "claimed_by": claimed_by or "",
        "created_at": _iso(created),
        "context": ctx,
        "target_state": "implementation complete",
    }


class _ApiFn:
    """Records api_fn calls so we can assert what the reaper decided to do."""

    def __init__(self, patch_response: dict | None = None, post_response: dict | None = None):
        self.calls: list[tuple[str, str, dict]] = []
        self._patch = patch_response if patch_response is not None else {"ok": True}
        self._post = post_response if post_response is not None else {"id": "resume-1"}

    def __call__(self, method: str, path: str, body: dict | None = None) -> Any:
        self.calls.append((method, path, body or {}))
        if method == "PATCH":
            return self._patch
        if method == "POST":
            return self._post
        return {}


# ---------------------------------------------------------------------------
# Runner-side attendance surface — the channels the new loop will publish on
# ---------------------------------------------------------------------------

def test_runner_exposes_attendance_surface():
    """execute_with_provider, _post_activity, _kill_process_tree are the three
    surfaces the spec changes touch. They must exist and be callable."""
    assert callable(local_runner._post_activity)
    assert callable(local_runner._kill_process_tree)
    assert callable(local_runner.execute_with_provider)


def test_post_activity_swallows_network_errors(monkeypatch):
    """Attendance posts are fire-and-forget — a transient API hiccup must not
    take down the runner's read loop. R2: heartbeats post regardless of network."""

    class _Boom:
        def post(self, *_a, **_kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(local_runner, "httpx", _Boom())
    # Must not raise — the runner attends even when posting fails.
    local_runner._post_activity("task-x", "liveness", {"elapsed_s": 10})


def test_post_activity_sends_event_type_and_data_payload(monkeypatch):
    """The liveness event channel carries (event_type, data) the reaper reads."""
    captured: dict[str, Any] = {}

    class _OkResp:
        status_code = 200
        text = ""

    class _Client:
        def post(self, url, json=None, timeout=None, **_kw):
            captured["url"] = url
            captured["json"] = json
            return _OkResp()

    monkeypatch.setattr(local_runner, "httpx", _Client())
    local_runner._post_activity(
        "task-attend",
        "liveness",
        {
            "elapsed_s": 12,
            "since_last_output_s": 12,
            "last_preview": "waiting for model",
            "process_alive": True,
            "provider": "claude",
        },
    )

    assert "task-attend" in captured["url"]
    assert captured["url"].endswith("/activity")
    payload = captured["json"]
    assert payload["event_type"] == "liveness"
    assert payload["data"]["elapsed_s"] == 12
    assert payload["data"]["process_alive"] is True
    assert payload["data"]["last_preview"] == "waiting for model"
    assert payload["provider"] == "claude"


# ---------------------------------------------------------------------------
# Reaper-side release contract — is_runner_alive is the attendance sensor
# ---------------------------------------------------------------------------

def test_recently_seen_runner_is_alive():
    """A runner with a fresh last_seen_at is attending — reaper must defer."""
    task = _task(claimed_by="runner-a")
    runners = [_runner("runner-a", seen_seconds_ago=30)]
    assert reaper.is_runner_alive(task, runners) is True


def test_long_silent_runner_is_not_alive():
    """A runner past REAP_RUNNER_LIVENESS_SECONDS is silent — reaper releases."""
    task = _task(claimed_by="runner-a")
    silent_for = reaper.REAP_RUNNER_LIVENESS_SECONDS + 60
    runners = [_runner("runner-a", seen_seconds_ago=silent_for)]
    assert reaper.is_runner_alive(task, runners) is False


def test_unclaimed_task_has_no_attending_runner():
    """A task with no claimed_by has no runner attending it — reaper can release."""
    task = _task(claimed_by=None)
    runners = [_runner("runner-a", seen_seconds_ago=10)]
    assert reaper.is_runner_alive(task, runners) is False


def test_unregistered_runner_is_not_alive():
    """claimed_by points at a runner that is not in the registry → silent."""
    task = _task(claimed_by="runner-ghost")
    runners = [_runner("runner-a", seen_seconds_ago=10)]
    assert reaper.is_runner_alive(task, runners) is False


# ---------------------------------------------------------------------------
# smart_reap_task — extension on live runner, reap on silent runner
# ---------------------------------------------------------------------------

def test_reaper_extends_when_runner_attending(tmp_path):
    """R6 inverse — when the runner IS attending (within liveness window) and
    extensions remain, the reaper extends rather than killing. The runner-side
    clock-based kill is gone; release is the reaper's call alone."""
    task = _task(claimed_by="runner-a", created_seconds_ago=60)
    runners = [_runner("runner-a", seen_seconds_ago=15)]
    api = _ApiFn()

    result = reaper.smart_reap_task(
        task,
        runners=runners,
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=30,
        api_fn=api,
    )

    assert result["action"] == "extended"
    # No reap PATCH to timed_out — only the extension PATCH on context.
    patches = [c for c in api.calls if c[0] == "PATCH"]
    assert len(patches) == 1
    body = patches[0][2]
    assert "context" in body and body["context"]["reap_extensions"] == 1
    assert "status" not in body  # not transitioning to timed_out yet


def test_reaper_releases_when_runner_silent(tmp_path):
    """When the runner has stopped attending (silent past liveness window),
    the reaper transitions the task to timed_out — this is the release the
    spec assigns solely to the reaper."""
    task = _task(claimed_by="runner-a")
    runners = [_runner("runner-a", seen_seconds_ago=reaper.REAP_RUNNER_LIVENESS_SECONDS + 60)]
    api = _ApiFn()

    result = reaper.smart_reap_task(
        task,
        runners=runners,
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=30,
        api_fn=api,
    )

    assert result["action"] == "reaped"
    # PATCH transitions the task to timed_out — the reaper's release.
    timeout_patch = next(
        (c for c in api.calls if c[0] == "PATCH" and c[2].get("status") == "timed_out"),
        None,
    )
    assert timeout_patch is not None
    assert timeout_patch[2]["context"]["reap_diagnosis"]["runner_alive"] is False


def test_reaper_releases_after_max_extensions(tmp_path):
    """Even with a live runner, once REAP_MAX_EXTENSIONS is reached the reaper
    stops extending and releases — preventing indefinite hangs the spec names
    in its 'Risks' section."""
    task = _task(
        claimed_by="runner-a",
        created_seconds_ago=60,
        extensions=reaper.REAP_MAX_EXTENSIONS,
    )
    runners = [_runner("runner-a", seen_seconds_ago=10)]
    api = _ApiFn()

    result = reaper.smart_reap_task(
        task,
        runners=runners,
        timed_out_tasks=[],
        log_dir=tmp_path,
        max_age_minutes=30,
        api_fn=api,
    )

    assert result["action"] == "reaped"
    diag = result["diagnosis"]
    assert diag["runner_alive"] is True  # honest record: runner WAS alive
    assert diag["extensions_granted"] == reaper.REAP_MAX_EXTENSIONS


def test_reaper_flags_human_attention_after_persistent_failures(tmp_path):
    """R6: persistent stalls (≥ REAP_HUMAN_ATTENTION_THRESHOLD timeouts on the
    same idea/task_type) escalate to needs_human_attention. The reaper aggregates
    this from prior timed_out tasks — the runner contributes no clock-based kill."""
    idea_id = "pipeline-reliability"
    prior_timeouts = [
        {
            "id": f"prior-{i}",
            "task_type": "impl",
            "status": "timed_out",
            "context": {
                "idea_id": idea_id,
                "reap_diagnosis": {
                    "reaped_at": _iso(datetime.now(timezone.utc) - timedelta(minutes=i + 1)),
                    "error_class": "executor_crash",
                    "partial_output_pct": 0,
                },
            },
        }
        for i in range(reaper.REAP_HUMAN_ATTENTION_THRESHOLD - 1)
    ]
    history = reaper.aggregate_reap_history(prior_timeouts, idea_id_filter=idea_id)
    # Below threshold — not yet flagged.
    assert history and history[0]["needs_human_attention"] is False

    # One more timeout brings it to threshold.
    one_more = dict(prior_timeouts[0])
    one_more["id"] = "prior-last"
    history2 = reaper.aggregate_reap_history(prior_timeouts + [one_more], idea_id_filter=idea_id)
    assert history2[0]["timeout_count"] == reaper.REAP_HUMAN_ATTENTION_THRESHOLD
    assert history2[0]["needs_human_attention"] is True


# ---------------------------------------------------------------------------
# build_reap_diagnosis — the structured record the reaper writes
# ---------------------------------------------------------------------------

def test_build_reap_diagnosis_carries_attendance_signal():
    """The diagnosis the reaper writes must carry runner_alive — that is the
    attendance signal the spec moves the runner toward emitting and the reaper
    toward consuming."""
    diag = reaper.build_reap_diagnosis(
        runner_alive=True,
        provider="claude",
        partial_output="some output",
        partial_chars=120,
        partial_pct=15,
        extensions_granted=1,
        resume_task_id="resume-42",
        error_class="executor_stall",
    )
    assert diag["runner_alive"] is True
    assert diag["provider"] == "claude"
    assert diag["error_class"] == "executor_stall"
    assert diag["extensions_granted"] == 1
    assert diag["resume_task_id"] == "resume-42"
    assert diag["partial_output_chars"] == 120
    assert "reaped_at" in diag


def test_build_reap_diagnosis_records_silent_runner():
    """When the runner went silent, the diagnosis records that plainly —
    runner_alive=False is the body's honest record of what happened, not
    a verdict the runner imposed via its own stopwatch."""
    diag = reaper.build_reap_diagnosis(
        runner_alive=False,
        provider="codex",
        partial_output="",
        partial_chars=0,
        partial_pct=0,
        extensions_granted=0,
        resume_task_id=None,
        error_class="executor_crash",
    )
    assert diag["runner_alive"] is False
    assert diag["resume_task_id"] is None
    assert diag["partial_output_chars"] == 0
