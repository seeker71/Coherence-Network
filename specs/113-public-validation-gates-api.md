# Spec: Public Validation Gates API

## Purpose

Expose a first-class API surface that reports, stores, and replays public validation gate results so that the `public-validation-gates-api` idea is no longer stuck in the spec stage. The contract must let automation confirm gate readiness (process), tie evidence to concrete FastAPI + workflow behavior (implementation), and prove the journeys succeeded across API + web probes (validation) before downstream tasks depend on it.

## Requirements

- [ ] Provide `GET /api/gates/public-validation` that returns per-journey-profile results (`runtime_feature`, `runtime_fix`, `process_only`, `docs_only`) including last run metadata, pass/fail state, evidence references, triggering branch/commit, and timestamps.
- [ ] Provide `POST /api/gates/public-validation/run` that triggers the release gate service to execute the journeys for the requested profile, persists the evidence payload, and returns the same shape as the GET response for determinism.
- [ ] Persist gate runs in a `PublicValidationGateRun` record (FastAPI service + JSONL evidence file) so runs are queryable by profile, branch, and commit, and retain at least the last 20 runs per profile.
- [ ] Link the stored evidence to the delivery flow so `/api/inventory/flow` rows for `public-validation-gates-api` (and any idea referencing this spec) report `process.tracked = true`, `implementation.tracked = true`, and `validation.tracked = true` as soon as at least one persisted gate run exists for the idea’s active profile.
- [ ] Extend `/gates` web UI to show the new API output (per-profile cards with latest evidence) so humans can audit public validation alongside PR/change-contract gates.

## API Contract (if applicable)

### `GET /api/gates/public-validation`

**Query Parameters**
- `profile` (optional enum) — limit to a single profile.
- `branch` (optional string) — filter by branch/ref recorded on gate runs.
- `limit` (optional int, default 5, max 20) — number of historical runs per profile.

**Response 200**
```json
{
  "profiles": [
    {
      "profile": "runtime_feature",
      "latest_result": "passed",
      "last_run_at": "2026-02-27T02:15:00Z",
      "commit_sha": "abc123",
      "branch": "codex/unblock-public-validation",
      "journeys": [
        {"journey_id": "api_health", "passed": true, "evidence": ["/api/health"]},
        {"journey_id": "web_core_pages", "passed": true, "evidence": ["/", "/ideas", "/specs"]}
      ],
      "history": [
        { "run_id": "pvg_001", "result": "passed", "validated_at": "2026-02-27T02:15:00Z" }
      ]
    }
  ]
}
```

### `POST /api/gates/public-validation/run`

**Body**
```json
{
  "journey_profile": "runtime_feature",
  "branch": "codex/unblock-public-validation",
  "commit_sha": "abc123",
  "trigger_source": "change_contract"
}
```

**Response 200**
```json
{
  "result": "public_validation_passed",
  "journey_profile": "runtime_feature",
  "run_id": "pvg_001",
  "journeys": [
    {"journey_id": "api_health", "passed": true, "evidence": ["/api/health"]},
    {"journey_id": "web_core_pages", "passed": true, "evidence": ["/", "/ideas", "/specs"]}
  ],
  "validated_at": "2026-02-27T02:15:00Z"
}
```

## Data Model (if applicable)

```yaml
PublicValidationGateRun:
  properties:
    run_id: { type: string }
    journey_profile: { type: string, enum: [runtime_feature, runtime_fix, process_only, docs_only] }
    branch: { type: string }
    commit_sha: { type: string }
    trigger_source: { type: string, enum: [change_contract, manual, workflow, api] }
    journeys:
      type: array
      items:
        type: object
        properties:
          journey_id: { type: string }
          passed: { type: boolean }
          evidence_refs:
            type: array
            items: { type: string }
    result: { type: string, enum: [public_validation_passed, public_validation_failed] }
    validated_at: { type: string, format: date-time }
```

## Files to Create/Modify

- `api/app/routers/gates.py` — register the new GET/POST public validation endpoints.
- `api/app/services/release_gate_service.py` — execute journey profiles, persist `PublicValidationGateRun`, expose query helpers.
- `api/app/services/inventory_service.py` — surface gate run linkage inside `/api/inventory/flow` process/implementation/validation sections for the `public-validation-gates-api` idea.
- `api/tests/test_gates_api.py` & `api/tests/test_release_gate_service.py` — cover API contract and persistence logic.
- `api/tests/test_inventory_api.py` — verify flow rows flip `process`, `implementation`, and `validation` when gate runs exist.
- `docs/PR-GATES-AND-PUBLIC-VALIDATION.md` — document the new API usage for humans and workflows.
- `web/app/gates/page.tsx` — render the new per-profile cards and evidence links.
- `.github/workflows/change-contract.yml` & `scripts/validate_pr_to_public.py` — optional trigger path to call POST endpoint when waiting on public validation.

## Acceptance Tests

- `api/tests/test_gates_api.py::test_get_public_validation_gates_returns_profiles_with_evidence`
- `api/tests/test_gates_api.py::test_post_public_validation_run_triggers_execution_and_persists_record`
- `api/tests/test_release_gate_service.py::test_public_validation_gate_run_persists_history_and_rolls_retention`
- `api/tests/test_inventory_api.py::test_flow_row_for_public_validation_gates_tracks_process_and_validation`
- Manual: `cd web && npm run build`, then load `/gates` in staging/public and confirm per-profile cards display the API payload with timestamps and evidence links.

## Verification

```bash
cd api && pytest -q tests/test_gates_api.py tests/test_release_gate_service.py tests/test_inventory_api.py -k public_validation_gate
cd api && python scripts/validate_spec_quality.py --file specs/113-public-validation-gates-api.md
cd web && npm run build
```

## Out of Scope

- Replacing the existing change-contract workflow beyond the POST trigger.
- Implementing new browser automation stacks; reuse the existing probes defined in spec 095.
- Altering payout or contributor acknowledgment logic.

## Risks and Assumptions

- Risk: storing only 20 runs per profile may hide long-term regressions; mitigation is exporting to system-audit logs before pruning.
- Risk: gating endpoints become a bottleneck if POST is overused; mitigation is to gate POST via workflow automation only.
- Assumption: release gate service already knows how to execute `runtime_feature`, `runtime_fix`, `process_only`, and `docs_only` journeys from spec 095.
- Assumption: `/gates` web UI can reuse existing shadcn components without new dependencies.

## Known Gaps and Follow-up Tasks

- Follow-up task `task_public_validation_gates_alerting` — add alerting when the latest gate run for a profile fails longer than 15 minutes.
- Follow-up task `task_public_validation_gates_history_export` — stream gate history into docs/system_audit for long-term auditing.

## Decision Gates (if any)

- Confirm which webhook/workflow is authorized to call `POST /api/gates/public-validation/run` before the endpoint is exposed publicly.
