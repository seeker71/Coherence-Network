---
idea_id: developer-experience
status: active
source:
  - file: scripts/external_proof_demo.py
    symbols: [_idea_create_payload, run_idea_lifecycle, record_contribution, check_coherence_score]
  - file: api/tests/test_external_proof_demo.py
    symbols: [test_external_proof_idea_payload_matches_public_contract]
  - file: api/app/routers/ideas.py
    symbols: [create_idea, get_idea, update_idea_stage, list_ideas]
  - file: api/app/routers/contributions.py
    symbols: [record_contribution, list_contributions]
  - file: api/app/routers/coherence.py
    symbols: [get_coherence_score]
  - file: api/app/routers/health.py
    symbols: [health_check]
  - file: docs/EXTERNAL_ENABLEMENT_TRACKING.md
    symbols: []
requirements:
  - "Script at scripts/external_proof_demo.py exercises full idea lifecycle via public API: create → stage → contribute → score"
  - "Script requires only COHERENCE_API_URL and COHERENCE_API_KEY env vars — no internal imports"
  - "All API calls use published /api/ paths, not internal or private routes"
  - "Script exit code 0 on success, non-zero with descriptive error on any API failure"
  - "docs/EXTERNAL_ENABLEMENT_TRACKING.md documents the proof run: API endpoints used, response fields verified, date of last passing run"
  - "CI step (GitHub Actions workflow) runs the proof script against https://api.coherencycoin.com on every push to main"
done_when:
  - "python3 scripts/external_proof_demo.py --api-url https://api.coherencycoin.com exits 0"
  - "Script creates a real idea, advances its stage, records a contribution, and reads back a coherence score without error"
  - "docs/EXTERNAL_ENABLEMENT_TRACKING.md shows last passing run date and all API endpoints exercised"
  - ".github/workflows/external-proof.yml exists and runs the proof script on push to main"
  - "All tests pass"
test: "COHERENCE_API_URL=http://localhost:8000 COHERENCE_API_KEY=dev-key python3 scripts/external_proof_demo.py --dry-run"
constraints:
  - "No internal imports — script must run from any machine with only requests/httpx"
  - "Script must clean up after itself: delete or close the test idea it creates"
  - "Do not expose real API keys in CI — use GitHub Secrets for COHERENCE_API_KEY"
  - "Dry-run mode (--dry-run flag) prints intended API calls without executing them"
---

> **Parent idea**: [developer-experience](../ideas/developer-experience.md)
> **Source**: [`scripts/external_proof_demo.py`](../scripts/external_proof_demo.py) | [`api/app/routers/ideas.py`](../api/app/routers/ideas.py) | [`api/app/routers/contributions.py`](../api/app/routers/contributions.py) | [`api/app/routers/coherence.py`](../api/app/routers/coherence.py)

# External Repo Milestone — Platform Proof from Outside the Kitchen

## Summary

Coherence Network claims to be an idea realization platform for *any* project. This spec closes the loop: a standalone script exercises the full idea lifecycle using only the public API, with no internal imports. If the script passes, the platform has proven it works outside its own codebase. If it fails, the failure is now visible and actionable rather than assumed.

## Purpose

Keep the external proof workflow aligned with the deployed public API contract so schema drift is caught by CI before operators need to debug live workflow failures manually.

## PLAN

**Optimizing for**: Trust — operators and prospective adopters need a reproducible, externally-visible proof that the platform's public API is complete and stable.

**System-level behavior change**: Before this spec, platform correctness is verified only from inside the monorepo (pytest, internal fixtures). After this spec, an independent script can run from any network location and verify the full lifecycle end-to-end. CI failure on the external proof script is a lagging indicator of API regressions that internal tests might miss.

### Option Thinking

| Option | Description | Tradeoff |
|--------|-------------|----------|
| A (chosen) | Standalone Python script + GitHub Actions CI | Minimal dependencies, runs anywhere, directly observable in CI logs |
| B | Separate `coherence-external-proof` GitHub repo | More realistic "external project" signal, but adds cross-repo maintenance overhead and auth complexity |
| C | Postman/Bruno collection | Visual, easy to share, but not scriptable in CI without extra tooling |

