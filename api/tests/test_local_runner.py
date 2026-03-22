from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts import local_runner


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "" if payload is None else "ok"

    def json(self) -> dict[str, Any]:
        return self._payload


def test_claim_and_complete_task_with_mocked_api_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def _patch(url: str, json: dict[str, Any] | None = None) -> _DummyResponse:
        calls.append((url, json))
        if json and json.get("status") == "running":
            return _DummyResponse(200, {"id": "task-1", "status": "running", "task_type": "test"})
        return _DummyResponse(200, {"id": "task-1", "status": "completed"})

    monkeypatch.setattr(local_runner._HTTP_CLIENT, "patch", _patch)

    claimed = local_runner.claim_task("task-1")
    ok = local_runner.complete_task("task-1", "runner output", True, {"provider": "codex"})

    assert claimed is not None
    assert claimed["status"] == "running"
    assert ok is True
    assert calls[0][0].endswith("/api/agent/tasks/task-1")
    assert calls[0][1] == {"status": "running", "claimed_by": local_runner.WORKER_ID}
    assert calls[1][0].endswith("/api/agent/tasks/task-1")
    assert calls[1][1] == {
        "status": "completed",
        "output": "runner output",
        "context": {"provider": "codex"},
    }


def test_select_provider_filters_to_tool_capable_for_test_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_runner, "PROVIDERS", {"openrouter": {"api": True}, "codex": {"cmd": ["codex"]}})
    monkeypatch.setattr(local_runner, "HAS_SERVICES", False)

    selected = local_runner.select_provider("test")

    assert selected == "codex"


def test_run_one_marks_false_positive_when_text_only_provider_reports_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    task = {"id": "task-fp-1", "task_type": "test", "direction": "Write tests"}
    completion: dict[str, Any] = {}

    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "claim_task", lambda _task_id: task | {"status": "running"})
    monkeypatch.setattr(local_runner, "select_provider", lambda _task_type: "openrouter")
    monkeypatch.setattr(local_runner, "build_prompt", lambda _task: "prompt")
    monkeypatch.setattr(local_runner, "execute_with_provider", lambda *_args, **_kwargs: (True, "all done", 1.2))
    monkeypatch.setattr(local_runner, "record_provider_outcome", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(local_runner, "PROVIDERS", {"openrouter": {"api": True}})

    class _GitStatus:
        def __init__(self, output: str) -> None:
            self.stdout = output

    monkeypatch.setattr(
        local_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: _GitStatus(""),
    )

    def _complete(task_id: str, output: str, success: bool, context_patch: dict[str, Any] | None = None) -> bool:
        completion["task_id"] = task_id
        completion["output"] = output
        completion["success"] = success
        completion["context_patch"] = context_patch
        return True

    monkeypatch.setattr(local_runner, "complete_task", _complete)

    ok = local_runner.run_one(task, dry_run=False)

    assert ok is False
    assert completion["task_id"] == "task-fp-1"
    assert completion["success"] is False
    assert "FALSE POSITIVE" in completion["output"]
    assert completion["context_patch"]["provider"] == "openrouter"


def test_get_timeout_for_uses_data_driven_slot_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Selector:
        def __init__(self, _scope: str) -> None:
            pass

        def stats(self, _providers: list[str]) -> dict[str, Any]:
            return {
                "slots": {
                    "codex": {
                        "suggested_timeout_s": 222,
                        "p90_duration_s": 88,
                    }
                }
            }

    monkeypatch.setattr(local_runner, "HAS_SERVICES", True)
    monkeypatch.setattr(local_runner, "SlotSelector", _Selector)

    timeout = local_runner.get_timeout_for("codex", "test")

    assert timeout == 222


def test_get_timeout_for_falls_back_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Selector:
        def __init__(self, _scope: str) -> None:
            pass

        def stats(self, _providers: list[str]) -> dict[str, Any]:
            return {"slots": {"codex": {"suggested_timeout_s": 0}}}

    monkeypatch.setattr(local_runner, "HAS_SERVICES", True)
    monkeypatch.setattr(local_runner, "SlotSelector", _Selector)
    local_runner._TASK_TIMEOUT[0] = 345

    timeout = local_runner.get_timeout_for("codex", "test")

    assert timeout == 345
