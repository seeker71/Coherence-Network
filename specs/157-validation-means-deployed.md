# Spec 157: Validation Means Deployed and Working

## Purpose

173 ideas are currently marked `validated` (manifestation_status) or `complete` (stage) after passing through spec → impl → test → review, but most of these features do not actually exist on the production site. The pipeline's definition of "complete" ends at code review, with no guarantee that artifacts were merged, deployed, or verified against production. This creates a dangerous false positive: operators believe features are live when they are not. This spec redefines validation to require deployment and production verification, adds two new pipeline stages (`deploying`, `deployed`), introduces a smoke-test phase, and provides an API to track deployment + verification status per idea.

## Requirements

- [ ] R1: Extend `IdeaStage` enum with two new stages after `REVIEWING`: `DEPLOYING` and `DEPLOYED`. The full ordered sequence becomes: `none → specced → implementing → testing → reviewing → deploying → deployed`.
- [ ] R2: Rename the current `COMPLETE` stage to `DEPLOYED` to reflect that completion requires deployment. Provide a migration path: any idea currently at `COMPLETE` stage is moved to `REVIEWING` (since deployment was never verified).
- [ ] R3: `manifestation_status = "validated"` may only be set when an idea reaches `DEPLOYED` stage **and** has a passing smoke-test record. Ideas that completed review but lack deployment verification must be set to `partial` at most.
- [ ] R4: Add a `DeploymentRecord` model tracking per-idea deployment state:
  - `idea_id: str` — the idea being tracked
  - `merged_to_main: bool` — PR merged to main branch
  - `merge_sha: str | None` — commit SHA on main
  - `deployed_to_vps: bool` — code deployed to production VPS
  - `deploy_timestamp: datetime | None` — when deployment happened
  - `smoke_test_passed: bool` — smoke test verified the feature works
  - `smoke_test_output: str | None` — test output or error message
  - `verified_by: str | None` — "automated" or human identifier
  - `verified_at: datetime | None` — when verification completed
- [ ] R5: New `POST /api/ideas/{idea_id}/deployment` endpoint to create or update a deployment record. Accepts partial updates (e.g., just `merged_to_main: true`). Returns the full `DeploymentRecord`.
- [ ] R6: New `GET /api/ideas/{idea_id}/deployment` endpoint returns the current deployment record. Returns 404 if no record exists.
- [ ] R7: New `POST /api/ideas/{idea_id}/smoke-test` endpoint triggers or records a smoke test. Accepts `{ "passed": bool, "output": str, "verified_by": str }`. On success with `passed: true`, auto-advances the idea from `deploying` to `deployed` and sets `manifestation_status` to `validated`.
- [ ] R8: New `GET /api/ideas/deployment-status` dashboard endpoint returns aggregate deployment stats: count of ideas per stage, count with passing smoke tests, count of ideas stuck at `reviewing` (merged but not deployed), and a list of ideas marked `validated` without a deployment record (the "false positive" set).
- [ ] R9: Auto-advance logic update: when a `review` task completes, the idea advances to `deploying` (not `complete`). The idea only reaches `deployed` after a passing smoke-test record is submitted.
- [ ] R10: Bulk remediation endpoint `POST /api/ideas/remediate-validation` scans all ideas with `manifestation_status = "validated"` that lack a deployment record with `smoke_test_passed = true`, and downgrades them to `partial`. Returns the count of ideas remediated.
- [ ] R11: The pipeline status UI (or CLI) must surface ideas stuck in `deploying` for more than 24 hours as "deployment stale" warnings.

## Research Inputs

- `2026-03-27` - [Spec 138: Idea Lifecycle Management](specs/138-idea-lifecycle-management.md) — defines the current `IdeaStage` enum and auto-advance logic being extended
- `2026-03-27` - [Spec 005: Project Manager Pipeline](specs/005-project-manager-pipeline.md) — pipeline task types that drive stage transitions
- `2026-03-27` - [Spec 156: Deploy Latest to VPS](specs/156-deploy-latest-to-vps.md) — existing deployment workflow to VPS that this spec formalizes as a pipeline stage
- `2026-03-27` - [CLAUDE.md Deployment Section](CLAUDE.md) — documents the current manual deploy flow (SSH → git pull → docker compose) that smoke tests must verify against

## Task Card

