from __future__ import annotations

import subprocess
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

    def _patch(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _DummyResponse:
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
    assert calls[0][1] == {"status": "running", "worker_id": local_runner.WORKER_ID}
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


def test_openrouter_chat_completion_uses_free_model_and_referer(monkeypatch: pytest.MonkeyPatch) -> None:
    request: dict[str, Any] = {}

    def _post(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> _DummyResponse:
        request["url"] = url
        request["headers"] = headers or {}
        request["json"] = json or {}
        request["timeout"] = timeout
        return _DummyResponse(
            200,
            {"choices": [{"message": {"content": "hello from openrouter"}}]},
        )

    monkeypatch.setattr(local_runner.httpx, "post", _post)

    content = local_runner._openrouter_chat_completion("Say hello", timeout_s=8.0)

    assert content == "hello from openrouter"
    assert request["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert request["headers"]["HTTP-Referer"] == "https://coherencycoin.com"
    assert request["json"]["model"] == "nvidia/nemotron-nano-12b-v2-vl:free"
    assert request["json"]["messages"][0]["content"] == "Say hello"
    assert request["timeout"] == 8.0


def test_check_openrouter_uses_simple_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def _chat(prompt: str, timeout_s: float, *, model: str | None = None) -> str:
        seen["prompt"] = prompt
        seen["timeout_s"] = timeout_s
        return "ok"

    monkeypatch.setattr(local_runner, "_openrouter_chat_completion", _chat)

    assert local_runner._check_openrouter() is True
    assert seen["prompt"] == "Reply with: ok"
    assert seen["timeout_s"] == 10.0


def test_run_one_marks_false_positive_when_text_only_provider_reports_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    task = {"id": "task-fp-1", "task_type": "test", "direction": "Write tests"}
    completion: dict[str, Any] = {}

    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "claim_task", lambda _task_id: task | {"status": "running"})
    monkeypatch.setattr(local_runner, "select_provider", lambda _task_type, **_kw: "openrouter")
    monkeypatch.setattr(local_runner, "build_prompt", lambda _task: "prompt")
    monkeypatch.setattr(local_runner, "execute_with_provider", lambda *_args, **_kwargs: (True, "all done", 1.2))
    monkeypatch.setattr(local_runner, "record_provider_outcome", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(local_runner, "PROVIDERS", {"openrouter": {"api": True}})
    monkeypatch.setattr(local_runner, "api", lambda *_args, **_kwargs: task | {"status": "running"})

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

    def _complete_status(task_id: str, output: str, status: str, context_patch: dict[str, Any] | None = None, error_category: str = "execution_error") -> bool:
        completion["task_id"] = task_id
        completion["output"] = output
        completion["success"] = (status == "completed")
        completion["context_patch"] = context_patch
        return True

    monkeypatch.setattr(local_runner, "complete_task", _complete)
    monkeypatch.setattr(local_runner, "_complete_task_with_status", _complete_status)
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
                        "p90_duration_s": 88,
                    }
                }
            }

    monkeypatch.setattr(local_runner, "HAS_SERVICES", True)
    monkeypatch.setattr(local_runner, "SlotSelector", _Selector)

    timeout = local_runner.get_timeout_for(
        "codex",
        "test",
        {"level": "complex"},
    )

    assert timeout == 352


def test_get_timeout_for_falls_back_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Selector:
        def __init__(self, _scope: str) -> None:
            pass

        def stats(self, _providers: list[str]) -> dict[str, Any]:
            return {"slots": {"codex": {"p90_duration_s": 0}}}

    monkeypatch.setattr(local_runner, "HAS_SERVICES", True)
    monkeypatch.setattr(local_runner, "SlotSelector", _Selector)
    local_runner._TASK_TIMEOUT[0] = 345

    timeout = local_runner.get_timeout_for("codex", "test")

    assert timeout == 600  # test task_type defaults to 600 when no p90 data


def test_estimate_task_complexity_simple() -> None:
    task = {
        "id": "task-simple",
        "task_type": "review",
        "direction": "Review wording in docs.",
    }

    estimate = local_runner.estimate_task_complexity(task)

    assert estimate["level"] == "simple"
    assert estimate["timeout_multiplier"] == 2.0
    assert estimate["file_mentions"] == 0


