# Spec 054: Commit Provenance Contract Gate

## Purpose

Ensure every meaningful change set is traceable to ideas/specs/tasks via a machine-readable commit evidence artifact, so automation and humans can audit intent, ownership, and validation without guesswork.

## Requirements

- [ ] CI fails when a diff range has no changed `docs/system_audit/commit_evidence_*.json` file, except for explicitly exempted automation/metadata-only change sets (for example Dependabot PRs and diffs limited to CI workflow files or dependency metadata like `web/package-lock.json`).
- [ ] Evidence schema includes attribution and traceability keys: `idea_ids`, `spec_ids`, `task_ids`, `contributors`, `agent`, `evidence_refs`, `change_files`.
- [ ] Evidence validates changed-file coverage: `change_files` includes all non-evidence changed paths in the diff range.
- [ ] Enforcement runs on both PR and push workflows.

## Validation
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_provenance-gate-mainline.json`

## Idea Traceability
- `idea_id`: `coherence-network-overall`
- Rationale: umbrella roadmap linkage for Coherence Network work.
