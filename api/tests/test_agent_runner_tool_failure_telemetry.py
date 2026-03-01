from __future__ import annotations

import base64
import io
import json
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
    assert agent_runner._infer_executor('openclaw run "task"', "openclaw/model") == "codex"


def test_infer_executor_detects_clawwork_alias():
    assert agent_runner._infer_executor('clawwork run "task"', "clawwork/model") == "codex"


def test_infer_executor_detects_openrouter_model():
    assert agent_runner._infer_executor('echo "task"', "openrouter/free") == "openrouter"


def test_run_one_task_dispatches_openrouter_server_executor(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_WORKER_ID", "runner:test")

    called: dict[str, object] = {}

    def _fake_dispatch(*, client, task_id, task_ctx, task_type, worker_id, log):
        called["task_id"] = task_id
        called["task_type"] = task_type
        called["worker_id"] = worker_id
        called["executor"] = str(task_ctx.get("executor") or "")
        return True

    monkeypatch.setattr(agent_runner, "_dispatch_openrouter_server_executor", _fake_dispatch)
    monkeypatch.setattr(
        agent_runner.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess should not run for openrouter executor")),
    )

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_openrouter_dispatch",
        command='openrouter-exec "run" --model openrouter/free',
        log=log,
        verbose=False,
        task_type="impl",
        model="openrouter/free",
        task_context={"executor": "openrouter"},
    )
    assert done is True
    assert called == {
        "task_id": "task_openrouter_dispatch",
        "task_type": "impl",
        "worker_id": "runner:test",
        "executor": "openrouter",
    }


def test_run_one_task_cursor_oauth_mode_strips_api_key_env(monkeypatch, tmp_path):
    t = [1200.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    captured_env: dict[str, str] = {}

    def _popen(*args, **kwargs):
        env = kwargs.get("env") or {}
        captured_env.clear()
        captured_env.update({str(k): str(v) for k, v in env.items()})
        return _Proc(returncode=0, stdout_text='{"result":"ok"}\n')

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setenv("CURSOR_API_KEY", "cursor-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "openai-admin-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)
    done = agent_runner.run_one_task(
        client=client,
        task_id="task_cursor_oauth_mode",
        command='agent "Return ok" --model auto',
        log=log,
        verbose=False,
        task_type="impl",
        model="cursor/auto",
        task_context={"runner_cursor_auth_mode": "oauth"},
    )
    assert done is True
    assert captured_env.get("CURSOR_API_KEY", "") == ""
    assert captured_env.get("OPENAI_API_KEY", "") == ""
    assert captured_env.get("OPENAI_ADMIN_API_KEY", "") == ""
    assert captured_env.get("OPENAI_API_BASE", "") == ""
    assert captured_env.get("OPENAI_BASE_URL", "") == ""


def test_run_one_task_claude_oauth_mode_strips_api_key_env(monkeypatch, tmp_path):
    t = [1400.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    captured_env: dict[str, str] = {}

    def _popen(*args, **kwargs):
        env = kwargs.get("env") or {}
        captured_env.clear()
        captured_env.update({str(k): str(v) for k, v in env.items()})
        return _Proc(returncode=0, stdout_text='{"result":"ok"}\n')

    session_payload = {
        "accessToken": "access-token-value",
        "refreshToken": "refresh-token-value",
    }
    encoded = base64.b64encode(json.dumps(session_payload).encode("utf-8")).decode("utf-8")

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key-should-not-be-used")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "anthropic-auth-should-not-be-used")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token-should-not-be-used")
    monkeypatch.setenv("AGENT_CLAUDE_OAUTH_SESSION_B64", encoded)

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)
    done = agent_runner.run_one_task(
        client=client,
        task_id="task_claude_oauth_mode",
        command='claude -p "ok" --dangerously-skip-permissions',
        log=log,
        verbose=False,
        task_type="impl",
        model="claude/sonnet",
        task_context={"runner_claude_auth_mode": "oauth", "runner_claude_oauth_session_b64": encoded},
    )
    assert done is True
    assert captured_env.get("ANTHROPIC_API_KEY", "") == ""
    assert captured_env.get("ANTHROPIC_AUTH_TOKEN", "") == ""
    assert captured_env.get("CLAUDE_CODE_OAUTH_TOKEN", "") == ""
    assert captured_env.get("CLAUDE_CONFIG_DIR", "") != ""


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