def test_estimate_task_complexity_complex() -> None:
    task = {
        "id": "task-complex",
        "task_type": "impl",
        "direction": (
            "Update `api/scripts/local_runner.py` and `api/tests/test_local_runner.py`, "
            "then align `api/app/services/agent_service_crud.py` and "
            "`api/app/models/agent.py` with task complexity metadata for scheduling. "
            "Additionally, ensure all validation paths are covered by adding more "
            "robust error handling and logging throughout the implementation."
        ),
    }

    estimate = local_runner.estimate_task_complexity(task)

    assert estimate["level"] == "complex"
    assert estimate["timeout_multiplier"] == 4.0
    assert estimate["file_mentions"] >= 4


def test_run_one_stores_complexity_estimate_before_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    task = {
        "id": "task-cx-1",
        "task_type": "impl",
        "direction": "Implement changes in `api/scripts/local_runner.py` and `api/tests/test_local_runner.py`.",
    }
    patch_calls: list[tuple[str, str, dict[str, Any] | None]] = []
    completion: dict[str, Any] = {}

    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "claim_task", lambda _task_id: task | {"status": "running"})
    monkeypatch.setattr(local_runner, "select_provider", lambda _task_type, **_kw: "codex")
    monkeypatch.setattr(local_runner, "build_prompt", lambda _task: "prompt")
    _impl_output = (
        "Implementation complete. Modified api/scripts/local_runner.py to add idea_id at top "
        "level. FILES_CHANGED=api/scripts/local_runner.py COMMIT=abc1234 All tests passing."
    )
    monkeypatch.setattr(local_runner, "execute_with_provider", lambda *_args, **_kwargs: (True, _impl_output, 0.6))
    monkeypatch.setattr(local_runner, "record_provider_outcome", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(local_runner, "PROVIDERS", {"codex": {"cmd": ["codex"]}})

    class _GitStatus:
        def __init__(self, output: str) -> None:
            self.stdout = output
            self.returncode = 0

    monkeypatch.setattr(local_runner.subprocess, "run", lambda *_args, **_kwargs: _GitStatus(" M api/scripts/local_runner.py"))

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        patch_calls.append((method, path, body))
        if method == "PATCH" and path == "/api/agent/tasks/task-cx-1":
            return task | {"status": "running", "context": body.get("context") if body else {}}
        return None

    monkeypatch.setattr(local_runner, "api", _api)

    def _complete(task_id: str, output: str, success: bool, context_patch: dict[str, Any] | None = None) -> bool:
        completion["task_id"] = task_id
        completion["success"] = success
        completion["context_patch"] = context_patch
        return True

    monkeypatch.setattr(local_runner, "complete_task", _complete)

    ok = local_runner.run_one(task, dry_run=False)

    assert ok is True
    assert patch_calls[0][0] == "PATCH"
    assert patch_calls[0][1] == "/api/agent/tasks/task-cx-1"
    assert "complexity_estimate" in (patch_calls[0][2] or {}).get("context", {})
    assert completion["context_patch"]["complexity_estimate"]["level"] in {"simple", "complex"}


def test_run_one_timeout_saves_partial_patch_and_creates_resume_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    task = {
        "id": "task-timeout-1",
        "task_type": "impl",
        "direction": "Implement timeout handling.",
        "context": {"task_agent": "dev-engineer"},
    }
    completion: dict[str, Any] = {}

    monkeypatch.setattr(local_runner, "_LOG_DIR", tmp_path)
    monkeypatch.setattr(local_runner, "_RESUME_MODE", [True])
    monkeypatch.setattr(local_runner, "claim_task", lambda _task_id: task | {"status": "running"})
    monkeypatch.setattr(local_runner, "select_provider", lambda _task_type, **_kw: "codex")
    monkeypatch.setattr(local_runner, "build_prompt", lambda _task: "prompt")
    monkeypatch.setattr(
        local_runner,
        "execute_with_provider",
        lambda *_args, **_kwargs: (False, "TIMEOUT after 300s (limit=300s)", 300.0),
    )
    monkeypatch.setattr(local_runner, "record_provider_outcome", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(local_runner, "PROVIDERS", {"codex": {"cmd": ["codex"]}})

    status_calls = iter(
        [
            [],
            [" M api/scripts/local_runner.py"],
        ]
    )
    diff_calls = iter(
        [
            "",
            "diff --git a/api/scripts/local_runner.py b/api/scripts/local_runner.py\n+partial work\n",
            "diff --git a/api/scripts/local_runner.py b/api/scripts/local_runner.py\n+partial work\n",
        ]
    )
    monkeypatch.setattr(local_runner, "_git_status_lines", lambda: next(status_calls))
    monkeypatch.setattr(local_runner, "_git_diff_for_paths", lambda _paths=None: next(diff_calls))
    monkeypatch.setattr(local_runner, "_create_resume_task", lambda *_args, **_kwargs: "task-resume-1")

    def _complete_with_status(
        task_id: str,
        output: str,
        status: str,
        context_patch: dict[str, Any] | None = None,
        error_category: str = "execution_error",
    ) -> bool:
        completion["task_id"] = task_id
        completion["output"] = output
        completion["status"] = status
        completion["context_patch"] = context_patch
        completion["error_category"] = error_category
        return True

    monkeypatch.setattr(local_runner, "_complete_task_with_status", _complete_with_status)

    ok = local_runner.run_one(task, dry_run=False)

    assert ok is False
    assert completion["task_id"] == "task-timeout-1"
    assert completion["status"] == "timed_out"
    assert completion["error_category"] == "timeout"
    assert completion["context_patch"]["resume_task_id"] == "task-resume-1"
    assert completion["context_patch"]["partial_patch_path"]
    patch_path = tmp_path / "partial_task_task-timeout-1.patch"
    assert patch_path.exists()
    assert "partial work" in patch_path.read_text()


def test_build_prompt_includes_resume_patch_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_runner, "_RESUME_MODE", [True])
    prompt = local_runner.build_prompt(
        {
            "id": "task-resume-2",
            "task_type": "impl",
            "direction": "Continue implementation",
            "context": {
                "task_agent": "dev-engineer",
                "resume_patch_path": "api/logs/partial_task_task-timeout-1.patch",
            },
        }
    )

    assert "Resume context:" in prompt
    assert "api/logs/partial_task_task-timeout-1.patch" in prompt


def test_post_task_hook_enqueues_next_phase_and_sets_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        calls.append((method, path, body))
        if method == "GET" and path == "/api/ideas/idea-1/tasks":
            return {
                "idea_id": "idea-1",
                "groups": [
                    {
                        "task_type": "spec",
                        "count": 1,
                        "status_counts": {
                            "pending": 0,
                            "running": 0,
                            "completed": 1,
                            "failed": 0,
                            "needs_decision": 0,
                        },
                    }
                ],
            }
        if method == "GET" and path == "/api/ideas/idea-1":
            return {"id": "idea-1", "name": "Idea One"}
        if method == "POST" and path == "/api/agent/tasks":
            return {"id": "task-next-1"}
        if method == "PATCH" and path == "/api/ideas/idea-1":
            return {"id": "idea-1", "manifestation_status": "partial"}
        return None

    monkeypatch.setattr(local_runner, "api", _api)

    local_runner._run_phase_auto_advance_hook(
        {
            "id": "task-spec-1",
            "task_type": "spec",
            "context": {"idea_id": "idea-1"},
        }
    )

    assert ("GET", "/api/ideas/idea-1/tasks", None) in calls
    create_calls = [row for row in calls if row[0] == "POST" and row[1] == "/api/agent/tasks"]
    assert len(create_calls) == 1
    assert create_calls[0][2]["task_type"] == "impl"
    assert create_calls[0][2]["context"]["auto_phase_advance_source"] == "local_runner_post_task_hook"
    assert (
        "PATCH",
        "/api/ideas/idea-1",
        {"manifestation_status": "partial"},
    ) in calls


def test_post_task_hook_marks_validated_after_review_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _completed_group(task_type: str, count: int = 1) -> dict:
        return {
            "task_type": task_type,
            "count": count,
            "status_counts": {"pending": 0, "running": 0, "completed": count, "failed": 0, "needs_decision": 0},
        }

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        calls.append((method, path, body))
        if method == "GET" and path == "/api/ideas/idea-2/tasks":
            return {
                "idea_id": "idea-2",
                "groups": [
                    _completed_group("spec"),
                    _completed_group("impl"),
                    _completed_group("test"),
                    _completed_group("review", 2),
                ],
            }
        if method == "GET" and path == "/api/ideas/idea-2":
            return {"id": "idea-2", "name": "Test Idea", "interfaces": []}
        if method == "PATCH" and path == "/api/ideas/idea-2":
            return {"id": "idea-2", "manifestation_status": body.get("manifestation_status") if body else "partial"}
        return None

    monkeypatch.setattr(local_runner, "api", _api)

    local_runner._run_phase_auto_advance_hook(
        {
            "id": "task-review-1",
            "task_type": "review",
            "context": {"idea_id": "idea-2"},
        }
    )

    create_calls = [row for row in calls if row[0] == "POST" and row[1] == "/api/agent/tasks"]
    assert create_calls == []
    assert (
        "PATCH",
        "/api/ideas/idea-2",
        {"manifestation_status": "validated"},
    ) in calls


def test_seed_task_from_open_idea_sets_idea_id_at_top_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """_seed_task_from_open_idea must set idea_id at top level so /api/ideas/{id}/tasks works."""
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        calls.append((method, path, body))
        if method == "GET" and path == "/api/ideas?limit=200":
            return [{"id": "seed-idea-1", "name": "Seed Idea", "manifestation_status": "none", "free_energy_score": 0.8}]
        if method == "GET" and path.startswith("/api/agent/tasks?status="):
            return []
        if method == "GET" and path == "/api/ideas/seed-idea-1/tasks":
            return {"total": 0, "groups": []}
        if method == "POST" and path == "/api/agent/tasks":
            return {"id": "task-seed-created-1"}
        return None

    monkeypatch.setattr(local_runner, "api", _api)
    monkeypatch.setattr(local_runner, "_count_active_tasks", lambda: 0)
    monkeypatch.setattr(local_runner, "_SEEDER_SKIP_CACHE", set())

    result = local_runner._seed_task_from_open_idea()

    assert result is True
    create_calls = [row for row in calls if row[0] == "POST" and row[1] == "/api/agent/tasks"]
    assert len(create_calls) == 1
    payload = create_calls[0][2] or {}
    # Top-level idea_id is required so /api/ideas/{id}/tasks query links correctly
    assert payload.get("idea_id") == "seed-idea-1", (
        "idea_id must be at the top level of the task payload, not only in context"
    )
    # Also verify it's in context (for backwards compatibility)
    assert (payload.get("context") or {}).get("idea_id") == "seed-idea-1"


# ---------------------------------------------------------------------------
# _run_operational_phase — merge / deploy / verify / reflect
# ---------------------------------------------------------------------------


class _CompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_operational_phase_reflect_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"task_id": task_id, "output": output, "success": success}
        ) or True,
    )
    monkeypatch.setattr(local_runner, "_run_phase_auto_advance_hook", lambda _task: None)

    task = {"id": "task-reflect-1", "task_type": "reflect", "context": {"idea_id": "idea-42"}}
    ok = local_runner._run_operational_phase(task, "task-reflect-1", "reflect")

    assert ok is True
    assert len(completions) == 1
    assert "REFLECT_COMPLETE" in completions[0]["output"]
    assert "idea-42" in completions[0]["output"]
    assert completions[0]["success"] is True


