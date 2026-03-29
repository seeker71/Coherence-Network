# Spec: UX Overhaul — Tabs-First, Mobile-First, Novice and Expert Modes

**Spec ID**: `task_75d5d79d7f75bb8c`  
**Status**: Draft (product specification — implementation follows in a separate task)  
**Author**: product-manager (Coherence Network)  
**Date**: 2026-03-28  
**Priority**: High  

---

## Purpose

The web application should stop relying on long single-column scrolls for primary workflows. Users need **sectioned navigation (tabs)** so structure is visible above the fold, **mobile-first** patterns (bottom bar, swipe-friendly lists, collapsible panels), and **novice vs expert** presentation modes so newcomers see guided language while operators see IDs, JSON, and API links. Persisted **per-contributor UI preferences** (`/api/preferences/ui`) make one codebase serve both audiences. This spec is the contract for that UX overhaul; the CLI remains **tab-free** by design.

---

## Summary

| Area | Contract |
|------|-----------|
| **Idea detail** | Route: **`/ideas/[idea_id]`**. Sections as **tabs** (shadcn/ui `Tabs`): **Overview \| Specs \| Tasks \| Contributors \| Edges \| History**. Only the active panel body scrolls; the tab strip stays fixed within the page chrome. |
| **Ideas list** | Route: **`/ideas`**. View modes: **Cards \| Table \| Graph** (tabs or segmented control). Selection persisted via preferences API. |
| **Global nav** | Primary: **Ideas, Concepts, Contributors, News, Tasks** — routes **`/ideas`**, **`/concepts`**, **`/contributors`**, **`/news`**, **`/tasks`**. Secondary items (settings, docs, account) in a **dropdown**. |
| **Mobile** | Below `md`: **bottom tab bar** for primary destinations; **swipeable** card rows where feasible; **collapsible** sections inside tab panels to limit vertical noise. |
| **Novice mode** | Hide technical fields; **tooltips** for key terms; simpler vocabulary; optional “Show details” for advanced blocks. |
| **Expert mode** | Show **IDs**, **raw JSON** toggle for API-shaped payloads, **copyable API URLs** (e.g. `GET https://api.coherencycoin.com/api/ideas/{id}`). |
| **API** | **`GET` / `PUT` / `PATCH`** on **`/api/preferences/ui`** — per-authenticated contributor. |
| **Web** | **shadcn/ui** `Tabs`, `DropdownMenu`, `Tooltip`, `Sheet`, `Toggle` as needed. |
| **CLI** | No change; structured commands remain the non-tab interface. |

---

## Requirements

- [ ] **R1 — Tabs replace long scroll for core pages**: Idea detail and ideas list use explicit section or view controls; no “infinite document” as the only pattern for primary content.
- [ ] **R2 — Idea detail tab set**: Stable slugs: `overview`, `specs`, `tasks`, `contributors`, `edges`, `history` (order fixed in spec; labels may shorten in UI but map 1:1).
- [ ] **R3 — Ideas list modes**: `cards`, `table`, `graph` persisted server-side via preferences.
- [ ] **R4 — Navigation shell**: Primary five destinations visible; secondary in dropdown; responsive breakpoint switches to bottom nav on small viewports.
- [ ] **R5 — Novice mode**: `ui_mode: novice` hides IDs/JSON/API chrome from default view; tooltips on first focus/hover where specified.
- [ ] **R6 — Expert mode**: `ui_mode: expert` exposes IDs, raw JSON toggle, API link buttons.
- [ ] **R7 — Preferences API**: Authenticated `GET`/`PUT`/`PATCH` on `/api/preferences/ui`; **401** without auth; **422** on invalid enums/body.
- [ ] **R8 — Accessibility**: Keyboard operable tabs; visible focus; information not conveyed by color alone.
- [ ] **R9 — Proof surfacing**: Overview tab shows a **status strip** (lifecycle, recent activity, open blockers count) using existing APIs; History tab shows timeline events (append-only) so “is it working?” improves over time as data accrues.

---

## Open Question — Improving the Idea, Showing Whether It Works, Clearer Proof Over Time

**Question**: How do we improve this idea, show whether it is working yet, and make that proof clearer over time?

**Answer (in-spec)**:

1. **Working yet (binary + qualitative)**  
   - **Overview** tab MUST render a compact **status strip** fed from existing idea/task/runtime data (no new synthetic “score” engine in v1): e.g. phase, last heartbeat or activity timestamp, count of open tasks/blockers.  
   - If required fields are missing, show **explicit “Unknown”** states, not empty space.

2. **Proof clarity over time**  
   - **History** tab MUST list chronological events (task updates, status changes, deploy/verify events if exposed).  
   - **Future**: optional links to **commit evidence** JSON or CI artifacts — tracked as follow-up; not blocking MVP.

