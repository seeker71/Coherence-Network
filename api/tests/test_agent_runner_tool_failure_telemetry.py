from __future__ import annotations

import io
import os
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
    payload: dict | None = None

    def json(self):
        return self.payload or {}


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
        assert any(
            url.endswith("/api/agent/tasks/task_test") and patch.get("status") == "failed"
            for url, patch in client.patches
        )
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


def test_infer_executor_detects_clawwork_alias():
    assert agent_runner._infer_executor('clawwork run "task"', "clawwork/model") == "openclaw"


def test_prepare_non_root_execution_for_command_enables_demote_on_root(monkeypatch):
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        agent_runner,
        "_resolve_non_root_exec_user",
        lambda preferred: ("runner", 1001, 1001, "/home/runner"),
    )
    env = {"PATH": "/usr/bin"}
    ok, detail, preexec = agent_runner._prepare_non_root_execution_for_command(
        command='claude -p "smoke" --dangerously-skip-permissions',
        env=env,
    )
    assert ok is True
    assert detail == "runner_non_root_exec_user:runner:1001:1001"
    assert callable(preexec)
    assert env["HOME"] == "/home/runner"
    assert env["USER"] == "runner"
    assert env["LOGNAME"] == "runner"
    assert env["PATH"].startswith("/home/runner/.local/bin:")


def test_prepare_non_root_execution_for_command_filters_root_paths(monkeypatch):
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        agent_runner,
        "_resolve_non_root_exec_user",
        lambda preferred: ("runner", 1001, 1001, "/home/runner"),
    )
    env = {"PATH": "/root/.local/bin:/usr/local/bin:/usr/bin"}
    ok, detail, preexec = agent_runner._prepare_non_root_execution_for_command(
        command='claude -p "smoke" --dangerously-skip-permissions',
        env=env,
    )
    assert ok is True
    assert detail == "runner_non_root_exec_user:runner:1001:1001"
    assert callable(preexec)
    assert "/root/.local/bin" not in env["PATH"]


def test_prepare_non_root_execution_for_command_noop_when_not_root(monkeypatch):
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 1000)
    env = {"PATH": "/usr/bin"}
    ok, detail, preexec = agent_runner._prepare_non_root_execution_for_command(
        command='claude -p "smoke" --dangerously-skip-permissions',
        env=env,
    )
    assert ok is True
    assert detail == ""
    assert preexec is None


def test_prepare_non_root_execution_for_command_fails_when_no_user(monkeypatch):
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        agent_runner,
        "_resolve_non_root_exec_user",
        lambda preferred: ("", -1, -1, ""),
    )
    env = {"PATH": "/usr/bin"}
    ok, detail, preexec = agent_runner._prepare_non_root_execution_for_command(
        command='claude -p "smoke" --dangerously-skip-permissions',
        env=env,
    )
    assert ok is False
    assert detail == "runner_non_root_user_unavailable"
    assert preexec is None


def test_cli_install_provider_for_command_detects_supported_providers():
    assert agent_runner._cli_install_provider_for_command('agent "run" --model auto') == "cursor"
    assert agent_runner._cli_install_provider_for_command('claude -p "run"') == "claude"
    assert agent_runner._cli_install_provider_for_command('codex exec "run" --json') == "codex"
    assert agent_runner._cli_install_provider_for_command("pytest -q") == ""


def test_ensure_cli_for_command_installs_cursor_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI", "1")
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI_IN_TESTS", "1")
    monkeypatch.setenv("AGENT_RUNNER_CURSOR_INSTALL_COMMANDS", "echo install-cursor")

    install_state = {"installed": False}

    def _which(binary: str, path: str | None = None):
        if binary == "agent" and install_state["installed"]:
            return str(tmp_path / "bin" / "agent")
        return None

    def _run_install(command: str, *, env: dict[str, str], timeout_seconds: int):
        assert "install-cursor" in command
        install_state["installed"] = True
        return True, "installed"

    monkeypatch.setattr(agent_runner.shutil, "which", _which)
    monkeypatch.setattr(agent_runner, "_run_cli_install_command", _run_install)

    env = {"PATH": "/usr/bin", "HOME": str(tmp_path)}
    ok, detail = agent_runner._ensure_cli_for_command(
        command='agent "smoke" --model auto',
        env=env,
        task_id="task_cursor_install",
        log=agent_runner._setup_logging(verbose=False),
    )
    assert ok is True
    assert detail.startswith("runner_cli_install_ok:cursor:agent:")
    assert str(tmp_path / "bin") in env["PATH"]