def test_run_operational_phase_merge_no_open_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(
        local_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: _CompletedProcess(returncode=0, stdout="[]"),
    )
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"output": output, "success": success}
        ) or True,
    )
    monkeypatch.setattr(local_runner, "_run_phase_auto_advance_hook", lambda _task: None)

    task = {"id": "task-merge-1", "task_type": "merge", "context": {"idea_id": "idea-99"}}
    ok = local_runner._run_operational_phase(task, "task-merge-1", "merge")

    assert ok is True
    assert "MERGE_PASSED" in completions[0]["output"]
    assert "already on main" in completions[0]["output"]


def test_run_operational_phase_merge_with_open_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    completions: list[dict[str, Any]] = []
    calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: Any) -> _CompletedProcess:
        calls.append(args)
        if "list" in args:
            return _CompletedProcess(returncode=0, stdout='[{"number": 7, "title": "test"}]')
        # merge call
        return _CompletedProcess(returncode=0, stdout="merged")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"output": output, "success": success}
        ) or True,
    )
    monkeypatch.setattr(local_runner, "_run_phase_auto_advance_hook", lambda _task: None)

    task = {"id": "task-merge-2", "task_type": "merge", "context": {"idea_id": "idea-77"}}
    ok = local_runner._run_operational_phase(task, "task-merge-2", "merge")

    assert ok is True
    assert "MERGE_PASSED" in completions[0]["output"]
    assert "PR #7" in completions[0]["output"]
    merge_call = [c for c in calls if "merge" in c]
    assert any("7" in str(c) for c in merge_call)


