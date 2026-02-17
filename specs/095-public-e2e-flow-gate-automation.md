# Spec: Public E2E Flow Gate Automation

## Purpose

The system currently allows changes to pass when technical checks are green but real public user journeys are not validated end to end. This spec defines enforceable public E2E validation gates for merge classes so contributors and automation only advance when real behavior is confirmed in deployed environments. It reduces high-cost regressions where deployment appears healthy but core usage flows are broken.

## Requirements

- [ ] Define minimum required public E2E journeys per merge class (`runtime_feature`, `runtime_fix`, `process_only`, `docs_only`) with clear pass/fail conditions.
- [ ] Require each journey to be machine-verifiable (API evidence) and human-verifiable (web path evidence) before contributor acknowledgment is marked passed.
- [ ] Persist E2E validation evidence (journey id, endpoints/pages checked, observed status, timestamps, commit sha, environment) and expose it via API/web.

## API Contract (if applicable)

### `POST /api/gates/public-deploy-contract`

**Request**
- Existing contract request payload
- Additional optional query/body field: `journey_profile` (`runtime_feature` | `runtime_fix` | `process_only` | `docs_only`)

**Response 200**
```json
{
  "result": "public_contract_passed",
  "journey_profile": "runtime_feature",
  "journeys": [
    {
      "journey_id": "web_navigate_core_pages",
      "passed": true,
      "evidence": ["/", "/ideas", "/specs", "/usage"]
    },
    {
      "journey_id": "api_usage_lineage_roundtrip",
      "passed": true,
      "evidence": ["/api/runtime/events", "/api/runtime/endpoints/summary"]
    }
  ]
}
```

If not applicable, write: `N/A - no API contract changes in this spec.`

## Data Model (if applicable)

```yaml
PublicE2EJourneyEvidence:
  properties:
    id: { type: string }
    commit_sha: { type: string }
    journey_profile: { type: string }
    journey_id: { type: string }
    passed: { type: boolean }
    environment: { type: string }
    evidence_refs:
      type: array
      items: { type: string }
    validated_at: { type: string, format: date-time }
```

## Files to Create/Modify

- `specs/095-public-e2e-flow-gate-automation.md` - requirements, acceptance, and verification contract
- `.github/workflows/change-contract.yml` - enforce journey profile for post-merge contract
- `api/app/services/release_gate_service.py` - evaluate profile-specific public E2E journeys and store evidence
- `api/app/routers/gates.py` - expose journey evidence through gate endpoints
- `web/app/gates/page.tsx` - show profile + journey-level pass/fail evidence for humans

## Acceptance Tests

- `api/tests/test_release_gate_service.py::test_evaluate_public_deploy_contract_requires_runtime_feature_journeys`
- `api/tests/test_release_gate_service.py::test_evaluate_public_deploy_contract_allows_docs_only_minimal_profile`
- `api/tests/test_gates_api.py::test_public_contract_response_includes_journey_evidence`
- Manual validation: load `/gates` on public web and verify journey-level evidence is visible and matches API payload.

## Verification

```bash
cd api && pytest -q tests/test_release_gate_service.py tests/test_gates_api.py
cd api && python scripts/validate_spec_quality.py --file specs/095-public-e2e-flow-gate-automation.md
curl -fsS https://coherence-network-production.up.railway.app/api/gates/public-deploy-contract | jq .
curl -fsS https://coherence-web-production.up.railway.app/gates | head -c 500
```

## Out of Scope

- Browser automation stack replacement (Playwright/Cypress migration) beyond current gate framework.
- Contributor identity/reputation weighting changes unrelated to public E2E evidence.

## Risks and Assumptions

- Risk: profile strictness may block throughput if journeys are over-specified; mitigation is profile-based scope and explicit downgrade paths.
- Assumption: public API/web endpoints used for journeys remain stable enough for deterministic checks.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_public_e2e_profile_tuning_001` to tune profile strictness from observed false-positive/false-negative rates.
- Follow-up task: `task_public_e2e_web_probe_002` to add richer web interaction evidence beyond reachability.

## Decision Gates (if any)

- Approve final journey profile matrix (`runtime_feature`, `runtime_fix`, `process_only`, `docs_only`) before enforcement is switched from soft to hard fail.
