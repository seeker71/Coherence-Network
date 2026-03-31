# Spec: Automation Garden Map (Capacity Page UX)

## Purpose

Replace the “server room / debug console” feel of `/automation` with a **living ecosystem metaphor**: providers as cultivated plots, federation nodes as creatures in a meadow, capacity and execution health as **visual gauges**, and recent signals as a **flowing stream**. First-time visitors should intuit *health and motion* before reading tables. The page still consumes the same public automation APIs; this is a **presentation-layer** change with explicit proof hooks so operators can verify freshness and correctness over time.

## Open Questions (Addressed Here)

| Question | Resolution |
|----------|------------|
| How can we improve this idea? | Add a **proof strip** (last refresh timestamps, links to JSON APIs) and `data-testid` hooks for automated checks. |
| Show whether it is working yet? | Garden renders only when usage payload loads; **error boundary** is server `throw` (Next error page); gauges use 0–100% scales with labels. |
| Make proof clearer over time? | Document **Verification Scenarios** (below) that hit APIs and assert DOM markers; repeat on deploy. |

## Requirements

- **R1:** The default view of `/automation` MUST lead with a **garden map** (not raw pipe-style telemetry dumps as the primary surface).
- **R2:** Each **provider** MUST appear as a **plot** with a **horizontal health gauge** (success rate when execution stats exist; otherwise readiness/usage-based fill).
- **R3:** Each **federation node** (when present) MUST appear as a **living cell** with online/offline **status glow**, not only hostname text.
- **R4:** **Activity** MUST appear as a **vertical flowing stream** (chronological items from alerts + snapshot times + node last-seen), not a monospace log.
- **R5:** **Technical tables** (validation, readiness, usage rows) MUST remain available under a **collapsed `<details>`** section labeled for operators (defaults **closed** on first paint).
- **R6:** **Proof strip** MUST show `generated_at` from usage (and link to `/api/automation/usage` docs via existing context links pattern).

## Research Inputs (Required)

- `2026-03-28` — Internal: `web/app/automation/page.tsx` (prior layout) — informed data sources and API URLs.
- `2026-03-28` — Internal: `specs/100-automation-provider-usage-readiness-api.md` — automation usage contract.

## Task Card (Required)

```yaml
goal: Present Automation Capacity as a garden map with gauges, living nodes, and activity stream while preserving API-backed data.
files_allowed:
  - specs/181-automation-garden-map.md
  - web/app/automation/page.tsx
  - web/app/globals.css
  - web/lib/automation-page-data.ts
  - web/components/automation/automation_garden.tsx
  - web/tests/integration/automation-garden.test.tsx
  - web/tests/integration/page-data-source.test.ts
  - api/tests/test_automation_garden_page_spec.py
done_when:
  - cd api && pytest -q tests/test_automation_garden_page_spec.py passes
  - cd web && npx vitest run tests/integration/automation-garden.test.tsx passes
  - cd web && npm run build succeeds
commands:
  - cd api && pytest -q tests/test_automation_garden_page_spec.py
  - cd web && npx vitest run tests/integration/automation-garden.test.tsx
  - cd web && npm run build
constraints:
  - No new backend routes; reuse existing GET /api/automation/* and federation endpoints consumed by the page.
  - Do not modify holdout tests.
```

## API Contract

**N/A — no API contract changes in this spec.** The page continues to call:

- `GET /api/automation/usage?force_refresh=true`
- `GET /api/automation/usage/alerts?threshold_ratio=0.2`
- `GET /api/automation/usage/readiness?force_refresh=true`
- `GET /api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true`
- `GET /api/providers/stats`
- `GET /api/federation/nodes/stats`
- `GET /api/federation/nodes`
- `GET /api/federation/nodes/capabilities`

## Data Model (if applicable)

**N/A** — uses existing JSON shapes from those endpoints (see types in `web/lib/automation-page-data.ts`).

## Files to Create/Modify