3. **Measuring whether the *UX spec* is working**  
   - Ship with **feature flags or analytics hooks** (optional): tab switches, mode toggles, time-on-tab — so product can validate adoption.  
   - **Verification Scenarios** below are the acceptance contract for reviewers.

---

## API Changes

### Endpoints (exact)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/preferences/ui` | Return current contributor UI preferences (defaults if none). |
| `PUT` | `/api/preferences/ui` | Full replace of mutable preference fields. |
| `PATCH` | `/api/preferences/ui` | Partial update. |

**`GET /api/preferences/ui`**

- **Auth**: Required (Bearer or session per existing API conventions).  
- **200**: Body includes at minimum: `contributor_id`, `ui_mode` (`novice` \| `expert`), `idea_detail_tab`, `ideas_list_view`, `mobile_bottom_nav`, `raw_json_expanded`, `updated_at` (ISO 8601 UTC).  
- **401**: Not authenticated.  
- **Default row**: If no row exists, return **200** with server defaults (preferred) — document in OpenAPI.

**`PUT /api/preferences/ui`**

- **Body**: Full document (see Data model).  
- **200**: Updated resource.  
- **422**: Validation failure (invalid enum, extra keys if forbidden).

**`PATCH /api/preferences/ui`**

- **Body**: Partial fields.  
- **200**: Merged full document.

---

## Data Model

```yaml
UiPreferences (API shape):
  contributor_id: string
  ui_mode: enum [novice, expert]
  idea_detail_tab: enum [overview, specs, tasks, contributors, edges, history]
  ideas_list_view: enum [cards, table, graph]
  mobile_bottom_nav: boolean
  raw_json_expanded: boolean
  updated_at: string  # ISO 8601 UTC
```

**Persistence**: Table keyed by contributor FK (e.g. `contributor_ui_preferences`), aligned with PostgreSQL in production and SQLite/dev migrations as used by the project.

---

## Web Pages (exact paths)

| Path | Behavior |
|------|----------|
| `/ideas` | List; view mode Cards \| Table \| Graph |
| `/ideas/[idea_id]` | Detail; tabs Overview \| Specs \| Tasks \| Contributors \| Edges \| History |
| `/concepts` | Primary nav |
| `/contributors` | Primary nav |
| `/news` | Primary nav |
| `/tasks` | Primary nav |

Unimplemented routes: placeholder with clear message — no silent 404 from nav.

---

## CLI

No new commands. **`cc`** and related CLIs remain **tab-free**; structured output and filters stay the expert path without this UI.

---

## Files to Create or Modify (implementation phase)

Listed for handoff; implementers MUST only touch files allowed by the implementation task card.

- `api/app/routers/preferences_ui.py`
- `api/app/models/preferences_ui.py`
- `api/app/services/preferences_ui_service.py`
- `api/app/main.py` (router registration)
- `api/tests/test_preferences_ui.py`
- `web/app/ideas/[idea_id]/page.tsx`
- `web/app/ideas/page.tsx`
- `web/components/layout/AppNav.tsx` (or equivalent)
- `web/lib/ui-preferences.ts`
- `web/components/ui/tabs.tsx` (if not present from shadcn)

---

## Acceptance Criteria

1. **Automated**: Tests cover preferences **create → read → update** (PUT/PATCH/GET) and **401** / **422**.  
2. **Build**: `npm run build` passes after web changes.  
3. **Manual / curl**: All **Verification Scenarios** pass against staging or production with real auth.

---

## Verification Scenarios

Production API base: **`https://api.coherencycoin.com`** (or `API_URL`). Web base: **`https://coherencycoin.com`** (or dev).

### Scenario 1 — Preferences full CRUD cycle (authenticated)

- **Setup**: Valid contributor token `TOKEN`; environment may have no prior preferences row.  
- **Action**:

```bash
curl -sS -w "\nHTTP:%{http_code}\n" -X GET "$API_URL/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/json"
```

- **Expected**: HTTP **200**; JSON includes `ui_mode`, `ideas_list_view`, `idea_detail_tab`, `updated_at`.  
- **Action**:

```bash
curl -sS -w "\nHTTP:%{http_code}\n" -X PUT "$API_URL/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ui_mode":"expert","idea_detail_tab":"history","ideas_list_view":"graph","mobile_bottom_nav":true,"raw_json_expanded":true}'
```

- **Expected**: HTTP **200**; stored values echoed; `updated_at` newer than first GET.  
- **Action**:

```bash
curl -sS -w "\nHTTP:%{http_code}\n" -X PATCH "$API_URL/api/preferences/ui" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ideas_list_view":"table"}'
```

- **Expected**: HTTP **200**; `ideas_list_view` is `table`; other fields unchanged.  
- **Action**: `GET` again — **Expected**: `ideas_list_view` remains `table`.  
- **Edge (bad input)**: `PUT` with `{"ui_mode":"ninja"}` → **422** with validation detail.  
- **Edge (unauthorized)**: `GET` without `Authorization` → **401**.