def test_ensure_cli_for_command_skips_install_when_cli_present(monkeypatch):
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI", "1")
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI_IN_TESTS", "1")
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda binary, path=None: "/usr/local/bin/claude" if binary == "claude" else None,
    )
    install_called = {"value": False}

    def _run_install(command: str, *, env: dict[str, str], timeout_seconds: int):
        install_called["value"] = True
        return True, "unexpected"

    monkeypatch.setattr(agent_runner, "_run_cli_install_command", _run_install)

    env = {"PATH": "/usr/bin:/usr/local/bin"}
    ok, detail = agent_runner._ensure_cli_for_command(
        command='claude -p "smoke"',
        env=env,
        task_id="task_claude_present",
        log=agent_runner._setup_logging(verbose=False),
    )
    assert ok is True
    assert detail.startswith("runner_cli_present:claude:claude:")
    assert install_called["value"] is False


def test_default_runtime_seconds_for_task_type_uses_defaults_and_env_bounds(monkeypatch):
    monkeypatch.delenv("AGENT_TASK_TIMEOUT_SPEC", raising=False)
    monkeypatch.setattr(agent_runner, "TASK_TIMEOUT", 3600)
    assert agent_runner._default_runtime_seconds_for_task_type("spec") == 1200

    monkeypatch.setenv("AGENT_TASK_TIMEOUT_SPEC", "90")
    assert agent_runner._default_runtime_seconds_for_task_type("spec") == 90

    monkeypatch.setenv("AGENT_TASK_TIMEOUT_SPEC", "99999")
    assert agent_runner._default_runtime_seconds_for_task_type("spec") == 3600


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


def test_apply_codex_model_alias_enforces_mandatory_remap_over_env_override(monkeypatch):
    monkeypatch.setenv("AGENT_CODEX_MODEL_ALIAS_MAP", "gpt-5.3-codex:gpt-5.3-codex")
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."'
    )
    assert alias == {
        "requested_model": "gpt-5.3-codex",
        "effective_model": "gpt-5-codex",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model gpt-5.3-codex" not in remapped


def test_apply_codex_model_alias_supports_gtp_typo_default_map():
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model gtp-5.3-codex "Output exactly MODEL_OK."'
    )
    assert alias == {
        "requested_model": "gtp-5.3-codex",
        "effective_model": "gpt-5-codex",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model gtp-5.3-codex" not in remapped


def test_apply_codex_model_alias_remaps_openrouter_free_default_map():
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model openrouter/free "Output exactly MODEL_OK."'
    )
    assert alias == {
        "requested_model": "openrouter/free",
        "effective_model": "gpt-5-codex",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model openrouter/free" not in remapped


def test_apply_codex_model_alias_merges_defaults_with_partial_env_map(monkeypatch):
    monkeypatch.setenv("AGENT_CODEX_MODEL_ALIAS_MAP", "gpt-5.3-codex:gpt-5-codex")
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model gtp-5.3-codex "Output exactly MODEL_OK."'
    )
    assert alias == {
        "requested_model": "gtp-5.3-codex",
        "effective_model": "gpt-5-codex",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model gtp-5.3-codex" not in remapped


def test_codex_model_not_found_fallback_only_applies_after_not_found_signal():
    command = 'codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."'
    output = "stream disconnected before completion: The model `gpt-5.3-codex` does not exist or you do not have access to it."

    remapped, alias = agent_runner._codex_model_not_found_fallback(command, output)
    assert alias == {
        "requested_model": "gpt-5.3-codex",
        "effective_model": "gpt-5-codex",
        "trigger": "model_not_found_or_access",
    }
    assert "--model gpt-5-codex" in remapped
    assert "--model gpt-5.3-codex" not in remapped

    unchanged, alias_none = agent_runner._codex_model_not_found_fallback(
        command,
        "command failed for unrelated reason",
    )
    assert alias_none is None
    assert unchanged == command


def test_run_one_task_schedules_model_not_found_fallback_retry(monkeypatch, tmp_path):
    t = [4500.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:test-runner")
    monkeypatch.delenv("AGENT_CODEX_MODEL_ALIAS_MAP", raising=False)
    monkeypatch.delenv("AGENT_CODEX_MODEL_NOT_FOUND_FALLBACK_MAP", raising=False)
    # Force model-not-found path to exercise retry fallback logic (bypass default alias remap).
    monkeypatch.setattr(agent_runner, "MANDATORY_CODEX_MODEL_ALIAS_MAP", {})
    monkeypatch.setattr(agent_runner, "_codex_model_alias_map", lambda: {})

    def _popen(*args, **kwargs):
        return _Proc(
            returncode=1,
            stdout_text=(
                "stream disconnected before completion: "
                "The model `gpt-5.3-codex` does not exist or you do not have access to it.\n"
            ),
        )

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_model_fallback",
        command='codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5.3-codex",
    )
    assert done is True

    pending_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_model_fallback") and patch.get("status") == "pending"
    )
    failed_patches = [
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_model_fallback") and patch.get("status") == "failed"
    ]
    assert failed_patches == []
    context = pending_patch.get("context") or {}
    assert "retry_override_command" in context
    assert "--model gpt-5-codex" in context["retry_override_command"]
    assert context.get("runner_model_not_found_fallback_attempted") is True
    fallback = context.get("runner_model_not_found_fallback") or {}
    assert fallback.get("requested_model") == "gpt-5.3-codex"
    assert fallback.get("effective_model") == "gpt-5-codex"
    assert fallback.get("trigger") == "model_not_found_or_access"
    assert "runner-model-fallback" in str(pending_patch.get("output") or "")


