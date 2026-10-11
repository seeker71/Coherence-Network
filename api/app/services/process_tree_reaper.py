"""Bounded process-tree termination for native Form carriers."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import Any

_STEP_TIMEOUT_SECONDS = 2.0
_FINAL_WAIT_SECONDS = 0.25
# Two Windows tree attempts, root collection, and the final direct-kill wait.
PROCESS_TREE_REAP_BUDGET_SECONDS = 3 * _STEP_TIMEOUT_SECONDS + _FINAL_WAIT_SECONDS


class ProcessTreeReapError(RuntimeError):
    """A carrier root exited without proof that every descendant exited."""


def _windows_tree_kill(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_STEP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def reap_process_tree(process: Any) -> None:
    """Terminate a carrier tree within the exported wall-clock budget."""
    tree_reaped = True
    root_reaped = True
    if sys.platform == "win32":
        # Retry while the root still identifies its children. A direct root kill
        # cannot establish that descendants exited, so that path fails closed.
        tree_reaped = _windows_tree_kill(process.pid) or _windows_tree_kill(process.pid)
        if not tree_reaped:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=_STEP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=_FINAL_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            root_reaped = False
    if not tree_reaped or not root_reaped:
        raise ProcessTreeReapError(
            "native Form process-tree termination was not confirmed"
        )
