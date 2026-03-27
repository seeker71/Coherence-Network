# Spec 156: Web audit findings — 25 pages checked, issues found and prioritized

## Purpose

Capture a complete, implementation-ready audit record for `coherencycoin.com` covering 25 pages reviewed on 2026-03-24, including verified behaviors, prioritized defects, and required remediation tasks. This spec turns raw audit observations into a deterministic execution contract so engineering can close high-impact reliability and readability issues without scope drift.

## Requirements

- [ ] Record audit scope and baseline result: 25/25 pages return HTTP 200.
- [ ] Document all six findings with explicit severity, current status, and expected post-fix behavior.
- [ ] Define implementation priorities (P0/P1/P2) and measurable acceptance criteria per priority.
- [ ] Include explicit UI behavior and API/proxy behavior expectations for affected routes.
- [ ] Include at least 3 executable verification scenarios with expected outcomes and edge/error behavior.

## Research Inputs (Required)

- `2026-03-24` - Internal visual audit notes (`web-audit-findings-2026-03-24`) - primary evidence source for page status and defect list.
- `2026-03-24` - Existing spec [155-tasks-page-fetch-error](./155-tasks-page-fetch-error.md) - confirms root cause and fixed status for the `/tasks` fetch failure.
- `2026-03-24` - Existing spec [150-homepage-readability-contrast](./150-homepage-readability-contrast.md) - baseline for homepage contrast improvements and remaining readability gap.

## Task Card (Required)

```yaml
goal: Define a prioritized implementation contract from the 2026-03-24 full-site web audit.
files_allowed:
  - specs/156-web-audit-findings-2026-03-24.md
done_when:
  - Spec includes prioritized findings with status and acceptance criteria
  - Verification section includes concrete scenarios, expected behavior, and edge/error handling
  - Spec passes scripts/validate_spec_quality.py
commands:
  - python3 scripts/validate_spec_quality.py
constraints:
  - Do not add implementation changes in this task
  - Keep scope limited to audit findings and prioritization contract
```

## Audit Scope and Findings

### Scope

- Pages checked: `25`
- HTTP status baseline: all 25 pages returned `200`
- Audit type: visual + interaction smoke pass + operational/deploy observations

### Prioritized Findings

| Priority | Finding | Status | Required Behavior |
|---|---|---|---|
| P0 | Tasks page was broken (`TypeError: Failed to fetch`) due to missing browser proxy rewrite path | Fixed | Browser-side requests from `/tasks` and other client pages use relative `/api/...` paths via Next rewrite and load data without CORS/fetch failures |
| P0 | Dev server crash on `/ideas` tied to Next.js standalone mode warning/runtime mismatch | Open | Navigating to `/ideas` in local/dev mode does not terminate the web process; page remains interactive |
| P0 | Deploy process rebuilt API only; web image could stay stale | Open | Deploy contract always rebuilds and restarts both API and web containers for production releases |
| P1 | Docker startup command references incorrect standalone server target (`server.j` typo / wrong path risk) | Open | Web Docker image starts from valid Next standalone entrypoint (`.next/standalone/server.js`) and serves pages successfully |
| P1 | Homepage readability improved, but some body text remains dim on specific screens | Partial | Body copy remains legible across common desktop/mobile displays without lowering information density |
| P2 | Nodes page and messaging form function correctly | Verified | `/nodes` route loads and messaging form submission UX remains functional with no regressions |

## API Contract (if applicable)

No backend API schema changes are required by this spec. This audit relies on existing routes and proxy behavior:

- Browser pages must fetch through the Next proxy path (`/api/:path*`) instead of hardcoding cross-origin API URLs.
- Existing API endpoints used by audited pages must continue returning non-500 responses for valid requests.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/156-web-audit-findings-2026-03-24.md` - audit findings and priority contract

## Acceptance Tests

Manual validation scenarios that prove audit findings are resolved:

- `Scenario A`: Tasks/client pages load without `Failed to fetch` when browser network uses relative `/api/...` routes.
- `Scenario B`: Local dev navigation to `/ideas` does not crash Next.js dev server process.
- `Scenario C`: Production deployment updates both API and web containers in the same release run.
- `Scenario D`: Web Docker image launches with valid standalone server file and serves HTTP 200 on `/`.
- `Scenario E`: Homepage body text meets readability expectation on desktop and mobile spot checks.

## Concurrency Behavior

- Read-only audit evidence capture is safe for concurrent review.
- Priority assignments are last-write-wins in the spec file; reviewers must resolve conflicts before merge.
- Deploy verification for API/web rebuild must be run as a single release transaction to avoid mixed-version drift.

## Verification

### Acceptance Criteria

1. A reviewer can map every listed finding to exactly one priority and status (`Fixed`, `Partial`, `Open`, or `Verified`).
2. For P0 findings, verification demonstrates either closure evidence or an executable remediation check.
3. Expected behavior is explicit for UI/runtime/deploy surfaces; no requirement is phrased as a vague aspiration.

### Test Scenarios

#### Scenario 1 - Browser proxy behavior on tasks route (P0)

- **Setup**: Web app running with configured rewrite from `/api/:path*` to API base.
- **Action**: Open `/tasks`, inspect network calls, refresh page.
- **Expected UI behavior**:
  - Page renders task data; no blocking error banner for fetch failure.
  - Browser console has no `TypeError: Failed to fetch` originating from tasks data load.
- **Expected network behavior**:
  - Requests are sent to relative `/api/agent/tasks...` from browser context.
  - Responses return `200` for healthy service (or non-200 with handled UI messaging, but no crash).
- **Edge/error handling**:
  - If API is unreachable, page shows recoverable error state and retry affordance; app shell remains responsive.

#### Scenario 2 - `/ideas` local dev stability (P0)

- **Setup**: Run web dev server in local environment.
- **Action**: Navigate directly to `/ideas`, then route between `/ideas` and at least one other page.
- **Expected behavior**:
  - Dev server process remains alive.
  - Route renders without fatal standalone-mode startup/runtime exception.
- **Edge/error handling**:
  - If warning appears, it must remain non-fatal and not terminate the process.
  - Repeated navigations should not accumulate errors that result in crash.

#### Scenario 3 - Deploy contract includes web rebuild (P0)

- **Setup**: Execute production release flow.
- **Action**: Run deploy sequence that rebuilds images and restarts services.
- **Expected behavior**:
  - Both API and web services are rebuilt and restarted in same deploy window.
  - Release output/logs show web build step executed, not skipped.
- **Edge/error handling**:
  - If API rebuild succeeds but web rebuild fails, deployment is marked failed and requires rerun after remediation (no partial success claim).

#### Scenario 4 - Docker standalone server entrypoint correctness (P1)

- **Setup**: Build web container from current Dockerfile.
- **Action**: Start container and request `/`.
- **Expected behavior**:
  - Container starts successfully using `.next/standalone/server.js`.
  - Root page returns HTTP `200`.
- **Edge/error handling**:
  - Missing/incorrect file path should produce explicit startup failure rather than silent loop.

#### Scenario 5 - Homepage readability regression check (P1)

- **Setup**: Open homepage on at least one desktop and one mobile viewport.
- **Action**: Review hero/body copy, cards, and secondary text in default theme.
- **Expected UI behavior**:
  - Primary informational text is readable without zoom or highlight workaround.
  - No section appears visually "washed out" to the point of lost meaning.
- **Edge/error handling**:
  - If display-specific dimness persists, capture viewport/device context and keep finding in `Partial` state for follow-up.

## Out of Scope

- Implementing code fixes directly (tracked as follow-on implementation tasks).
- Redesigning information architecture or adding new pages.
- Changing API response schema for unrelated routes.

## Risks and Assumptions

- Assumes audit observations reflect current production behavior at capture time; drift may occur after subsequent deploys.
- Risk: visual readability judgments can vary by display profile; mitigation is cross-device spot checks with explicit pass/fail notes.
- Risk: deploy process updates may be applied inconsistently across environments; mitigation is mandatory dual rebuild verification in release checklist.
- Assumes `/nodes` messaging path remains stable while P0/P1 fixes are shipped.

## Known Gaps and Follow-up Tasks

- Create implementation task for `/ideas` dev crash root-cause fix and regression test coverage.
- Create implementation task to enforce deploy contract requiring both web and API rebuilds per release.
- Create implementation task to validate/fix web Docker standalone entrypoint and startup health check.
- Create implementation task to complete homepage body text readability normalization across screen types.
- Add periodic web audit automation (route status + screenshot diff) to reduce manual-only regression detection.

## Failure/Retry Reflection

- Failure mode: manual audit catches issues but no enforceable gate exists; issue can regress silently.
- Blind spot: route-level HTTP 200 checks alone do not prove runtime stability/readability.
- Next action: convert P0/P1 scenarios into CI-friendly smoke checks after implementation tasks land.

## Decision Gates (if any)

- None required to approve this spec.
- Engineering lead sign-off required before closing P0 findings as resolved.