def test_resolve_non_root_exec_user_skips_low_uid_candidates(monkeypatch):
    class _PwdRow:
        def __init__(self, name: str, uid: int, gid: int, home: str, shell: str):
            self.pw_name = name
            self.pw_uid = uid
            self.pw_gid = gid
            self.pw_dir = home
            self.pw_shell = shell

    monkeypatch.setenv("AGENT_RUN_AS_USER_FALLBACKS", "runner,app")
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_DISCOVER", "0")
    monkeypatch.setattr(agent_runner.os.path, "isdir", lambda path: path in {"/home/runner", "/home/app"})
    fake_accounts = type("FakeAccounts", (), {})()
    monkeypatch.setattr(agent_runner, "pwd", fake_accounts)

    def _getpwnam(name: str):
        if name == "runner":
            return _PwdRow("runner", 500, 500, "/home/runner", "/bin/bash")
        if name == "app":
            return _PwdRow("app", 1001, 1001, "/home/app", "/bin/bash")
        raise KeyError(name)

    monkeypatch.setattr(fake_accounts, "getpwnam", _getpwnam, raising=False)
    user, uid, gid, home = agent_runner._resolve_non_root_exec_user("")
    assert user == "app"
    assert uid == 1001
    assert gid == 1001
    assert home == "/home/app"


def test_resolve_non_root_exec_user_auto_discover_skips_system_users(monkeypatch):
    class _PwdRow:
        def __init__(self, name: str, uid: int, gid: int, home: str, shell: str):
            self.pw_name = name
            self.pw_uid = uid
            self.pw_gid = gid
            self.pw_dir = home
            self.pw_shell = shell

    monkeypatch.setenv("AGENT_RUN_AS_USER_FALLBACKS", "")
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_DISCOVER", "1")
    monkeypatch.setattr(agent_runner.os.path, "isdir", lambda path: path in {"/bin", "/home/app"})
    fake_accounts = type("FakeAccounts", (), {})()
    monkeypatch.setattr(agent_runner, "pwd", fake_accounts)
    monkeypatch.setattr(fake_accounts, "getpwnam", lambda name: (_ for _ in ()).throw(KeyError(name)), raising=False)
    monkeypatch.setattr(
        fake_accounts,
        "getpwall",
        lambda: [
            _PwdRow("sync", 4, 65534, "/bin", "/bin/sync"),
            _PwdRow("app", 1001, 1001, "/home/app", "/bin/bash"),
        ],
        raising=False,
    )

    user, uid, gid, home = agent_runner._resolve_non_root_exec_user("")
    assert user == "app"
    assert uid == 1001
    assert gid == 1001
    assert home == "/home/app"


def test_auto_create_non_root_exec_user_creates_account_when_missing(monkeypatch):
    class _PwdRow:
        def __init__(self, name: str, uid: int, gid: int, home: str):
            self.pw_name = name
            self.pw_uid = uid
            self.pw_gid = gid
            self.pw_dir = home

    state = {"created": False}
    fake_accounts = type("FakeAccounts", (), {})()
    monkeypatch.setattr(agent_runner, "pwd", fake_accounts)

    def _getpwnam(name: str):
        if name == "runner" and state["created"]:
            return _PwdRow("runner", 1001, 1001, "/home/runner")
        raise KeyError(name)

    monkeypatch.setattr(fake_accounts, "getpwnam", _getpwnam, raising=False)
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 0)
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_CREATE", "1")
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_CREATE_USER", "runner")
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_CREATE_UID", "1001")
    monkeypatch.setattr(agent_runner.os.path, "isdir", lambda path: path == "/home/runner")
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda binary: "/usr/sbin/useradd" if binary == "useradd" else None,
    )

    class _RunResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def _run(argv, **kwargs):
        assert argv[0] == "useradd"
        state["created"] = True
        return _RunResult()

    monkeypatch.setattr(agent_runner.subprocess, "run", _run)

    user, uid, gid, home = agent_runner._auto_create_non_root_exec_user(min_uid=1000)
    assert user == "runner"
    assert uid == 1001
    assert gid == 1001
    assert home == "/home/runner"