def test_run_operational_phase_merge_gh_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    completions: list[dict[str, Any]] = []

    def _run(args: list[str], **_kwargs: Any) -> _CompletedProcess:
        if "list" in args:
            return _CompletedProcess(returncode=0, stdout='[{"number": 3, "title": "test"}]')
        return _CompletedProcess(returncode=1, stderr="GraphQL error: merge blocked")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"output": output, "success": success}
        ) or True,
    )
    monkeypatch.setattr(local_runner, "_run_phase_auto_advance_hook", lambda _task: None)

    task = {"id": "task-merge-3", "task_type": "merge", "context": {"idea_id": "idea-11"}}
    ok = local_runner._run_operational_phase(task, "task-merge-3", "merge")

    assert ok is False
    assert "MERGE_FAILED" in completions[0]["output"]
    assert completions[0]["success"] is False


def test_run_operational_phase_deploy_no_ssh_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    completions: list[dict[str, Any]] = []

    monkeypatch.setattr(local_runner.os.path, "exists", lambda _p: False)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"output": output, "success": success}
        ) or True,
    )
    monkeypatch.setattr(local_runner, "_run_phase_auto_advance_hook", lambda _task: None)

    task = {"id": "task-deploy-1", "task_type": "deploy", "context": {"idea_id": "idea-88"}}
    ok = local_runner._run_operational_phase(task, "task-deploy-1", "deploy")

    assert ok is False
    assert "DEPLOY_SKIPPED" in completions[0]["output"]
    assert completions[0]["success"] is False


