# Spec: MVP Cost Tracking and Acceptance Proof

## Purpose

The MVP must prove that idea-to-implementation-to-review workflows can be accepted using objective evidence while tracking both infrastructure and external provider costs. This prevents ambiguous completion claims, enables owner acceptance decisions, and provides the minimum revenue-readiness signal for unit economics.

## Requirements

- [ ] Runtime task tool-call telemetry records `infrastructure_cost_usd`, `external_provider_cost_usd`, and `total_cost_usd` for each execution event linked to a `task_id`.
- [ ] Review completion telemetry records acceptance evidence fields (`review_pass_fail`, verified assertion counts when present) so acceptance can be audited without manual log parsing.
- [ ] API exposes a single MVP acceptance summary endpoint returning acceptance counts and cost rollups (external, infrastructure, total) for a time window.
- [ ] API exposes an external judge endpoint with explicit assertion checks and a single pass/fail decision for acceptance claims.
- [ ] External judge supports publicly trusted validator attestations (Ed25519 signature quorum from configured public keys) and can enforce this as a required gate.
- [ ] External judge supports public transparency-log anchoring of the acceptance claim hash (trusted domain allowlist + hash presence verification) and can enforce this as a required gate.
- [ ] MVP acceptance economics and trust gates are loaded from configuration data (`api/config/mvp_acceptance_policy.json`) rather than environment variables.
- [ ] Summary and judge responses include base budget inputs (`railway_base_budget_usd`, `provider_base_budget_usd`) and revenue/reinvestment calculations.
- [ ] Judge responses include a trust-adjusted revenue proof (`estimated_revenue_usd`, `trust_adjusted_revenue_usd`, uplift, and payout readiness) so improved trust directly maps to measurable revenue potential.
- [ ] Tasks evidence UI shows a task-level proof panel with acceptance verdict and cost breakdown sourced from runtime telemetry.
- [ ] Automated tests validate the endpoint contract and cost/acceptance evidence behavior.

## Research Inputs (Required)