def test_resolve_non_root_exec_user_uses_auto_create_when_discovery_off(monkeypatch):
    monkeypatch.setenv("AGENT_RUN_AS_USER_FALLBACKS", "")
    monkeypatch.setenv("AGENT_RUN_AS_AUTO_DISCOVER", "0")
    monkeypatch.setattr(
        agent_runner,
        "_auto_create_non_root_exec_user",
        lambda *, min_uid, preferred_user="": ("runner", 1001, 1001, "/home/runner"),
    )
    user, uid, gid, home = agent_runner._resolve_non_root_exec_user("")
    assert user == "runner"
    assert uid == 1001
    assert gid == 1001
    assert home == "/home/runner"


def test_cli_install_provider_for_command_detects_supported_providers():
    assert agent_runner._cli_install_provider_for_command('agent "run" --model auto') == "cursor"
    assert agent_runner._cli_install_provider_for_command('claude -p "run"') == "claude"
    assert agent_runner._cli_install_provider_for_command('codex exec "run" --json') == "codex"
    assert agent_runner._cli_install_provider_for_command("pytest -q") == ""


def test_ensure_cli_for_command_installs_cursor_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI", "1")
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI_IN_TESTS", "1")
    monkeypatch.setenv("AGENT_RUNNER_CURSOR_INSTALL_COMMANDS", "echo install-cursor")
    monkeypatch.setattr(
        agent_runner,
        "_ensure_cursor_node_shim",
        lambda *, env, cursor_binary="": (True, "cursor_node_shim_created:/usr/local/bin/node->/usr/bin/node"),
    )

    install_state = {"installed": False}

    agent_bin = tmp_path / "bin" / "agent"
    runtime_node = tmp_path / "bin" / "node"
    runtime_index = tmp_path / "bin" / "index.js"

    def _which(binary: str, path: str | None = None):
        if binary == "agent" and install_state["installed"]:
            return str(agent_bin)
        return None

    def _run_install(command: str, *, env: dict[str, str], timeout_seconds: int):
        assert "install-cursor" in command
        install_state["installed"] = True
        agent_bin.parent.mkdir(parents=True, exist_ok=True)
        agent_bin.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        runtime_node.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        runtime_index.write_text("console.log('ok')\n", encoding="utf-8")
        agent_bin.chmod(0o755)
        runtime_node.chmod(0o755)
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


def test_ensure_cli_for_command_does_not_promote_cursor_binary_when_root(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI", "1")
    monkeypatch.setenv("AGENT_RUNNER_AUTO_INSTALL_CLI_IN_TESTS", "1")
    monkeypatch.setattr(agent_runner.os, "geteuid", lambda: 0)
    cursor_home = tmp_path / "cursor-home"
    runtime_dir = cursor_home / ".local" / "bin"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    agent_bin = runtime_dir / "agent"
    runtime_node = runtime_dir / "node"
    runtime_index = runtime_dir / "index.js"
    agent_bin.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    runtime_node.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    runtime_index.write_text("console.log('ok')\n", encoding="utf-8")
    agent_bin.chmod(0o755)
    runtime_node.chmod(0o755)
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda binary, path=None: str(agent_bin) if binary == "agent" else None,
    )
    monkeypatch.setattr(
        agent_runner,
        "_ensure_cursor_node_shim",
        lambda *, env, cursor_binary="": (True, "cursor_node_shim_present:/root/.local/bin/node"),
    )
    promote_called = {"value": False}

    def _promote(binary: str, source_path: str):
        promote_called["value"] = True
        return "/usr/local/bin/agent"

    monkeypatch.setattr(agent_runner, "_promote_binary_to_shared_path", _promote)

    env = {"PATH": f"/usr/bin:{runtime_dir}", "HOME": str(cursor_home)}
    ok, detail = agent_runner._ensure_cli_for_command(
        command='agent "smoke" --model auto',
        env=env,
        task_id="task_cursor_no_promote",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert ok is True
    assert promote_called["value"] is False
    assert str(agent_bin) in detail
    assert "/usr/local/bin/agent" not in detail


def test_resolve_node_binary_prefers_non_shim_candidate(monkeypatch):
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda binary, path=None: "/mise/shims/node" if binary == "node" else None,
    )
    monkeypatch.setattr(
        agent_runner.os.path,
        "isfile",
        lambda path: path in {"/usr/local/bin/node", "/bin/node", "/mise/shims/node"},
    )
    monkeypatch.setattr(
        agent_runner.os,
        "access",
        lambda path, mode: path in {"/usr/local/bin/node", "/bin/node", "/mise/shims/node"},
    )
    monkeypatch.setattr(
        agent_runner.os.path,
        "realpath",
        lambda path: "/mise/shims/node" if path in {"/usr/local/bin/node", "/mise/shims/node"} else path,
    )

    resolved = agent_runner._resolve_node_binary({"PATH": "/mise/shims:/usr/local/bin:/bin"})
    assert resolved == "/bin/node"


