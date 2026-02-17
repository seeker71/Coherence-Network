# Spec: Non-Blocking Monitoring Workflows

## Purpose

Scheduled monitoring workflows should generate artifacts and open/update issues, but should not fail CI on `main` by default. This prevents automated audits from blocking developer workflows while preserving visibility into drift and missing automation prerequisites.

## Requirements

- [ ] Scheduled monitoring workflows can alert via GitHub issues and artifacts without causing a failing conclusion on `main` by default.
- [ ] If a repository variable explicitly enables strict mode, monitoring workflows may hard-fail when their contract is violated.
- [ ] Manual dispatch (`workflow_dispatch`) remains available for triage and validation.

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `.github/workflows/asset-modularity-drift.yml` - keep reporting/issue creation, but ensure workflow is non-blocking by default.

## Acceptance Tests

- Manual: run the workflow via `workflow_dispatch` and confirm it uploads `asset_modularity_report.json` and (when drift exists) updates/creates the drift issue without failing the workflow run.

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
- Assumption: strict enforcement (hard fail) should be opt-in via repository variable, not the default.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_asset_modularity_split_blockers_001` to iteratively split the highest ROI blockers from the audit report.

## Decision Gates (if any)

- Decide whether `ASSET_MODULARITY_STRICT` should be reintroduced as an opt-in strict variable and what its default should be.

