# Spec: Release Gates API

## Purpose

Automated checks for deployment readiness. Validates that PRs meet quality gates (CI passing, approvals, deploy contract) before merging to production.

## Requirements

- [x] GET /api/gates/pr-to-public — Check if PR is ready for merge to production
- [x] GET /api/gates/merged-contract — Verify merged change meets contract (CI, approvals, deploy)
- [x] GET /api/gates/main-head — Get current main branch status
- [x] Integrates with GitHub API for PR status, checks, approvals
- [x] Supports polling with timeout for async CI completion
- [x] Returns detailed reports with pass/fail reasons

## API Contract

### `GET /api/gates/pr-to-public`

**Purpose**: Check if PR is ready for production merge

**Request**:
- `branch`: String (query, required) — PR head branch
- `repo`: String (query, default: "seeker71/Coherence-Network")
- `base`: String (query, default: "main")
- `wait_public`: Boolean (query, default: false) — Poll until ready or timeout
- `timeout_seconds`: Integer (query, 10-7200, default: 1200)
- `poll_seconds`: Integer (query, 1-300, default: 30)

**Response 200**:
```json
{
  "ready": true,
  "pr_number": 123,
  "checks_passed": true,
  "approvals_met": true,
  "required_checks": ["CI", "tests"],
  "failed_checks": [],
  "rerunnable_run_ids": []
}
```

### `GET /api/gates/merged-contract`

**Purpose**: Verify merged commit meets deployment contract

**Request**:
- `sha`: String (query, required, min 7 chars) — Merged commit SHA
- `repo`: String (query, default: "seeker71/Coherence-Network")
- `min_approvals`: Integer (query, 0-10, default: 1)
- `min_unique_approvers`: Integer (query, 0-10, default: 1)
- `timeout_seconds`: Integer (query, 10-7200, default: 1200)
- `poll_seconds`: Integer (query, 1-300, default: 30)

**Response 200**:
```json
{
  "contract_met": true,
  "ci_passed": true,
  "approvals": 2,
  "unique_approvers": 2,
  "deploy_sha_match": true
}
```

### `GET /api/gates/main-head`

**Purpose**: Get current main branch HEAD status

**Response 200**:
```json
{
  "sha": "abc123def456",
  "ci_status": "success",
  "deploy_status": "deployed"
}
```

**Response 502**: When GitHub API unavailable

## Files

- `api/app/routers/gates.py` (implemented)
- `api/app/services/release_gate_service.py` (implemented)
- `api/tests/test_gates.py` (implemented)
- `specs/051-release-gates.md` (this spec)

## Acceptance Tests

- [x] `test_gate_pr_to_public_endpoint_returns_report`
- [x] `test_gate_merged_contract_endpoint_returns_report`
- [x] `test_gate_main_head_502_when_unavailable`

All tests passing.
