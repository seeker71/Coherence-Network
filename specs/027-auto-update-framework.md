# Spec: Auto-Update Framework (update_spec_coverage.py + CI)

## Purpose

Keep framework docs in sync with the codebase: when tests pass, a script updates `docs/SPEC-COVERAGE.md` and `docs/STATUS.md` so spec→implementation→test mapping and status snapshots stay current without manual edits. This spec defines the script `update_spec_coverage.py` and its CI integration.

## Requirements

- [x] Script `api/scripts/update_spec_coverage.py` runs after pytest and updates SPEC-COVERAGE when all tests pass.
- [x] SPEC-COVERAGE update: additive only — add missing spec rows from `specs/*.md`; never remove rows or change existing Present/Spec'd/Tested marks unless explicitly specified (e.g. optional "mark tested when pytest passes").
- [x] STATUS update: script updates at least one of (a) Test count in `docs/STATUS.md` from pytest output or env, or (b) "Specs Implemented" / "Specs Pending" derived from SPEC-COVERAGE; format and sections as in current STATUS.md.
- [x] Script is idempotent: repeated run with no new specs or test changes leaves files unchanged.
- [x] Script accepts `--dry-run`: preview changes without writing; exit 0.
- [x] CI job runs the script after the "Run API tests" step when pytest succeeds; script failure does not fail the CI job (e.g. `continue-on-error: true`).
- [x] Script only writes when tests have passed: in CI, run only after pytest step (GitHub Actions sets `CI=true`); locally, pass `--tests-passed` or script no-ops.

## API Contract (if applicable)

Not applicable — script is CLI-only.

## Script contract (CLI)

- **Invocation:** `python scripts/update_spec_coverage.py [--dry-run] [--tests-passed]` (run from `api/`).
- **`--dry-run`:** Preview SPEC-COVERAGE and STATUS changes; do not write files; exit 0.
- **`--tests-passed`:** Allow writes when not in CI. Omit locally → script no-ops and prints "Skipping (tests not confirmed passed). Use --tests-passed or run in CI."
- **CI:** When `CI=true` (e.g. GitHub Actions), script performs writes without `--tests-passed` (pytest is assumed to have run in the previous step).
- **Test count:** From env `TEST_COUNT` or from `pytest --co -q` when updating STATUS.
- **Paths:** Script resolves `docs/` and `specs/` relative to repo root (parent of `api/`).

## Data Model (if applicable)

Not applicable — script edits Markdown files under `docs/`.

## Files to Create/Modify

- `api/scripts/update_spec_coverage.py` — add or extend: SPEC-COVERAGE additive rows; optional STATUS updates (test count and/or specs implemented/pending from SPEC-COVERAGE).
- `docs/SPEC-COVERAGE.md` — updated by script (additive rows; optional mark-tested logic if specified).
- `docs/STATUS.md` — updated by script (test count and/or specs list) when required.
- `.github/workflows/test.yml` — ensure a step runs the script after "Run API tests" when pytest succeeds; step is non-blocking (e.g. `continue-on-error: true`).
- `api/tests/test_update_spec_coverage.py` — tests for dry-run, no-op without `--tests-passed`, idempotency, STATUS sections, CI step, additive rows.

## CI integration

The workflow must run the script only after pytest succeeds, and must not fail the job if the script fails. Implemented in `.github/workflows/test.yml`:

```yaml
- name: Run API tests
  run: |
    cd api && pytest -v

- name: Update spec coverage (post-test, non-blocking)
  continue-on-error: true
  run: |
    cd api && python scripts/update_spec_coverage.py
```

- GitHub Actions sets `CI=true`; the script performs writes without `--tests-passed`.
- Order: pytest step first; script step second. If pytest fails, the job fails and the script step is not run.
- Script is run from `api/` so paths to `docs/` and `specs/` resolve via repo root.

## Acceptance Tests

Tests define the contract; do not modify tests to make implementation pass. Fix the implementation instead.

- `update_spec_coverage.py --dry-run` exits 0 and prints preview; does not modify files.
- With a new spec in `specs/` and no row in SPEC-COVERAGE, script (no dry-run) adds one row; idempotent on second run.
- CI workflow includes "run script after pytest"; script step has `continue-on-error: true` so CI does not fail on script failure.
- STATUS update: "Test count" and "Specs Implemented" / "Specs Pending" in STATUS.md reflect script output and SPEC-COVERAGE.

**Test files:** `api/tests/test_update_spec_coverage.py` (dry-run, no-op without `--tests-passed`, idempotency, STATUS sections, CI workflow step, additive rows). `api/tests/test_agent.py` also has `test_update_spec_coverage_dry_run`.

**Contract (spec 027):** The tests in `test_update_spec_coverage.py` define the contract. Key behaviors: `--dry-run --tests-passed` exits 0, prints a preview (e.g. "(Dry run" or "Would add" or "No new specs"), and does not modify SPEC-COVERAGE or STATUS; without `--tests-passed` and not in CI, script prints exactly "Skipping (tests not confirmed passed). Use --tests-passed or run in CI." and exits 0; CI workflow has "Run API tests" before "Update spec coverage" and the update step has `continue-on-error: true`; after a run, every spec id from `specs/*.md` has a row in SPEC-COVERAGE (additive); STATUS.md contains "## Specs Implemented", "## Test Count", and a test count number; second run with no changes leaves files unchanged. Do not modify tests to make implementation pass.

## Verification

- **Dry-run (no writes):** `cd api && python scripts/update_spec_coverage.py --dry-run --tests-passed`
- **Full run (after tests pass):** `cd api && python scripts/update_spec_coverage.py --tests-passed`
- **CI:** Push to main/master or open PR; after "Run API tests" passes, "Update spec coverage" step runs (failure does not fail the job).

## Out of Scope

- Changing SPEC-COVERAGE existing marks (✓/?) based on pytest results (optional future; not required for this spec).
- Web or API endpoints for coverage/status; docs-only.
- Cost/token tracking, metrics persistence, monitor attention (see [027-fully-automated-pipeline](027-fully-automated-pipeline.md)).
- Auto-commit and push of updated docs from CI (runner updates workspace only).

## Decision Gates (if any)

- **CI:** Script runs after pytest; non-blocking so a flaky script does not fail CI.
- **STATUS scope:** Minimum is test count or specs list; human-only sections (e.g. Strategic gaps, Next priority) remain manual unless a follow-up spec defines them.

## See also

- [027 Fully Automated Pipeline](027-fully-automated-pipeline.md) — Broader pipeline automation (Phase 1 includes this script).
- [004 CI Pipeline](004-ci-pipeline.md) — GitHub Actions workflow.
- [030 Spec Coverage Update](030-spec-coverage-update.md) — Human-triggered SPEC-COVERAGE edits (does not change this script).
- [docs/EXECUTION-PLAN.md](../docs/EXECUTION-PLAN.md) — SPEC-COVERAGE and STATUS auto-update.
