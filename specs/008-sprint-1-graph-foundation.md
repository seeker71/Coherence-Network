# Spec: Sprint 1 Graph Foundation (Canonical Alias)

## Purpose

Preserve canonical `specs/008-sprint-1-graph-foundation.md` references used across docs/specs while mapping to the current graph foundation implementation lineage. This avoids dead links and keeps historical references resolvable for audits.

## Requirements

- [ ] Provide a canonical spec path at `specs/008-sprint-1-graph-foundation.md`.
- [ ] Explicitly map legacy 008 references to the active graph foundation source spec.
- [ ] Keep this alias doc documentation-only, with no runtime behavior changes.

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/008-sprint-1-graph-foundation.md` - canonical alias spec for legacy 008 references

## Acceptance Tests

- Manual validation: open `specs/008-sprint-1-graph-foundation.md` and confirm it exists and references `specs/sprint0-graph-foundation-indexer-api.md`.
- Manual validation: run docs/spec markdown link integrity scan and confirm no missing target for `008-sprint-1-graph-foundation.md` references.

## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
```

## Out of Scope

- Rewriting historical specs to remove 008 references.
- Any API, database, or runtime pipeline behavior changes.

## Risks and Assumptions

- Risk: alias docs can drift from active implementation references.
- Assumption: `specs/sprint0-graph-foundation-indexer-api.md` remains the source of truth for this lineage.

## Known Gaps and Follow-up Tasks

- Follow-up task: define a repository-wide canonical alias policy for legacy spec filenames and duplicate spec numbers.

## See also

- [sprint0-graph-foundation-indexer-api.md](sprint0-graph-foundation-indexer-api.md)
- [019-graph-store-abstraction.md](019-graph-store-abstraction.md)
- [docs/SPEC-COVERAGE.md](../docs/SPEC-COVERAGE.md)

## Decision Gates (if any)

- None. Documentation-only alias for reference integrity.
