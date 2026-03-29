# Progress — cli-full-coverage

## Completed phases

- **2026-03-28 — Spec task (task_8e2dc68955c08364):** Added `specs/cli-full-coverage.md` defining 100% OpenAPI→CLI mapping, priority phases (messaging, tasks/agent, treasury, governance, services), canonical coverage artifact, CI regression strategy, 5 verification scenarios for production validation, and independently verifiable evidence model.

- **2026-03-28 — Implementation (task_6e7209a79749dcce):**
  - Generic `cc api <METHOD> <path>` with `--query`, `--body`, `--no-auth`, optional leading `--json` for machine stdout.
  - `cc api coverage` reads meta + manifest for contract proof.
  - `cli/lib/cli-coverage-manifest.json` with `minimum_openapi_operations: 215` and optional `last_openapi_operations_count` (via `scripts/sync_cli_coverage_manifest.py`).
  - `cli/lib/api.mjs` extended with `request()`, `put()`.
  - Pytest: `api/tests/test_cli_full_coverage.py`.

## Current task

(none — implementation delivered for this task)

## Key decisions

- Coverage is **machine-checkable** via manifest minimum + pytest; exact snapshot is optional (`sync_cli_coverage_manifest.py`).
- **215** is the **minimum** contract floor for OpenAPI operations; the API may expose more.
- Generic `cc api` gives full reachability; existing `cc` subcommands remain the preferred UX for common flows.

## Blockers

- None.
