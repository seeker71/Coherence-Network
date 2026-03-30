# Progress — runner-self-update

## Completed phases

- **spec** (2026-03-30): Full spec written and validated at `specs/runner-self-update.md`. 8 requirements (cooldown, drain window, task rescue, heartbeat field, spawn health check, post-stash check, argv preservation). 5 verification scenarios with exact commands. Passes `validate_spec_quality.py`.
- **impl** (2026-03-30): Implemented spec 027 (auto-update framework). Created contract test file `api/tests/test_update_spec_coverage.py` with 14 tests. Fixed idempotency bug in `api/scripts/update_spec_coverage.py` (regex trailing whitespace). All tests pass. Commit `6ce7e32b`.

## Current task

impl — COMPLETE

## Key decisions

- Cooldown default: 120 seconds (configurable via `runner.json`)
- Drain window default: 60 seconds
- Task rescue is best-effort with 5 s timeout per API call — orphan recovery service is the safety net
- Spawn health check waits 2 s and falls back to keeping old process alive if child exits immediately
- Telemetry endpoint deferred to follow-up (not in this spec scope)
- Fixed idempotency bug: changed regex from lookahead `(?=\n+\s*## )` to consuming pattern `\s*(?=## )` to prevent blank line accumulation on repeated runs

## Blockers

(none)
