# Spec 054: Commit Provenance Contract Gate

## Purpose

Ensure every meaningful change set is traceable to ideas/specs/tasks via a machine-readable commit evidence artifact, so automation and humans can audit intent, ownership, and validation without guesswork.

## Requirements

- [ ] CI fails when a diff range has no changed `docs/system_audit/commit_evidence_*.json` file, except for explicitly exempted automation/metadata-only change sets (for example Dependabot PRs and diffs limited to CI workflow files or dependency metadata like `web/package-lock.json`).
- [ ] Evidence schema includes attribution and traceability keys: `idea_ids`, `spec_ids`, `task_ids`, `contributors`, `agent`, `evidence_refs`, `change_files`.
- [ ] Evidence validates changed-file coverage: `change_files` includes all non-evidence changed paths in the diff range.
- [ ] Enforcement runs on both PR and push workflows.

## Files to Create/Modify

- `scripts/validate_commit_evidence.py` - evidence schema validation + diff-range enforcement.
- `.github/workflows/test.yml` - enforce evidence contract in the test workflow.
- `.github/workflows/thread-gates.yml` - enforce evidence contract in the thread-gates workflow.
- `docs/CODEX-THREAD-PROCESS.md` - contributor-facing instructions for creating valid evidence.

## Acceptance Tests

- `Manual validation`: open a PR that changes a runtime file (for example under `api/app/`) without adding a `docs/system_audit/commit_evidence_*.json` file and confirm CI fails with an evidence error.
- `Manual validation`: open a PR that changes only `.github/workflows/*` and confirm CI does not hard-fail on missing evidence (when the change set matches an exempted category).

## Verification

```bash
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_provenance-gate-mainline.json
python3 scripts/validate_commit_evidence.py --base origin/main --head HEAD --require-changed-evidence
```

## Out of Scope

- Expanding evidence schema beyond the required attribution/traceability fields.

## Risks and Assumptions

- Risk: overly strict enforcement blocks automation (Dependabot); mitigation is explicit, narrow exemptions for automation/metadata-only diffs.

## Known Gaps and Follow-up Tasks

- None.

## Decision Gates (if any)

- Approve and periodically review the exemption rules so they remain narrow and do not erode provenance for runtime/spec changes.
