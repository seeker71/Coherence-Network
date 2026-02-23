# Spec: n8n Security Patch and HITL Hardening

## Purpose

Protect automation workflows from known critical exposure and reduce high-impact execution risk by enforcing a patched n8n baseline plus Human-in-the-loop (HITL) approval gates for sensitive agent actions.

## Requirements

- [ ] Runtime docs and deployment checks define a minimum supported n8n version at or above fixed security releases (`1.123.17` for v1 or `2.5.2` for v2).
- [ ] Automation workflows require explicit HITL approval before executing destructive or external-impacting actions (for example: delete/write/send).
- [ ] Security and workflow-edit permissions are documented with operational validation steps and evidence hooks.

## API Contract (if applicable)

N/A - no Coherence API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `docs/DEPLOY.md` - add minimum n8n version contract and verification checklist.
- `docs/RUNBOOK.md` - add HITL enforcement and operational recovery steps.
- `docs/PR-CHECK-FAILURE-TRIAGE.md` - add n8n version/HITL validation path for deployment blockers.
- `api/scripts/validate_pr_to_public.py` - add optional n8n minimum-version gate check for deploy validation.
- `api/tests/test_validate_pr_to_public.py` - cover n8n version floor parser and gate behavior.

## Acceptance Tests

- `cd api && pytest -v tests/test_validate_pr_to_public.py`
- `python3 scripts/validate_spec_quality.py --file specs/108-n8n-security-and-hitl-hardening.md`
- Manual validation:
  - Verify runtime/deploy target version is `>=1.123.17` (v1) or `>=2.5.2` (v2).
  - Verify at least one destructive tool action is blocked until HITL approval is provided.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/108-n8n-security-and-hitl-hardening.md
```

## Out of Scope

- Migrating all existing workflows to n8n v2.
- Replacing n8n with another orchestration system.

## Risks and Assumptions

- Risk: HITL prompts can increase completion latency; mitigate by scoping approval only to high-risk actions.
- Assumption: deployment/runtime surfaces can reliably expose active n8n version for checks.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_n8n_credentials_patch_rotation_001` to automate secret rotation via credentials PATCH API.

## Decision Gates (if any)

- Confirm high-risk action classes that must always require HITL in production.