- `specs/181-automation-garden-map.md` — this document
- `web/lib/automation-page-data.ts` — shared types + `loadAutomationData`
- `web/components/automation/automation_garden.tsx` — client “garden” UI
- `web/app/automation/page.tsx` — compose garden + collapsible technical sections
- `web/app/globals.css` — stream animation utility
- `web/tests/integration/automation-garden.test.tsx` — Vitest static checks
- `web/tests/integration/page-data-source.test.ts` — update automation hints
- `api/tests/test_automation_garden_page_spec.py` — pytest contract on spec + files

## Acceptance Tests

- `api/tests/test_automation_garden_page_spec.py::test_spec_181_file_exists`
- `api/tests/test_automation_garden_page_spec.py::test_spec_181_has_verification_scenarios`
- `api/tests/test_automation_garden_page_spec.py::test_automation_page_imports_garden_and_details`
- `web/tests/integration/automation-garden.test.tsx` — garden markers and stream

## Verification Scenarios

### Scenario 1 — Full read cycle: usage snapshot supports garden proof strip

- **Setup:** Public API reachable; optional auth as required by deployment.
- **Action:** `curl -sS "$API/api/automation/usage?force_refresh=true" | jq '.generated_at, .tracked_providers'`
- **Expected:** HTTP 200; `generated_at` is a non-empty ISO-8601 string; `tracked_providers` is a non-negative integer.
- **Edge:** `curl -sS -o /dev/null -w "%{http_code}" "$API/api/automation/usage"` with invalid host → connection error or non-200; page server fetch fails and Next shows error (not silent empty garden).

### Scenario 2 — Alerts feed the activity stream (create-read via snapshot)

- **Setup:** Same as scenario 1.
- **Action:** `curl -sS "$API/api/automation/usage/alerts?threshold_ratio=0.2" | jq '.alerts | length'`
- **Expected:** HTTP 200; JSON has `alerts` array (may be empty).
- **Edge:** `threshold_ratio=2` or negative — API returns **422** or documented validation error (not 500).

### Scenario 3 — Web page: garden DOM markers (browser or static build)

- **Setup:** Built web artifact from this branch.
- **Action:** Open `/automation` (or `grep -r data-testid web/components/automation` in CI).
- **Expected:** Elements with `data-testid="automation-garden"`, `"garden-canopy"`, `"garden-activity-brook"` exist in source; collapsed `<details>` wraps technical tables with `data-testid="automation-technical-soil"`.
- **Edge:** Missing federation data — meadow section shows empty-state copy, not an exception.

### Scenario 4 — Readiness + validation error handling

- **Setup:** API returns partial failures (simulated by taking down optional routes in staging only).
- **Action:** Load `/automation` when readiness returns 503 vs 200.
- **Expected:** With 200, readiness badges appear in garden canopy; with failure, page still renders from usage where possible (graceful degradation as implemented in loader).
- **Edge:** Empty `providers: []` — garden shows empty plots message, not blank screen.

### Scenario 5 — Federation nodes last-seen in stream

- **Setup:** `GET /api/federation/nodes` returns a list (may be empty).
- **Action:** `curl -sS "$API/api/federation/nodes" | jq 'length'`
- **Expected:** HTTP 200; array (possibly empty). When non-empty, garden meadow lists nodes with status indicators.
- **Edge:** Malformed JSON from proxy — page fails at fetch with controlled error, not undefined access crash.

## Verification (commands)

```bash
cd api && pytest -q tests/test_automation_garden_page_spec.py
cd web && npx vitest run tests/integration/automation-garden.test.tsx
cd web && npm run build
```

## Concurrency Behavior

- Read-only UI; safe for concurrent users.

## Out of Scope

- New WebSocket or SSE live stream endpoint.
- Changing automation usage aggregation logic on the API.

## Risks and Assumptions

- **Risk:** Large provider lists clutter the garden — mitigated by scroll and compact cards.
- **Assumption:** `generated_at` fields remain ISO strings from the API.

## Known Gaps and Follow-up Tasks

- Optional: add real-time tick via client polling (would need product decision).

## Failure/Retry Reflection

- **Failure mode:** API timeout on usage — **Blind spot:** user sees error page — **Next action:** retry navigation; check API health.