def test_configure_codex_cli_environment_uses_oauth_mode_and_strips_api_env(monkeypatch, tmp_path):
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", "0")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "admin-test")

    env = {
        "OPENAI_API_KEY": "sk-test",
        "OPENAI_ADMIN_API_KEY": "admin-test",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session"] is True
    assert auth["oauth_missing"] is False
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env


def test_configure_codex_cli_environment_defaults_oauth_fallback_on(monkeypatch, tmp_path):
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.delenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", raising=False)
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    env = {
        "OPENAI_API_KEY": "sk-test",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_default_fallback",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_fallback_allowed"] is True
    assert env.get("OPENAI_API_KEY") == "sk-test"
    assert env.get("OPENAI_API_BASE") == "https://api.openai.com/v1"


def test_configure_codex_cli_environment_oauth_without_api_key_strips_openai_env(monkeypatch, tmp_path):
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.delenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", raising=False)
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_ADMIN_API_KEY", raising=False)

    env = {
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_oauth_no_api_key",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_fallback_allowed"] is True
    assert auth["api_key_present"] is False
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env


def test_configure_codex_cli_environment_api_key_mode_isolates_home(monkeypatch, tmp_path):
    class _Completed:
        returncode = 1
        stdout = ""
        stderr = ""

    real_home = tmp_path / "real-home"
    auth_dir = real_home / ".codex"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "auth.json").write_text('{"token":"oauth"}', encoding="utf-8")

    monkeypatch.setenv("HOME", str(real_home))
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "api_key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENT_CODEX_OAUTH_SESSION_FILE", raising=False)
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda name: "/usr/local/bin/codex" if name == "codex" else None,
    )
    monkeypatch.setattr(agent_runner.subprocess, "run", lambda *args, **kwargs: _Completed())

    env = {"HOME": str(real_home)}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_api_key_home",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "api_key"
    assert auth["effective_mode"] == "api_key"
    assert auth["oauth_session"] is False
    assert auth["oauth_fallback_allowed"] is True
    assert env.get("AGENT_CODEX_OAUTH_SESSION_FILE") == ""
    assert "agent-runner-codex-api-key" in str(env.get("HOME") or "")
    assert "agent-runner-codex-api-key" in str(env.get("CODEX_HOME") or "")
    assert str(env.get("HOME") or "").startswith(str(real_home))


