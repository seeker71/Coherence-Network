# Spec: Auto-Update Framework (update_spec_coverage.py + CI)

## Purpose

Keep framework docs in sync with the codebase: when tests pass, a script updates `docs/SPEC-COVERAGE.md` and `docs/STATUS.md` so spec→implementation→test mapping and status snapshots stay current without manual edits. This spec defines implementing `update_spec_coverage.py` and wiring it into CI.

## Requirements

- [ ] Script `api/scripts/update_spec_coverage.py` runs after pytest and updates SPEC-COVERAGE when all tests pass.
- [ ] SPEC-COVERAGE update: additive only — add missing spec rows from `specs/*.md`; never remove rows or change existing Present/Spec'd/Tested marks unless explicitly specified (e.g. optional "mark tested when pytest passes").
- [ ] STATUS update: script updates at least one of (a) Test count in `docs/STATUS.md` from pytest output or env, or (b) "Specs Implemented" / "Specs Pending" derived from SPEC-COVERAGE; format and sections as in current STATUS.md.
- [ ] Script is idempotent: repeated run with no new specs or test changes leaves files unchanged.
- [ ] Script accepts `--dry-run`: preview changes without writing; exit 0.
- [ ] CI job runs the script after the "Run API tests" step when pytest succeeds; script failure does not fail the CI job (e.g. `continue-on-error: true`).
- [ ] Script only writes when tests have passed: in CI, run only after pytest step; locally, either run after pytest or accept a flag (e.g. `--tests-passed`) and no-op if not set.

## API Contract (if applicable)

Not applicable — script is CLI-only.

## Data Model (if applicable)

Not applicable — script edits Markdown files under `docs/`.

## Files to Create/Modify

- `api/scripts/update_spec_coverage.py` — add or extend: SPEC-COVERAGE additive rows; optional STATUS updates (test count and/or specs implemented/pending from SPEC-COVERAGE).
- `docs/SPEC-COVERAGE.md` — updated by script (additive rows; optional mark-tested logic if specified).
- `docs/STATUS.md` — updated by script (test count and/or specs list) when required.
- `.github/workflows/test.yml` — ensure a step runs the script after "Run API tests" when pytest succeeds; step is non-blocking (e.g. `continue-on-error: true`).

## CI Wiring

The workflow must run the script only after pytest succeeds, and must not fail the job if the script fails:

```yaml
- name: Run API tests
  run: |
    cd api && pytest -v

- name: Update spec coverage (post-test, non-blocking)
  continue-on-error: true
  run: |
    cd api && python scripts/update_spec_coverage.py
```

- Script sees `CI=true` in GitHub Actions and performs writes; no `--tests-passed` needed in CI.
- Order: pytest step first; script step second. If pytest fails, the job fails and the script step is not run.

## Acceptance Tests

- `update_spec_coverage.py --dry-run` exits 0 and prints preview; does not modify files.
- With a new spec in `specs/` and no row in SPEC-COVERAGE, script (no dry-run) adds one row; idempotent on second run.
- CI workflow includes "run script after pytest"; script step has `continue-on-error` or equivalent so CI does not fail on script failure.
- If STATUS update is implemented: "Test count" or "Specs Implemented" in STATUS.md reflects script output or SPEC-COVERAGE.

See `api/tests/test_agent.py` — `test_update_spec_coverage_dry_run`; optionally add `api/tests/test_update_spec_coverage.py` for STATUS update and idempotency tests.

## Out of Scope

- Changing SPEC-COVERAGE existing marks (✓/?) based on pytest results (optional future; not required for this spec).
- Web or API endpoints for coverage/status; docs-only.
- Cost/token tracking, metrics persistence, monitor attention (see 027-fully-automated-pipeline).
- Auto-commit and push of updated docs from CI (runner updates workspace only).

## Decision Gates (if any)

- **CI:** Script runs after pytest; non-blocking so a flaky script does not fail CI.
- **STATUS scope:** Minimum is test count or specs list; human-only sections (e.g. Strategic gaps, Next priority) remain manual unless a follow-up spec defines them.

## See also

- [027 Fully Automated Pipeline](027-fully-automated-pipeline.md) — Phase 1 auto-update, metrics, attention.
- [004 CI Pipeline](004-ci-pipeline.md) — GitHub Actions.
- [007 Meta-pipeline backlog](007-meta-pipeline-backlog.md) — Pipeline improvement work.
- [docs/EXECUTION-PLAN.md](../docs/EXECUTION-PLAN.md) — SPEC-COVERAGE and STATUS auto-update.