```yaml
goal: Redefine validation to require deployment + smoke test, add deploying/deployed stages, track deployment records per idea, and remediate 173 falsely-validated ideas.
files_allowed:
  - api/app/models/idea.py
  - api/app/models/deployment.py
  - api/app/routers/ideas.py
  - api/app/routers/deployment.py
  - api/app/services/idea_service.py
  - api/app/services/deployment_service.py
  - api/app/services/pipeline_advance_service.py
  - api/tests/test_deployment_validation.py
  - api/tests/test_idea_lifecycle.py
done_when:
  - IdeaStage enum contains DEPLOYING and DEPLOYED (COMPLETE removed or aliased)
  - POST /api/ideas/{idea_id}/deployment creates/updates deployment records
  - GET /api/ideas/{idea_id}/deployment returns deployment state
  - POST /api/ideas/{idea_id}/smoke-test records test results and auto-advances on pass
  - GET /api/ideas/deployment-status returns aggregate deployment dashboard
  - POST /api/ideas/remediate-validation downgrades falsely-validated ideas
  - Review completion advances to deploying, not complete/deployed
  - All tests in api/tests/test_deployment_validation.py pass
commands:
  - cd api && python -m pytest tests/test_deployment_validation.py -x -v
  - cd api && python -m pytest tests/test_idea_lifecycle.py -x -v
constraints:
  - Do not break existing idea CRUD endpoints
  - Backward compatibility: consumers reading manifestation_status continue to work
  - Coherence scores remain 0.0–1.0
  - Dates in ISO 8601 UTC
```

## API Contract

### `POST /api/ideas/{idea_id}/deployment`

**Request**
- `idea_id`: string (path)
- Body (all fields optional for partial update):
```json
{
  "merged_to_main": true,
  "merge_sha": "abc123def",
  "deployed_to_vps": true,
  "deploy_timestamp": "2026-03-27T12:00:00Z"
}
```

**Response 200**
```json
{
  "idea_id": "validation-means-deployed",
  "merged_to_main": true,
  "merge_sha": "abc123def",
  "deployed_to_vps": true,
  "deploy_timestamp": "2026-03-27T12:00:00Z",
  "smoke_test_passed": false,
  "smoke_test_output": null,
  "verified_by": null,
  "verified_at": null
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

### `GET /api/ideas/{idea_id}/deployment`

**Response 200**
```json
{
  "idea_id": "validation-means-deployed",
  "merged_to_main": true,
  "merge_sha": "abc123def",
  "deployed_to_vps": true,
  "deploy_timestamp": "2026-03-27T12:00:00Z",
  "smoke_test_passed": true,
  "smoke_test_output": "GET /api/health → 200 OK; feature endpoint → 200 OK",
  "verified_by": "automated",
  "verified_at": "2026-03-27T12:05:00Z"
}
```

**Response 404**
```json
{ "detail": "No deployment record for this idea" }
```

### `POST /api/ideas/{idea_id}/smoke-test`

**Request**
```json
{
  "passed": true,
  "output": "GET /api/health → 200; feature endpoint returns expected data",
  "verified_by": "automated"
}
```

**Response 200** (on pass — idea auto-advanced to `deployed`)
```json
{
  "idea_id": "validation-means-deployed",
  "smoke_test_passed": true,
  "smoke_test_output": "GET /api/health → 200; feature endpoint returns expected data",
  "verified_by": "automated",
  "verified_at": "2026-03-27T12:05:00Z",
  "stage_advanced_to": "deployed",
  "manifestation_status": "validated"
}
```

**Response 200** (on fail — idea stays at `deploying`)
```json
{
  "idea_id": "validation-means-deployed",
  "smoke_test_passed": false,
  "smoke_test_output": "GET /api/feature → 502 Bad Gateway",
  "verified_by": "automated",
  "verified_at": "2026-03-27T12:05:00Z",
  "stage_advanced_to": null,
  "manifestation_status": "partial"
}
```

**Response 404**
```json
{ "detail": "Idea not found" }
```

**Response 409**
```json
{ "detail": "Idea is not in deploying stage; current stage is 'specced'" }
```

### `GET /api/ideas/deployment-status`

**Response 200**
```json
{
  "total_ideas": 200,
  "stage_counts": {
    "none": 10,
    "specced": 15,
    "implementing": 5,
    "testing": 3,
    "reviewing": 2,
    "deploying": 12,
    "deployed": 153
  },
  "smoke_test_summary": {
    "passed": 140,
    "failed": 8,
    "pending": 5
  },
  "false_positives": {
    "count": 47,
    "idea_ids": ["idea-1", "idea-2", "..."]
  },
  "deployment_stale": {
    "count": 3,
    "ideas": [
      { "idea_id": "stale-idea", "stuck_since": "2026-03-25T10:00:00Z", "hours_stale": 50.1 }
    ]
  }
}
```

### `POST /api/ideas/remediate-validation`

**Response 200**
```json
{
  "remediated_count": 173,
  "remediated_idea_ids": ["idea-1", "idea-2", "..."],
  "new_status": "partial"
}
```

## Data Model

```yaml
DeploymentRecord:
  properties:
    idea_id: { type: string, description: "FK to idea" }
    merged_to_main: { type: boolean, default: false }
    merge_sha: { type: string, nullable: true }
    deployed_to_vps: { type: boolean, default: false }
    deploy_timestamp: { type: datetime, nullable: true, format: "ISO 8601 UTC" }
    smoke_test_passed: { type: boolean, default: false }
    smoke_test_output: { type: string, nullable: true }
    verified_by: { type: string, nullable: true, description: "'automated' or human identifier" }
    verified_at: { type: datetime, nullable: true, format: "ISO 8601 UTC" }

