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

## Implementation
- `scripts/validate_commit_evidence.py`
- `api/tests/test_commit_evidence_validation.py`
- `docs/CODEX-THREAD-PROCESS.md`

## Validation
- `cd api && .venv/bin/pytest -q tests/test_commit_evidence_validation.py`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_runtime-intent-gate.json`