def test_resolve_node_binary_falls_back_to_shim_when_no_concrete_binary(monkeypatch):
    monkeypatch.setattr(
        agent_runner.shutil,
        "which",
        lambda binary, path=None: "/mise/shims/node" if binary == "node" else None,
    )
    monkeypatch.setattr(
        agent_runner.os.path,
        "isfile",
        lambda path: path == "/mise/shims/node",
    )
    monkeypatch.setattr(
        agent_runner.os,
        "access",
        lambda path, mode: path == "/mise/shims/node",
    )
    monkeypatch.setattr(agent_runner.os.path, "realpath", lambda path: path)

    resolved = agent_runner._resolve_node_binary({"PATH": "/mise/shims"})
    assert resolved == "/mise/shims/node"


def test_ensure_cursor_node_shim_writes_compat_wrapper_when_node_lacks_use_system_ca(monkeypatch, tmp_path):
    shim_path = tmp_path / "node"
    monkeypatch.setenv("AGENT_RUNNER_CURSOR_NODE_SHIM_PATH", str(shim_path))
    monkeypatch.setattr(agent_runner, "_resolve_node_binary", lambda env: "/usr/bin/node")
    monkeypatch.setattr(
        agent_runner,
        "_node_binary_accepts_use_system_ca",
        lambda binary, *, env: binary == str(shim_path),
    )

    ok, detail = agent_runner._ensure_cursor_node_shim(env={"PATH": "/usr/bin"}, cursor_binary="")

    assert ok is True
    assert detail.startswith("cursor_node_shim_created_compat:")
    assert shim_path.exists()
    content = shim_path.read_text(encoding="utf-8")
    assert "--use-system-ca" in content
    assert "exec /usr/bin/node \"$@\"" in content
    assert os.access(shim_path, os.X_OK)


def test_cursor_node_shim_path_uses_realpath_target(monkeypatch):
    monkeypatch.delenv("AGENT_RUNNER_CURSOR_NODE_SHIM_PATH", raising=False)
    monkeypatch.setattr(
        agent_runner.os.path,
        "realpath",
        lambda path: "/usr/local/bin/agent" if path == "/usr/bin/agent" else path,
    )
    shim_path = agent_runner._cursor_node_shim_path(cursor_binary="/usr/bin/agent")
    assert shim_path == "/usr/local/bin/node"


def test_resolve_cursor_cli_binary_prefers_path_with_runtime_layout(monkeypatch, tmp_path):
    bad_dir = tmp_path / "bad"
    good_dir = tmp_path / "good"
    bad_dir.mkdir(parents=True, exist_ok=True)
    good_dir.mkdir(parents=True, exist_ok=True)

    bad_agent = bad_dir / "agent"
    good_agent = good_dir / "agent"
    good_node = good_dir / "node"
    good_index = good_dir / "index.js"

    bad_agent.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    good_agent.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    good_node.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    good_index.write_text("console.log('ok')\n", encoding="utf-8")
    bad_agent.chmod(0o755)
    good_agent.chmod(0o755)
    good_node.chmod(0o755)

    monkeypatch.setattr(agent_runner, "_candidate_cli_paths", lambda binary, env: [str(bad_agent), str(good_agent)])
    monkeypatch.setattr(agent_runner.shutil, "which", lambda binary, path=None: str(bad_agent))

    resolved, layout_ok, layout_detail = agent_runner._resolve_cursor_cli_binary("agent", {"PATH": str(bad_dir)})
    assert resolved == str(good_agent)
    assert layout_ok is True
    assert layout_detail.startswith("cursor_runtime_layout_ok:")


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


