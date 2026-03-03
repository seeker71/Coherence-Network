# Spec: Value Lineage and Payout Attribution

## Purpose

Create a verifiable, machine-readable chain from **idea -> research -> spec creation/upgrade -> implementation -> usage/value signals -> payout preview** so contributors can be rewarded based on measurable system value and energy-balanced contribution quality.

## Requirements

- [ ] API supports creating and fetching a lineage link that binds idea/spec/implementation references, contributor roles, and explicit stage investments.
- [ ] API supports appending usage/value events to a lineage link.
- [ ] API exposes valuation summary for a lineage link (measured value, estimated cost, ROI ratio, event count).
- [ ] API supports payout preview from valuation using explicit stage weights and returns per-contributor attribution.
- [ ] Payout preview applies optimization objectives for coherence, energy flow, awareness, friction relief, and stage-balance.
- [ ] All artifacts are persisted in a durable local store for auditability.
- [ ] Missing lineage id returns 404 with `{ "detail": "Lineage link not found" }`.

## API Contract

### `POST /api/value-lineage/links`

Create a lineage link.

**Request**
```json
{
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "research": "rita",
    "spec": "bob",
    "spec_upgrade": "sam",
    "implementation": "carol",
    "review": "dave"
  },
  "investments": [
    {
      "stage": "research",
      "contributor": "rita",
      "energy_units": 3.0,
      "coherence_score": 0.9,
      "awareness_score": 0.8,
      "friction_score": 0.1
    },
    {
      "stage": "implementation",
      "contributor": "carol",
      "energy_units": 4.0,
      "coherence_score": 0.85,
      "awareness_score": 0.7,
      "friction_score": 0.2
    }
  ],
  "estimated_cost": 120.0
}
```

**Response 201**
```json
{
  "id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "research": "rita",
    "spec": "bob",
    "spec_upgrade": "sam",
    "implementation": "carol",
    "review": "dave"
  },
  "investments": [
    {
      "stage": "research",
      "contributor": "rita",
      "energy_units": 3.0,
      "coherence_score": 0.9,
      "awareness_score": 0.8,
      "friction_score": 0.1
    },
    {
      "stage": "implementation",
      "contributor": "carol",
      "energy_units": 4.0,
      "coherence_score": 0.85,
      "awareness_score": 0.7,
      "friction_score": 0.2
    }
  ],
  "estimated_cost": 120.0
}
```

### `GET /api/value-lineage/links/{lineage_id}`

Fetch lineage link.

**Response 200**
```json
{
  "id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "research": "rita",
    "spec": "bob",
    "spec_upgrade": "sam",
    "implementation": "carol",
    "review": "dave"
  },
  "investments": [
    {
      "stage": "research",
      "contributor": "rita",
      "energy_units": 3.0,
      "coherence_score": 0.9,
      "awareness_score": 0.8,
      "friction_score": 0.1
    },
    {
      "stage": "implementation",
      "contributor": "carol",
      "energy_units": 4.0,
      "coherence_score": 0.85,
      "awareness_score": 0.7,
      "friction_score": 0.2
    }
  ],
  "estimated_cost": 120.0
}
```

**Response 404**
```json
{ "detail": "Lineage link not found" }
```

### `POST /api/value-lineage/links/{lineage_id}/usage-events`

Append measurable value signal to lineage link.

**Request**
```json
{
  "source": "api",
  "metric": "adoption_events",
  "value": 45.5
}
```

**Response 201**
```json
{
  "id": "evt_123",
  "lineage_id": "lnk_123",
  "source": "api",
  "metric": "adoption_events",
  "value": 45.5,
  "captured_at": "2026-02-15T00:00:00Z"
}
```

### `GET /api/value-lineage/links/{lineage_id}/valuation`

Return summarized measured value and ROI.

**Response 200**
```json
{
  "lineage_id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "measured_value_total": 100.0,
  "estimated_cost": 120.0,
  "roi_ratio": 0.8333,
  "event_count": 2
}
```

### `POST /api/value-lineage/links/{lineage_id}/payout-preview`

Compute payout attribution for contributors.

**Request**
```json
{
  "payout_pool": 1000.0
}
```

**Response 200**
```json
{
  "lineage_id": "lnk_123",
  "schema_version": "energy-balanced-v1",
  "payout_pool": 1000.0,
  "measured_value_total": 100.0,
  "estimated_cost": 120.0,
  "roi_ratio": 0.8333,
  "weights": {
    "idea": 0.1,
    "research": 0.2,
    "spec": 0.2,
    "spec_upgrade": 0.15,
    "implementation": 0.5,
    "review": 0.2
  },
  "objective_weights": {
    "coherence": 0.35,
    "energy_flow": 0.2,
    "awareness": 0.2,
    "friction_relief": 0.15,
    "balance": 0.1
  },
  "signals": {
    "coherence": 0.45,
    "energy_flow": 0.45,
    "awareness": 0.5,
    "friction": 0.2,
    "balance": 0.9
  },
  "payouts": [
    {
      "role": "research",
      "contributor": "rita",
      "amount": 240.0,
      "energy_units": 3.0,
      "effective_weight": 0.24
    },
    {
      "role": "implementation",
      "contributor": "carol",
      "amount": 760.0,
      "energy_units": 4.0,
      "effective_weight": 0.76
    }
  ]
}
```