**Chosen: Option A.** A single script in `scripts/` with a GitHub Actions workflow is the simplest form that achieves the proof without cross-repo complexity. The script is self-contained and can be extracted into a separate repo later once the API surface stabilizes.

### Failure Anticipation

1. **API drift**: A new required field is added to `POST /api/ideas` without updating the script → script fails with 422. Guardrail: CI runs on every push to main, so drift is caught immediately.
2. **Auth key rotation**: `COHERENCE_API_KEY` secret expires or is rotated → CI fails with 401. Guardrail: the script prints `HTTP 401` with a clear message pointing to the GitHub Secret.

## Requirements

- [ ] **R1**: Script at `scripts/external_proof_demo.py` creates a test idea via `POST /api/ideas` using the current public `IdeaCreate` fields (`name`, `description`, `potential_value`, `estimated_cost`, `confidence`, `workspace_id`, `tags`), verifies the response contains `id` and `stage`, then advances the stage via `PATCH /api/ideas/{id}/stage`.
- [ ] **R2**: Script records a contribution for the test idea via `POST /api/contributions` and reads back the contribution list via `GET /api/contributions?idea_id={id}`, verifying the contribution appears.
- [ ] **R3**: Script reads the coherence score via `GET /api/coherence/{id}` (or equivalent endpoint) and asserts the score is a float in [0.0, 1.0].
- [ ] **R4**: Script closes/archives the test idea via the lifecycle endpoint so it does not pollute the live portfolio.
- [ ] **R5**: `--dry-run` flag prints each intended API call (method + URL + body summary) without executing, for safe local preview.
- [ ] **R6**: `docs/EXTERNAL_ENABLEMENT_TRACKING.md` is updated after each passing run (manually or via script flag `--update-tracking`) with: date, API base URL, list of endpoints exercised, pass/fail status.
- [ ] **R7**: `.github/workflows/external-proof.yml` runs `python3 scripts/external_proof_demo.py` on push to `main`, using `COHERENCE_API_KEY` from GitHub Secrets.

## Acceptance Criteria

- `cd api && .venv/bin/pytest -q tests/test_external_proof_demo.py` passes and proves the script's idea-create payload uses the current public schema.
- `python3 scripts/external_proof_demo.py --dry-run` exits 0 and prints the intended external proof lifecycle without making HTTP requests.
- `python3 scripts/validate_spec_quality.py --file specs/external-repo-milestone.md` passes.

## API Contract

The script exercises these existing endpoints. No new endpoints are added by this spec.

### `POST /api/ideas`
**Request body**
```json
{
  "name": "External Proof Test Idea [auto-cleanup]",
  "description": "Created by external_proof_demo.py - will be archived.",
  "potential_value": 1.0,
  "estimated_cost": 0.1,
  "confidence": 0.8,
  "workspace_id": "coherence-network",
  "tags": ["external-proof", "auto-cleanup"]
}
```
**Response 200** — must contain `id` (string), `stage` (string).

### `PATCH /api/ideas/{id}/stage`
**Request body** `{"stage": "spec"}`
**Response 200** — must contain updated `stage`.

### `POST /api/contributions`
**Request body**
```json
{
  "idea_id": "{id}",
  "contributor_id": "external-proof-bot",
  "type": "code",
  "description": "Proof contribution",
  "cc_amount": 1
}
```
**Response 200** — must contain `id`.

### `GET /api/coherence/{id}`
**Response 200** — must contain `score` (float, 0.0–1.0).

## Data Model

No new data models. The script uses existing Pydantic models already served by the API.

## Files to Modify

- `scripts/external_proof_demo.py`
- `api/tests/test_external_proof_demo.py`
- `specs/external-repo-milestone.md`
- `docs/EXTERNAL_ENABLEMENT_TRACKING.md`
- `.github/workflows/external-proof.yml`

| File | Action | What changes |
|------|--------|-------------|
| `scripts/external_proof_demo.py` | **Create** | Standalone proof script; exercises idea lifecycle, contributions, coherence score |
| `api/tests/test_external_proof_demo.py` | **Create** | Contract test that keeps the standalone proof script aligned with the public idea create schema |
| `docs/EXTERNAL_ENABLEMENT_TRACKING.md` | **Update** | Add last-run metadata: date, endpoints, status |
| `.github/workflows/external-proof.yml` | **Create** | CI workflow: runs proof script on push to main using secret API key |