def test_configure_codex_cli_environment_bootstraps_api_key_login(monkeypatch, tmp_path):
    class _Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    real_home = tmp_path / "real-home"
    real_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(real_home))
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "api_key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENT_CODEX_OAUTH_SESSION_FILE", raising=False)

    calls: list[list[str]] = []
    state = {"logged_in": False}

    def _run(argv, *args, **kwargs):
        cmd = [str(part) for part in (argv or [])]
        calls.append(cmd)
        if cmd[:3] == ["codex", "login", "--with-api-key"]:
            state["logged_in"] = True
            return _Completed(0, stdout="Successfully logged in\n")
        if cmd[:3] == ["codex", "login", "status"]:
            if state["logged_in"]:
                return _Completed(0, stdout="Logged in using an API key\n")
            return _Completed(1, stderr="Not logged in\n")
        if cmd[:3] == ["codex", "auth", "status"]:
            return _Completed(1, stderr="unknown command\n")
        return _Completed(1, stderr="unexpected command\n")

    monkeypatch.setattr(agent_runner.subprocess, "run", _run)

    env = {"HOME": str(real_home)}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_api_key_bootstrap",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["effective_mode"] == "api_key"
    assert auth["api_key_present"] is True
    assert auth["api_key_login_bootstrapped"] is True
    assert auth["api_key_login_source"] == "codex_login_with_api_key"
    assert auth["oauth_session"] is True
    assert env.get("OPENAI_API_KEY") == "sk-test"
    assert ["codex", "login", "--with-api-key"] in calls


def test_configure_codex_cli_environment_uses_admin_key_when_primary_missing(monkeypatch):
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "api_key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "admin-only-key")

    env: dict[str, str] = {}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_admin_key_fallback",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["effective_mode"] == "api_key"
    assert auth["api_key_present"] is True
    assert env.get("OPENAI_API_KEY") == "admin-only-key"


def test_configure_codex_cli_environment_overrides_blank_api_key_env(monkeypatch):
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "api_key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-non-empty")

    env = {
        "OPENAI_API_KEY": "",
        "OPENAI_API_BASE": "",
        "OPENAI_BASE_URL": "",
    }
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_blank_api_key_env",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["effective_mode"] == "api_key"
    assert auth["api_key_present"] is True
    assert env.get("OPENAI_API_KEY") == "sk-non-empty"
    assert env.get("OPENAI_API_BASE") == "https://api.openai.com/v1"
    assert env.get("OPENAI_BASE_URL") == "https://api.openai.com/v1"


def test_configure_codex_cli_environment_respects_task_auth_override(monkeypatch, tmp_path):
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", "0")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "admin-test")

    env = {
        "OPENAI_API_KEY": "sk-test",
        "OPENAI_ADMIN_API_KEY": "admin-test",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_override",
        log=agent_runner._setup_logging(verbose=False),
        task_ctx={"runner_codex_auth_mode": "api_key"},
    )

    assert auth["requested_mode"] == "api_key"
    assert auth["effective_mode"] == "api_key"
    assert auth["api_key_present"] is True
    assert env.get("OPENAI_API_KEY") == "sk-test"
    assert env.get("OPENAI_API_BASE") == "https://api.openai.com/v1"


def test_run_one_task_schedules_codex_oauth_refresh_token_fallback_retry(monkeypatch, tmp_path):
    t = [5200.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", "0")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:oauth-fallback-runner")

    failure_output = (
        'ERROR codex_core::auth: Failed to refresh token: 401 Unauthorized: {"error":{"code":"refresh_token_reused"}}\n'
        "Your refresh token has already been used to generate a new access token.\n"
    )

    def _popen(*args, **kwargs):
        return _Proc(returncode=1, stdout_text=failure_output)

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_oauth_refresh_reused",
        command='codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5.3-codex",
    )
    assert done is True

    pending_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_oauth_refresh_reused") and patch.get("status") == "pending"
    )
    failed_patches = [
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_oauth_refresh_reused") and patch.get("status") == "failed"
    ]
    assert failed_patches == []
    context = pending_patch.get("context") or {}
    assert context.get("runner_codex_auth_mode") == "api_key"
    assert context.get("runner_codex_auth_fallback_attempted") is True
    auth_fallback = context.get("runner_codex_auth_fallback") or {}
    assert auth_fallback.get("trigger") == "oauth_refresh_token_reused"
    assert auth_fallback.get("to_mode") == "api_key"
    assert "runner-codex-auth-fallback" in str(pending_patch.get("output") or "")