IdeaStage (updated enum):
  values: [none, specced, implementing, testing, reviewing, deploying, deployed]

ManifestationStatus mapping:
  none/specced/implementing: none
  testing/reviewing/deploying: partial
  deployed (with smoke test): validated
```

## Files to Create/Modify

- `api/app/models/idea.py` — extend IdeaStage enum, update IDEA_STAGE_ORDER
- `api/app/models/deployment.py` — new DeploymentRecord and related Pydantic models
- `api/app/routers/ideas.py` — add deployment-status and remediate-validation endpoints
- `api/app/routers/deployment.py` — new router for per-idea deployment and smoke-test endpoints
- `api/app/services/deployment_service.py` — business logic for deployment tracking and smoke tests
- `api/app/services/idea_service.py` — update manifestation_status logic to require deployment
- `api/app/services/pipeline_advance_service.py` — update auto-advance: review → deploying (not complete)
- `api/tests/test_deployment_validation.py` — new test file for all deployment validation flows

## Acceptance Tests

- `api/tests/test_deployment_validation.py::test_create_deployment_record` — POST creates record, returns full state
- `api/tests/test_deployment_validation.py::test_get_deployment_record` — GET returns record; 404 when missing
- `api/tests/test_deployment_validation.py::test_smoke_test_pass_advances_to_deployed` — passing smoke test moves idea to `deployed` and sets `manifestation_status = validated`
- `api/tests/test_deployment_validation.py::test_smoke_test_fail_stays_deploying` — failing smoke test keeps idea at `deploying`, status stays `partial`
- `api/tests/test_deployment_validation.py::test_smoke_test_wrong_stage_returns_409` — smoke test on idea not in `deploying` returns 409
- `api/tests/test_deployment_validation.py::test_review_completion_advances_to_deploying` — review task completion auto-advances to `deploying`, not `complete`
- `api/tests/test_deployment_validation.py::test_remediate_validation_downgrades_false_positives` — bulk remediation finds ideas with `validated` but no deployment record and sets to `partial`
- `api/tests/test_deployment_validation.py::test_deployment_status_dashboard` — dashboard returns correct stage counts, false positives, and stale deployments
- `api/tests/test_deployment_validation.py::test_partial_deployment_update` — PATCH-style update only changes submitted fields
- `api/tests/test_deployment_validation.py::test_deployment_stale_detection` — ideas in `deploying` for >24h appear in stale list

## Concurrency Behavior

- **Read operations** (GET deployment, GET dashboard): Safe for concurrent access; no locking required.
- **Write operations** (POST deployment, POST smoke-test): Last-write-wins semantics on deployment records. Smoke-test auto-advance uses optimistic check (verify stage is still `deploying` before advancing).
- **Remediation** (POST remediate-validation): Bulk operation; should be idempotent. Running twice produces the same result (already-partial ideas are unchanged).

## Verification

```bash
# Unit and integration tests
cd api && python -m pytest tests/test_deployment_validation.py -x -v

# Verify IdeaStage enum has new stages
cd api && python -c "from app.models.idea import IdeaStage; assert hasattr(IdeaStage, 'DEPLOYING'); assert hasattr(IdeaStage, 'DEPLOYED'); print('OK')"