def test_run_operational_phase_exception_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    completions: list[dict[str, Any]] = []

    def _run(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(local_runner.subprocess, "run", _run)
    monkeypatch.setattr(
        local_runner,
        "complete_task",
        lambda task_id, output, success, context_patch=None: completions.append(
            {"output": output, "success": success}
        ) or True,
    )

    task = {"id": "task-exc-1", "task_type": "merge", "context": {"idea_id": "idea-0"}}
    ok = local_runner._run_operational_phase(task, "task-exc-1", "merge")

    assert ok is False
    assert "MERGE_FAILED" in completions[0]["output"]
    assert "network unreachable" in completions[0]["output"]


def test_run_one_dispatches_operational_phase_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    operational_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(local_runner, "claim_task", lambda _task_id: {"id": "task-op-1", "task_type": "reflect", "status": "running", "context": {"idea_id": "idea-x"}})
    monkeypatch.setattr(
        local_runner,
        "_run_operational_phase",
        lambda task, task_id, task_type: operational_calls.append((task["id"], task_id, task_type)) or True,
    )

    task = {"id": "task-op-1", "task_type": "reflect", "context": {"idea_id": "idea-x"}}
    ok = local_runner.run_one(task, dry_run=False)

    assert ok is True
    assert len(operational_calls) == 1
    assert operational_calls[0][2] == "reflect"


def test_create_worktree_recovers_when_slot_still_occupied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stale worktree + branch from a prior run must not block a second create (impl retry)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "f").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "f"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "i"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "fetch", "origin"], check=True, capture_output=True)

    wt_base = repo / ".worktrees"
    monkeypatch.setattr(local_runner, "_REPO_DIR", repo)
    monkeypatch.setattr(local_runner, "_WORKTREE_BASE", wt_base)

    tid = "task_staleworktree9"
    first = local_runner._create_worktree(tid)
    assert first is not None
    assert first.exists()
    # No cleanup — same state as "branch push failed, worktree kept"
    second = local_runner._create_worktree(tid)
    assert second is not None
    assert second.exists()
