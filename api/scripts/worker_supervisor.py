#!/usr/bin/env python3
"""Worker supervisor: own the local_runner worker's life and death, and record both.

The worker has been vanishing with no last words — killed by SIGTERM at session
teardown or by the OS under memory pressure, neither of which Python can
self-report once it's gone. This supervisor launches the worker as a child,
waits on it, and writes a structured record the moment it exits: exit code,
decoded signal, uptime, and the tail of its output. Then it restarts the worker
with crash-loop backoff. Run the supervisor detached so it outlives the session
that started it — that detachment is what stops the worker disappearing every
time a monitoring session ends.

Usage:
  python api/scripts/worker_supervisor.py --interval 15 --no-self-update
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent
_REPO_DIR = _API_DIR.parent
_LOG_DIR = _API_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_SUP_LOG = _LOG_DIR / "worker_supervisor.log"
_CHILD_LOG = _LOG_DIR / "worker_service.log"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    line = f"{_now()} SUPERVISOR {msg}"
    try:
        with open(_SUP_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def _decode_exit(rc) -> str:
    """Name the worker's cause of death from its return code.

    POSIX Popen reports a signal kill as a negative return code; a wrapper that
    already translated it lands as 128+N. Windows reports large unsigned codes
    for terminated processes — surface those as hex so they're recognisable.
    """
    if rc is None:
        return "launch-failed"
    if rc == 0:
        return "exit_code=0 (clean)"
    if rc < 0:
        try:
            name = signal.Signals(-rc).name
        except Exception:
            name = str(-rc)
        return f"signal:{name}({-rc})"
    if 128 < rc < 192:
        try:
            name = signal.Signals(rc - 128).name
        except Exception:
            name = str(rc - 128)
        return f"exit_code={rc} (signal:{name})"
    if rc > 0xFF:
        return f"exit_code={rc} (0x{rc & 0xFFFFFFFF:08X})"
    return f"exit_code={rc}"


def _tail(path: Path, n: int = 25) -> str:
    try:
        with open(path, "rb") as fh:
            data = fh.read()[-65536:]
        lines = data.decode("utf-8", "replace").splitlines()[-n:]
        return "\n    ".join(lines) if lines else "<empty>"
    except Exception as exc:
        return f"<tail unavailable: {exc}>"


def main() -> int:
    ap = argparse.ArgumentParser(description="Supervise the local_runner worker, recording every death")
    ap.add_argument("--interval", type=int, default=15, help="Worker poll interval (seconds)")
    ap.add_argument("--no-self-update", action="store_true", help="Pass through to the worker")
    ap.add_argument("--python", default=sys.executable, help="Python interpreter for the worker")
    ap.add_argument("--max-restarts", type=int, default=0, help="0 = unlimited")
    ap.add_argument("--backoff", type=float, default=5.0, help="Base restart delay (seconds)")
    ap.add_argument("--max-backoff", type=float, default=120.0, help="Cap on crash-loop backoff")
    args = ap.parse_args()

    runner = str(_SCRIPT_DIR / "local_runner.py")
    cmd = [args.python, "-u", runner, "--loop", "--interval", str(args.interval)]
    if args.no_self_update:
        cmd.append("--no-self-update")

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")

    stop = {"flag": False}

    def _on_term(signum, _frame):
        stop["flag"] = True
        _log(f"received signal {signum} — stopping after current child")

    for _name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        _sig = getattr(signal, _name, None)
        if _sig is not None:
            try:
                signal.signal(_sig, _on_term)
            except (ValueError, OSError):
                pass

    _log(f"start pid={os.getpid()} cwd={_REPO_DIR} supervising: {' '.join(cmd)}")

    restarts = 0
    backoff = args.backoff

    while not stop["flag"]:
        started = time.time()
        rc = None
        try:
            with open(_CHILD_LOG, "a", encoding="utf-8") as out:
                out.write(f"\n{_now()} === supervisor launching worker ===\n")
                out.flush()
                proc = subprocess.Popen(
                    cmd, cwd=str(_REPO_DIR), env=env,
                    stdout=out, stderr=subprocess.STDOUT,
                )
                _log(f"worker started pid={proc.pid}")
                rc = proc.wait()
        except Exception as exc:
            _log(f"FAILED to launch worker: {exc}")

        uptime = time.time() - started
        _log(f"worker DIED {_decode_exit(rc)} uptime={uptime:.0f}s restarts_so_far={restarts}")
        _log(f"worker last words (tail of {_CHILD_LOG.name}):\n    {_tail(_CHILD_LOG)}")

        if stop["flag"]:
            break

        restarts += 1
        if args.max_restarts and restarts > args.max_restarts:
            _log(f"max-restarts={args.max_restarts} reached — supervisor exiting")
            break

        # Crash-loop backoff: a worker that dies fast probably can't recover in
        # one breath, so wait longer; one that ran a while resets to the base.
        backoff = min(backoff * 2, args.max_backoff) if uptime < 30 else args.backoff
        _log(f"restarting in {backoff:.0f}s")
        slept = 0.0
        while slept < backoff and not stop["flag"]:
            time.sleep(1)
            slept += 1.0

    _log("supervisor exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