def test_run_one_task_executes_codex_via_argv_to_avoid_shell_expansion(monkeypatch, tmp_path):
    t = [6100.0]
    popen_calls: list[dict[str, object]] = []

    def _mono():
        t[0] += 0.25
        return t[0]

    def _popen(*args, **kwargs):
        popen_calls.append(
            {
                "command": args[0],
                "shell": kwargs.get("shell"),
            }
        )
        return _Proc(returncode=0, stdout_text="OK\n")

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "api_key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_codex_argv",
        command='codex exec "RUN `echo risky` literal text"',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5.3-codex",
    )
    assert done is True
    assert popen_calls
    codex_call = next(call for call in popen_calls if isinstance(call.get("command"), list))
    assert not bool(codex_call.get("shell"))
    assert isinstance(codex_call["command"], list)


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


def test_run_one_task_records_codex_oauth_auth_context_and_log(monkeypatch, tmp_path):
    t = [5000.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_ALLOW_API_KEY_FALLBACK", "0")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:oauth-runner")

    popen_env: dict[str, str] = {}

    def _popen(*args, **kwargs):
        env = kwargs.get("env") or {}
        if isinstance(env, dict):
            popen_env.update(env)
        return _Proc(returncode=0, stdout_text="MODEL_OK\n")

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_oauth",
        command='codex exec --model gpt-5-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5-codex",
    )
    assert done is True

    assert popen_env.get("OPENAI_API_KEY", "") == ""

    running_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_oauth") and patch.get("status") == "running"
    )
    context = running_patch.get("context") or {}
    auth = context.get("runner_codex_auth") or {}
    assert auth.get("requested_mode") == "oauth"
    assert auth.get("effective_mode") == "oauth"
    assert auth.get("oauth_session") is True
    assert auth.get("oauth_fallback_allowed") is False
    assert auth.get("oauth_missing") is False

    log_file = tmp_path / "task_task_oauth.log"
    body = log_file.read_text(encoding="utf-8")
    assert "runner-codex-auth" in body
    assert "effective_mode=oauth" in body


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


def test_append_agent_manifest_entry_includes_code_references(monkeypatch, tmp_path):
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
        task_id="task_manifest_ref",
        task_type="impl",
        task_direction="Add provenance with code references",
        task_ctx={
            "task_agent": "dev-engineer",
            "code_references": [
                {
                    "url": "https://github.com/example/public-repo/blob/main/demo.py",
                    "license": "MIT",
                }
            ],
        },
        repo_path=str(tmp_path),
        executor="openai-codex",
    )

    manifest = payload.get("agent_manifest") or {}
    assert manifest.get("code_refs")
    doc_path = Path(str(manifest.get("doc_path") or ""))
    body = doc_path.read_text(encoding="utf-8")
    assert "Code references" in body
    assert "MIT" in body


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


def test_auto_generate_tasks_when_idle_creates_spec_gap_tasks(monkeypatch, tmp_path):
    calls: list[tuple[str, str, dict | None]] = []

    def _fake_http(client, method, url, log, **kwargs):
        params = kwargs.get("params")
        calls.append((method.upper(), url, params if isinstance(params, dict) else None))
        if method.upper() == "GET" and url.endswith("/api/agent/tasks"):
            return _Resp(200, {"total": 0, "tasks": []})
        if method.upper() == "POST" and url.endswith("/api/inventory/specs/sync-implementation-tasks"):
            return _Resp(200, {"created_count": 2})
        return _Resp(500, {})

    monkeypatch.setattr(agent_runner, "_http_with_retry", _fake_http)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASKS", True)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASK_LIMIT", 25)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(agent_runner, "_last_idle_task_generation_ts", 0.0)
    monkeypatch.setattr(agent_runner.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))

    created = agent_runner._auto_generate_tasks_when_idle(client=object(), log=agent_runner._setup_logging())
    assert created == 2
    assert any(
        call[0] == "POST" and call[1].endswith("/api/inventory/specs/sync-implementation-tasks")
        for call in calls
    )
    assert not any(
        call[0] == "POST" and call[1].endswith("/api/inventory/flow/next-unblock-task")
        for call in calls
    )


