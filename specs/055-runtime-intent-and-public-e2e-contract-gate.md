# Spec 055: Runtime Intent and Public E2E Contract Gate

## Goal
Fail CI when a runtime feature/fix intent is declared without actual API/Web runtime changes and public E2E validation metadata.

## Requirements
1. Commit evidence must include `change_intent`.
2. Runtime intents (`runtime_feature`, `runtime_fix`) require runtime code changes under:
   - `api/app/`
   - `web/app/`
   - `web/components/`
3. Runtime intents require `e2e_validation` block with:
   - `status`
   - `expected_behavior_delta`
   - `public_endpoints`
   - `test_flows`
4. Non-runtime intents must not include runtime file changes.
5. CI enforces these checks through commit evidence validator.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Commit evidence must include `change_intent`.
  - Runtime intents (`runtime_feature`, `runtime_fix`) require runtime code changes under:
  - Runtime intents require `e2e_validation` block with:
  - Non-runtime intents must not include runtime file changes.
  - CI enforces these checks through commit evidence validator.
commands:
  - python3 -m pytest api/tests/test_validate_pr_to_public.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Implementation
- `scripts/validate_commit_evidence.py`
- `api/tests/test_commit_evidence_validation.py`
- `docs/CODEX-THREAD-PROCESS.md`

## Validation
- `cd api && .venv/bin/pytest -q tests/test_commit_evidence_validation.py`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_runtime-intent-gate.json`

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.

## Acceptance Tests

See `api/tests/test_runtime_intent_and_public_e2e_contract_gate.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_validate_pr_to_public.py -x -v
```
