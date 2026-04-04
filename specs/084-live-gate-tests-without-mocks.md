# Spec 084: Live Gate Tests Without Mock API Responses

## Goal
Replace fake/mocked gate endpoint tests with real integration checks that execute actual gate logic against live GitHub/public deployment data. This removes false confidence from monkeypatched endpoint tests.

## Requirements
- [x] `api/tests/test_gates.py` no longer monkeypatches gate service functions.
- [x] Gate route tests assert real response shape and contract behavior from live calls.
- [x] `api/tests/test_release_gate_service.py` no longer monkeypatches public deploy and traceability report fetch paths.
- [x] Release gate service tests for public deploy and traceability use real external data and validate response structure.
- [x] Updated tests pass locally.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - `api/tests/test_gates.py` no longer monkeypatches gate service functions.
  - Gate route tests assert real response shape and contract behavior from live calls.
  - `api/tests/test_release_gate_service.py` no longer monkeypatches public deploy and traceability report fetch paths.
  - Release gate service tests for public deploy and traceability use real external data and validate response structure.
  - Updated tests pass locally.
commands:
  - python3 -m pytest api/tests/test_gates.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/084-live-gate-tests-without-mocks.md`
- `api/tests/test_gates.py`
- `api/tests/test_release_gate_service.py`
- `docs/system_audit/commit_evidence_2026-02-16_live-gate-tests-no-mocks.json`

## Validation
```bash
cd api && pytest -q tests/test_gates.py tests/test_release_gate_service.py
```

## Out of Scope
- Rewriting every unit test that uses local monkeypatch for pure-function behavior.
- Refactoring release gate implementation logic.

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

See `api/tests/test_live_gate_tests_without_mocks.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_gates.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