def test_auto_generate_tasks_when_idle_falls_back_to_flow_task_generation(monkeypatch, tmp_path):
    calls: list[tuple[str, str, dict | None]] = []

    def _fake_http(client, method, url, log, **kwargs):
        params = kwargs.get("params")
        calls.append((method.upper(), url, params if isinstance(params, dict) else None))
        if method.upper() == "GET" and url.endswith("/api/agent/tasks"):
            return _Resp(200, {"total": 0, "tasks": []})
        if method.upper() == "POST" and url.endswith("/api/inventory/specs/sync-implementation-tasks"):
            return _Resp(200, {"created_count": 0})
        if method.upper() == "POST" and url.endswith("/api/inventory/flow/next-unblock-task"):
            return _Resp(
                200,
                {
                    "result": "task_suggested",
                    "created_task": {"id": "task_flow_fallback", "task_type": "spec"},
                },
            )
        return _Resp(500, {})

    monkeypatch.setattr(agent_runner, "_http_with_retry", _fake_http)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASKS", True)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASK_LIMIT", 25)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(agent_runner, "_last_idle_task_generation_ts", 0.0)
    monkeypatch.setattr(agent_runner.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))

    created = agent_runner._auto_generate_tasks_when_idle(client=object(), log=agent_runner._setup_logging())
    assert created == 1
    assert any(
        call[0] == "POST" and call[1].endswith("/api/inventory/specs/sync-implementation-tasks")
        for call in calls
    )
    assert any(
        call[0] == "POST" and call[1].endswith("/api/inventory/flow/next-unblock-task")
        for call in calls
    )


def test_ensure_repo_checkout_accepts_git_marker_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").write_text("gitdir: /tmp/example\n", encoding="utf-8")

    ok = agent_runner._ensure_repo_checkout(str(repo), log=agent_runner._setup_logging())
    assert ok is True


def test_resolve_repo_path_for_execution_uses_fallback_clone_path(monkeypatch, tmp_path):
    primary = tmp_path / "app"
    primary.mkdir(parents=True, exist_ok=True)
    (primary / "README.md").write_text("not a git checkout\n", encoding="utf-8")
    fallback = (tmp_path / "runner-fallback").resolve()

    calls: list[str] = []

    def _fake_ensure(repo_path: str, *, log):
        calls.append(repo_path)
        os.makedirs(repo_path, exist_ok=True)
        (Path(repo_path) / ".git").mkdir(exist_ok=True)
        return True

    monkeypatch.setattr(agent_runner, "REPO_FALLBACK_PATH", str(fallback))
    monkeypatch.setattr(agent_runner, "_ensure_repo_checkout", _fake_ensure)

    resolved = agent_runner._resolve_repo_path_for_execution(str(primary), log=agent_runner._setup_logging())
    assert resolved == str(fallback)
    assert calls == [str(fallback)]


def test_auto_generate_tasks_when_idle_skips_when_open_tasks_exist(monkeypatch, tmp_path):
    calls: list[tuple[str, str, dict | None]] = []

    def _fake_http(client, method, url, log, **kwargs):
        params = kwargs.get("params")
        calls.append((method.upper(), url, params if isinstance(params, dict) else None))
        if method.upper() == "GET" and url.endswith("/api/agent/tasks"):
            status = str((params or {}).get("status") or "")
            if status == "pending":
                return _Resp(200, {"total": 1, "tasks": [{"id": "task_existing"}]})
            return _Resp(200, {"total": 0, "tasks": []})
        return _Resp(500, {})

    monkeypatch.setattr(agent_runner, "_http_with_retry", _fake_http)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASKS", True)
    monkeypatch.setattr(agent_runner, "AUTO_GENERATE_IDLE_TASK_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(agent_runner, "_last_idle_task_generation_ts", 0.0)
    monkeypatch.setattr(agent_runner.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))

    created = agent_runner._auto_generate_tasks_when_idle(client=object(), log=agent_runner._setup_logging())
    assert created == 0
    assert not any(
        call[0] == "POST" and call[1].endswith("/api/inventory/specs/sync-implementation-tasks")
        for call in calls
    )
