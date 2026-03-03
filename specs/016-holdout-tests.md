# Spec: Holdout Tests Pattern

## Purpose

Prevent implementations that "game" tests (e.g. return true without real logic). Tests in `tests/holdout/` are excluded from agent context; CI runs them.

## Requirements

- [x] Directory `api/tests/holdout/` exists with README
- [x] Placeholder test in holdout (e.g. test_holdout_placeholder)
- [x] Agent runs use `pytest --ignore=tests/holdout/` (project_manager)
- [x] CI runs full suite including holdout: `pytest -v` (no ignore)
- [x] Document pattern in docs/SPEC-COVERAGE.md and AGENTS.md

## API Contract

N/A.

## Files to Create/Modify

- `api/tests/holdout/README.md` — pattern explanation
- `api/tests/holdout/test_placeholder.py` — placeholder
- Project manager / agent runner — use `--ignore=tests/holdout` when invoking pytest for validation
- `docs/SPEC-COVERAGE.md` — add holdout section

## Acceptance Tests

- `pytest api/tests` runs holdout tests
- `pytest api/tests --ignore=api/tests/holdout` skips holdout
- Holdout README explains purpose

## Out of Scope

- Specific holdout test implementations (add per feature)
- Coverage exclusion for holdout

## See also

- [005-project-manager-pipeline.md](005-project-manager-pipeline.md) — PM uses --ignore=tests/holdout

## Decision Gates

None.