def test_apply_codex_model_alias_does_not_remap_openrouter_free_by_default():
    remapped, alias = agent_runner._apply_codex_model_alias(
        'codex exec --model openrouter/free "Output exactly MODEL_OK."'
    )
    assert alias is None
    assert "--model openrouter/free" in remapped


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


def test_apply_claude_model_alias_strips_provider_prefix():
    remapped, alias = agent_runner._apply_claude_model_alias(
        'claude -p "smoke" --model claude/claude-sonnet-4-5-20250929 --output-format json'
    )
    assert alias == {
        "requested_model": "claude/claude-sonnet-4-5-20250929",
        "effective_model": "claude-sonnet-4-5-20250929",
    }
    assert "--model claude-sonnet-4-5-20250929" in remapped
    assert "--model claude/claude-sonnet-4-5-20250929" not in remapped


def test_apply_claude_model_alias_noop_for_already_normalized_model():
    command = 'claude -p "smoke" --model claude-sonnet-4-5-20250929 --output-format json'
    remapped, alias = agent_runner._apply_claude_model_alias(command)
    assert alias is None
    assert remapped == command


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


def test_run_one_task_skips_codex_auth_retry_when_retry_explicitly_disabled(monkeypatch, tmp_path):
    t = [5200.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:test-runner")

    def _popen(*args, **kwargs):
        return _Proc(
            returncode=1,
            stdout_text=(
                "ERROR codex_core::auth: Failed to refresh token: 401 Unauthorized\\n"
                "refresh_token_reused\\n"
            ),
        )

    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setattr(
        agent_runner,
        "_configure_codex_cli_environment",
        lambda **kwargs: {
            "requested_mode": "oauth",
            "effective_mode": "oauth",
            "oauth_session": True,
            "oauth_source": "session_file:/tmp/codex-auth.json",
            "api_key_present": False,
            "oauth_missing": False,
        },
    )
    monkeypatch.setattr(agent_runner, "_attempt_codex_oauth_relogin", lambda **kwargs: (False, "mock_relogin_failed"))
    monkeypatch.setattr(
        agent_runner,
        "_attempt_codex_oauth_session_refresh_from_env",
        lambda **kwargs: (False, "mock_session_refresh_failed"),
    )

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)
    done = agent_runner.run_one_task(
        client=client,
        task_id="task_auth_retry_disabled",
        command='codex exec --model gpt-5-codex "Output exactly AUTH_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5-codex",
        task_context={"retry_max": 0},
    )
    assert done is True

    pending_patches = [
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_auth_retry_disabled") and patch.get("status") == "pending"
    ]
    assert pending_patches == []
    failed_patches = [
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_auth_retry_disabled") and patch.get("status") == "failed"
    ]
    assert failed_patches
    output = str(failed_patches[-1].get("output") or "")
    assert "retry disabled by explicit retry_max=0" in output


def test_retry_explicitly_disabled_ignores_null_values():
    assert agent_runner._retry_explicitly_disabled({"retry_max": None}) is False
    assert agent_runner._retry_explicitly_disabled({"runner_retry_max": ""}) is False
    assert agent_runner._retry_explicitly_disabled({"max_retries": "  "}) is False
    assert agent_runner._retry_explicitly_disabled({"retry_max": 0}) is True


