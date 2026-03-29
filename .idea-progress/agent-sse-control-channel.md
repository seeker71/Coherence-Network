# Progress — agent-sse-control-channel

## Completed phases

- **2026-03-28 — Spec task (task_0883cfbefa768f86):** Added `specs/agent-sse-control-channel.md` defining SSE `GET .../control/stream`, `POST .../control/commands`, `POST .../control/responses`, `GET .../control/state`; ControlCommand/ControlResponse models; JSONL command-file convention; five runnable verification scenarios (inject/state, SSE fan-out, responses, validation errors, terminal task); risks; how proof improves over time (telemetry, flags, dashboards).

## Current task

- Complete git commit for spec delivery (runner pushes).

## Key decisions

- **Wire format:** REST for inject/responses + SSE for fan-out (not WebSocket in MVP).
- **Idempotency:** `command_id` + optional `Idempotency-Key` on inject.
- **Local I/O:** JSONL command file under runner workdir for CLI portability; server remains source of truth for audit via `control/state`.

## Blockers

- None.
