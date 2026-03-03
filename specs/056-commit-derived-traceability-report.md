# Spec 056: Commit-Derived Traceability Report

## Goal
Allow the system to derive idea/spec/implementation traceability from a commit SHA without manually entering public links.

## Requirements
1. Add API endpoint `GET /api/gates/commit-traceability`.
2. Endpoint must accept `sha` and `repo` and return:
   - derived idea API references from commit evidence `idea_ids`
   - derived spec references from commit evidence `spec_ids`
   - derived implementation references from commit evidence `change_files` or commit file diff
3. Traceability derivation must read changed `docs/system_audit/commit_evidence_*.json` files in the commit.
4. Response must include machine/human access pointers and explicit unanswered items when derivation is incomplete.

## Implementation
- `api/app/services/release_gate_service.py`
- `api/app/routers/gates.py`
- `api/tests/test_release_gate_service.py`
- `api/tests/test_gates.py`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_release_gate_service.py tests/test_gates.py`
