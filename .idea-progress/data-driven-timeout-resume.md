# Progress — data-driven-timeout-resume

## Completed phases

- **spec** (2026-03-30): Wrote detailed spec at `specs/data-driven-timeout-resume.md` covering 6 requirements (R1–R6), 5 verification scenarios, data model, API contract, risks, and gaps. Validated with `validate_spec_quality.py`. Committed as `fe3e0719`.
- **impl** (2026-03-30): Implemented spec 136 — data-driven timeout dashboard. Added Pydantic models, service logic with p90/deterministic formula, API endpoint, React component with sortable table, and /automation/usage page. 5 API tests + 5 web tests passing. Committed as `6a8cbee6`.

## Current task

Impl phase complete.

## Key decisions

- 5-tier complexity scoring (trivial/simple/moderate/complex/heavy) replaces binary simple/complex
- Adaptive per-provider ceiling via `timeout_max_s` in runner.json (default 1800s) replaces hard 900s cap
- Persistent calibration store in `api/logs/timeout_calibration.json` with 7-day decay
- Reaper threshold derived from `timeout_granted_s * 1.3` stored in task context
- Resume reuses existing worktree when available, falls back to patch-based retry
- New `GET /api/automation/timeout-dashboard` endpoint with deterministic formula: `max(round(p90*1.5), 3000)` clamped to 20000
- Timeout events derived from existing friction events (block_type containing "timeout")
- Dashboard uses sortable table with expandable event rows per provider
- Web test file uses .ts extension (not .tsx) to match vitest config include pattern

## Blockers

(none)
