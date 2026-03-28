# Spec: Automation Capacity — Garden Map (idea `idea-c3731991380b`)

## Goal

Replace the default “server room / debug console” feel of `/automation` with a **living ecosystem** visualization: a garden map where federation nodes appear as entities, provider health uses **gauges** instead of raw metric dumps, and recent activity reads as a **flowing stream**. First-time visitors should intuit capacity and liveness without parsing pipe-delimited or table-heavy telemetry.

## Files

| File | Action |
|------|--------|
| `web/app/automation/page.tsx` | Modify — compose garden + collapsible detail panels |
| `web/components/automation_garden/types.ts` | Add — shared serializable types for props |
| `web/components/automation_garden/automation_garden_experience.tsx` | Add — client UI (garden, gauges, stream) |
| `web/app/globals.css` | Modify — stream/keyframe helpers for motion |
| `api/tests/test_automation_garden_contract.py` | Add — API contract pytest for page data sources |

## Functional requirements

1. **Garden map (primary view)**  
   - Shows federation / network nodes as distinct “organisms” with online/degraded/offline styling.  
   - Shows each tracked provider as a row with **at least one** horizontal gauge (success or health proxy when exec stats missing).  
   - Shows ecosystem-level indicators: required readiness, validation, alert count, limit coverage when present.

2. **Provider health as gauges**  
   - Primary gauge: execution success rate when `GET /api/providers/stats` data exists; otherwise readiness/validation-derived health.  
   - Secondary gauge when possible: remaining ratio from usage metrics (first metric with `limit` + `remaining`).

3. **Activity stream**  
   - Horizontally scrolling (CSS) “river” of derived events from alerts, exec stats highlights, and node heartbeat text — not raw API dumps.

4. **Progressive disclosure**  
   - Existing tables and dense metrics remain available under a clearly labeled disclosure (e.g. “Detailed metrics & tables”) default **closed** so the default path is the garden.

5. **Proof of liveness**  
   - Visible timestamps from `generated_at` fields and a short “how to verify” line pointing at the same APIs the page uses.

## API & pages (network contract)

| Endpoint | Role |
|----------|------|
| `GET /api/automation/usage?force_refresh=true` | Provider snapshots, limit coverage |
| `GET /api/automation/usage/alerts?threshold_ratio=0.2` | Capacity alerts |
| `GET /api/automation/usage/readiness?force_refresh=true` | Readiness rows |
| `GET /api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true` | Validation rows |
| `GET /api/providers/stats` | Execution stats (optional) |
| `GET /api/federation/nodes/stats` | Network stats (optional) |
| `GET /api/federation/nodes` | Node list (optional) |
| `GET /api/federation/nodes/capabilities` | Fleet caps (optional) |

| Page | Role |
|------|------|
| `GET /automation` | Server-rendered page; garden is first paint |

## Acceptance criteria

1. Visiting `/automation` shows the garden map above the fold; detailed tables are not the primary surface (disclosure closed by default).  
2. At least one provider row shows a filled horizontal gauge when usage providers exist.  
3. When `execStats` is present, gauges reflect success rate (0–100%).  
4. Activity stream shows at least one derived line when any of alerts, exec stats, or federation nodes exist.  
5. No new API endpoints required for the feature; existing contracts unchanged.

## Verification Scenarios

### 1. Page loads and shows garden shell

- **Setup:** API reachable from web (`NEXT_PUBLIC_API_URL` or default public API).  
- **Action:** Open `https://coherencycoin.com/automation` (or local `http://localhost:3000/automation`).  
- **Expected:** Title contains “Automation”; visible region includes a section with accessible name containing “ecosystem” or “garden” (aria-labelledby); a “Detailed metrics” (or equivalent) disclosure exists and is closed by default.  
- **Edge:** If automation usage API fails, page error boundary or error — not a blank white screen without message.

### 2. Full read cycle for automation usage API

- **Setup:** None.  
- **Action:** `curl -sS "$API/api/automation/usage?force_refresh=true" | jq '.generated_at, (.providers|length)'`  
- **Expected:** HTTP 200; `generated_at` is non-empty ISO-like string; `providers` is an array (may be empty).  
- **Edge:** Invalid query `force_refresh=maybe` still returns 200 or 422 per existing API — must not 500.

### 3. Readiness + validation read

- **Setup:** Same as above.  
- **Action:**  
  `curl -sS "$API/api/automation/usage/readiness?force_refresh=true" | jq '.all_required_ready, .generated_at'`  
  `curl -sS "$API/api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true" | jq '.all_required_validated, .generated_at'`  
- **Expected:** HTTP 200; booleans and timestamps present.  
- **Edge:** Missing optional env — `blocking_issues` may be non-empty; response still 200 with structured body.

### 4. Provider stats optional path

- **Setup:** None.  
- **Action:** `curl -sS -o /dev/null -w "%{http_code}" "$API/api/providers/stats"`  
- **Expected:** HTTP 200 when service configured; garden still renders if this returns non-200 (degraded gauges).  
- **Edge:** Timeout or 503 — page should load from usage alone (other fetches optional in loader).

### 5. Error handling — bad automation alerts threshold

- **Setup:** None.  
- **Action:** `curl -sS -o /dev/null -w "%{http_code}" "$API/api/automation/usage/alerts?threshold_ratio=2"`  
- **Expected:** HTTP 422 or 400 (validation), not 500.  
- **Edge:** `threshold_ratio=-1` — same expectation.

## Risks and Assumptions

- **Assumption:** Web build allows client components importing only serializable props from server page.  
- **Risk:** Large federation lists may crowd the garden — mitigated by capping visible node orbs with overflow.

## Known Gaps and Follow-up Tasks

- Live WebSocket updates for the stream (currently SSR + optional future client refresh).  
- Automated Playwright visual regression for the garden layout.

## Open questions (from idea)

- **Improvement:** Add a persistent “freshness” score (min age across `generated_at` fields) and surface it in the proof strip.  
- **Working yet:** Expose green/amber/red on the proof strip from `all_required_ready && all_required_validated`.  
- **Clearer over time:** Store last N garden snapshots client-side (sessionStorage) to show trend arrows — follow-up.
