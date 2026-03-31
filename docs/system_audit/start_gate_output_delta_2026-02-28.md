# Start-Gate Output Delta (2026-02-28)

## Before

`start-gate: current worktree has local changes. Do not abandon in-flight work: finish merge/deploy (or record an explicit blocker), then rerun start-gate from a clean worktree.`

Source: `docs/system_audit/start_gate_output_before_2026-02-28.txt`

## After

`start-gate: current worktree has local changes. Do not abandon in-flight work: finish merge/deploy (or record an explicit blocker), then rerun start-gate from a clean worktree. If you must run gates without abandoning changes, use ./scripts/auto_heal_start_gate.sh --with-rebase --with-pr-gate.`

Source: `docs/system_audit/start_gate_output_after_2026-02-28.txt`

## Concrete behavior improvement

- New actionable continuation command is included directly in the failure output.
- `./scripts/auto_heal_start_gate.sh --start-command "START_GATE_ENFORCE_REMOTE_FAILURES=0 make start-gate"` now supports full command strings and executed successfully.
