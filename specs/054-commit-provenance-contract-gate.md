# Spec 054: Commit Provenance Contract Gate

## Goal
Require each change set to include a machine-readable provenance artifact that links changed files to idea/spec/task attribution and verifiable evidence.

## Requirements
1. CI fails when a diff range has no changed `docs/system_audit/commit_evidence_*.json` file, except for explicitly exempted automation/metadata-only change sets (for example Dependabot PRs and diffs limited to CI workflow files or dependency metadata like `web/package-lock.json`).
2. Evidence schema must include attribution and traceability keys:
   - `idea_ids`, `spec_ids`, `task_ids`, `contributors`, `agent`, `evidence_refs`, `change_files`.
3. CI validates changed-file coverage (`change_files` must include all non-evidence changed files).
4. Enforcement runs on PR and push workflows.
5. Process docs define the required evidence format for machine/human contributors.

## Implementation
- `scripts/validate_commit_evidence.py`
- `.github/workflows/test.yml`
- `.github/workflows/thread-gates.yml`
- `docs/CODEX-THREAD-PROCESS.md`

## Validation
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_provenance-gate-mainline.json`
