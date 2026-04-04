# Spec: Expand docs/SETUP.md — Troubleshooting and venv Path Note

## Purpose

Reduce setup friction for contributors and agents: document common failures and how to fix them, and make venv usage for scripts explicit so scripts run reliably from any working directory.

## Requirements

- [ ] `docs/SETUP.md` has a **Troubleshooting** section that includes at least: ModuleNotFoundError/import errors when running scripts, pytest not found, port in use, venv activation vs path.
- [ ] `docs/SETUP.md` has a clear **venv path note for scripts**: recommend `api/.venv/bin/python` (or `.venv/bin/python` when already in `api/`) for all `api/scripts/*` invocations; note Windows equivalent if applicable.
- [ ] Troubleshooting entries are specific and actionable (problem → fix).
- [ ] No new files; only modify `docs/SETUP.md`.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 006

## Task Card

```yaml
goal: Reduce setup friction for contributors and agents: document common failures and how to fix them, and make venv usage for scripts explicit so scripts run reliably from any working directory.
files_allowed:
  - docs/SETUP.md
done_when:
  - `docs/SETUP.md` has a Troubleshooting section that includes at least: ModuleNotFoundError/import errors when running ...
  - `docs/SETUP.md` has a clear venv path note for scripts: recommend `api/.venv/bin/python` (or `.venv/bin/python` when ...
  - Troubleshooting entries are specific and actionable (problem → fix).
  - No new files; only modify `docs/SETUP.md`.
commands:
  - python3 -m pytest api/tests/test_setup_docs.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A — documentation only.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A.

## Files to Create/Modify

- `docs/SETUP.md` — add or expand Troubleshooting section; add or consolidate venv path note for scripts (e.g. in Run Tests / Scripts or a dedicated "Scripts and venv" subsection).

## Acceptance Tests

- Human review: SETUP.md reads clearly; a new user can resolve "script fails with ModuleNotFoundError" and "pytest not found" using the doc.
- No automated test required for doc-only change (per project conventions).

## Out of Scope

- Changing any script implementation or adding new scripts.
- Modifying AGENTS.md, CLAUDE.md, or other docs unless they explicitly reference SETUP.md content that is moved/renamed.

## Decision Gates (if any)

None.

## See also

- `specs/006-overnight-backlog.md` — backlog item "Expand docs/SETUP.md: add Troubleshooting section, venv path note for scripts"
- `specs/TEMPLATE.md` — spec format

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Review coverage and add missing edge-case tests.


## Verification

```bash
python3 -m pytest api/tests/test_setup_docs.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
