# Spec: Non-Blocking Monitoring Workflows

## Purpose

Scheduled monitoring workflows should generate artifacts and open/update issues, but should not fail CI on `main` by default. This prevents automated audits from blocking developer workflows while preserving visibility into drift and missing automation prerequisites.

## Requirements

- [ ] Scheduled monitoring workflows alert via GitHub issues and artifacts without causing a failing conclusion on `main` by default.
- [ ] Strict mode for monitoring workflows is opt-in via an explicit repository variable.
- [ ] Manual dispatch (`workflow_dispatch`) remains available for triage and validation.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Scheduled monitoring workflows should generate artifacts and open/update issues, but should not fail CI on `main` by default.
files_allowed:
  - .github/workflows/asset-modularity-drift.yml
done_when:
  - Scheduled monitoring workflows alert via GitHub issues and artifacts without causing a failing conclusion on `main` b...
  - Strict mode for monitoring workflows is opt-in via an explicit repository variable.
  - Manual dispatch (`workflow_dispatch`) remains available for triage and validation.
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

- `.github/workflows/asset-modularity-drift.yml` - keep reporting/issue creation and ensure the workflow is non-blocking by default.

## Acceptance Tests

- Manual validation: run the workflow via `workflow_dispatch` and confirm it uploads `asset_modularity_report.json` and (when drift exists) updates/creates the drift issue without failing the workflow run.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.


## Verification

```bash
python3 scripts/validate_workflow_references.py
python3 scripts/validate_spec_quality.py --file specs/104-nonblocking-monitoring-workflows.md
```

## Out of Scope

- Fixing the underlying modularity drift blockers (splitting large files) in this change set.
- Changing audit thresholds or drift detection logic.

## Risks and Assumptions

- Risk: non-blocking workflows can reduce urgency; mitigation is issue creation + artifact upload for traceability.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_asset_modularity_split_blockers_001` to iteratively split the highest ROI blockers from the audit report.

## Decision Gates (if any)

- Decide which scheduled workflows should remain non-blocking, and what variables (if any) enable strict mode.
