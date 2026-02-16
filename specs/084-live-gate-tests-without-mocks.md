# Spec 084: Live Gate Tests Without Mock API Responses

## Goal
Replace fake/mocked gate endpoint tests with real integration checks that execute actual gate logic against live GitHub/public deployment data. This removes false confidence from monkeypatched endpoint tests.

## Requirements
- [x] `api/tests/test_gates.py` no longer monkeypatches gate service functions.
- [x] Gate route tests assert real response shape and contract behavior from live calls.
- [x] `api/tests/test_release_gate_service.py` no longer monkeypatches public deploy and traceability report fetch paths.
- [x] Release gate service tests for public deploy and traceability use real external data and validate response structure.
- [x] Updated tests pass locally.

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