def test_configure_cursor_cli_environment_bootstraps_oauth_session_from_b64(monkeypatch, tmp_path):
    session_payload = {
        "accessToken": "cursor-access-token",
        "refreshToken": "cursor-refresh-token",
        "apiKey": "should-be-removed",
    }
    encoded = base64.b64encode(json.dumps(session_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CURSOR_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CURSOR_OAUTH_SESSION_B64", encoded)
    monkeypatch.delenv("AGENT_CURSOR_OAUTH_SESSION_FILE", raising=False)

    env = {
        "HOME": str(tmp_path),
        "CURSOR_API_KEY": "cursor-key",
        "OPENAI_API_KEY": "openai-key",
        "OPENAI_ADMIN_API_KEY": "openai-admin-key",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
    }
    auth = agent_runner._configure_cursor_cli_environment(
        env=env,
        task_id="task_cursor_auth_bootstrap_b64",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session_bootstrapped"] is True
    assert auth["oauth_session"] is True
    assert str(auth.get("oauth_session_bootstrap_detail") or "").startswith("oauth_session_bootstrapped:")
    assert "CURSOR_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env
    target = env.get("AGENT_CURSOR_OAUTH_SESSION_FILE") or ""
    assert target.endswith("/.config/cagent/auth.json")
    assert env.get("CURSOR_CONFIG_DIR") == str(Path(target).parent)
    loaded = json.loads(Path(target).read_text(encoding="utf-8"))
    assert loaded.get("refreshToken") == "cursor-refresh-token"
    assert loaded.get("accessToken") == "cursor-access-token"
    assert "apiKey" not in loaded


def test_configure_claude_cli_environment_bootstraps_oauth_session_from_b64(monkeypatch, tmp_path):
    session_payload = {
        "accessToken": "claude-access-token",
        "refreshToken": "claude-refresh-token",
        "apiKey": "should-be-removed",
    }
    encoded = base64.b64encode(json.dumps(session_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CLAUDE_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CLAUDE_OAUTH_SESSION_B64", encoded)
    monkeypatch.delenv("AGENT_CLAUDE_OAUTH_SESSION_FILE", raising=False)

    env = {
        "HOME": str(tmp_path),
        "ANTHROPIC_API_KEY": "anthropic-key",
        "ANTHROPIC_AUTH_TOKEN": "anthropic-auth",
        "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
        "CLAUDE_CODE_OAUTH_TOKEN": "short-lived-token",
    }
    auth = agent_runner._configure_claude_cli_environment(
        env=env,
        task_id="task_claude_auth_bootstrap_b64",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session_bootstrapped"] is True
    assert auth["oauth_session"] is True
    assert str(auth.get("oauth_session_bootstrap_detail") or "").startswith("oauth_session_bootstrapped:")
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "ANTHROPIC_BASE_URL" not in env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env
    target = env.get("AGENT_CLAUDE_OAUTH_SESSION_FILE") or ""
    assert target.endswith("/.claude/.credentials.json")
    assert env.get("CLAUDE_CONFIG_DIR") == str(Path(target).parent)
    loaded = json.loads(Path(target).read_text(encoding="utf-8"))
    assert loaded.get("refreshToken") == "claude-refresh-token"
    assert loaded.get("accessToken") == "claude-access-token"
    assert "apiKey" not in loaded


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


def test_configure_codex_cli_environment_bootstraps_oauth_session_from_b64(monkeypatch, tmp_path):
    session_payload = {
        "access_token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "account_id": "acct-test",
    }
    encoded = base64.b64encode(json.dumps(session_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_B64", encoded)
    monkeypatch.delenv("AGENT_CODEX_OAUTH_SESSION_FILE", raising=False)

    env = {"HOME": str(tmp_path)}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_bootstrap_b64",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session_bootstrapped"] is True
    bootstrap_detail = str(auth.get("oauth_session_bootstrap_detail") or "")
    assert bootstrap_detail.startswith("oauth_session_bootstrapped:")
    target = env.get("AGENT_CODEX_OAUTH_SESSION_FILE") or ""
    assert target.endswith("/.codex/auth.json")
    loaded = json.loads(Path(target).read_text(encoding="utf-8"))
    assert loaded.get("refresh_token") == "refresh-token-value"
    assert loaded.get("access_token") == "access-token-value"


def test_configure_codex_cli_environment_bootstraps_oauth_session_from_nested_b64_tokens(monkeypatch, tmp_path):
    session_payload = {
        "auth_mode": "oauth",
        "last_refresh": {"at": "2026-02-28T10:00:00Z"},
        "tokens": {
            "chatgpt": {
                "access_token": "nested-access-token",
                "refresh_token": "nested-refresh-token",
            }
        },
    }
    encoded = base64.b64encode(json.dumps(session_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_B64", encoded)
    monkeypatch.delenv("AGENT_CODEX_OAUTH_SESSION_FILE", raising=False)

    env = {"HOME": str(tmp_path)}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_bootstrap_nested_b64",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session_bootstrapped"] is True
    target = env.get("AGENT_CODEX_OAUTH_SESSION_FILE") or ""
    loaded = json.loads(Path(target).read_text(encoding="utf-8"))
    assert loaded.get("refresh_token") == "nested-refresh-token"
    assert loaded.get("access_token") == "nested-access-token"


def test_configure_codex_cli_environment_preserves_existing_oauth_session_when_b64_present(monkeypatch, tmp_path):
    existing_payload = {
        "access_token": "existing-access-token",
        "refresh_token": "existing-refresh-token",
        "auth_mode": "oauth",
    }
    target = tmp_path / ".codex" / "auth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(existing_payload), encoding="utf-8")

    incoming_payload = {
        "access_token": "incoming-access-token",
        "refresh_token": "incoming-refresh-token",
        "auth_mode": "oauth",
    }
    encoded = base64.b64encode(json.dumps(incoming_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_B64", encoded)
    monkeypatch.delenv("AGENT_CODEX_OAUTH_SESSION_FILE", raising=False)

    env = {"HOME": str(tmp_path)}
    auth = agent_runner._configure_codex_cli_environment(
        env=env,
        task_id="task_auth_preserve_existing_session",
        log=agent_runner._setup_logging(verbose=False),
    )

    assert auth["effective_mode"] == "oauth"
    assert auth["oauth_session"] is True
    assert auth["oauth_session_bootstrapped"] is False
    assert str(auth.get("oauth_session_bootstrap_detail") or "").startswith("oauth_session_preserved_existing:")
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded.get("refresh_token") == "existing-refresh-token"
    assert loaded.get("access_token") == "existing-access-token"


def test_bootstrap_codex_oauth_session_overwrites_existing_when_requested(monkeypatch, tmp_path):
    existing_payload = {
        "access_token": "existing-access-token",
        "refresh_token": "existing-refresh-token",
        "auth_mode": "oauth",
    }
    incoming_payload = {
        "access_token": "incoming-access-token",
        "refresh_token": "incoming-refresh-token",
        "auth_mode": "oauth",
    }
    target = tmp_path / ".codex" / "auth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(existing_payload), encoding="utf-8")
    encoded = base64.b64encode(json.dumps(incoming_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_B64", encoded)

    env = {"HOME": str(tmp_path), "AGENT_CODEX_OAUTH_SESSION_FILE": str(target)}
    refreshed, detail = agent_runner._bootstrap_codex_oauth_session_from_env(
        env=env,
        task_id="task_auth_overwrite_existing_session",
        log=agent_runner._setup_logging(verbose=False),
        overwrite_existing=True,
    )

    assert refreshed is True
    assert detail.startswith("oauth_session_overwritten:")
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded.get("refresh_token") == "incoming-refresh-token"
    assert loaded.get("access_token") == "incoming-access-token"


def test_configure_codex_cli_environment_defaults_oauth_fallback_off(monkeypatch, tmp_path):
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
    assert auth["oauth_fallback_allowed"] is False
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env


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
    assert auth["oauth_fallback_allowed"] is False
    assert auth["api_key_present"] is False
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env


def test_configure_codex_cli_environment_ignores_non_oauth_task_auth_override(monkeypatch, tmp_path):
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
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

    assert auth["requested_mode"] == "oauth"
    assert auth["effective_mode"] == "oauth"
    assert auth["api_key_present"] is False
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_ADMIN_API_KEY" not in env
    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_BASE_URL" not in env


def test_run_one_task_schedules_oauth_retry_on_refresh_token_reused_without_api_key_fallback(monkeypatch, tmp_path):
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
    context = pending_patch.get("context") or {}
    assert context.get("runner_codex_auth_mode") == "oauth"
    assert context.get("runner_codex_oauth_refresh_retry_attempted") is True
    retry_meta = context.get("runner_codex_oauth_refresh_retry") or {}
    assert retry_meta.get("trigger") == "oauth_refresh_token_reused"
    assert retry_meta.get("mode") == "oauth"
    assert context.get("runner_codex_auth_fallback_attempted") is not True
    assert (context.get("runner_codex_auth_fallback") or {}) == {}
    assert "retrying with oauth auth mode" in str(pending_patch.get("output") or "")


def test_run_one_task_schedules_oauth_retry_when_retry_max_is_null(monkeypatch, tmp_path):
    t = [5220.0]

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
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:oauth-null-retry-runner")

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
        task_id="task_oauth_retry_null_retry_max",
        command='codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5.3-codex",
        task_context={"retry_max": None},
    )
    assert done is True

    pending_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_oauth_retry_null_retry_max") and patch.get("status") == "pending"
    )
    context = pending_patch.get("context") or {}
    assert context.get("runner_codex_oauth_refresh_retry_attempted") is True
    assert int(context.get("runner_retry_max") or 0) >= 1
    assert "retrying with oauth auth mode" in str(pending_patch.get("output") or "")


def test_run_one_task_refresh_token_reuse_recovers_oauth_session_from_b64(monkeypatch, tmp_path):
    t = [5300.0]

    def _mono():
        t[0] += 0.25
        return t[0]

    monkeypatch.setattr(agent_runner.time, "monotonic", _mono)
    monkeypatch.setattr(agent_runner, "LOG_DIR", str(tmp_path))
    session_file = tmp_path / ".codex" / "auth.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps({"access_token": "stale-access", "refresh_token": "stale-refresh", "auth_mode": "oauth"}),
        encoding="utf-8",
    )
    new_session_payload = {
        "access_token": "fresh-access",
        "refresh_token": "fresh-refresh",
        "auth_mode": "oauth",
    }
    encoded = base64.b64encode(json.dumps(new_session_payload).encode("utf-8")).decode("utf-8")
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_B64", encoded)
    monkeypatch.setenv("AGENT_WORKER_ID", "openai-codex:oauth-refresh-runner")

    relogin_calls = {"count": 0}

    def _relogin(*, env, task_id, log):
        relogin_calls["count"] += 1
        return True, "oauth_relogin_called"

    monkeypatch.setattr(agent_runner, "_attempt_codex_oauth_relogin", _relogin)

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
        task_id="task_oauth_refresh_reused_with_b64",
        command='codex exec --model gpt-5.3-codex "Output exactly MODEL_OK."',
        log=log,
        verbose=False,
        task_type="impl",
        model="openclaw/gpt-5.3-codex",
    )
    assert done is True
    assert relogin_calls["count"] == 0

    pending_patch = next(
        patch
        for url, patch in client.patches
        if url.endswith("/api/agent/tasks/task_oauth_refresh_reused_with_b64") and patch.get("status") == "pending"
    )
    context = pending_patch.get("context") or {}
    refresh_meta = context.get("runner_codex_oauth_session_refresh") or {}
    assert context.get("runner_codex_auth_mode") == "oauth"
    assert context.get("runner_codex_oauth_session_refresh_attempted") is True
    assert refresh_meta.get("ok") is True
    assert str(refresh_meta.get("detail") or "").startswith("oauth_session_overwritten:")
    loaded = json.loads(session_file.read_text(encoding="utf-8"))
    assert loaded.get("refresh_token") == "fresh-refresh"
    assert loaded.get("access_token") == "fresh-access"


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
    session_file = tmp_path / "codex-auth.json"
    session_file.write_text('{"token":"test"}', encoding="utf-8")
    monkeypatch.setattr(agent_runner.subprocess, "Popen", _popen)
    monkeypatch.setenv("AGENT_CODEX_AUTH_MODE", "oauth")
    monkeypatch.setenv("AGENT_CODEX_OAUTH_SESSION_FILE", str(session_file))

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


def test_run_one_task_executes_cursor_via_argv_to_avoid_shell_expansion(monkeypatch, tmp_path):
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
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    client = _Client()
    log = agent_runner._setup_logging(verbose=False)

    done = agent_runner.run_one_task(
        client=client,
        task_id="task_cursor_argv",
        command='agent "RUN `echo risky` literal text" --model auto',
        log=log,
        verbose=False,
        task_type="impl",
        model="cursor/auto",
    )
    assert done is True
    assert popen_calls
    cursor_call = next(
        call
        for call in popen_calls
        if isinstance(call.get("command"), list) and "risky" in " ".join(str(part) for part in call["command"])
    )
    assert not bool(cursor_call.get("shell"))
    assert isinstance(cursor_call["command"], list)
    assert "RUN `echo risky` literal text" in str(cursor_call["command"])


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