# Verify deployment endpoints respond
cd api && uvicorn app.main:app --port 8099 &
sleep 2
curl -s -X POST http://localhost:8099/api/ideas/test-idea/deployment -H 'Content-Type: application/json' -d '{"merged_to_main": true}' | python -m json.tool
curl -s http://localhost:8099/api/ideas/deployment-status | python -m json.tool
kill %1

# Verify remediation (manual)
curl -s -X POST http://localhost:8099/api/ideas/remediate-validation | python -m json.tool
```

## Out of Scope

- Automated deployment triggering (this spec tracks deployment state, it does not execute deploys)
- CI/CD pipeline integration (deployment records are submitted via API, not pushed by CI)
- Rollback tracking (a future spec can add rollback records)
- Per-endpoint smoke test definitions (smoke tests are recorded as pass/fail strings; structured test definitions are a follow-up)
- Web UI for the deployment dashboard (API-only for now)

## Risks and Assumptions

- **Risk**: Renaming `COMPLETE` to `DEPLOYED` and adding `DEPLOYING` may break consumers that check for `stage == "complete"`. **Mitigation**: Provide a one-time migration and document the change. Add a `COMPLETE` alias that maps to `DEPLOYED` during a transition period.
- **Risk**: Bulk remediation of 173 ideas may cause confusion if operators are not warned. **Mitigation**: The remediation endpoint returns the full list of affected idea IDs, and should be gated behind confirmation or admin-only access.
- **Risk**: Smoke tests depend on production being accessible. If VPS is down, all smoke tests fail. **Mitigation**: Smoke test failures do not revert deployment records; they can be retried. The `deployment_stale` metric alerts operators.
- **Assumption**: The existing `IdeaStage` auto-advance logic in `pipeline_advance_service.py` can be extended without breaking the task-completion hook chain.
- **Assumption**: Deployment records can be stored in the same PostgreSQL database as ideas (no need for a separate store).
- **Assumption**: The current manual deploy flow (SSH → git pull → docker compose) will continue to be the primary deployment mechanism; this spec wraps it with tracking, not replacement.

## Known Gaps and Follow-up Tasks

- **Automated smoke test runner**: This spec only records smoke test results. A follow-up task should implement an automated runner that hits production endpoints after deploy and submits results via the smoke-test API. (`Follow-up task: task_automated_smoke_runner`)
- **CI/CD integration**: A follow-up should have the merge/deploy pipeline automatically call `POST /api/ideas/{id}/deployment` with merge SHA and deploy timestamp. (`Follow-up task: task_cicd_deployment_tracking`)
- **Historical deployment audit**: Need a one-time script to audit which of the 173 "validated" ideas actually have code on main and deployed to production vs. which are entirely phantom. (`Follow-up task: task_historical_deployment_audit`)
- **Web dashboard**: The deployment-status endpoint needs a UI in the cockpit. (`Follow-up task: task_deployment_dashboard_ui`)
- **Rollback tracking**: If a deploy is rolled back, the deployment record should reflect that the feature is no longer live. (`Follow-up task: task_rollback_tracking`)

## Failure/Retry Reflection

- **Failure mode**: Smoke test hits a transient 502 during VPS restart → incorrectly marks feature as not working.
  - **Blind spot**: No retry logic for transient failures.
  - **Next action**: Allow smoke-test endpoint to accept a `retry_count` field; surface "flaky" results in the dashboard.

- **Failure mode**: Deployment record created (merged_to_main: true) but VPS deploy never happens → idea stuck at `deploying` indefinitely.
  - **Blind spot**: No automated timeout or escalation.
  - **Next action**: The `deployment_stale` detection (R11) mitigates this by surfacing stale items; a follow-up should add automated alerts.

- **Failure mode**: Bulk remediation runs while pipeline is actively advancing ideas → race condition between remediation downgrade and auto-advance upgrade.
  - **Blind spot**: No locking between remediation and auto-advance.
  - **Next action**: Remediation should check deployment record existence atomically with status update (single transaction).

## Decision Gates

- **Human approval required**: Before running `POST /api/ideas/remediate-validation` in production for the first time, an operator must review the list of ideas that will be downgraded. The endpoint should support a `dry_run=true` query parameter that returns the list without making changes.
- **Human approval required**: The removal/renaming of `COMPLETE` stage affects existing consumers. The migration plan must be reviewed before implementation.
