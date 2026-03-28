"""Provider wrapper — process-level control for running agent CLIs.

Sits between the runner and the provider subprocess. Provides:
- Real-time stdout streaming with checkpoint capture
- Control commands via .task-control file (no agent cooperation needed)
- Graceful abort with partial output preservation
- Stdin injection for providers that support it

Usage (from runner):
    wrapper = ProviderWrapper(cmd, cwd, timeout, control_dir)
    success, output, duration = wrapper.run()
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger("provider_wrapper")


class ProviderWrapper:
    """Wraps a provider subprocess with process-level control."""

    def __init__(
        self,
        cmd: list[str],
        cwd: str,
        timeout: int = 300,
        control_dir: Path | None = None,
        stdin_input: str | None = None,
    ):
        self.cmd = cmd
        self.cwd = cwd
        self.timeout = timeout
        self.control_dir = Path(control_dir) if control_dir else None
        self.stdin_input = stdin_input

        # State
        self._proc: subprocess.Popen | None = None
        self._output_lines: list[str] = []
        self._output_lock = threading.Lock()
        self._checkpoints: list[dict] = []
        self._aborted = False
        self._stop_event = threading.Event()

        # Control files
        self._control_file = self.control_dir / ".task-control" if self.control_dir else None
        self._response_file = self.control_dir / ".task-response" if self.control_dir else None
        self._checkpoint_file = self.control_dir / ".task-checkpoint.md" if self.control_dir else None

    def run(self) -> tuple[bool, str, float]:
        """Execute the provider with control channel. Returns (success, output, duration)."""
        start = time.time()

        # Platform-specific process creation
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE if self.stdin_input else None,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.cwd,
                creationflags=creation_flags,
            )
        except Exception as e:
            return False, f"Failed to start provider: {e}", time.time() - start

        # Start control monitor thread
        control_thread = None
        if self._control_file:
            self._clear_old_commands()
            control_thread = threading.Thread(target=self._control_monitor, daemon=True)
            control_thread.start()

        # Start stdout reader thread
        stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        stdout_thread.start()

        # Send stdin if needed
        if self.stdin_input and self._proc.stdin:
            try:
                self._proc.stdin.write(self.stdin_input)
                self._proc.stdin.close()
            except Exception:
                pass

        # Wait for process with timeout
        try:
            self._proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            log.warning("WRAPPER timeout after %ds — killing", self.timeout)
            self._kill_process()
            self._save_checkpoint("timeout")

        duration = time.time() - start

        # Collect output
        self._stop_event.set()
        stdout_thread.join(timeout=5)

        with self._output_lock:
            output = "\n".join(self._output_lines)

        # Also capture stderr (with timeout to avoid pipe hang on Windows)
        stderr = ""
        if self._proc.stderr:
            def _read_stderr():
                nonlocal stderr
                try:
                    stderr = self._proc.stderr.read()
                except Exception:
                    pass
            t = threading.Thread(target=_read_stderr, daemon=True)
            t.start()
            t.join(timeout=5)
            if t.is_alive():
                log.warning("WRAPPER stderr read hung — pipe held by orphan child")
                try:
                    self._proc.stderr.close()
                except Exception:
                    pass

        if not output and stderr:
            output = stderr

        if not output:
            output = "(no output)"

        success = self._proc.returncode == 0 and not self._aborted
        log.info(
            "WRAPPER finished: rc=%s output=%d chars duration=%.1fs aborted=%s",
            self._proc.returncode, len(output), duration, self._aborted,
        )
        if not success and len(output) < 100:
            log.warning(
                "WRAPPER low-output failure: rc=%s stderr=%s",
                self._proc.returncode, (stderr or "")[:500],
            )
        return success, output, duration

    def _read_stdout(self) -> None:
        """Read provider stdout line by line.

        Uses readline() instead of iterator to avoid Python's internal
        buffering which can block on Windows until the buffer fills.
        Logs exceptions instead of silently swallowing them.
        """
        try:
            while not self._stop_event.is_set():
                line = self._proc.stdout.readline()
                if not line:  # EOF — process closed stdout
                    break
                with self._output_lock:
                    self._output_lines.append(line.rstrip("\n"))
        except ValueError:
            # Pipe closed — expected after kill
            pass
        except Exception as exc:
            log.warning("WRAPPER stdout reader error: %s", exc)

    def _control_monitor(self) -> None:
        """Monitor .task-control for commands. Process-level control — no agent cooperation needed."""
        last_size = 0

        while not self._stop_event.is_set():
            try:
                if self._control_file and self._control_file.exists():
                    content = self._control_file.read_text()
                    if len(content) > last_size:
                        new_lines = content[last_size:].strip().split("\n")
                        last_size = len(content)

                        for line in new_lines:
                            if not line.strip():
                                continue
                            try:
                                cmd = json.loads(line)
                                self._handle_command(cmd)
                            except json.JSONDecodeError:
                                pass
            except Exception:
                pass

            self._stop_event.wait(2.0)

    def _handle_command(self, cmd: dict) -> None:
        """Handle a control command at the process level."""
        cmd_type = cmd.get("type", "")

        if cmd_type == "checkpoint":
            log.info("WRAPPER checkpoint requested")
            self._save_checkpoint("requested")
            self._write_response({"type": "checkpoint_saved", "chars": self._checkpoint_size()})

        elif cmd_type == "abort":
            log.info("WRAPPER abort requested")
            self._aborted = True
            self._save_checkpoint("abort")
            self._kill_process()
            self._write_response({"type": "aborted", "partial_output_chars": len("\n".join(self._output_lines))})

        elif cmd_type == "steer":
            direction = cmd.get("payload", {}).get("direction", "")
            log.info("WRAPPER steer: %s", direction[:80])
            # Write steer instruction to stdin if provider supports it
            if self._proc and self._proc.stdin and not self._proc.stdin.closed:
                try:
                    self._proc.stdin.write(f"\n[STEER]: {direction}\n")
                    self._proc.stdin.flush()
                    self._write_response({"type": "steered", "direction": direction[:200]})
                except Exception:
                    self._write_response({"type": "steer_failed", "reason": "stdin closed"})
            else:
                # Can't steer — stdin not available. Log the direction for post-task context.
                self._write_response({"type": "steer_noted", "direction": direction[:200], "note": "stdin not available, direction saved for resume"})

        elif cmd_type == "ping":
            with self._output_lock:
                lines = len(self._output_lines)
            alive = self._proc and self._proc.poll() is None
            self._write_response({
                "type": "pong",
                "alive": alive,
                "output_lines": lines,
                "uptime_s": int(time.time() - (self._proc.args[0] if hasattr(self._proc, '_start_time') else time.time())),
            })

        elif cmd_type == "report":
            with self._output_lock:
                lines = len(self._output_lines)
                last_line = self._output_lines[-1] if self._output_lines else "(no output yet)"
            self._write_response({
                "type": "status",
                "output_lines": lines,
                "last_line": last_line[:200],
                "process_alive": self._proc.poll() is None if self._proc else False,
            })

        elif cmd_type in ("connected", "disconnected"):
            pass  # lifecycle events, no action needed

    def _save_checkpoint(self, reason: str) -> None:
        """Save current output as a checkpoint."""
        if not self._checkpoint_file:
            return

        with self._output_lock:
            output_so_far = "\n".join(self._output_lines)

        checkpoint = {
            "reason": reason,
            "timestamp": time.time(),
            "output_chars": len(output_so_far),
            "output_lines": len(self._output_lines),
        }
        self._checkpoints.append(checkpoint)

        try:
            self._checkpoint_file.write_text(
                f"# Task Checkpoint ({reason})\n\n"
                f"Saved at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
                f"Output so far: {len(output_so_far)} chars, {len(self._output_lines)} lines\n\n"
                f"## Partial output\n\n```\n{output_so_far[-3000:]}\n```\n"
            )
            log.info("WRAPPER checkpoint saved (%s): %d chars", reason, len(output_so_far))
        except Exception as e:
            log.warning("WRAPPER checkpoint save failed: %s", e)

    def _checkpoint_size(self) -> int:
        if self._checkpoint_file and self._checkpoint_file.exists():
            return len(self._checkpoint_file.read_text())
        return 0

    def _write_response(self, data: dict) -> None:
        """Write a response to the response file."""
        if not self._response_file:
            return
        try:
            with open(self._response_file, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception:
            pass

    def _clear_old_commands(self) -> None:
        """Clear old control/response files from previous runs."""
        for f in (self._control_file, self._response_file):
            if f and f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

    def _kill_process(self) -> None:
        """Kill the provider process tree."""
        if not self._proc:
            return
        pid = self._proc.pid
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=10)
            else:
                # Kill process group
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                # Wait briefly, then force kill
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        self._proc.kill()
        except Exception as e:
            log.warning("WRAPPER kill failed: %s", e)
