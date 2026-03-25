#!/usr/bin/env python3
"""Executor handoff: interactive sessions take over from background runner.

Architecture:
- One active executor at a time on each machine
- Interactive session (Claude Code, Codex) takes priority over background runner
- Lock file at ~/.coherence-network/executor.lock tracks who's active
- Background runner checks lock on each poll cycle — pauses if interactive is active
- When interactive exits, it releases the lock — runner auto-resumes

Usage:
  # Interactive session takes over:
  python scripts/executor_handoff.py acquire --session-id "claude-code-12345"

  # Interactive session releases:
  python scripts/executor_handoff.py release

  # Check who's active:
  python scripts/executor_handoff.py status

  # Background runner checks before executing:
  python scripts/executor_handoff.py check  # exits 0 if runner can proceed, 1 if paused
"""

import json
import os
import sys
import time
from pathlib import Path

LOCK_DIR = Path.home() / ".coherence-network"
LOCK_FILE = LOCK_DIR / "executor.lock"
HEARTBEAT_STALE_SECONDS = 300  # 5 min without heartbeat = stale lock


def _read_lock() -> dict | None:
    if not LOCK_FILE.exists():
        return None
    try:
        data = json.loads(LOCK_FILE.read_text())
        return data
    except Exception:
        return None


def _write_lock(data: dict) -> None:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(data, indent=2))


def _is_stale(lock: dict) -> bool:
    """Lock is stale if heartbeat is older than threshold."""
    last_heartbeat = lock.get("heartbeat", 0)
    return (time.time() - last_heartbeat) > HEARTBEAT_STALE_SECONDS


def _is_pid_alive(pid: int) -> bool:
    """Check if a process is still running. Cross-platform (macOS + Windows)."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        alive = handle != 0
        if handle:
            kernel32.CloseHandle(handle)
        return alive
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def acquire(session_id: str, session_type: str = "interactive") -> bool:
    """Acquire executor lock for an interactive session.

    Returns True if acquired, False if another interactive session is active.
    """
    lock = _read_lock()

    if lock and lock.get("type") == "interactive":
        # Another interactive session holds the lock
        if not _is_stale(lock) and _is_pid_alive(lock.get("pid", 0)):
            print(f"Another interactive session is active: {lock.get('session_id')} (PID {lock.get('pid')})")
            return False
        # Stale or dead — take over
        print(f"Stale interactive lock from {lock.get('session_id')} — taking over")

    _write_lock({
        "type": session_type,
        "session_id": session_id,
        "pid": os.getpid(),
        "acquired_at": time.time(),
        "heartbeat": time.time(),
    })
    print(f"Executor lock acquired: {session_id} (PID {os.getpid()})")
    return True


def release() -> None:
    """Release executor lock."""
    if LOCK_FILE.exists():
        lock = _read_lock()
        LOCK_FILE.unlink()
        print(f"Executor lock released (was: {lock.get('session_id', '?')})")
    else:
        print("No lock to release")


def heartbeat() -> None:
    """Update heartbeat timestamp. Call periodically from interactive session."""
    lock = _read_lock()
    if lock and lock.get("pid") == os.getpid():
        lock["heartbeat"] = time.time()
        _write_lock(lock)


def check() -> bool:
    """Check if the background runner should proceed.

    Returns True if runner can execute tasks, False if it should pause.
    """
    lock = _read_lock()

    if lock is None:
        # No lock — runner is free to execute
        return True

    if lock.get("type") == "background":
        # Background runner holds it — that's us, proceed
        return True

    if lock.get("type") == "interactive":
        if _is_stale(lock):
            # Interactive session is stale — clean up and proceed
            print(f"Stale interactive lock from {lock.get('session_id')} — resuming runner")
            LOCK_FILE.unlink()
            return True
        if not _is_pid_alive(lock.get("pid", 0)):
            # Interactive session is dead — clean up and proceed
            print(f"Dead interactive session {lock.get('session_id')} (PID {lock.get('pid')}) — resuming runner")
            LOCK_FILE.unlink()
            return True
        # Interactive session is active — pause
        return False

    return True


def status() -> dict:
    """Get current executor status."""
    lock = _read_lock()
    if lock is None:
        return {"active": "background_runner", "lock": None}

    stale = _is_stale(lock)
    alive = _is_pid_alive(lock.get("pid", 0))

    return {
        "active": lock.get("type", "unknown"),
        "session_id": lock.get("session_id", "?"),
        "pid": lock.get("pid", 0),
        "stale": stale,
        "pid_alive": alive,
        "acquired_ago": int(time.time() - lock.get("acquired_at", 0)),
        "heartbeat_ago": int(time.time() - lock.get("heartbeat", 0)),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "acquire":
        sid = sys.argv[2] if len(sys.argv) > 2 else f"claude-code-{os.getpid()}"
        ok = acquire(sid)
        sys.exit(0 if ok else 1)
    elif cmd == "release":
        release()
    elif cmd == "heartbeat":
        heartbeat()
    elif cmd == "check":
        can_run = check()
        s = status()
        if can_run:
            print(f"Runner can proceed (no interactive lock)")
        else:
            print(f"Runner PAUSED — interactive session active: {s.get('session_id')} (PID {s.get('pid')})")
        sys.exit(0 if can_run else 1)
    elif cmd == "status":
        s = status()
        print(json.dumps(s, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: executor_handoff.py [acquire|release|heartbeat|check|status]")
        sys.exit(1)
