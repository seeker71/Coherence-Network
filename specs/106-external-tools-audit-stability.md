# Spec: External Tools Audit Stability

## Purpose

Keep the scheduled `External Tools Audit` workflow green by preventing the tool-discovery script from misclassifying workflow content (heredocs, GitHub expressions, shell helpers) as external tooling, and by keeping the registry aligned with the workflows.

## Requirements

- [ ] `scripts/audit_external_tools.py` must ignore GitHub Actions expressions (for example `${{ ... }}`) when discovering CLI tools.
- [ ] `scripts/audit_external_tools.py` must ignore heredoc bodies/terminators when discovering CLI tools.
- [ ] `scripts/audit_external_tools.py` must ignore shell helper function calls that are not external tools.
- [ ] `docs/system_audit/external_tools_registry.json` must track the GitHub Actions versions used in `.github/workflows/*.yml`.
- [ ] `docs/system_audit/external_tools_registry.json` must track workflow CLI tools used in `.github/workflows/*.yml`.

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `scripts/audit_external_tools.py`
- `docs/system_audit/external_tools_registry.json`
- `docs/system_audit/commit_evidence_2026-02-17_external-tools-audit-stability.json`

## Acceptance Tests

- Manual validation: `python3 scripts/audit_external_tools.py --json --fail-on-untracked` exits 0 and reports `untracked` lists are empty.

## Verification

```bash
python3 scripts/audit_external_tools.py --json --fail-on-untracked
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-17_external-tools-audit-stability.json
```

## Out of Scope

- Changing CI cadence, disabling the external tools audit workflow, or loosening its policy.

## Risks and Assumptions

- Risk: overly-broad filtering could hide a real external tool addition; mitigation is to keep filters narrowly targeted to known non-tool patterns (heredocs, GitHub expressions, helper identifiers).
- Assumption: workflow CLI tool discovery only needs to recognize top-level commands in `run: |` blocks.

## Known Gaps and Follow-up Tasks

- None at spec time.

## Decision Gates (if any)

None.
