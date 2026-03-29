# Progress — data-retention-summarization

## Completed phases

- **2026-03-28 — Spec task (task_aedfe58cc5aa8597):** Added `specs/data-retention-summarization.md` defining hot (7d) / warm (30d) / cold (90d+) tiers, never-delete domain sets vs trim-allowlist (`runtime_events`, `telemetry_automation_usage_snapshots`, `telemetry_task_metrics`), summarize-before-delete, off-DB export with manifests, `retention_policy.json` + scheduled job, target API (`/api/retention/policy`, `/api/retention/status`, admin dry-run run), five executable verification scenarios, evidence for operators, and follow-ups (friction events, Prometheus).

## Current task

(none — spec delivered; implementation is a separate phase per spec task card)

## Key decisions

- Product phrase “telemetry snapshots” maps to **`telemetry_automation_usage_snapshots`** in the current schema (not a separate `telemetry_snapshots` table).
- **Fail-closed** trimming: tables outside the explicit allowlist cannot be processed; policy validation rejects unsafe allowlist entries.
- Cold-tier detail exists only in **off-DB** backup after verified export; MVP skips automatic rehydration.

## Blockers

- Agent session could not run `git`, `curl`, `cc`, or `validate_spec_quality.py` (sandbox). Runner should commit and run gates locally.