- `2026-03-06` - [Coherence Runtime API implementation](https://github.com/seeker71/Coherence-Network) - Existing runtime telemetry already carries task metadata and is the lowest-friction integration point.
- `2026-03-06` - [Coherence task execution flow](https://github.com/seeker71/Coherence-Network) - Agent execution paths already emit tool-call and completion events that can be extended with tiny deltas.

## Task Card (Required)

```yaml
goal: add MVP acceptance proof with external and infrastructure cost tracking
files_allowed:
  - specs/114-mvp-cost-and-acceptance-proof.md
  - api/config/mvp_acceptance_policy.json
  - api/app/services/agent_execution_service.py
  - api/app/services/agent_execution_codex_service.py
  - api/app/services/agent_service_completion_tracking.py
  - api/app/services/runtime_service.py
  - api/app/routers/runtime.py
  - api/tests/test_runtime_api.py
  - web/app/tasks/types.ts
  - web/app/tasks/page.tsx
  - web/app/tasks/EvidenceTrail.tsx
done_when:
  - runtime tool-call events include infrastructure/external/total cost fields per task
  - review completion events include acceptance pass/fail evidence metadata
  - /api/runtime/mvp/acceptance-summary returns acceptance + cost rollups
  - /api/runtime/mvp/acceptance-judge returns contract assertions + pass/fail
  - acceptance policy values are sourced from api/config/mvp_acceptance_policy.json
  - when public-validator requirement is enabled, judge fails without quorum and passes with valid quorum signatures
  - when transparency-anchor requirement is enabled, judge fails without valid anchor and passes with valid trusted-log anchor
  - when trust-adjusted revenue coverage is required, judge fails without trust evidence and passes once trust evidence activates revenue uplift that covers cost
  - tasks evidence UI renders acceptance proof and cost breakdown for selected task
  - targeted tests pass for runtime endpoint and acceptance proof behavior
commands:
  - cd api && pytest -q tests/test_runtime_api.py
  - cd web && npm run -s lint
constraints:
  - keep implementation as tiny deltas on existing runtime telemetry model
  - do not remove or rename existing telemetry fields used by current tests
  - do not modify files outside files_allowed
```

## API Contract (if applicable)

### `GET /api/runtime/mvp/acceptance-summary`

**Request**
- Query `seconds` (optional, default `86400`, min `60`, max `2592000`)
- Query `limit` (optional, default `2000`, min `100`, max `5000`)

**Response 200**
```json
{
  "window_seconds": 86400,
  "event_limit": 2000,
  "totals": {
    "tasks_seen": 12,
    "completed_tasks": 8,
    "accepted_reviews": 3,
    "acceptance_rate": 0.375,
    "infrastructure_cost_usd": 0.124,
    "external_provider_cost_usd": 0.452,
    "total_cost_usd": 0.576
  },
  "tasks": [
    {
      "task_id": "task_abc",
      "task_type": "review",
      "final_status": "completed",
      "review_pass_fail": "PASS",
      "verified_assertions": "4/4",
      "infrastructure_cost_usd": 0.01,
      "external_provider_cost_usd": 0.03,
      "total_cost_usd": 0.04
    }
  ]
}
```

If no telemetry exists in window, return `totals` with zeros and `tasks: []`.

### `GET /api/runtime/mvp/acceptance-judge`

**Request**
- Query `seconds` (optional, default `86400`, min `60`, max `2592000`)
- Query `limit` (optional, default `2000`, min `100`, max `5000`)

**Response 200**
```json
{
  "pass": true,
  "assertions": [
    {
      "id": "accepted_reviews_minimum",
      "expected": ">= 1",
      "actual": "1",
      "pass": true
    }
  ],
  "summary": {},
  "contract": {
    "judge_id": "coherence_mvp_acceptance_judge_v1",
    "external_validation_endpoint": "/api/runtime/mvp/acceptance-judge",
    "business_proof": {
      "trust": {
        "public_validator_pass": true,
        "public_transparency_anchor_pass": true
      },
      "revenue": {
        "estimated_revenue_usd": 0.1,
        "trust_adjusted_revenue_usd": 0.15625,
        "trust_revenue_uplift_usd": 0.05625
      },
      "payout_ready": true
    },
    "measurement": {}
  }
}
```

## Data Model (if applicable)

```yaml
RuntimeEvent.metadata:
  infrastructure_cost_usd: float >= 0
  external_provider_cost_usd: float >= 0
  total_cost_usd: float >= 0
  review_pass_fail: "PASS" | "FAIL" | ""   # completion events when review output includes PASS_FAIL
  verified_assertions: string               # completion events when review output includes VERIFIED field
MvpSummary:
  budget:
    railway_base_budget_usd: float >= 0
    provider_base_budget_usd: float >= 0
    base_budget_usd: float >= 0
  revenue:
    revenue_per_accepted_review_usd: float >= 0
    estimated_revenue_usd: float >= 0
  reinvestment:
    reinvestment_ratio: float [0,1]
    reinvestment_pool_usd: float >= 0
    allocations:
      infrastructure_usd: float >= 0
      code_quality_usd: float >= 0
      product_delivery_usd: float >= 0
MvpJudgeContract.business_proof:
  trust:
    public_validator_pass: bool
    public_transparency_anchor_pass: bool
  revenue:
    estimated_revenue_usd: float >= 0
    trust_adjusted_revenue_usd: float >= 0
    trust_revenue_uplift_usd: float >= 0
    trust_multiplier: float >= 1
    trust_adjusted_operating_surplus_usd: float
  payout_ready: bool
```

## Files to Create/Modify

- `specs/114-mvp-cost-and-acceptance-proof.md` - MVP contract and acceptance checklist
- `api/config/mvp_acceptance_policy.json` - config data for acceptance thresholds, economics, and trust gates
- `api/app/services/agent_execution_service.py` - include external/infrastructure/total cost fields for tool-call runtime events
- `api/app/services/agent_execution_codex_service.py` - include external/infrastructure/total cost fields for codex tool-call events
- `api/app/services/agent_service_completion_tracking.py` - derive and persist review acceptance metadata in completion events
- `api/app/services/runtime_service.py` - build acceptance summary aggregation from runtime telemetry
- `api/app/routers/runtime.py` - expose `/api/runtime/mvp/acceptance-summary`
- `api/app/routers/runtime.py` - expose `/api/runtime/mvp/acceptance-judge`
- `api/tests/test_runtime_api.py` - contract tests for summary and metadata behavior
- `web/app/tasks/types.ts` - add fields for acceptance/cost proof rendering
- `web/app/tasks/page.tsx` - compute selected-task proof metrics from runtime events
- `web/app/tasks/EvidenceTrail.tsx` - render acceptance verdict and cost proof block

## Acceptance Tests

- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_summary_reports_cost_rollups_and_accepted_reviews`
- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_summary_empty_window_returns_zero_totals`
- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_contract_passes_when_budget_and_revenue_cover_cost`
- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_requires_public_validator_quorum`
- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_requires_public_transparency_anchor`
- `api/tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_trust_adjusted_revenue_proves_uplift_and_payout_readiness`

## Verification

Run:

```bash
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_summary_reports_cost_rollups_and_accepted_reviews
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_summary_empty_window_returns_zero_totals
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_contract_passes_when_budget_and_revenue_cover_cost
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_requires_public_validator_quorum
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_requires_public_transparency_anchor
cd api && pytest -q tests/test_runtime_api.py::test_runtime_mvp_acceptance_judge_trust_adjusted_revenue_proves_uplift_and_payout_readiness
cd api && pytest -q tests/test_runtime_api.py
```

## Out of Scope

- Historical billing reconciliation against provider invoices.
- Full accounting-grade infra allocation across services outside runtime events.
- Subscription pricing and invoicing product UX.

## Risks and Assumptions

- Runtime event metadata must remain available for the selected window; low event limits can undercount totals.
- External provider cost is estimated from token usage when no provider-billed amount exists.

## Known Gaps and Follow-up Tasks

- Follow-up task: wire summary endpoint into a dedicated portfolio/revenue dashboard.
- Follow-up task: add provider-specific exact billing adapters for non-estimated external costs.
- Follow-up task: support multiple transparency logs with Merkle inclusion proof validation.
- **External validator governance**: Use independent third-party validator keys and require quorum from multiple orgs so external entities can audit and trust the judge. Config supports multiple keys and quorum; see `docs/MVP-EXTERNAL-VALIDATORS.md` for onboarding and attestation flow. Optional follow-up: attestation submission API so third parties do not need config file access.

## Failure/Retry Reflection

- Failure mode: review outputs omit `PASS_FAIL` or `VERIFIED` lines.
- Blind spot: relying on free-form output without deterministic extraction.
- Next action: keep extraction tolerant and default to empty strings while preserving raw completion status.

## Decision Gates (if any)

- N/A for MVP implementation in current runtime telemetry architecture.
