# Spec 141: Community Project Funder Match Showcase Page

## Purpose

The current funder-ready data exists at `GET /api/ideas/showcase`, but there is no first-class public page that presents this information in a clear, action-oriented format for potential funders. This spec adds a public `/showcase` route in the web app that translates idea showcase records into concise funding narratives with a clear ask, budget context, proof of traction, and a call-to-action so external supporters can quickly understand where funding produces measurable value.

## Requirements

- [ ] **R1: Public showcase route** - Add a public `GET /showcase` web page that renders without authentication and is linked from existing primary navigation surfaces.
- [ ] **R2: Data source contract** - The page must load showcase entries from `GET /api/ideas/showcase` via existing web API client patterns and gracefully handle empty/error/loading states.
- [ ] **R3: Funder-ready presentation** - Each rendered card must display, at minimum: title, clear ask, budget block (`estimated`, `spent`, `remaining`), early proof, and current status.
- [ ] **R4: Actionability** - Each card must include a visible call-to-action that directs funders to engage (for MVP: a contact/contribution action target that can be implemented with existing public routes).
- [ ] **R5: Ordering and readability** - Showcase cards must preserve API ordering (already ranked by realized value) and present currency figures in consistent CC-aligned formatting.

## Research Inputs (Required)

- `2026-03-21` - [Coherence Network spec template](https://github.com/seeker71/Coherence-Network/blob/main/specs/TEMPLATE.md) - defines required spec sections and quality gate expectations.
- `2026-03-21` - [Ideas router showcase endpoint](https://github.com/seeker71/Coherence-Network/blob/main/api/app/routers/ideas.py) - confirms `GET /api/ideas/showcase` exists and is public-facing.
- `2026-03-21` - [Idea showcase response models](https://github.com/seeker71/Coherence-Network/blob/main/api/app/models/idea.py) - defines exact response fields for ask, budget, proof, and status rendering.
- `2026-03-21` - [Showcase service shaping logic](https://github.com/seeker71/Coherence-Network/blob/main/api/app/services/idea_service.py) - confirms ranking behavior and semantic meaning of `clear_ask`, budget fields, and proof text.

## Task Card (Required)

```yaml
goal: Add a public web showcase page that renders funder-ready cards from GET /api/ideas/showcase.
files_allowed:
  - specs/141-community-project-funder-match-showcase-page.md
  - web/app/showcase/page.tsx
  - web/lib/api.ts
  - web/app/page.tsx
done_when:
  - /showcase renders list items from GET /api/ideas/showcase with ask, budget, proof, status, and CTA.
  - Empty/error/loading states are visible and non-blocking for users.
  - Spec quality validation passes for this spec file.
commands:
  - cd web && npm run build
  - python3 scripts/validate_spec_quality.py --file specs/141-community-project-funder-match-showcase-page.md
constraints:
  - Do not modify API showcase contract in this task.
  - Keep changes scoped to listed files only.
  - Preserve existing API ordering from /api/ideas/showcase.
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/141-community-project-funder-match-showcase-page.md` - spec definition and implementation contract.
- `web/app/showcase/page.tsx` - new public showcase page UI and rendering flow.
- `web/lib/api.ts` - API client helper wiring for `/api/ideas/showcase` (if missing).
- `web/app/page.tsx` - optional navigation/link update so `/showcase` is discoverable.

## Acceptance Tests

- Manual validation: open `/showcase` and verify each card includes title, clear ask, budget, early proof, current status, and CTA.
- Manual validation: simulate empty showcase response and verify a user-friendly no-opportunity message is shown.
- Manual validation: simulate API failure and verify page displays a recoverable error state (no crash, no blank page).
- `web` build check: `cd web && npm run build`.

## Concurrency Behavior

- **Read operations**: Page performs read-only fetch from `GET /api/ideas/showcase`; no write-path locking requirements.
- **Write operations**: N/A in this spec.
- **Recommendation**: Client should tolerate concurrent background data changes by rendering the latest returned snapshot without local mutation assumptions.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/141-community-project-funder-match-showcase-page.md
cd web && npm run build
```

Manual verification steps:
- Start API and web locally, then visit `/showcase`.
- Confirm card order matches API response order from `/api/ideas/showcase`.
- Confirm CTA is visible on each card and routes users to a public engagement path.

## Out of Scope

- Backend changes to `GET /api/ideas/showcase`.
- Payment rails, wallet integrations, or on-page transaction execution.
- Personalized funder dashboards or authenticated donor flows.
- Advanced analytics (conversion tracking, attribution funnels) for showcase CTA clicks.

## Risks and Assumptions

- **Risk**: CTA destination may be ambiguous if public contribution/contact routes are inconsistent. **Mitigation**: choose an existing stable public route and document it in implementation PR notes.
- **Risk**: Showcase fields may be technically correct but too dense for external funders. **Mitigation**: keep copy concise and use a predictable card layout with explicit labels.
- **Assumption**: `GET /api/ideas/showcase` remains available and returns `IdeaShowcaseResponse` fields (`clear_ask`, `budget`, `early_proof`, `current_status`) without contract drift.

## Known Gaps and Follow-up Tasks

- Follow-up task: add automated web UI test coverage for `/showcase` rendering and fallback states.
- Follow-up task: define canonical CTA destination policy for funder engagement across all public pages.
- Follow-up task: evaluate adding a dedicated `showcase_detail` route for deeper proof artifacts.

## Failure/Retry Reflection

- Failure mode: API fetch fails and users see no opportunities.
- Blind spot: assuming network/API reliability and not budgeting for resilient fallback UX.
- Next action: provide clear retry affordance and preserve explanatory error copy on the page.

## Decision Gates (if any)

- Confirm final CTA destination (`/contributors`, `/contributions`, or alternate public route) before implementation starts.
