"""Tests for auto-commit workflow (spec 030).

Validates commit_progress.py behavior: git add/commit/push, no-op when no changes,
proper commit message format, and integration with agent_runner.py.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the commit_progress module
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_api_dir, "scripts"))

from commit_progress import commit_progress


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

        yield repo_path


def test_commit_progress_commits_changes(temp_git_repo):
    """commit_progress should create commit when there are changes."""
    # Create a file change
    (temp_git_repo / "test.txt").write_text("Hello world")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        result = commit_progress(
            task_id="task_abc123",
            task_type="impl",
            message="Add test file",
            push=False,
        )

    assert result is True

    # Verify commit was created
    log_output = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=temp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[pipeline] impl task_abc123: Add test file" in log_output.stdout


def test_commit_progress_no_changes(temp_git_repo):
    """commit_progress should return True and skip commit when no changes."""
    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        result = commit_progress(
            task_id="task_xyz789",
            task_type="test",
            message="No changes",
            push=False,
        )

    assert result is True

    # Verify no new commit
    log_output = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=temp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "task_xyz789" not in log_output.stdout


def test_commit_progress_not_git_repo():
    """commit_progress should return True and skip when not a git repo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("commit_progress.PROJECT_ROOT", str(tmpdir)):
            result = commit_progress(
                task_id="task_def456",
                task_type="spec",
                message="Not a repo",
                push=False,
            )

        assert result is True


def test_commit_progress_message_format(temp_git_repo):
    """Commit message should follow format: [pipeline] {task_type} {task_id}: {message}."""
    (temp_git_repo / "feature.py").write_text("def foo(): pass")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        commit_progress(
            task_id="task_msg_test",
            task_type="review",
            message="Review code quality",
            push=False,
        )

    log_output = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=temp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert log_output.stdout.strip() == "[pipeline] review task_msg_test: Review code quality"


def test_commit_progress_message_sanitization(temp_git_repo):
    """Commit message should sanitize newlines and limit length."""
    (temp_git_repo / "long.txt").write_text("content")

    long_message = "Line 1\nLine 2\nLine 3\n" + ("x" * 300)

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        commit_progress(
            task_id="task_sanitize",
            task_type="impl",
            message=long_message,
            push=False,
        )

    log_output = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=temp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    msg = log_output.stdout.strip()

    # Should not contain newlines
    assert "\n" not in msg
    # Should be limited in length (200 chars for message + prefix)
    assert len(msg) <= 250


def test_commit_progress_with_push(temp_git_repo):
    """commit_progress with push=True should attempt git push."""
    (temp_git_repo / "push_test.txt").write_text("push me")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        with patch("commit_progress.run") as mock_run:
            # Mock git status
            mock_run.side_effect = [
                (True, "M push_test.txt"),  # git status --porcelain
                (True, ""),  # git add
                (True, ""),  # git commit
                (True, ""),  # git push
            ]

            result = commit_progress(
                task_id="task_push",
                task_type="impl",
                message="Test push",
                push=True,
            )

    assert result is True
    # Verify git push was called
    calls = [str(call) for call in mock_run.call_args_list]
    assert any("push" in str(call) for call in calls)


def test_commit_progress_push_failure(temp_git_repo):
    """commit_progress should return False if push fails."""
    (temp_git_repo / "fail_push.txt").write_text("fail push")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        with patch("commit_progress.run") as mock_run:
            # Mock git commands, push fails
            mock_run.side_effect = [
                (True, "M fail_push.txt"),  # git status
                (True, ""),  # git add
                (True, ""),  # git commit
                (False, "fatal: no upstream branch"),  # git push fails
            ]

            result = commit_progress(
                task_id="task_fail_push",
                task_type="impl",
                message="Push should fail",
                push=True,
            )

    assert result is False


def test_commit_progress_git_add_failure(temp_git_repo):
    """commit_progress should return False if git add fails."""
    (temp_git_repo / "bad_add.txt").write_text("bad add")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        with patch("commit_progress.run") as mock_run:
            mock_run.side_effect = [
                (True, "M bad_add.txt"),  # git status
                (False, "fatal: pathspec error"),  # git add fails
            ]

            result = commit_progress(
                task_id="task_bad_add",
                task_type="impl",
                message="Add should fail",
                push=False,
            )

    assert result is False


def test_commit_progress_empty_message(temp_git_repo):
    """commit_progress should use default message when message is empty."""
    (temp_git_repo / "empty_msg.txt").write_text("content")

    with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
        commit_progress(
            task_id="task_empty_msg",
            task_type="test",
            message="",
            push=False,
        )

    log_output = subprocess.run(
        ["git", "log", "--format=%s", "-1"],
        cwd=temp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    msg = log_output.stdout.strip()
    assert "pipeline progress" in msg or "task_empty_msg" in msg


def test_commit_progress_task_types(temp_git_repo):
    """commit_progress should work with all task types (spec, test, impl, review)."""
    task_types = ["spec", "test", "impl", "review"]

    for i, task_type in enumerate(task_types):
        (temp_git_repo / f"file_{i}.txt").write_text(f"Task type: {task_type}")

        with patch("commit_progress.PROJECT_ROOT", str(temp_git_repo)):
            result = commit_progress(
                task_id=f"task_{task_type}",
                task_type=task_type,
                message=f"Test {task_type}",
                push=False,
            )

        assert result is True

        # Verify commit message includes task type
        log_output = subprocess.run(
            ["git", "log", "--format=%s", "-1"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert f"[pipeline] {task_type}" in log_output.stdout


def test_agent_runner_integration():
    """Test that agent_runner._try_commit calls commit_progress.py correctly."""
    # This test verifies the integration point in agent_runner.py
    import sys
    import os

    agent_runner_path = os.path.join(_api_dir, "scripts", "agent_runner.py")
    with open(agent_runner_path, "r") as f:
        content = f.read()

    # Verify _try_commit function exists
    assert "def _try_commit" in content

    # Verify it calls commit_progress.py
    assert "commit_progress.py" in content

    # Verify it passes task_id and task_type
    assert "--task-id" in content
    assert "--task-type" in content

    # Verify it respects PIPELINE_AUTO_PUSH
    assert 'PIPELINE_AUTO_PUSH' in content

    # Verify it's called after completed tasks
    assert 'if status == "completed"' in content or 'status == "completed"' in content


def test_agent_runner_auto_commit_env_var():
    """Test that agent_runner only commits when PIPELINE_AUTO_COMMIT=1."""
    import os

    agent_runner_path = os.path.join(_api_dir, "scripts", "agent_runner.py")
    with open(agent_runner_path, "r") as f:
        content = f.read()

    # Verify PIPELINE_AUTO_COMMIT env var is checked
    assert 'PIPELINE_AUTO_COMMIT' in content

    # Verify it checks for "1" value
    assert '"1"' in content or "'1'" in content


def test_agent_runner_skips_heal_tasks():
    """Test that agent_runner does not auto-commit for heal tasks."""
    agent_runner_path = os.path.join(_api_dir, "scripts", "agent_runner.py")
    with open(agent_runner_path, "r") as f:
        content = f.read()

    # Verify heal tasks are excluded
    assert 'task_type != "heal"' in content or '!= "heal"' in content