## Data Model

```yaml
LineageLink:
  id: string
  idea_id: string
  spec_id: string
  implementation_refs: string[]
  contributors:
    idea: string?
    research: string?
    spec: string?
    spec_upgrade: string?
    implementation: string?
    review: string?
  investments:
    - stage: enum(idea, research, spec, spec_upgrade, implementation, review)
      contributor: string
      energy_units: number (> 0)
      coherence_score: number (0..1)
      awareness_score: number (0..1)
      friction_score: number (0..1)
  estimated_cost: number

UsageEvent:
  id: string
  lineage_id: string
  source: string
  metric: string
  value: number
  captured_at: datetime
```

## Validation Contract

- Tests define contract in `api/tests/test_value_lineage.py`.
- Required behaviors:
  - Create + fetch lineage link works with persistence.
  - Usage events accumulate measured value.
  - Valuation computes `roi_ratio = measured_value_total / estimated_cost` (0 when estimated_cost is 0).
  - Payout preview allocates by stage weights among present contributors and explicit investments.
  - Payout preview includes optimization objective weights and calculated system signals.
  - For contributors sharing a stage, higher coherence/awareness and lower friction can outweigh raw energy input.
  - Missing lineage returns 404 exact detail message.
- Public deploy gate must include a live E2E transaction check for this flow and fail deployment contract when invariants break.

## Files to Create/Modify

- `api/app/models/value_lineage.py` — request/response models
- `api/app/services/value_lineage_service.py` — persistence + valuation + payout logic
- `api/app/routers/value_lineage.py` — API endpoints
- `api/app/main.py` — router wiring
- `api/tests/test_value_lineage.py` — contract tests
- `api/app/services/release_gate_service.py` — public E2E transaction gate check
- `api/tests/test_release_gate_service.py` — deploy contract coverage for value-lineage E2E
- `api/app/routers/gates.py` — machine-access endpoint for public deploy contract report
- `web/app/gates/page.tsx` — human-access report viewer for public deploy contract

## Acceptance Tests

- `api/tests/test_value_lineage.py::test_create_and_get_lineage_link` validates persisted lineage links include contributors and optional investment payloads.
- `api/tests/test_value_lineage.py::test_usage_events_roll_up_to_valuation` validates usage event aggregation and ROI ratio calculation.
- `api/tests/test_value_lineage.py::test_payout_preview_uses_role_weights` validates default stage/objective weighting signals in payout preview responses.
- `api/tests/test_value_lineage.py::test_payout_preview_supports_stage_investments` validates investment-stage attribution and stage-peer ranking behavior.
- `api/tests/test_value_lineage.py::test_lineage_404_contract` validates not-found behavior and detail contract.
- `api/tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections` validates inventory reporting includes value-lineage core sections.
- `api/tests/test_release_gate_service.py::test_evaluate_public_deploy_contract_report_live_shape` validates the public deploy contract includes `railway_value_lineage_e2e`.

## Verification

```bash
cd api && pytest -q tests/test_value_lineage.py
cd api && pytest -q tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections
cd api && pytest -q tests/test_release_gate_service.py::test_evaluate_public_deploy_contract_report_live_shape
python3 scripts/validate_spec_quality.py --file specs/048-value-lineage-and-payout-attribution.md
./scripts/verify_web_api_deploy.sh
curl -fsS https://coherence-network-production.up.railway.app/api/gates/public-deploy-contract | jq .
```

Manual verification:
- Create a lineage link, append at least one usage event, and verify payout preview from the same `lineage_id`.
- Confirm `GET /api/value-lineage/links/{lineage_id}/valuation` returns deterministic totals and ROI.

## Out of Scope

- On-chain payout execution
- Fiat/crypto settlement integration
- Dynamic governance voting/weight tuning beyond static defaults

## Risks and Assumptions

- Risk: usage/value signals may be noisy and could overstate value if event sources are not normalized.
- Risk: payout attribution can be gamed if contributor-role assignment is not audited.
- Assumption: static role weights are acceptable for initial release and can be governed later.
- Assumption: persisted lineage and usage data remain available through API restarts and deploys.

## Known Gaps and Follow-up Tasks

- Follow-up: add stronger anti-fraud/event-source trust scoring for usage events.
- Follow-up: add role-weight governance policy and signed audit trail for role assignment changes.
