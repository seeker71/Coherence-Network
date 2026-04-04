---
idea_id: value-attribution
status: partial
source:
  - file: api/app/routers/onboarding.py
    symbols: [register(), get_session(), upgrade()]
  - file: api/app/services/onboarding_service.py
    symbols: [register(), resolve_session()]
  - file: api/app/services/governance_service.py
    symbols: [create_change_request(), vote_on_change_request()]
  - file: api/app/models/governance.py
    symbols: [ChangeRequest, ChangeRequestVote, VoteDecision]
---

# Spec 094 — Contributor Onboarding and Governed Change Flow

## Goal

Enable a new human contributor to register, propose idea/spec/question updates, get attribution, and pass through a yes/no review flow that can be executed by humans or machines.

## Problem

- Existing web pages were mostly read-only for contributors, ideas, and specs.
- There was no explicit change-request workflow with voting and approval state.
- Contributors could not follow one clear path from onboarding to attributable change.

## Scope

- Add idea creation and idea-question creation APIs.
- Add structured spec registry APIs (`create`, `update`, `list`, `get`) with contributor attribution fields.
- Add governance APIs for:
  - submitting change requests,
  - listing change requests,
  - casting yes/no votes,
  - automatic apply on approval (default minimum approvals = 1).
- Add web page `/contribute` as human console for:
  - contributor registration,
  - submitting idea/spec/question change requests,
  - voting yes/no as human or machine reviewer.
- Link the console from global navigation and onboarding entry points.

## Out of Scope

- Full role-based permission system.
- Weighted voting/reputation.
- Multi-stage branch/merge orchestration equivalent to GitHub checks.

## Acceptance Criteria

1. New contributor can register from web and appear in contributor list.
2. Human can submit change requests for:
   - idea create/update,
   - question add/answer,
   - spec create/update.
3. Change request stores proposer attribution and vote attribution.
4. Human or machine reviewer can cast yes/no vote via API and web.
5. Approved request auto-applies by default and records apply result.
6. Rejected request remains rejected and is not applied.
7. `/contribute` is reachable from root navigation and onboarding.
8. Local API tests and web build pass.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - New contributor can register from web and appear in contributor list.
  - Human can submit change requests for:
  - Change request stores proposer attribution and vote attribution.
  - Human or machine reviewer can cast yes/no vote via API and web.
  - Approved request auto-applies by default and records apply result.
commands:
  - - `pytest -q tests/test_ideas.py tests/test_spec_registry_api.py tests/test_governance_api.py tests/test_inventory_api.py`
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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

See `api/tests/test_contributor_onboarding_and_governed_change_flow.py` for test cases covering this spec's requirements.


## Verification

- API tests:
  - `pytest -q tests/test_ideas.py tests/test_spec_registry_api.py tests/test_governance_api.py tests/test_inventory_api.py`
- Web:
  - `cd web && npm run build`
- Manual:
  - Open `/contribute`, register contributor, submit request, vote yes/no, verify state transitions.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
