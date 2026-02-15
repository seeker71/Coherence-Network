# Spec 071: Commit Provenance Contract Gate

## Goal
Require each change set to include a machine-readable provenance artifact that links changed files to idea/spec/task attribution and verifiable evidence.

## Requirements
1. CI fails when a diff range has no changed `docs/system_audit/commit_evidence_*.json` file.
2. Evidence schema must include attribution and traceability keys:
   - `idea_ids`, `spec_ids`, `task_ids`, `contributors`, `agent`, `evidence_refs`, `change_files`.
3. CI validates changed-file coverage (`change_files` must include all non-evidence changed files).
4. Enforcement runs on PR and push workflows.
5. Process docs define the required evidence format for machine/human contributors.

## Implementation
- `scripts/validate_commit_evidence.py`
- `.github/workflows/thread-gates.yml`
- `.github/workflows/test.yml`
- `docs/CODEX-THREAD-PROCESS.md`

## Validation
- `python scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_provenance-gate.json`
- `python scripts/validate_commit_evidence.py --base HEAD~1 --head HEAD --require-changed-evidence` (in CI with proper base/head)
