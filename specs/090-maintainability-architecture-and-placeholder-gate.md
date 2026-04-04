# Spec 090: Maintainability Architecture and Placeholder Gate

## Goal

Add a recurring maintainability review that scans architecture quality from top-level to module-level and detects runtime mock/fake/placeholder debt before it compounds.

## Requirements

1. Provide a machine-readable maintainability audit report with architecture metrics (layer violations, large modules, long functions) and runtime placeholder findings.
2. Include ROI-oriented recommended cleanup tasks in the report so remediation can be prioritized.
3. Add a scheduled GitHub workflow that runs the audit at least twice per week and opens/updates an issue when drift becomes blocking or regresses against baseline.
4. Add a PR gate that fails when maintainability metrics regress beyond baseline.
5. Integrate audit into pipeline monitoring so conditions are visible in `/api/agent/monitor-issues`, and auto-fix can create a high-ROI heal task when configured.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Provide a machine-readable maintainability audit report with architecture metrics (layer violations, large modules, l...
  - Include ROI-oriented recommended cleanup tasks in the report so remediation can be prioritized.
  - Add a scheduled GitHub workflow that runs the audit at least twice per week and opens/updates an issue when drift bec...
  - Add a PR gate that fails when maintainability metrics regress beyond baseline.
  - Integrate audit into pipeline monitoring so conditions are visible in `/api/agent/monitor-issues`, and auto-fix can c...
commands:
  - python3 -m pytest api/tests/test_maintainability_audit_service.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Validation

- `api/tests/test_maintainability_audit_service.py`
- `python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression`
- Workflow: `.github/workflows/maintainability-architecture-audit.yml`

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add deployment smoke tests post-release.

## Acceptance Tests

See `api/tests/test_maintainability_architecture_and_placeholder_gate.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_maintainability_audit_service.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