### Scenario 2 — Error handling: missing resource vs bad method

- **Setup**: Authenticated `TOKEN`.  
- **Action**: `GET /api/preferences/ui` — **Expected**: **200** (defaults).  
- **Edge**: `POST /api/preferences/ui` with body `{}` — **Expected**: **405** Method Not Allowed (or **404** if route not defined for POST — document actual behavior in OpenAPI; must not return **500** for unknown method).

### Scenario 3 — Idea detail tabs (browser)

- **Setup**: Idea `IDEA_ID` exists; web dev server or production.  
- **Action**: Open `/ideas/IDEA_ID`.  
- **Expected**: Visible tabs **Overview \| Specs \| Tasks \| Contributors \| Edges \| History**; switching tabs updates visible panel without full page reload; URL contains `?tab=` or `#` per implementation (documented).  
- **Edge**: Navigate to `?tab=invalid` — **Expected**: Fallback to **Overview**, no uncaught error boundary.

### Scenario 4 — Novice vs expert visibility

- **Setup**: `PATCH` `ui_mode` to `novice`.  
- **Action**: Load idea detail — **Expected**: No raw JSON toggle in default layout; IDs not emphasized.  
- **Action**: `PATCH` to `expert` — reload — **Expected**: IDs visible; JSON toggle; API copy buttons present.  
- **Edge**: Rapid mode switch — **Expected**: No duplicate POST to ideas API; preferences only.

### Scenario 5 — Ideas list view persistence

- **Setup**: Authenticated session in browser.  
- **Action**: On `/ideas`, switch **Graph → Cards → Table**; hard reload.  
- **Expected**: Last mode restored from server preferences.  
- **Edge**: Simulate API failure (offline in DevTools) — **Expected**: Graceful fallback (e.g. Cards + one warning); no infinite loading spinner.

---

## Research Inputs

- `2026-03-28` — [shadcn/ui Tabs](https://ui.shadcn.com/docs/components/tabs) — Accessible tab primitives for Next.js.  
- `2026-03-28` — Internal: `specs/TEMPLATE.md`, `specs/ux-homepage-readability.md` — UX spec precedents.  
- `2026-03-28` — Internal: `CLAUDE.md` — API path conventions, ISO dates, Pydantic responses.

---

## Task Card (implementation handoff)

```yaml
goal: Deliver tabs-first mobile-first UX with novice/expert modes and /api/preferences/ui persistence.
files_allowed:
  - api/app/routers/preferences_ui.py
  - api/app/models/preferences_ui.py
  - api/app/services/preferences_ui_service.py
  - api/app/main.py
  - api/tests/test_preferences_ui.py
  - web/app/ideas/[idea_id]/page.tsx
  - web/app/ideas/page.tsx
  - web/components/layout/AppNav.tsx
  - web/lib/ui-preferences.ts
done_when:
  - pytest api/tests/test_preferences_ui.py passes
  - cd web && npm run build succeeds
  - Verification Scenarios 1–5 executable and passing
commands:
  - cd api && pytest -q tests/test_preferences_ui.py
  - cd web && npm run build
constraints:
  - Do not modify tests to weaken assertions
  - No scope beyond files listed without spec amendment
```

---

## Risks and Assumptions

- **Risk**: Graph view bundle size hurts LCP — **Mitigation**: dynamic import + skeleton.  
- **Risk**: Last-write-wins on preferences — **Mitigation**: document; optional ETag later.  
- **Assumption**: Authenticated contributor identity exists for API sessions; otherwise preferences need a spec amendment for anonymous keys.

---

## Known Gaps and Follow-up Tasks

- Link **History** tab to commit evidence / CI artifacts when those APIs exist.  
- Product confirmation if **News** or **Concepts** paths differ from `/news`, `/concepts` in current app.  
- Optional analytics on tab usage for proof of adoption.

---

## Out of Scope

- Native mobile apps; full PWA offline mode.  
- Changing core graph or idea business rules beyond presentation + preferences storage.  
- CLI tabbed TUI.

---

## Verification (commands)

```bash
cd api && pytest -q tests/test_preferences_ui.py
cd web && npm run build
```

---

## Concurrency Behavior

- Reads: safe concurrent.  
- Writes: last-write-wins for MVP unless ETag added later.

---

## Failure / Retry Reflection

- **Failure**: 500 on first `PUT` — likely migration missing — **Next**: run DB migrations, check logs, return clear 503/503 body in API until fixed.

---

## Decision Gates

- Confirm canonical web routes for Concepts and News with product owner.  
- Security: preferences must store **UI state only** — no secrets.

---

## Related

- Complementary draft: `specs/task_2fd886e591f06caa.md` (parallel UX overhaul narrative — reconcile at implementation kickoff).
