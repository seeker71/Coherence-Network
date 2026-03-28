# Spec: Automation Capacity — Garden Map (Living Ecosystem View)

## Purpose

The Automation Capacity page (`/automation`) exposed provider and federation data primarily as tables and dense text, which reads like a server console. Operators and new visitors need an immediate **living-ecosystem** metaphor: nodes as organisms, provider health as **gauges**, and recent signals as a **flowing stream**, while preserving access to the same underlying APIs and detailed traces for debugging.

## Goal

Replace the default “telemetry wall” experience with a **garden map** as the primary surface: visual status for providers and federation nodes, gauge-based health (not raw metric dumps), and a combined activity stream. Technical tables remain available under explicit disclosure so proof and debugging stay possible.

## Open Questions (Addressed in UI)

| Question | How we improve / show proof |
|----------|-----------------------------|
| How to improve the idea? | Add a **proof strip** (readiness + validation + alert count) with color semantics and short labels; iterate copy and layout in follow-ups. |
| Show whether it is working? | **Ecosystem pulse** score derived from `all_required_ready`, `all_required_validated`, and zero critical alerts; shown as a single headline state + gauges. |
| Clearer proof over time? | Same APIs remain; snapshot timestamps (`generated_at`) visible in the stream and proof strip; detailed tables unchanged for regression comparison. |

## Requirements

- [ ] `/automation` renders a **garden map** section before detailed sections: provider “plots”, node “organisms”, visual gauges, activity stream.
- [ ] Provider execution health uses **gauge-style** visuals (bars or arcs), not paragraph dumps, when `execStats` is present.
- [ ] Federation nodes appear as **distinct entities** with online/degraded styling (not only a text table).
- [ ] Alerts and key signals appear in a **scrollable stream** (most recent first), not only isolated list sections.
- [ ] **No API contract change** — existing endpoints listed below remain the source of truth.
- [ ] **Detailed tables** from the prior page remain reachable (e.g. collapsible “Technical soil” / detail region) for full CRUD-style inspection of the same data shapes.

## Research Inputs

- `2026-03-28` — Internal product requirement (task `task_dc8f879c202c6f7d`): UX shift from console to ecosystem metaphor.
- Existing automation API behavior — `api/app/routers/automation_usage.py` and federation routes (no change in this spec).

## Task Card

```yaml
goal: Ship garden-map primary UX on /automation with gauges, stream, and preserved technical detail.
files_allowed:
  - specs/181-automation-capacity-garden-map.md
  - web/app/automation/page.tsx
  - web/components/automation/automation_garden_map.tsx
  - api/tests/test_automation_page_garden_contract.py
done_when:
  - pytest api/tests/test_automation_page_garden_contract.py passes
  - /automation renders garden map with data-testid hooks for automation
commands:
  - cd api && .venv/bin/pytest -v api/tests/test_automation_page_garden_contract.py
  - cd api && .venv/bin/ruff check api/tests/test_automation_page_garden_contract.py
constraints:
  - Do not change automation router payloads or tests in test_automation_usage_api.py
```

## API Contract

**N/A — no new or modified endpoints.** The page continues to consume:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/automation/usage` | Provider snapshots, metrics, limits |
| GET | `/api/automation/usage/alerts` | Capacity alerts |
| GET | `/api/automation/usage/readiness` | Provider readiness rows |
| GET | `/api/automation/usage/provider-validation` | Validation contract |
| GET | `/api/providers/stats` | Execution stats per provider |
| GET | `/api/federation/nodes/stats` | Per-node provider stats |
| GET | `/api/federation/nodes` | Registered nodes |
| GET | `/api/federation/nodes/capabilities` | Fleet capabilities |

## Web Pages

| Path | Change |
|------|--------|
| `/automation` | Garden map hero + proof strip + stream; legacy detail preserved |

## Files to Create/Modify

- `specs/181-automation-capacity-garden-map.md` — this spec
- `web/components/automation/automation_garden_map.tsx` — client garden UI (gauges, stream, plots)
- `web/app/automation/page.tsx` — compose garden + existing sections
- `api/tests/test_automation_page_garden_contract.py` — API contract tests for endpoints the page relies on

## Acceptance Criteria

1. First screenful of `/automation` includes a **garden** region with provider plots and at least one **SVG or CSS gauge** per provider when stats exist.
2. **Activity stream** lists merged alerts (and optional synthetic lines from exec stats) with timestamps where available.
3. **Federation nodes** show as cards or plot cells with status color, not only pipe-like ID dumps in the hero.
4. **Technical detail**: previous table-heavy sections remain in the document (below the fold or inside disclosure).
5. Contract tests pass against the FastAPI app for the listed GET routes.

## Verification Scenarios

### Scenario 1 — Full read path for automation usage (create/read cycle for cached data)

- **Setup:** API test client with in-memory app (no auth required for public automation routes as today).
- **Action:** `GET /api/automation/usage?force_refresh=true`
- **Expected:** HTTP 200, JSON includes `generated_at`, `providers` (array), `tracked_providers` (number ≥ 0).
- **Edge:** `force_refresh=false` still returns 200 with same top-level keys (may be cached).

### Scenario 2 — Readiness + alerts error handling

- **Setup:** Same client.
- **Action:** `GET /api/automation/usage/readiness?force_refresh=true` and `GET /api/automation/usage/alerts?threshold_ratio=0.2`
- **Expected:** HTTP 200; readiness includes `providers` (array) and `all_required_ready` (bool); alerts includes `alerts` (array) and `threshold_ratio` ≈ 0.2.
- **Edge:** `threshold_ratio=2` returns **422** (validation), not 500.

### Scenario 3 — Provider validation contract

- **Action:** `GET /api/automation/usage/provider-validation?runtime_window_seconds=86400&min_execution_events=1&force_refresh=true`
- **Expected:** HTTP 200, JSON includes `providers`, `all_required_validated`, `runtime_window_seconds` == 86400.
- **Edge:** Invalid `runtime_window_seconds=0` returns **422**.

### Scenario 4 — Web page contains garden hooks (deployed / local)

- **Setup:** Build or dev server, or inspect source in repo after merge.
- **Action:** Open `/automation` (or `curl -s` HTML in CI from static export if applicable — here: **grep built source** or **Playwright not required**; manual: browser shows `data-testid="automation-garden-root"`).
- **Expected:** DOM contains `data-testid="automation-garden-root"` and `data-testid="automation-activity-stream"`.
- **Edge:** When `execStats` is null, garden still renders without throwing (shows “still germinating” style empty gauges).

### Scenario 5 — Federation optional degradation

- **Action:** `GET /api/federation/nodes` (may be empty in dev).
- **Expected:** HTTP 200, response is JSON array (possibly `[]`).
- **Edge:** Page still renders when federation fetch fails (server catches; existing pattern).

## Risks and Assumptions

- **Assumption:** Next.js client components are allowed for this route; bundle size increase is acceptable for one `"use client"` island.
- **Risk:** Large provider counts may crowd the garden — mitigated with flex-wrap and compact cards.
- **Assumption:** No new localization requirement in this iteration.

## Known Gaps and Follow-up Tasks

- Add E2E Playwright snapshot for `/automation` garden (not in this spec).
- Consider virtualizing the activity stream for very high alert volume.

## Verification (CI)

- `cd api && pytest -v api/tests/test_automation_page_garden_contract.py`
- `cd api && ruff check api/tests/test_automation_page_garden_contract.py`
