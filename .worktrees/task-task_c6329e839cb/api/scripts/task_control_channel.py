"""Task control channel — real-time SSE bridge between running tasks and the network.

When the runner executes a task via a provider CLI, this module:
1. Connects to the SSE stream for this node
2. Writes incoming commands to a control file the agent can read
3. Reads agent responses from a response file
4. Posts responses back to the network

Control flow:
  Network → SSE → control file → Agent reads → Agent writes response file → POST back

Supported commands:
  checkpoint  — Agent saves progress to .task-checkpoint.md
  steer       — Agent adjusts task direction (payload.direction)
  abort       — Agent stops, saves partial work, exits
  ask         — Agent pauses, asks user for permission, replies
  report      — Agent sends status update (no action needed from agent)
  ping        — Agent confirms it's alive

File protocol:
  {task_dir}/.task-control   — JSON commands written by this channel, read by agent
  {task_dir}/.task-response  — JSON responses written by agent, read by this channel
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("task_control")

# How often to check for agent responses
_RESPONSE_POLL_INTERVAL = 2.0
# How long to wait for SSE reconnect
_SSE_RECONNECT_DELAY = 5.0


class TaskControlChannel:
    """Bidirectional control channel for a running task.

    Usage:
        channel = TaskControlChannel(node_id, task_id, task_dir, api_base)
        channel.start()  # starts SSE listener + response poller in background
        ... run the provider ...
        channel.stop()   # clean shutdown
    """

    def __init__(self, node_id: str, task_id: str, task_dir: Path, api_base: str):
        self.node_id = node_id
        self.task_id = task_id
        self.task_dir = Path(task_dir)
        self.api_base = api_base
        self.control_file = self.task_dir / ".task-control"
        self.response_file = self.task_dir / ".task-response"
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._command_queue: list[dict] = []

    def start(self) -> None:
        """Start SSE listener and response poller in background threads."""
        self.task_dir.mkdir(parents=True, exist_ok=True)

        # Clear old files
        if self.control_file.exists():
            self.control_file.unlink()
        if self.response_file.exists():
            self.response_file.unlink()

        # Write initial control file so agent knows we're listening
        self._write_control({"type": "connected", "task_id": self.task_id, "timestamp": time.time()})

        # Start SSE listener thread
        sse_thread = threading.Thread(target=self._sse_listener, daemon=True, name=f"sse-{self.task_id[:8]}")
        sse_thread.start()
        self._threads.append(sse_thread)

        # Start response poller thread
        resp_thread = threading.Thread(target=self._response_poller, daemon=True, name=f"resp-{self.task_id[:8]}")
        resp_thread.start()
        self._threads.append(resp_thread)

        log.info("CONTROL_CHANNEL started for task %s", self.task_id[:16])

    def stop(self) -> None:
        """Stop the control channel."""
        self._stop_event.set()
        self._write_control({"type": "disconnected", "task_id": self.task_id, "timestamp": time.time()})
        for t in self._threads:
            t.join(timeout=5)
        log.info("CONTROL_CHANNEL stopped for task %s", self.task_id[:16])

    def send_command(self, command: str, payload: dict | None = None) -> None:
        """Send a command to the running agent."""
        cmd = {
            "type": command,
            "task_id": self.task_id,
            "payload": payload or {},
            "timestamp": time.time(),
        }
        self._write_control(cmd)
        self._command_queue.append(cmd)
        log.info("CONTROL_CMD %s → task %s", command, self.task_id[:16])

    def _write_control(self, data: dict) -> None:
        """Write a command to the control file (append as JSONL)."""
        try:
            with open(self.control_file, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            log.warning("CONTROL_WRITE failed: %s", e)

    def _sse_listener(self) -> None:
        """Listen to SSE stream and forward relevant events to control file."""
        import httpx

        url = f"{self.api_base}/api/federation/nodes/{self.node_id}/stream"

        while not self._stop_event.is_set():
            try:
                with httpx.stream("GET", url, timeout=None, headers={"Accept": "text/event-stream"}) as response:
                    if response.status_code != 200:
                        log.warning("CONTROL_SSE HTTP %d — retrying in %ds", response.status_code, _SSE_RECONNECT_DELAY)
                        time.sleep(_SSE_RECONNECT_DELAY)
                        continue

                    for line in response.iter_lines():
                        if self._stop_event.is_set():
                            break

                        if not line.startswith("data: "):
                            continue

                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        # Filter: only forward events targeted at this task or this node
                        event_type = event.get("type") or event.get("event_type", "")

                        if event_type in ("checkpoint", "steer", "abort", "ask", "report", "ping"):
                            # Direct control command
                            self.send_command(event_type, event.get("payload", event))
                        elif event_type == "command" and event.get("payload", {}).get("task_id") == self.task_id:
                            # Task-specific command
                            self.send_command(
                                event["payload"].get("command", "unknown"),
                                event.get("payload", {}),
                            )

            except Exception as e:
                if not self._stop_event.is_set():
                    log.warning("CONTROL_SSE error: %s — retrying in %ds", e, _SSE_RECONNECT_DELAY)
                    time.sleep(_SSE_RECONNECT_DELAY)

    def _response_poller(self) -> None:
        """Poll for agent responses and send them back to the network."""
        import httpx

        last_size = 0

        while not self._stop_event.is_set():
            try:
                if self.response_file.exists():
                    content = self.response_file.read_text()
                    if len(content) > last_size:
                        new_lines = content[last_size:].strip().split("\n")
                        last_size = len(content)

                        for line in new_lines:
                            if not line.strip():
                                continue
                            try:
                                response = json.loads(line)
                                self._post_response(response)
                            except json.JSONDecodeError:
                                # Plain text response
                                self._post_response({"type": "text", "text": line, "task_id": self.task_id})

            except Exception as e:
                log.warning("CONTROL_RESPONSE poll error: %s", e)

            self._stop_event.wait(_RESPONSE_POLL_INTERVAL)

    def _post_response(self, response: dict) -> None:
        """Send agent response back to the network via API."""
        import httpx

        try:
            # Post as task activity
            httpx.post(
                f"{self.api_base}/api/agent/tasks/{self.task_id}/activity",
                json={
                    "event_type": f"control_response_{response.get('type', 'unknown')}",
                    "data": response,
                },
                timeout=10,
            )
            log.info("CONTROL_RESPONSE posted for task %s: %s", self.task_id[:16], response.get("type", "?"))
        except Exception as e:
            log.warning("CONTROL_RESPONSE post failed: %s", e)


def inject_control_instructions(prompt: str, task_dir: Path) -> str:
    """Add control channel instructions to the agent's prompt.

    Uses coh CLI for communication — agents are network participants.
    """
    instructions = """

## Real-time network communication

You are a node in the Coherence Network. Use `coh` to communicate:

### Check for messages (do this every 5-7 minutes)
```bash
coh inbox
```

If you see a command, act on it:
- `checkpoint` — Write your current progress to `.task-checkpoint.md` and reply with `coh msg <sender> "checkpoint saved"`
- `steer` — Adjust your approach as directed and reply with `coh msg <sender> "acknowledged, adjusting"`
- `abort` — Stop work, save progress to `.task-checkpoint.md`, reply with `coh msg <sender> "aborting, progress saved"`, then exit
- `ask` — Answer the question via `coh msg <sender> "<your answer>"`

### Send status updates
```bash
coh msg broadcast "Working on <idea>: 60% complete, implementing API endpoints"
```

### Report issues
```bash
coh msg broadcast "Blocked: missing dependency X, need guidance"
```

### When done
```bash
coh contribute --type code --cc 5 --desc "Implemented <feature>"
```
"""
    return prompt + instructions
