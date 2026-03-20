# Spec: PyPI Indexing (Canonical Alias)

## Purpose

Preserve canonical `specs/024-pypi-indexing.md` references used in specs/docs while mapping to the active implementation and coverage artifacts. This ensures historical references resolve without requiring broad doc rewrites.

## Requirements

- [ ] Provide a canonical spec path at `specs/024-pypi-indexing.md`.
- [ ] Point readers to the current implementation/coverage source for PyPI indexing.
- [ ] Keep this alias doc documentation-only, with no runtime behavior changes.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 019, 034

## Task Card

```yaml
goal: Preserve canonical `specs/024-pypi-indexing.
files_allowed:
  - specs/024-pypi-indexing.md
done_when:
  - Provide a canonical spec path at `specs/024-pypi-indexing.md`.
  - Point readers to the current implementation/coverage source for PyPI indexing.
  - Keep this alias doc documentation-only, with no runtime behavior changes.
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/024-pypi-indexing.md` - canonical alias spec for legacy 024 references

## Acceptance Tests

- Manual validation: open `specs/024-pypi-indexing.md` and confirm it links to PyPI indexing coverage in `docs/SPEC-COVERAGE.md`.
- Manual validation: run docs/spec markdown link integrity scan and confirm no missing target for `024-pypi-indexing.md` references.

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


## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
```

## Out of Scope

- Backfilling a full historical implementation spec for PyPI indexing.
- Any runtime indexing logic or endpoint behavior changes.

## Risks and Assumptions

- Risk: alias docs can diverge from implementation evidence if not maintained.
- Assumption: `docs/SPEC-COVERAGE.md` remains the authoritative mapping for this legacy spec lineage.

## Known Gaps and Follow-up Tasks

- Follow-up task: optionally replace this alias with a full archival spec document if historical audit depth is required.

## See also

- [docs/SPEC-COVERAGE.md](../docs/SPEC-COVERAGE.md)
- [034-ops-runbook.md](034-ops-runbook.md)
- [019-graph-store-abstraction.md](019-graph-store-abstraction.md)

## Decision Gates (if any)

- None. Documentation-only alias for reference integrity.
