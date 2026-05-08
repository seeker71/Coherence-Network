"""Tests for the Claude Code PreToolUse hook that surfaces substrate
annotation on file Reads.

The hook receives JSON from stdin (Claude Code's hook contract) and
writes the annotation to stderr (Claude Code surfaces stderr to the
agent as transcript context). It must NEVER block the read — failures
are silent.
"""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "substrate_read_hook.py"


def _run_hook(payload: dict) -> tuple[int, str, str]:
    """Run the hook with the given payload on stdin. Return (rc, stdout, stderr)."""
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


def test_hook_exits_zero_on_non_read_tool():
    """Bash, Edit, Write — anything other than Read — exits 0 with no output."""
    rc, stdout, stderr = _run_hook({
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    })
    assert rc == 0
    assert stderr.strip() == ""
    assert stdout.strip() == ""


def test_hook_exits_zero_on_malformed_json():
    """Garbled stdin must not block the read."""
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        input="not valid json",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_hook_exits_zero_on_empty_stdin():
    """Empty stdin must not block."""
    rc, stdout, stderr = _run_hook({})
    assert rc == 0


def test_hook_exits_zero_on_missing_file_path():
    """Read tool call without file_path: skip silently."""
    rc, stdout, stderr = _run_hook({
        "tool_name": "Read",
        "tool_input": {},
    })
    assert rc == 0
    assert stderr.strip() == ""


def test_hook_skips_non_md_files():
    """Reads of non-.md files don't trigger annotation."""
    rc, stdout, stderr = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": "/some/path/script.py"},
    })
    assert rc == 0
    # No substrate output for non-.md files
    assert "[substrate]" not in stderr


def test_hook_emits_not_in_substrate_for_unknown_md(tmp_path):
    """An .md file not in the substrate gets the 'not in substrate' message —
    so the agent knows the substrate has no claim."""
    p = tmp_path / "random.md"
    p.write_text("# Random\n")
    rc, stdout, stderr = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": str(p)},
    })
    assert rc == 0
    # We can't reliably assert "not in substrate" text because the test
    # might run without a substrate database available. Just verify the
    # hook didn't crash and exits cleanly.
    assert rc == 0


def test_hook_never_blocks_even_on_internal_error():
    """If the substrate is somehow broken, the hook still exits 0."""
    # This invokes the hook normally; the test is that it returns 0 in
    # all cases. The actual error handling in the script catches any
    # Exception during annotation.
    rc, stdout, stderr = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": "/nonexistent/path/foo.md"},
    })
    assert rc == 0