## Out of Scope

- Replacing the public API idea model or changing the `/api/ideas` endpoint behavior.
- Adding a separate external repository for this proof script.
- Storing or rotating the production `COHERENCE_API_KEY`.

## Verification Scenarios

### Scenario 1 — Happy path against live API
```bash
export COHERENCE_API_URL=https://api.coherencycoin.com
export COHERENCE_API_KEY=<real-key>
python3 scripts/external_proof_demo.py
```
**Expected**: exit code 0, stdout shows `[PASS] idea created`, `[PASS] stage advanced`, `[PASS] contribution recorded`, `[PASS] coherence score read`, `[PASS] idea archived`.

### Scenario 2 — Dry run (no side effects)
```bash
python3 scripts/external_proof_demo.py --dry-run
```
**Expected**: exit code 0, prints each API call with `[DRY-RUN]` prefix, no HTTP requests made, no ideas created in the database.

### Scenario 3 — Missing API key
```bash
unset COHERENCE_API_KEY
python3 scripts/external_proof_demo.py
```
**Expected**: exit code 1, stderr shows `Error: COHERENCE_API_KEY environment variable not set`.

### Scenario 4 — API returns 422 (schema drift)
Simulate by pointing at a dev server with a modified `POST /api/ideas` schema. **Expected**: exit code 1, stderr shows `HTTP 422` and the full response body, so the operator knows which field is missing or invalid.

### Scenario 5 — CI runs on push to main
Push a commit to `main`. **Expected**: GitHub Actions workflow `external-proof` appears in the Actions tab, runs the script, and shows green if the live API is healthy.

## Risks and Assumptions

- Live API availability can fail independently of this payload contract; CI should surface that as an operational failure, not hide it.
- Production API keys are managed outside this spec and must remain in GitHub Secrets, never in committed files.
- The local unit test only verifies request shape; the live workflow still verifies deployed behavior.

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Live API is temporarily unavailable during CI run | Low | CI workflow retries once on network error; failure is surfaced as a CI alert, not silently skipped |
| Test ideas accumulate if script crashes before cleanup | Medium | Script uses a try/finally block to archive the test idea even on error |
| `GET /api/coherence/{id}` endpoint path differs from spec assumption | Medium | Verify exact path against `api/app/routers/coherence.py` before implementation; update spec if needed |
| API key secret expires in CI | Low | Document key rotation procedure in `docs/EXTERNAL_ENABLEMENT_TRACKING.md` |
| Script added tokens inflate context budget | Low | Script is ~150 lines; well within context budget tooling thresholds |

## Known Gaps

- Follow-up task: split operational live API availability failures from schema-contract failures in the external proof workflow output.
- Follow-up task: add a tracking update mode once `docs/EXTERNAL_ENABLEMENT_TRACKING.md` should be updated automatically by CI.

## Unblock Guidance

### Lint / test failures
```bash
cd api && python -m pytest api/tests/ -q --tb=short   # run full suite
flake8 scripts/external_proof_demo.py                 # lint the script
```
Proof: test suite exits 0; no flake8 errors.

### Missing env vars
```bash
echo $COHERENCE_API_URL   # must be set
echo $COHERENCE_API_KEY   # must be set
```
If unset: export them or add to `.env` (not committed). For CI: add as GitHub Repository Secret (`Settings → Secrets → Actions`).

### Stale branch / rebase conflict
```bash
git fetch origin main && git rebase origin/main
```
Proof: `git status` shows clean working tree.

### Flaky CI (network timeout on live API)
Retry the failing GitHub Actions run once. If it fails twice consecutively, check `curl https://api.coherencycoin.com/api/health` for service health before filing an issue.

### Missing httpx/requests dependency
```bash
pip install httpx   # or: pip install requests
```
Proof: `python3 -c "import httpx; print('ok')"` exits without ImportError.

## Maintainability

- The script is the living proof, not a report. Update it whenever the API contract changes.
- `docs/EXTERNAL_ENABLEMENT_TRACKING.md` is the human-readable audit trail — update it after each manual run or include `--update-tracking` in CI.
- If `GET /api/coherence/{id}` is renamed or restructured, the CI failure is the signal — fix the script, not the test.
