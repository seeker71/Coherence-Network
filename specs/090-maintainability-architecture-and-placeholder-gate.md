# Spec 090: Maintainability Architecture and Placeholder Gate

## Goal

Add a recurring maintainability review that scans architecture quality from top-level to module-level and detects runtime mock/fake/placeholder debt before it compounds.

## Requirements

1. Provide a machine-readable maintainability audit report with architecture metrics (layer violations, large modules, long functions) and runtime placeholder findings.
2. Include ROI-oriented recommended cleanup tasks in the report so remediation can be prioritized.
3. Add a scheduled GitHub workflow that runs the audit at least twice per week and opens/updates an issue when drift becomes blocking or regresses against baseline.
4. Add a PR gate that fails when maintainability metrics regress beyond baseline.
5. Integrate audit into pipeline monitoring so conditions are visible in `/api/agent/monitor-issues`, and auto-fix can create a high-ROI heal task when configured.

## Validation

- `api/tests/test_maintainability_audit_service.py`
- `python3 api/scripts/run_maintainability_audit.py --output maintainability_audit_report.json --fail-on-regression`
- Workflow: `.github/workflows/maintainability-architecture-audit.yml`
