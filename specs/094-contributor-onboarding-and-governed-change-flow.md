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

## Verification

- API tests:
  - `pytest -q tests/test_ideas.py tests/test_spec_registry_api.py tests/test_governance_api.py tests/test_inventory_api.py`
- Web:
  - `cd web && npm run build`
- Manual:
  - Open `/contribute`, register contributor, submit request, vote yes/no, verify state transitions.
